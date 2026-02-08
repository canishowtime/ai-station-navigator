#!/usr/bin/env python3
"""
skill_install_workflow.py - Skill Installation Workflow
--------------------------------------------------------
LangGraph 工作流：串联 clone_manager + security_scanner + skill_manager

流程:
1. clone_repo_node - 克隆 GitHub 仓库并提取技能
2. security_scan_node - 批量安全扫描
3. check_threat_level - 判断威胁级别
4. llm_analysis_review_node - LLM 二次分析 (可中断)
5. install_skills_node - 安装技能

特性:
- 状态持久化 (SQLite)
- 中断恢复 (interrupt)
- 误报处理 (LLM 分析)
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated, Dict, List, Literal, Optional, TypedDict
from urllib.parse import urlparse

# 添加项目根目录到 sys.path
# 从 bin/skill_install_workflow.py → 项目根目录
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))  # 添加 bin 目录以导入 security_scanner

# 添加 lib 目录到 sys.path（绿色包依赖）
LIB_DIR = PROJECT_ROOT / "lib"
if LIB_DIR.exists():
    sys.path.insert(0, str(LIB_DIR))

# LangGraph imports
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph, END
from typing_extensions import operator


# =============================================================================
# State Definition
# =============================================================================

class InstallWorkflowState(TypedDict):
    """技能安装工作流状态"""
    # 输入参数
    github_url: str                      # GitHub 仓库 URL
    skill_name: Optional[str]            # 可选：子技能名
    force_install: bool                  # 是否强制覆盖

    # 中间状态
    cloned_repo_path: Optional[str]      # 克隆的仓库路径
    extracted_skills: List[str]          # 提取的技能目录列表
    scan_results: Dict[str, Dict]        # 扫描结果 {skill_name: result}
    threatened_skills: List[Dict]        # 威胁技能列表

    # LLM 分析
    llm_analysis_pending: bool           # 是否需要 LLM 二次分析
    llm_analysis_result: Optional[str]   # LLM 分析结果 (JSON 字符串)
    rule_decisions: Dict[str, str]       # 规则引擎决策 {skill_name: "keep"/"uninstall"}
    analysis_prompt: Optional[str]       # 分析提示词（供 Kernel 使用）
    pending_skills: List[str]            # 待 LLM 审核的技能名称列表
    prompt_file: Optional[str]           # 分析提示词文件路径

    # 输出结果
    installed_skills: List[str]          # 成功安装的技能
    failed_skills: List[str]             # 失败的技能
    skipped_skills: List[str]            # 跳过的技能

    # 日志
    logs: Annotated[List[str], operator.add]


# =============================================================================
# Utility Functions
# =============================================================================

def extract_skill_name_from_url(url: str) -> Optional[str]:
    """从 GitHub URL 提取最后的子技能名

    Examples:
        https://github.com/user/repo/tree/main/skills/anndata → anndata
        https://github.com/user/repo → None
    """
    try:
        parsed = urlparse(url)
        path_parts = parsed.path.strip('/').split('/')

        # 查找 /tree/ 分隔符
        if 'tree' in path_parts:
            tree_idx = path_parts.index('tree')
            # 提取 tree 之后的最后一段作为技能名
            if len(path_parts) > tree_idx + 2:
                return path_parts[-1]
    except Exception:
        pass

    return None


def run_subprocess(cmd: List[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    """运行子进程命令"""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=cwd
    )


def parse_skill_paths(output: str) -> List[str]:
    """从 clone_manager 输出解析技能路径"""
    paths = []
    for line in output.split('\n'):
        line = line.strip()
        if line.startswith('- ') and len(line) > 2:
            path = line[2:].strip()
            if Path(path).exists():
                paths.append(path)
    return paths


def extract_github_info(github_url: str) -> tuple[Optional[str], Optional[str]]:
    """从 GitHub URL 提取 author 和 repo

    支持格式:
    - https://github.com/author/repo
    - https://github.com/author/repo/tree/branch/subpath
    - author/repo (简写格式)

    Returns:
        (author, repo)
    """
    import re
    if "github.com" in github_url:
        # 解析 URL，提取路径部分
        parsed = urlparse(github_url)
        path_parts = parsed.path.strip('/').split('/')
        if len(path_parts) >= 2:
            author = path_parts[0]
            repo = path_parts[1]
            return author, repo
    elif '/' in github_url:
        parts = github_url.strip().split('/')
        if len(parts) >= 2:
            author = parts[0]
            repo = parts[1]
            return author, repo
    return None, None


# =============================================================================
# Node Implementations
# =============================================================================

def clone_repo_node(state: InstallWorkflowState) -> Dict:
    """
    克隆 GitHub 仓库并提取技能目录

    调用: python bin/clone_manager.py clone <url> [--skill <name>]

    自动从 URL 子路径提取技能名:
    - https://github.com/user/repo/tree/main/skills/anndata → --skill anndata
    """
    url = state["github_url"]
    skill_name = state.get("skill_name")

    # 自动从 URL 提取技能名（如果未显式指定）
    if not skill_name:
        extracted_name = extract_skill_name_from_url(url)
        if extracted_name:
            skill_name = extracted_name

    force = state.get("force_install", False)

    cmd = [sys.executable, str(SCRIPT_DIR / "clone_manager.py"), "clone", url]
    if skill_name:
        cmd.extend(["--skill", skill_name])
    if force:
        cmd.append("--force")

    result = run_subprocess(cmd, cwd=PROJECT_ROOT)

    logs = []
    if result.returncode != 0:
        error_msg = result.stderr or result.stdout
        logs.append(f"[ERROR] 克隆失败: {error_msg}")
        return {"logs": logs}

    # 解析输出获取技能目录
    skill_dirs = parse_skill_paths(result.stdout)

    if not skill_dirs:
        logs.append("[WARN] 未检测到技能目录")
        logs.append(f"[DEBUG] 输出: {result.stdout}")
    else:
        logs.append(f"[OK] 克隆成功，发现 {len(skill_dirs)} 个技能")

    return {
        "cloned_repo_path": url,
        "extracted_skills": skill_dirs,
        "logs": logs
    }


def security_scan_node(state: InstallWorkflowState) -> Dict:
    """
    批量安全扫描所有技能（并发模式）

    调用: batch_scan() - 4 线程并发，批次处理
    """
    from security_scanner import batch_scan

    skill_dirs = state["extracted_skills"]
    scan_results = {}
    threatened_skills = []

    logs = [f"[INFO] 开始并发扫描 {len(skill_dirs)} 个技能..."]

    # 转换为 Path 对象
    skill_paths = [Path(p) for p in skill_dirs]

    # 调用并发扫描（4 线程，批次处理）
    batch_results = batch_scan(skill_paths)

    # 处理结果
    for skill_name, scan_data in batch_results.items():
        scan_results[skill_name] = scan_data

        severity = scan_data.get("severity", "UNKNOWN")
        if severity not in ["SAFE", "LOW"]:
            # 查找原始路径
            original_path = next((p for p in skill_dirs if Path(p).name == skill_name), None)
            if not original_path:
                original_path = str(skill_paths[0].parent / skill_name)
            threatened_skills.append({
                "name": skill_name,
                "path": original_path,
                "scan_result": scan_data
            })
            logs.append(f"[!] {skill_name}: {severity} ({scan_data.get('findings_count', 0)} 威胁)")
        else:
            logs.append(f"[OK] {skill_name}: {severity}")

    threatened_count = len(threatened_skills)
    logs.append(f"[SUMMARY] 扫描完成: {threatened_count} 个威胁技能")

    return {
        "scan_results": scan_results,
        "threatened_skills": threatened_skills,
        "logs": logs
    }


def parse_scan_output(output: str, skill_name: str) -> Dict:
    """解析 security_scanner 输出为结构化数据"""
    lines = output.split('\n')

    result = {
        "name": skill_name,
        "status": "unknown",
        "severity": "UNKNOWN",
        "findings_count": 0,
        "threats": []
    }

    # 尝试提取 JSON 数据（scanner 输出可能包含 JSON）
    json_data = None
    for line in lines:
        if line.strip().startswith('{'):
            try:
                json_data = json.loads(line.strip())
                break
            except json.JSONDecodeError:
                pass

    if json_data:
        # 从 JSON 中提取完整信息
        result["status"] = json_data.get("status", "unknown")
        result["severity"] = json_data.get("severity", "UNKNOWN")
        result["findings_count"] = json_data.get("findings_count", 0)
        result["threats"] = json_data.get("threats", [])
    else:
        # 降级为文本解析
        for line in lines:
            if "状态:" in line:
                result["status"] = line.split("状态:")[1].strip()
            elif "严重级别:" in line:
                result["severity"] = line.split("严重级别:")[1].strip()
            elif "发现威胁:" in line:
                try:
                    result["findings_count"] = int(line.split("发现威胁:")[1].strip())
                except ValueError:
                    pass

    return result


def extract_code_snippet(file_path: str, line_number: int, context_lines: int = 2) -> str:
    """
    提取指定代码行的上下文片段

    Args:
        file_path: 文件路径
        line_number: 问题代码行号（1-based）
        context_lines: 上下文行数（默认前后各2行）

    Returns:
        代码片段字符串，失败时返回错误信息
    """
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        # 转换为 0-based 索引
        start = max(0, line_number - context_lines - 1)
        end = min(len(lines), line_number + context_lines)

        snippet_lines = []
        for i in range(start, end):
            line_num = i + 1  # 1-based 行号
            marker = ">>> " if line_num == line_number else "    "
            snippet_lines.append(f"{marker}{line_num:4d} | {lines[i].rstrip()}")

        return "\n".join(snippet_lines)

    except Exception as e:
        return f"[无法读取文件: {file_path}:{line_number} - {e}]"


def llm_analysis_review_node(state: InstallWorkflowState) -> Dict:
    """
    LLM 二次分析节点（纯 LLM 分析模式）

    流程：
    1. 所有威胁技能直接进入 LLM 分析（不使用规则引擎初筛）
    2. 构建 analysis_prompt
    3. 返回 pending_llm_analysis 状态，交由 Kernel 处理

    注：规则引擎已注释，如需启用请取消注释下方代码
    """
    threatened = state["threatened_skills"]

    if not threatened:
        return {"llm_analysis_pending": False, "logs": ["[INFO] 无需 LLM 分析"]}

    logs = [f"[INFO] 启动 LLM 分析 {len(threatened)} 个威胁技能..."]

    # ============================================================================
    # 【已注释】规则引擎初筛
    # 如需启用规则引擎，取消下方注释并注释掉"纯 LLM 分析模式"部分
    # ============================================================================

    # decisions = {}
    # pending_llm = []  # 需要LLM审核的技能
    #
    # THREAT_PATTERNS = {
    #     "confirmed": [
    #         (r"requests\.post\([^)]*user[_-]input", "用户输入直接用于网络请求"),
    #         (r"urllib\.request\.urlopen\([^)]*user", "用户输入直接用于URL请求"),
    #         (r"subprocess\.call\([^)]*user", "用户输入直接用于命令执行"),
    #         (r"os\.system\([^)]*user", "用户输入直接用于系统命令"),
    #         (r"eval\([^)]*user[_-]input", "用户输入直接用于eval"),
    #         (r"pathlib\.Path\([\"']home/[\"']\)\.rglob", "扫描用户主目录"),
    #         (r"shutil\.copy2\([^)]*\.ssh/", "复制SSH密钥"),
    #         (r"open\([^)]*\.env", "读取环境变量文件"),
    #         (r"while\s+True:.*requests\.post", "无限循环网络请求（后门）"),
    #         (r"cryptonight|monero|bitcoin.*mining", "加密货币挖矿"),
    #         (r"socket\.create_server\([\"']0\.0\.0\.0", "监听所有端口（后门）"),
    #         (r"base64\.b64decode\([^)]+exec\(", "Base64解码后执行代码"),
    #         (r"compile\([^)]+eval\(", "动态编译执行代码"),
    #     ],
    #     "false_positive": [
    #         (r"test_|_test\.py", "测试文件"),
    #         (r"example|demo|sample", "示例代码"),
    #         (r"README|CONTRIBUTING|LICENSE", "文档文件"),
    #         (r"__init__\.py", "包初始化文件"),
    #         (r"skill\.md", "技能描述文件"),
    #         (r"pytest|unittest|assert", "测试框架"),
    #         (r"logging\.|print\(", "日志输出"),
    #         (r"dataclass|@dataclass", "数据类定义"),
    #         (r"typing\.|List\|Dict", "类型注解"),
    #         (r"argparse|click|typer", "命令行参数解析"),
    #         (r"pathlib\.Path\([^)]*\)\.exists\(\)", "文件存在性检查"),
    #         (r"pathlib\.Path\([^)]*\)\.read_text\(\)", "读取自身文件"),
    #         (r"State\[|TypedDict", "状态类型定义"),
    #         (r"langgraph|LangGraph", "工作流框架"),
    #         (r"def\s+.*_node\(", "工作流节点函数"),
    #         (r"workflow|graph\.add_edge", "工作流构建"),
    #     ]
    # }
    #
    # import re
    #
    # for threat in threatened:
    #     skill_name = threat["name"]
    #     skill_path = Path(threat["path"])
    #     severity = threat["scan_result"].get("severity", "UNKNOWN")
    #
    #     logs.append(f"[RULES] {skill_name} ({severity})")
    #
    #     # 读取代码
    #     all_code = []
    #     file_count = 0
    #     for file_path in skill_path.rglob("*"):
    #         if file_path.is_file() and file_path.suffix in [".py", ".js", ".ts", ".md"]:
    #             try:
    #                 content = file_path.read_text(encoding="utf-8", errors="ignore")
    #                 all_code.append(f"// {file_path.name}\n{content}")
    #                 file_count += 1
    #             except Exception:
    #                 pass
    #
    #     combined_code = "\n".join(all_code)
    #
    #     # 规则匹配
    #     confirmed_count = 0
    #     false_positive_count = 0
    #
    #     for pattern, _ in THREAT_PATTERNS["confirmed"]:
    #         if re.search(pattern, combined_code, re.IGNORECASE):
    #             confirmed_count += 1
    #
    #     for pattern, _ in THREAT_PATTERNS["false_positive"]:
    #         if re.search(pattern, skill_name, re.IGNORECASE) or \
    #            re.search(pattern, combined_code, re.IGNORECASE):
    #             false_positive_count += 1
    #
    #     # 决策逻辑
    #     if confirmed_count >= 2:
    #         # 高置信度威胁
    #         decisions[skill_name] = "uninstall"
    #         logs.append(f"  -> CONFIRMED THREAT ({confirmed_count} 个威胁模式)")
    #     elif false_positive_count >= 3:
    #         # 高置信度安全
    #         decisions[skill_name] = "keep"
    #         logs.append(f"  -> CONFIRMED SAFE ({false_positive_count} 个误报特征)")
    #     else:
    #         # 低置信度，需要 LLM 审核
    #         pending_llm.append({
    #             "name": skill_name,
    #             "path": str(skill_path),
    #             "severity": severity,
    #             "code_preview": combined_code[:3000] if combined_code else "",
    #             "confirmed_count": confirmed_count,
    #             "false_positive_count": false_positive_count
    #         })
    #         logs.append(f"  -> PENDING LLM REVIEW")
    #
    # # ============================================================================
    # # 阶段2：判断是否需要 LLM 审核
    # # ============================================================================
    #
    # if not pending_llm:
    #     logs.append(f"[SUMMARY] 规则引擎完成，无需 LLM 审核")
    #     return {
    #         "llm_analysis_result": json.dumps(decisions, ensure_ascii=False),
    #         "llm_analysis_pending": False,
    #         "logs": logs
    #     }
    #
    # # 有需要 LLM 审核的技能
    # logs.append(f"[INFO] {len(pending_llm)} 个技能需 LLM 审核")

    # ============================================================================
    # 纯 LLM 分析模式：所有威胁技能直接进入 LLM 审核
    # ============================================================================

    decisions = {}
    pending_llm = []  # 需要LLM审核的技能

    for threat in threatened:
        skill_name = threat["name"]
        skill_path = Path(threat["path"])
        severity = threat["scan_result"].get("severity", "UNKNOWN")
        threats_data = threat["scan_result"].get("threats", [])

        logs.append(f"[LLM_ONLY] {skill_name} ({severity})")

        # 从扫描结果中提取代码片段（用 snippet 搜索上下文）
        code_snippets = []
        for t in threats_data:
            snippet = t.get("snippet")  # YARA 匹配的关键词
            rule_id = t.get("rule_id")
            title = t.get("title", "")
            file_path = t.get("file")

            if snippet and file_path:
                # 用 snippet 作为关键词在文件中搜索，提取上下文
                abs_file_path = Path(file_path)
                if not abs_file_path.is_absolute():
                    abs_file_path = skill_path / file_path

                # 提取关键词用于搜索（取 snippet 的前50字符作为搜索词）
                keyword = snippet[:50].strip()

                # 在文件中搜索关键词并提取上下文
                try:
                    with open(abs_file_path, encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()

                    # 搜索包含关键词的行
                    matched_line = -1
                    for i, line in enumerate(lines):
                        if keyword.lower() in line.lower():
                            matched_line = i
                            break

                    if matched_line >= 0:
                        # 提取上下文（前后各2行）
                        start = max(0, matched_line - 2)
                        end = min(len(lines), matched_line + 3)

                        context_lines = []
                        for i in range(start, end):
                            line_num = i + 1
                            marker = ">>> " if i == matched_line else "    "
                            context_lines.append(f"{marker}{line_num:4d} | {lines[i].rstrip()}")

                        code = "\n".join(context_lines)
                    else:
                        code = f"[未找到关键词: {keyword[:30]}...]"

                except Exception as e:
                    code = f"[读取失败: {e}]"

                code_snippets.append({
                    "rule": rule_id,
                    "title": title,
                    "file": file_path,
                    "line": matched_line + 1 if matched_line >= 0 else 0,
                    "code": code
                })

        # 直接加入 LLM 审核列表（无规则过滤）
        pending_llm.append({
            "name": skill_name,
            "path": str(skill_path),
            "severity": severity,
            "code_snippets": code_snippets,
            "threats_count": len(code_snippets),
            "confirmed_count": 0,  # 无规则引擎，设为 0
            "false_positive_count": 0  # 无规则引擎，设为 0
        })
        logs.append(f"  -> PENDING LLM REVIEW ({len(code_snippets)} 个代码片段)")

    # 有需要 LLM 审核的技能
    logs.append(f"[INFO] {len(pending_llm)} 个技能需 LLM 审核（纯 LLM 模式）")

    # 构建 interrupt instruction（参考模板：包含完整上下文）
    instruction_parts = [
        "=" * 60,
        "【LLM 二次分析任务】",
        "=" * 60,
        f"\n任务：分析以下 {len(pending_llm)} 个威胁技能，判断是否为误报",
        f"\n判断标准：",
        "  - 误报特征（允许安装）：工作流设计、开发工具、质量控制、测试代码、正常代码结构",
        "  - 确认威胁（应卸载）：eval/exec 拼接用户输入、shell 命令注入、敏感数据窃取、后门、挖矿",
        "\n待分析技能：",
    ]

    for i, skill in enumerate(pending_llm, 1):
        instruction_parts.extend([
            f"\n{i}. {skill['name']}",
            f"   严重级别: {skill['severity']}",
            f"   路径: {skill['path']}",
        ])

        # 添加具体代码片段
        if skill["code_snippets"]:
            instruction_parts.append(f"   威胁代码片段 ({skill['threats_count']} 个):")
            for j, snippet in enumerate(skill["code_snippets"][:5], 1):  # 最多显示 5 个片段
                instruction_parts.extend([
                    f"     [{j}] {Path(snippet['file']).name}:{snippet['line']}",
                    f"         规则: {snippet['rule']} | {snippet['title']}",
                    f"         ```",
                    snippet['code'],
                    f"         ```",
                ])

            if skill['threats_count'] > 5:
                instruction_parts.append(f"     ... 还有 {skill['threats_count'] - 5} 个片段")
        else:
            instruction_parts.append(f"   无具体代码片段（仅元数据）")

    instruction_parts.extend([
        "\n" + "=" * 60,
        "ACTION REQUIRED:",
        "输出格式（JSON）：",
        '{"skill-name-1": "keep", "skill-name-2": "uninstall", ...}',
        "\n恢复方法:",
        f"  python bin/skill_install_workflow.py {state.get('github_url', '')} --result='{{\"skill\": \"keep\"}}'",
        "=" * 60,
    ])

    analysis_prompt = "\n".join(instruction_parts)

    # 保存 analysis_prompt 到文件（供 Kernel 读取）
    prompt_file = PROJECT_ROOT / "mybox" / "temp" / "llm_analysis_prompt.txt"
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(analysis_prompt, encoding="utf-8")

    logs.append(f"[INFO] 分析提示词已保存: {prompt_file}")

    # ============================================================================
    # 使用 LangGraph interrupt() 暂停工作流
    # ============================================================================

    try:
        from langgraph.types import interrupt

        # 暂停工作流，等待 LLM 分析结果
        # 恢复时，LLM 决策将通过 Command(resume=...) 传入
        llm_decision = interrupt(analysis_prompt)

        # 恢复后执行：解析 LLM 决策
        if llm_decision and str(llm_decision).strip():
            try:
                if isinstance(llm_decision, str):
                    decisions.update(json.loads(llm_decision))
                else:
                    decisions.update(llm_decision)
                logs.append(f"[INFO] LLM 决策已接收: {decisions}")
            except json.JSONDecodeError as e:
                logs.append(f"[ERROR] LLM 决策解析失败: {e}")
                # 降级为保守策略
                for skill in pending_llm:
                    decisions[skill["name"]] = "keep"
                logs.append(f"[WARN] 降级为保守策略：全部 keep")
        else:
            # 无决策，保守策略：全部 keep
            for skill in pending_llm:
                decisions[skill["name"]] = "keep"
            logs.append(f"[WARN] 无 LLM 决策，采用保守策略：全部 keep")

        return {
            "llm_analysis_result": json.dumps(decisions, ensure_ascii=False),
            "llm_analysis_pending": False,
            "rule_decisions": decisions,
            "logs": logs
        }

    except ImportError:
        # interrupt 不可用，降级为手动模式
        logs.append(f"[ERROR] interrupt() 不可用，请安装 langgraph")
        logs.append(f"[INFO] 分析提示词: {prompt_file}")

        # 保存手动恢复请求
        manual_request = {
            "url": state.get("github_url", ""),
            "pending_skills": [s["name"] for s in pending_llm],
            "prompt_file": str(prompt_file),
            "resume_command": f"python bin/skill_install_workflow.py {state.get('github_url', '')} --result='{{\"skill-name\": \"keep\", ...}}'"
        }

        request_file = PROJECT_ROOT / "mybox" / "temp" / "manual_resume_request.json"
        request_file.write_text(json.dumps(manual_request, ensure_ascii=False, indent=2), encoding="utf-8")

        print("\n" + "=" * 60)
        print("[INTERRUPT NOT AVAILABLE]")
        print("=" * 60)
        print(analysis_prompt)
        print(f"\n恢复命令已保存: {request_file}")
        print("=" * 60)

        # 退出（需要手动恢复）
        import sys
        sys.exit(0)


def install_skills_node(state: InstallWorkflowState) -> Dict:
    """
    安装技能节点

    调用: python bin/skill_manager.py install <skill_path>
    """
    skill_dirs = state["extracted_skills"]
    scan_results = state["scan_results"]
    llm_analysis = state.get("llm_analysis_result")
    rule_decisions = state.get("rule_decisions", {})
    force = state.get("force_install", False)

    # 合并规则决策和 LLM 决策
    uninstall_skills = set()

    # 1. 处理规则引擎的决策（高置信度）
    for skill_name, decision in rule_decisions.items():
        if decision == "uninstall":
            uninstall_skills.add(skill_name)

    # 2. 处理 LLM 分析结果（低置信度技能的二次审核）
    if llm_analysis:
        try:
            decisions = json.loads(llm_analysis)
            for skill_name, decision in decisions.items():
                if decision == "uninstall":
                    uninstall_skills.add(skill_name)
        except json.JSONDecodeError:
            pass

    installed = []
    failed = []
    skipped = list(uninstall_skills)

    logs = [f"[INFO] 开始安装 {len(skill_dirs)} 个技能..."]
    logs.append(f"[INFO] 规则决策: {len(rule_decisions)} 个, LLM决策: {len(json.loads(llm_analysis) if llm_analysis else {})} 个")

    # 从 GitHub URL 提取 author 和 repo（用于构建技能名称）
    github_author, github_repo = extract_github_info(state.get("github_url", ""))

    for skill_path in skill_dirs:
        skill_name = Path(skill_path).name

        # 跳过判定为威胁的技能（规则或 LLM）
        if skill_name in uninstall_skills:
            source = "规则引擎" if skill_name in rule_decisions else "LLM分析"
            logs.append(f"[SKIP] {skill_name}: {source}判定为威胁，已跳过")
            continue

        cmd = [sys.executable, str(SCRIPT_DIR / "skill_manager.py"), "install", skill_path]
        if force:
            cmd.append("--force")
        if github_author:
            cmd.extend(["--author", github_author])
        if github_repo:
            cmd.extend(["--repo", github_repo])

        result = run_subprocess(cmd, cwd=PROJECT_ROOT)

        if result.returncode == 0:
            installed.append(skill_name)
            logs.append(f"[OK] {skill_name}: 安装成功")
        else:
            failed.append(skill_name)
            error_msg = result.stderr or result.stdout
            logs.append(f"[FAIL] {skill_name}: {error_msg[:100]}")

    logs.append(f"[SUMMARY] 安装完成: {len(installed)} 成功, {len(failed)} 失败, {len(skipped)} 跳过")

    return {
        "installed_skills": installed,
        "failed_skills": failed,
        "skipped_skills": skipped,
        "logs": logs
    }


# =============================================================================
# Routing Functions
# =============================================================================

def check_threat_level(
    state: InstallWorkflowState
) -> Literal["llm_analysis", "install"]:
    """
    路由函数：判断是否需要 LLM 分析

    逻辑:
    - 无威胁 → 直接安装
    - 有 MEDIUM+ 威胁 → LLM 分析
    - 仅有 LOW 威胁 → 直接安装
    """
    threatened = state["threatened_skills"]

    if not threatened:
        return "install"

    # 检查是否有 MEDIUM+ 级别威胁
    for threat in threatened:
        severity = threat["scan_result"].get("severity", "")
        if severity in ["MEDIUM", "HIGH", "CRITICAL"]:
            return "llm_analysis"

    return "install"


# =============================================================================
# Workflow Builder
# =============================================================================

def build_graph() -> StateGraph:
    """构建工作流图 - 返回 builder 供外部编译"""
    builder = StateGraph(InstallWorkflowState)

    # 添加节点
    builder.add_node("clone_repo", clone_repo_node)
    builder.add_node("security_scan", security_scan_node)
    builder.add_node("llm_analysis_review", llm_analysis_review_node)
    builder.add_node("install_skills", install_skills_node)

    # 设置入口
    builder.set_entry_point("clone_repo")

    # 添加边
    builder.add_edge("clone_repo", "security_scan")

    # 条件路由：根据威胁级别决定是否需要 LLM 分析
    builder.add_conditional_edges(
        "security_scan",
        check_threat_level,
        {
            "llm_analysis": "llm_analysis_review",
            "install": "install_skills"
        }
    )

    builder.add_edge("llm_analysis_review", "install_skills")
    builder.add_edge("install_skills", END)

    return builder


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    """CLI 入口"""
    parser = argparse.ArgumentParser(
        description="技能安装工作流 - 串联 clone + scan + install",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本安装
  python bin/skill_install_workflow.py https://github.com/user/repo

  # 安装指定子技能
  python bin/skill_install_workflow.py https://github.com/user/repo --skill my-skill

  # 强制覆盖安装
  python bin/skill_install_workflow.py https://github.com/user/repo --force

  # 中断恢复（LLM 分析后）
  python bin/skill_install_workflow.py https://github.com/user/repo --result='{"skill": "keep"}'
        """
    )

    parser.add_argument("url", help="GitHub 仓库 URL")
    parser.add_argument("--skill", help="指定子技能名")
    parser.add_argument("--force", "-f", action="store_true", help="强制覆盖已存在的技能")

    # 中断恢复选项
    parser.add_argument("--result", help="LLM 分析结果 (JSON 格式，用于中断恢复)")
    parser.add_argument("--skip-interrupt", action="store_true", help="跳过中断，自动继续")

    # 调试选项
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument("--dry-run", action="store_true", help="仅显示计划，不执行")

    args = parser.parse_args()

    # 初始状态
    initial_state: InstallWorkflowState = {
        "github_url": args.url,
        "skill_name": args.skill,
        "force_install": args.force,
        "cloned_repo_path": None,
        "extracted_skills": [],
        "scan_results": {},
        "threatened_skills": [],
        "llm_analysis_pending": False,
        "llm_analysis_result": args.result if args.result else None,
        "rule_decisions": {},
        "analysis_prompt": None,
        "pending_skills": [],
        "prompt_file": None,
        "installed_skills": [],
        "failed_skills": [],
        "skipped_skills": [],
        "logs": []
    }

    if args.dry_run:
        print("[DRY RUN] 计划执行以下操作:")
        print(f"  1. 克隆仓库: {args.url}")
        if args.skill:
            print(f"  2. 提取子技能: {args.skill}")
        print(f"  3. 安全扫描所有技能")
        print(f"  4. LLM 分析威胁 (如有)")
        print(f"  5. 安装技能")
        return 0

    # 执行工作流
    builder = build_graph()

    # 生成唯一的 thread_id（基于 URL）
    url_normalized = args.url.replace('/', '_').replace('\\', '_').replace(':', '')
    thread_id = f"skill_install_{url_normalized}"

    # 配置检查点（参考模板：每个任务独立的数据库）
    checkpoint_dir = PROJECT_ROOT / "mybox" / "temp" / "langgraph" / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    db_path = checkpoint_dir / f"skill_install_{url_normalized}.db"

    config = {"configurable": {"thread_id": thread_id}}

    print(f"[START] 技能安装工作流启动")
    print(f"[URL] {args.url}")
    print(f"[TIME] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    try:
        # 使用文件持久化 checkpointer（参考模板模式）
        with SqliteSaver.from_conn_string(str(db_path)) as checkpointer:
            graph = builder.compile(checkpointer=checkpointer)

            # 检查是否有未完成的任务（中断恢复）
            current = graph.get_state(config)

            if current.next and not args.skip_interrupt:
                # 恢复模式
                print(f"[System] 检测到中断任务，正在恢复: {thread_id}")

                # 解析恢复参数
                from langgraph.types import Command
                resume_value = args.result if args.result else "auto"
                graph.invoke(Command(resume=resume_value), config=config)

                # 恢复完成后清理中断文件
                interrupt_file = PROJECT_ROOT / "mybox" / "temp" / "langgraph_interrupt.json"
                if interrupt_file.exists():
                    interrupt_file.unlink()
                    print(f"[System] 已清理中断状态文件")

            else:
                # 新任务模式
                graph.invoke(initial_state, config=config)

            # 输出最终状态
            final = graph.get_state(config)

            if final.interrupts:
                # 任务中断，显示中断信息
                # 参考 template: 只需显示 interrupt value，LangGraph 自动持久化到 checkpoint
                interrupt_msg = final.interrupts[0].value

                print(interrupt_msg)
                print(f"\n[Info] 任务已暂停，状态已保存到 checkpoint")
                print(f"[Info] 恢复方法: python bin/skill_install_workflow.py {args.url} --result='{{\"skill-name\": \"keep\"}}'")

                # 中断时退出（LangGraph 已自动保存状态到 SQLite checkpoint）
                return 0
            else:
                # 任务完成，显示日志
                final_logs = final.values.get("logs", [])
                if final_logs:
                    print("\n" + "=" * 60)
                    print("[LOGS]")
                    for log in final_logs:
                        print(f"  {log}")

                print("\n" + "=" * 60)

                # checkpoint 数据库保留（用于调试和状态追踪）
                # 如需清理，手动删除：rm mybox/temp/langraph/checkpoints/skill_install.db

                # 根据安装结果决定退出码
                installed = final.values.get("installed_skills", [])
                failed = final.values.get("failed_skills", [])

                # 检查是否有错误日志（克隆失败等情况）
                has_error = any("[ERROR]" in log for log in final_logs)

                if len(installed) > 0:
                    print("[DONE] 工作流执行完成: 安装成功")
                    return 0
                elif len(failed) > 0:
                    print("[FAIL] 工作流执行完成: 安装失败")
                    return 1
                elif has_error:
                    print("[FAIL] 工作流执行完成: 克隆或处理失败")
                    return 1
                else:
                    print("[DONE] 工作流执行完成: 无技能需安装")
                    return 0

    except KeyboardInterrupt:
        print("\n[INTERRUPT] 用户中断")
        return 1
    except Exception as e:
        print(f"\n[ERROR] 工作流执行失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

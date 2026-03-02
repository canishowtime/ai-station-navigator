#!/usr/bin/env python3
"""
security_scanner.py - Agent Skills Security Scanner
封装 cisco-ai-skill-scanner，集成到项目路径体系

职责:
1. 一期安全扫描（StaticAnalyzer + BehavioralAnalyzer）
2. 批量扫描（并发支持）
3. 配置管理

注意: 克隆功能已移至 clone_manager.py

Based on cisco-ai-skill-scanner (Apache 2.0)
https://github.com/cisco-ai-defense/skill-scanner
Original Copyright 2026 Cisco Systems, Inc.
"""

import sys
import os

# Windows UTF-8 兼容 (P0 - 所有脚本必须包含)
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
import gc
import time

# =============================================================================
# 补丁应用状态标志（懒加载）
# =============================================================================

_patches_applied = False


def _ensure_patches_applied() -> None:
    """确保补丁已应用（懒加载，仅在首次需要时执行）"""
    global _patches_applied
    if not _patches_applied:
        _patch_skill_loader()
        _patches_applied = True


# =============================================================================
# Frontmatter 容错解析补丁 (方案 A)
# =============================================================================

def _patch_skill_loader() -> bool:
    """
    修复 skill_scanner 的 frontmatter 解析问题

    问题：YAML 格式错误（如 key:value）导致整个扫描失败
    解决：容错解析，失败时使用降级方案继续扫描代码

    注意：这是 Monkey Patching，如果 cisco-ai-skill-scanner 更新内部实现，
    补丁可能会失效。建议定期检查补丁兼容性。

    长期方案：向上游提交 PR 改进 frontmatter 容错性。
    """
    try:
        import re
        from skill_scanner.core.loader import SkillLoader

        # 保存原始方法
        original_parse_skill_md = SkillLoader._parse_skill_md

        def _parse_frontmatter_forgiving(content: str):
            """容错解析 frontmatter"""
            try:
                import frontmatter
                post = frontmatter.loads(content)
                return post.metadata, post.content, None
            except Exception as e:
                # frontmatter 解析失败，手动分离
                metadata, body = _split_frontmatter_raw(content)
                return metadata, body, str(e)

        def _split_frontmatter_raw(content: str):
            """手动分离 frontmatter 和 body（容错）"""
            if not content.startswith("---"):
                return {}, content

            # 找到第二个 ---
            parts = content.split("---", 2)
            if len(parts) < 3:
                return {}, content

            # 尝试宽松解析 YAML
            frontmatter_text = parts[1]
            body = parts[2].lstrip()

            # 使用正则容错提取（处理 key:value 格式）
            metadata = {}
            for line in frontmatter_text.strip().split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                # 容错匹配：key: value 或 key:value
                match = re.match(r'^([\w-]+):\s*(.+)$', line)
                if match:
                    key, value = match.groups()
                    metadata[key] = value
                else:
                    # 处理 key:value 格式（无空格）
                    match = re.match(r'^([\w-]+):(.+)$', line)
                    if match:
                        key, value = match.groups()
                        metadata[key] = value

            return metadata, body

        def _extract_fallback_metadata(skill_md_path, content, partial_metadata):
            """从文件名和内容推断元数据"""
            metadata = {}

            # 从路径提取 name
            metadata["name"] = skill_md_path.parent.name

            # 从首段提取 description
            body_lines = content.split('\n')
            for line in body_lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    metadata["description"] = line[:200]
                    break

            if "description" not in metadata:
                metadata["description"] = "No description available"

            # 合并部分解析的元数据
            metadata.update(partial_metadata)

            return metadata

        def patched_parse_skill_md(self, skill_md_path, *, lenient: bool = False):
            """容错解析 SKILL.md

            Args:
                skill_md_path: SKILL.md 文件路径
                lenient: 宽松模式标志（2.0 新增，补丁中忽略）
            """
            try:
                with open(skill_md_path, encoding="utf-8") as f:
                    content = f.read()
            except (OSError, UnicodeDecodeError) as e:
                from skill_scanner.core.loader import SkillLoadError
                raise SkillLoadError(f"Failed to read SKILL.md: {e}")

            # 容错解析 frontmatter
            metadata, body, parse_error = _parse_frontmatter_forgiving(content)

            # 如果解析失败，使用降级方案
            if parse_error:
                metadata = _extract_fallback_metadata(skill_md_path, content, metadata)
                # 标记解析错误（但不中断扫描）
                metadata["_parse_error"] = parse_error

            # 验证必需字段（使用默认值）
            from skill_scanner.core.models import SkillManifest

            name = metadata.get("name") or skill_md_path.parent.name
            description = metadata.get("description") or "No description available"

            # 清理内部标记
            metadata.pop("_parse_error", None)

            # 提取 metadata 字段
            metadata_field = None
            if "metadata" in metadata and isinstance(metadata["metadata"], dict):
                metadata_field = metadata["metadata"]
            else:
                known_fields = [
                    "name", "description", "license", "compatibility",
                    "allowed-tools", "allowed_tools", "metadata",
                    "disable-model-invocation", "disable_model_invocation",
                ]
                metadata_field = {k: v for k, v in metadata.items() if k not in known_fields}
                if not metadata_field:
                    metadata_field = None

            # 提取 disable-model-invocation
            disable_model_invocation = metadata.get("disable-model-invocation")
            if disable_model_invocation is None:
                disable_model_invocation = metadata.get("disable_model_invocation", False)

            # 创建 manifest
            manifest = SkillManifest(
                name=name,
                description=description,
                license=metadata.get("license"),
                compatibility=metadata.get("compatibility"),
                allowed_tools=metadata.get("allowed-tools") or metadata.get("allowed_tools"),
                metadata=metadata_field,
                disable_model_invocation=bool(disable_model_invocation),
            )

            return manifest, body

        # 应用 monkey patch
        SkillLoader._parse_skill_md = patched_parse_skill_md
        return True

    except Exception as e:
        # 补丁失败不影响扫描器运行
        import warnings
        warnings.warn(f"Failed to patch skill_loader: {e}")
        return False


# =============================================================================
# 路径配置
# =============================================================================

BASE_DIR = Path(__file__).parent.parent
SKILLS_DIR = BASE_DIR / ".claude" / "skills"
CACHE_DIR = BASE_DIR / "mybox" / "cache" / "repos"
TEMP_DIR = BASE_DIR / "mybox" / "temp"
CONFIG_FILE = BASE_DIR / ".claude" / "config" / "security.yml"

# 添加 bin 目录到 sys.path
_bin_dir = Path(__file__).parent
if str(_bin_dir) not in sys.path:
    sys.path.insert(0, str(_bin_dir))


# =============================================================================
# 日志工具
# =============================================================================

def log(level: str, message: str, emoji: str = ""):
    """统一的日志输出"""
    from datetime import datetime
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"{timestamp} [{level}] {emoji} {message}")

def success(msg: str):
    log("SUCCESS", msg, "[OK]")

def info(msg: str):
    log("INFO", msg, "[INFO]")

def warn(msg: str):
    log("WARN", msg, "[WARN]")

def error(msg: str):
    log("ERROR", msg, "[ERROR]")


# =============================================================================
# 安全扫描接口
# =============================================================================

def scan(skill_path: Path, config: Optional[Dict] = None) -> Dict[str, Any]:
    """扫描指定路径的技能或目录

    使用 StaticAnalyzer + BehavioralAnalyzer 组合（默认模式）
    - 无需网络请求
    - 无需 API Key
    - 检测覆盖率 ~95%
    - 支持无 SKILL.md 的普通目录扫描

    Args:
        skill_path: 技能目录路径或任意代码目录
        config: 可选配置字典（如不提供则加载默认配置）

    Returns:
        扫描结果字典
    """
    # 确保补丁已应用（懒加载）
    _ensure_patches_applied()

    try:
        from skill_scanner import SkillScanner
        from skill_scanner.core.analyzers import StaticAnalyzer, BehavioralAnalyzer
    except ImportError as e:
        return {
            "status": "error",
            "error": f"cisco-ai-skill-scanner 未安装: {e}",
            "severity": "UNKNOWN",
            "findings_count": 0,
            "threats": []
        }

    # 加载配置
    if config is None:
        config = load_config()

    engines = config.get("engines", {})
    use_static = engines.get("static", True)
    use_behavioral = engines.get("behavioral", True)

    # 构建分析器列表
    analyzers = []
    if use_static:
        analyzers.append(StaticAnalyzer())
    if use_behavioral:
        analyzers.append(BehavioralAnalyzer())

    if not analyzers:
        return {
            "status": "error",
            "error": "未启用任何扫描引擎",
            "severity": "UNKNOWN",
            "findings_count": 0,
            "threats": []
        }

    # 检查是否存在 SKILL.md
    has_skill_md = (Path(skill_path) / "SKILL.md").exists()

    # 执行扫描
    try:
        import time
        start_time = time.time()

        all_findings = []
        analyzers_used = []

        if has_skill_md:
            # 使用 SkillScanner（技能格式）
            scanner = SkillScanner(analyzers=analyzers)
            result = scanner.scan_skill(Path(skill_path))
            all_findings = result.findings
            analyzers_used = result.analyzers_used
            scan_duration = result.scan_duration_seconds
        else:
            # 直接调用分析器（无 SKILL.md）
            for analyzer in analyzers:
                try:
                    findings = analyzer.analyze(Path(skill_path))
                    all_findings.extend(findings)
                    analyzers_used.append(analyzer.get_name())
                except Exception as e:
                    warn(f"分析器 {analyzer.get_name()} 执行失败: {e}")
            scan_duration = time.time() - start_time

        # 提取威胁信息（包含上下文）
        def extract_context(file_path: Path, line_number: int, window: int = 3) -> List[str]:
            """提取威胁代码的上下文"""
            try:
                if not file_path.exists():
                    return [f"[File not found: {file_path}]"]

                with open(file_path, 'r', encoding='utf-8', errors='replace') as fp:
                    lines = fp.readlines()

                context_lines = []
                start = max(0, line_number - window - 1)
                end = min(len(lines), line_number + window)

                for i in range(start, end):
                    prefix = ">>> " if i == line_number - 1 else "    "
                    context_lines.append(f"{prefix}{i+1:4d} | {lines[i].rstrip()}")

                return context_lines
            except Exception:
                return [f"[Failed to read context: {file_path}:{line_number}]"]

        threats = []
        for f in all_findings:
            threat_data = {
                "rule_id": f.rule_id,
                "severity": f.severity.value,
                "title": f.title,
                "file": str(f.file_path) if f.file_path else None,
                "line": f.line_number,
                "snippet": f.snippet
            }

            # 添加完整上下文（仅当文件路径存在时）
            if f.file_path and f.line_number:
                threat_data["context"] = extract_context(f.file_path, f.line_number)

            threats.append(threat_data)

        return {
            "status": "threat_found" if all_findings else "success",
            "severity": max([f.severity.value for f in all_findings]) if all_findings else "SAFE",
            "findings_count": len(all_findings),
            "threats": threats,
            "details": {
                "scan_duration": scan_duration,
                "analyzers_used": analyzers_used,
                "skill_md_present": has_skill_md
            }
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "severity": "UNKNOWN",
            "findings_count": 0,
            "threats": []
        }


def batch_scan(skill_dirs: List[Path], config: Optional[Dict] = None,
               timeout: int = 60, show_progress: bool = True) -> Dict[str, Dict]:
    """
    批量扫描技能（支持并发、超时和进度反馈）

    Args:
        skill_dirs: 技能目录列表
        config: 可选配置
        timeout: 单个技能超时时间（秒），默认 5 分钟
        show_progress: 是否显示进度信息

    Returns:
        {skill_name: scan_result, ...}
    """
    if config is None:
        config = load_config()

    if not config.get("scan_enabled", True):
        return {d.name: {"status": "skipped"} for d in skill_dirs}

    scan_results = {}

    # 单个技能：直接扫描
    if len(skill_dirs) == 1:
        skill_dir = skill_dirs[0]
        info(f"[SCAN] 安全扫描: {skill_dir.name}")
        try:
            scan_results[skill_dir.name] = scan(skill_dir, config)
        except Exception as e:
            scan_results[skill_dir.name] = {
                "status": "error",
                "error": str(e),
                "severity": "UNKNOWN",
                "findings_count": 0,
                "threats": []
            }
        return scan_results

    # 批量技能：线程池并行扫描
    info(f"[SCAN] 批量并行扫描 {len(skill_dirs)} 个技能 (4线程)...")

    batch_size = 8
    total_batches = (len(skill_dirs) + batch_size - 1) // batch_size
    completed_count = 0
    start_time = time.time()

    for i in range(0, len(skill_dirs), batch_size):
        batch = skill_dirs[i:i + batch_size]
        batch_num = i // batch_size + 1

        if show_progress:
            elapsed = time.time() - start_time
            avg_time = elapsed / completed_count if completed_count > 0 else 0
            remaining = avg_time * (len(skill_dirs) - completed_count) if avg_time > 0 else 0
            info(f"  批次 {batch_num}/{total_batches} ({completed_count}/{len(skill_dirs)} 完成, "
                 f"已用时: {elapsed:.1f}s, 预估剩余: {remaining:.1f}s)")

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(scan, skill_dir, config): skill_dir
                for skill_dir in batch
            }

            for future in as_completed(futures):
                skill_dir = futures[future]
                try:
                    result = future.result(timeout=timeout)
                    scan_results[skill_dir.name] = result
                    if show_progress:
                        completed_count += 1
                        status_icon = "[OK]" if result["status"] == "success" else "[!]"
                        print(f"    {completed_count}/{len(skill_dirs)} {skill_dir.name} {status_icon} "
                              f"{result['severity']} ({result['findings_count']} 威胁)")
                except TimeoutError:
                    scan_results[skill_dir.name] = {
                        "status": "error",
                        "error": f"扫描超时 (>{timeout}s)",
                        "severity": "UNKNOWN",
                        "findings_count": 0,
                        "threats": []
                    }
                    if show_progress:
                        completed_count += 1
                        print(f"    {completed_count}/{len(skill_dirs)} {skill_dir.name} [TIMEOUT]")
                except Exception as e:
                    scan_results[skill_dir.name] = {
                        "status": "error",
                        "error": str(e),
                        "severity": "UNKNOWN",
                        "findings_count": 0,
                        "threats": []
                    }
                    if show_progress:
                        completed_count += 1
                        print(f"    {completed_count}/{len(skill_dirs)} {skill_dir.name} [ERROR] {str(e)[:50]}")

        # 强制垃圾回收
        gc.collect()

    return scan_results


def is_safe(result: Dict[str, Any], allowed_severity: List[str]) -> bool:
    """判断扫描结果是否在允许的安全级别内"""
    severity = result.get("severity", "UNKNOWN")
    return severity in allowed_severity


def load_config() -> Dict[str, Any]:
    """加载安全配置"""
    if CONFIG_FILE.exists():
        import yaml
        try:
            return yaml.safe_load(CONFIG_FILE.read_text())
        except Exception:
            pass

    # 默认配置
    return {
        "scan_enabled": True,
        "scan_on_install": True,
        "auto_uninstall_on_threat": True,
        "allowed_severity": ["SAFE", "LOW"],
        "engines": {
            "static": True,
            "behavioral": True,
            "llm": False,
            "virustotal": False
        }
    }


# =============================================================================
# CLI 入口
# =============================================================================

def main():
    """CLI 入口"""
    import argparse

    parser = argparse.ArgumentParser(
        description="security_scanner.py - Agent Skills Security Scanner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 扫描缓存目录中的新技能（根据克隆脚本输出）
  python bin/security_scanner.py scan-cache

  # 扫描指定路径（仅允许缓存目录）
  python bin/security_scanner.py scan <cache_path>

  # 查看当前配置
  python bin/security_scanner.py config

SECURITY: 扫描仅限 mybox/cache/repos/ 目录，禁止扫描已安装技能。
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # scan 命令（仅允许缓存目录）
    scan_parser = subparsers.add_parser("scan", help="扫描指定路径（仅限缓存目录）")
    scan_parser.add_argument("target", help="技能路径（必须是 mybox/cache/repos/ 下的路径）")
    scan_parser.add_argument("--json", action="store_true", help="输出 JSON 格式（供脚本解析）")

    # scan-cache 命令（扫描克隆脚本输出的新技能）
    subparsers.add_parser("scan-cache", help="扫描缓存目录中的新技能（根据克隆脚本输出）")

    # config 命令
    subparsers.add_parser("config", help="查看当前配置")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # 加载配置
    config = load_config()

    if args.command == "config":
        print("当前安全配置:")
        print(json.dumps(config, ensure_ascii=False, indent=2))
        return 0

    elif args.command == "scan":
        target = args.target
        skill_path = None

        if Path(target).is_absolute():
            # 绝对路径：直接使用
            skill_path = Path(target)
        else:
            # 相对路径：从 BASE_DIR 解析
            skill_path = BASE_DIR / target

        # 路径安全验证：必须位于缓存目录下
        try:
            skill_path.resolve().relative_to(CACHE_DIR.resolve())
        except ValueError:
            print(f"错误: 安全限制 - 扫描仅限缓存目录 (mybox/cache/repos/)")
            print(f"目标路径: {skill_path.resolve()}")
            print(f"允许范围: {CACHE_DIR.resolve()}")
            return 1

        if not skill_path.exists():
            print(f"错误: 路径不存在: {skill_path.resolve()}")
            return 1

        result = scan(skill_path, config)

        # JSON 输出模式（供脚本解析）
        if getattr(args, 'json', False):
            print(json.dumps(result, ensure_ascii=False, separators=(',', ':')))
            return 0 if result["status"] == "success" else 1

        # 默认：人类可读输出
        print(f"扫描: {skill_path}")
        print(f"\n状态: {result['status']}")
        print(f"严重级别: {result['severity']}")
        print(f"发现威胁: {result['findings_count']}")

        if result.get("error"):
            print(f"\n错误信息: {result['error']}")

        if result.get("threats"):
            print("\n威胁详情:")
            for threat in result["threats"]:
                print(f"  - [{threat['severity']}] {threat['title']}")
                if threat.get("file"):
                    print(f"    文件: {threat['file']}:{threat.get('line', '?')}")

        if result.get("details"):
            print(f"\n扫描耗时: {result['details'].get('scan_duration', 0):.2f}s")
            print(f"分析器: {', '.join(result['details'].get('analyzers_used', []))}")

        return 0 if result["status"] == "success" else 1

    elif args.command == "scan-cache":
        # 扫描缓存目录中的新技能（根据克隆脚本输出）
        if not CACHE_DIR.exists():
            print("错误: 缓存目录不存在")
            return 1

        # 优先读取 .last_cloned_repo 文件（克隆脚本写入）
        last_cloned_file = TEMP_DIR / ".last_cloned_repo"
        scan_dirs = []

        if last_cloned_file.exists():
            try:
                with open(last_cloned_file, "r", encoding="utf-8") as f:
                    repo_name = f.read().strip()
                target_repo = CACHE_DIR / repo_name
                if target_repo.exists() and target_repo.is_dir():
                    scan_dirs = [target_repo]
                    info(f"[SCAN] 扫描最新克隆仓库: {repo_name}")
                else:
                    warn(f".last_cloned_repo 指定的仓库不存在: {repo_name}")
                    scan_dirs = [d for d in CACHE_DIR.iterdir() if d.is_dir() and d.name != ".gitkeep"]
            except Exception as e:
                warn(f"读取 .last_cloned_repo 失败: {e}")
                scan_dirs = [d for d in CACHE_DIR.iterdir() if d.is_dir() and d.name != ".gitkeep"]
        else:
            # 文件不存在：扫描全部（向后兼容）
            info("[SCAN] 未找到 .last_cloned_repo 标记，扫描全部缓存目录")
            scan_dirs = [d for d in CACHE_DIR.iterdir() if d.is_dir() and d.name != ".gitkeep"]

        # 查找技能子目录
        cache_skills = []
        for repo_dir in scan_dirs:
            # 查找 repo 下的技能目录（包含 SKILL.md 的目录）
            for skill_dir in repo_dir.rglob("*"):
                if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                    cache_skills.append(skill_dir)

        if not cache_skills:
            print("缓存目录中没有发现技能")
            return 0

        print(f"扫描缓存目录中的 {len(cache_skills)} 个技能...\n")

        # 使用批量并发扫描
        scan_results = batch_scan(cache_skills, config, timeout=60, show_progress=True)

        # 汇总结果
        all_safe = True
        threatened_skills = []

        for skill_dir, result in scan_results.items():
            if result["status"] != "success":
                all_safe = False
                threatened_skills.append((skill_dir, result))
            else:
                status_icon = "[OK]"
                print(f"  {status_icon} {skill_dir}: {result['severity']}")

        print()

        # 显示威胁详情
        if threatened_skills:
            print(f"发现 {len(threatened_skills)} 个威胁技能:")
            for skill_name, result in threatened_skills:
                status = result.get("status", "unknown")
                severity = result.get("severity", "UNKNOWN")
                count = result.get("findings_count", 0)
                error = result.get("error", "")

                if error:
                    print(f"  [!] {skill_name}: {error}")
                else:
                    print(f"  [!] {skill_name}: {severity} ({count} 个威胁)")

                    # 显示威胁列表
                    for threat in result.get("threats", [])[:3]:
                        print(f"      - [{threat['severity']}] {threat['title']}")
                    if len(result.get("threats", [])) > 3:
                        print(f"      ... 还有 {len(result.get('threats', [])) - 3} 个")

        if all_safe:
            print("所有技能扫描通过")
            return 0
        else:
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

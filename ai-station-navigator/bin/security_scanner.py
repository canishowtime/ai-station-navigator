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
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor
import gc

# =============================================================================
# YARA 修复补丁 (Windows 兼容性)
# =============================================================================

def _patch_yara_scanner() -> bool:
    """
    修复 yara-python 在 Windows 上的 filepaths 编译问题
    """
    try:
        from skill_scanner.core.rules import yara_scanner
        import yara

        original_load = yara_scanner.YaraScanner._load_rules

        def patched_load_rules(self):
            """修复后的 _load_rules 方法"""
            if not self.rules_dir.exists():
                raise FileNotFoundError(f"YARA rules directory not found: {self.rules_dir}")

            yara_files = list(self.rules_dir.glob("*.yara"))
            if not yara_files:
                raise FileNotFoundError(f"No .yara files found in {self.rules_dir}")

            # 修复: 从文件内容编译 (兼容 Windows)
            rules_dict = {}
            for yara_file in yara_files:
                namespace = yara_file.stem
                content = yara_file.read_text(encoding="utf-8")
                rules_dict[namespace] = content

            self.rules = yara.compile(sources=rules_dict)

        yara_scanner.YaraScanner._load_rules = patched_load_rules
        return True
    except Exception:
        return False


# 应用补丁
_patch_yara_scanner()


# =============================================================================
# Frontmatter 容错解析补丁 (方案 A)
# =============================================================================

def _patch_skill_loader() -> bool:
    """
    修复 skill_scanner 的 frontmatter 解析问题

    问题：YAML 格式错误（如 key:value）导致整个扫描失败
    解决：容错解析，失败时使用降级方案继续扫描代码
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

        def patched_parse_skill_md(self, skill_md_path):
            """容错解析 SKILL.md"""
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


# 应用 frontmatter 容错补丁
_patch_skill_loader()


# =============================================================================
# 路径配置
# =============================================================================

BASE_DIR = Path(__file__).parent.parent
SKILLS_DIR = BASE_DIR / ".claude" / "skills"
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
    log("SUCCESS", msg, "✅")

def info(msg: str):
    log("INFO", msg, "🔄")

def warn(msg: str):
    log("WARN", msg, "⚠️")

def error(msg: str):
    log("ERROR", msg, "❌")


# =============================================================================
# 安全扫描接口
# =============================================================================

def scan(skill_path: Path, config: Optional[Dict] = None) -> Dict[str, Any]:
    """扫描指定路径的技能

    使用 StaticAnalyzer + BehavioralAnalyzer 组合（默认模式）
    - 无需网络请求
    - 无需 API Key
    - 检测覆盖率 ~95%

    Args:
        skill_path: 技能目录路径
        config: 可选配置字典（如不提供则加载默认配置）

    Returns:
        扫描结果字典
    """
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

    # 执行扫描
    try:
        scanner = SkillScanner(analyzers=analyzers)
        result = scanner.scan_skill(Path(skill_path))

        # 提取威胁信息
        threats = [
            {
                "rule_id": f.rule_id,
                "severity": f.severity.value,
                "title": f.title,
                "file": str(f.file_path) if f.file_path else None,
                "line": f.line_number,
                "snippet": f.snippet  # YARA 匹配的实际代码内容
            }
            for f in result.findings
        ]

        return {
            "status": "threat_found" if not result.is_safe else "success",
            "severity": result.max_severity.value if result.findings else "SAFE",
            "findings_count": len(result.findings),
            "threats": threats,
            "details": {
                "scan_duration": result.scan_duration_seconds,
                "analyzers_used": result.analyzers_used
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


def batch_scan(skill_dirs: List[Path], config: Optional[Dict] = None) -> Dict[str, Dict]:
    """
    批量扫描技能（支持并发）

    Args:
        skill_dirs: 技能目录列表
        config: 可选配置

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
        info(f"🔄 安全扫描: {skill_dir.name}")
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
    info(f"🔄 批量并行扫描 {len(skill_dirs)} 个技能 (4线程)...")

    batch_size = 8
    for i in range(0, len(skill_dirs), batch_size):
        batch = skill_dirs[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(skill_dirs) + batch_size - 1) // batch_size
        info(f"  批次 {batch_num}/{total_batches}: 扫描 {len(batch)} 个技能...")

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(scan, skill_dir, config): skill_dir
                for skill_dir in batch
            }

            for future in futures:
                skill_dir = futures[future]
                try:
                    scan_results[skill_dir.name] = future.result()
                except Exception as e:
                    scan_results[skill_dir.name] = {
                        "status": "error",
                        "error": str(e),
                        "severity": "UNKNOWN",
                        "findings_count": 0,
                        "threats": []
                    }

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
  # 扫描指定技能
  python bin/security_scanner.py scan my-skill

  # 扫描所有已安装技能
  python bin/security_scanner.py scan-all

  # 查看当前配置
  python bin/security_scanner.py config

Note: 克隆功能已移至 clone_manager.py
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # scan 命令
    scan_parser = subparsers.add_parser("scan", help="扫描指定技能")
    scan_parser.add_argument("target", help="技能名称或路径")
    scan_parser.add_argument("--json", action="store_true", help="输出 JSON 格式（供脚本解析）")

    # scan-all 命令
    subparsers.add_parser("scan-all", help="扫描所有已安装技能")

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

        if not Path(target).is_absolute():
            skill_path = SKILLS_DIR / target
            if not skill_path.exists():
                print(f"错误: 技能不存在: {target}")
                return 1
        else:
            skill_path = Path(target)

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

    elif args.command == "scan-all":
        if not SKILLS_DIR.exists():
            print("错误: 技能目录不存在")
            return 1

        skills = [d for d in SKILLS_DIR.iterdir() if d.is_dir()]

        if not skills:
            print("没有已安装的技能")
            return 0

        print(f"扫描 {len(skills)} 个已安装技能...\n")

        all_safe = True
        threatened_skills = []

        for skill_dir in skills:
            print(f"扫描: {skill_dir.name}")
            result = scan(skill_dir, config)

            status_icon = "[OK]" if result["status"] == "success" else "[!]"
            print(f"  {status_icon} {result['severity']} - {result['findings_count']} 个威胁")

            if result["status"] != "success":
                all_safe = False
                threatened_skills.append((skill_dir.name, result))
            print()

        if all_safe:
            print("所有技能扫描通过")
            return 0
        else:
            print(f"发现 {len(threatened_skills)} 个威胁技能")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

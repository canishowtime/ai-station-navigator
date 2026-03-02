#!/usr/bin/env python3
"""
security_scanner.py - Agent Skills Security Scanner
Wraps cisco-ai-skill-scanner, integrated into project path system

Responsibilities:
1. Phase 1 Security Scan (StaticAnalyzer + BehavioralAnalyzer)
2. Batch Scan (with concurrency support)
3. Configuration Management

Note: Clone functionality moved to clone_manager.py

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
# Patch Application Status Flag (lazy loading)
# =============================================================================

_patches_applied = False


def _ensure_patches_applied() -> None:
    """Ensure patches are applied (lazy load, only on first use)"""
    global _patches_applied
    if not _patches_applied:
        _patch_skill_loader()
        _patches_applied = True


# =============================================================================
# Frontmatter Forgiving Parse Patch (Plan A)
# =============================================================================

def _patch_skill_loader() -> bool:
    """
    Fix skill_scanner frontmatter parsing issues

    Issue: YAML format errors (e.g., key:value) cause entire scan to fail
    Solution: Forgiving parse, fallback to continue code scan on failure

    Note: This is Monkey Patching. If cisco-ai-skill-scanner updates internal implementation,
    patch may become ineffective. Recommend checking patch compatibility periodically.

    Long-term: Submit PR upstream to improve frontmatter fault tolerance.
    """
    try:
        import re
        from skill_scanner.core.loader import SkillLoader

        # 保存原始方法
        original_parse_skill_md = SkillLoader._parse_skill_md

        def _parse_frontmatter_forgiving(content: str):
            """Forgiving frontmatter parsing"""
            try:
                import frontmatter
                post = frontmatter.loads(content)
                return post.metadata, post.content, None
            except Exception as e:
                # frontmatter parse failed, manual split
                metadata, body = _split_frontmatter_raw(content)
                return metadata, body, str(e)

        def _split_frontmatter_raw(content: str):
            """Manual frontmatter and body split (forgiving)"""
            if not content.startswith("---"):
                return {}, content

            # Find second ---
            parts = content.split("---", 2)
            if len(parts) < 3:
                return {}, content

            # Try lenient YAML parsing
            frontmatter_text = parts[1]
            body = parts[2].lstrip()

            # Use regex for fault-tolerant extraction (handle key:value format)
            metadata = {}
            for line in frontmatter_text.strip().split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                # Forgiving match: key: value or key:value
                match = re.match(r'^([\w-]+):\s*(.+)$', line)
                if match:
                    key, value = match.groups()
                    metadata[key] = value
                else:
                    # Handle key:value format (no space)
                    match = re.match(r'^([\w-]+):(.+)$', line)
                    if match:
                        key, value = match.groups()
                        metadata[key] = value

            return metadata, body

        def _extract_fallback_metadata(skill_md_path, content, partial_metadata):
            """Extract metadata from filename and content"""
            metadata = {}

            # Extract name from path
            metadata["name"] = skill_md_path.parent.name

            # Extract description from first paragraph
            body_lines = content.split('\n')
            for line in body_lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    metadata["description"] = line[:200]
                    break

            if "description" not in metadata:
                metadata["description"] = "No description available"

            # Merge partially parsed metadata
            metadata.update(partial_metadata)

            return metadata

        def patched_parse_skill_md(self, skill_md_path, *, lenient: bool = False):
            """Forgiving SKILL.md parsing

            Args:
                skill_md_path: SKILL.md file path
                lenient: Lenient mode flag (added in 2.0, ignored in patch)
            """
            try:
                with open(skill_md_path, encoding="utf-8") as f:
                    content = f.read()
            except (OSError, UnicodeDecodeError) as e:
                from skill_scanner.core.loader import SkillLoadError
                raise SkillLoadError(f"Failed to read SKILL.md: {e}")

            # Forgiving frontmatter parsing
            metadata, body, parse_error = _parse_frontmatter_forgiving(content)

            # If parse failed, use fallback
            if parse_error:
                metadata = _extract_fallback_metadata(skill_md_path, content, metadata)
                # Mark parse error (but don't interrupt scan)
                metadata["_parse_error"] = parse_error

            # Validate required fields (use defaults)
            from skill_scanner.core.models import SkillManifest

            name = metadata.get("name") or skill_md_path.parent.name
            description = metadata.get("description") or "No description available"

            # Clean internal markers
            metadata.pop("_parse_error", None)

            # Extract metadata field
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

            # Extract disable-model-invocation
            disable_model_invocation = metadata.get("disable-model-invocation")
            if disable_model_invocation is None:
                disable_model_invocation = metadata.get("disable_model_invocation", False)

            # Create manifest
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

        # Apply monkey patch
        SkillLoader._parse_skill_md = patched_parse_skill_md
        return True

    except Exception as e:
        # Patch failure doesn't affect scanner operation
        import warnings
        warnings.warn(f"Failed to patch skill_loader: {e}")
        return False


# =============================================================================
# Path Configuration
# =============================================================================

BASE_DIR = Path(__file__).parent.parent
SKILLS_DIR = BASE_DIR / ".claude" / "skills"
CACHE_DIR = BASE_DIR / "mybox" / "cache" / "repos"
TEMP_DIR = BASE_DIR / "mybox" / "temp"
CONFIG_FILE = BASE_DIR / ".claude" / "config" / "security.yml"

# Add bin directory to sys.path
_bin_dir = Path(__file__).parent
if str(_bin_dir) not in sys.path:
    sys.path.insert(0, str(_bin_dir))


# =============================================================================
# Logging Utilities
# =============================================================================

def log(level: str, message: str, emoji: str = ""):
    """Unified log output"""
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
    """Scan skill or directory at specified path

    Uses StaticAnalyzer + BehavioralAnalyzer combination (default mode)
    - No network requests required
    - No API Key required
    - Detection coverage ~95%
    - Supports scanning normal directories without SKILL.md

    Args:
        skill_path: Skill directory path or any code directory
        config: Optional config dict (loads default if not provided)

    Returns:
        Scan result dictionary
    """
    # 确保补丁已应用（懒加载）
    _ensure_patches_applied()

    try:
        from skill_scanner import SkillScanner
        from skill_scanner.core.analyzers import StaticAnalyzer, BehavioralAnalyzer
    except ImportError as e:
        return {
            "status": "error",
            "error": f"cisco-ai-skill-scanner not installed: {e}",
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
            "error": "No scan engines enabled",
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

        # Extract threat information (including context)
        def extract_context(file_path: Path, line_number: int, window: int = 3) -> List[str]:
            """Extract context of threat code"""
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
    Batch scan skills (supports concurrency, timeout, and progress feedback)

    Args:
        skill_dirs: List of skill directories
        config: Optional configuration
        timeout: Per-skill timeout (seconds), default 5 minutes
        show_progress: Whether to show progress info

    Returns:
        {skill_name: scan_result, ...}
    """
    if config is None:
        config = load_config()

    if not config.get("scan_enabled", True):
        return {d.name: {"status": "skipped"} for d in skill_dirs}

    scan_results = {}

    # Single skill: direct scan
    if len(skill_dirs) == 1:
        skill_dir = skill_dirs[0]
        info(f"[SCAN] Security scan: {skill_dir.name}")
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

    # Batch skills: thread pool parallel scan
    info(f"[SCAN] Batch parallel scan {len(skill_dirs)} skills (4 threads)...")

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
            info(f"  Batch {batch_num}/{total_batches} ({completed_count}/{len(skill_dirs)} completed, "
                 f"elapsed: {elapsed:.1f}s, estimated remaining: {remaining:.1f}s)")

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
                              f"{result['severity']} ({result['findings_count']} threats)")
                except TimeoutError:
                    scan_results[skill_dir.name] = {
                        "status": "error",
                        "error": f"Scan timeout (>{timeout}s)",
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

        # Force garbage collection
        gc.collect()

    return scan_results


def is_safe(result: Dict[str, Any], allowed_severity: List[str]) -> bool:
    """Check if scan result is within allowed severity levels"""
    severity = result.get("severity", "UNKNOWN")
    return severity in allowed_severity


def load_config() -> Dict[str, Any]:
    """Load security configuration"""
    if CONFIG_FILE.exists():
        import yaml
        try:
            return yaml.safe_load(CONFIG_FILE.read_text())
        except Exception:
            pass

    # Default configuration
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
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="security_scanner.py - Agent Skills Security Scanner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan new skills in cache directory (based on clone script output)
  python bin/security_scanner.py scan-cache

  # Scan specified path (cache directory only)
  python bin/security_scanner.py scan <cache_path>

  # View current configuration
  python bin/security_scanner.py config

SECURITY: Scan limited to mybox/cache/repos/ directory, scanning installed skills prohibited.
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # scan command (cache directory only)
    scan_parser = subparsers.add_parser("scan", help="Scan specified path (cache directory only)")
    scan_parser.add_argument("target", help="Skill path (must be under mybox/cache/repos/)")
    scan_parser.add_argument("--json", action="store_true", help="Output JSON format (for script parsing)")

    # scan-cache command (scan new skills from clone script output)
    subparsers.add_parser("scan-cache", help="Scan new skills in cache directory (based on clone script output)")

    # config command
    subparsers.add_parser("config", help="View current configuration")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Load configuration
    config = load_config()

    if args.command == "config":
        print("Current security configuration:")
        print(json.dumps(config, ensure_ascii=False, indent=2))
        return 0

    elif args.command == "scan":
        target = args.target
        skill_path = None

        if Path(target).is_absolute():
            # Absolute path: use directly
            skill_path = Path(target)
        else:
            # Relative path: resolve from BASE_DIR
            skill_path = BASE_DIR / target

        # Path security verification: must be under cache directory
        try:
            skill_path.resolve().relative_to(CACHE_DIR.resolve())
        except ValueError:
            print(f"Error: Security restriction - scan limited to cache directory (mybox/cache/repos/)")
            print(f"Target path: {skill_path.resolve()}")
            print(f"Allowed scope: {CACHE_DIR.resolve()}")
            return 1

        if not skill_path.exists():
            print(f"Error: Path does not exist: {skill_path.resolve()}")
            return 1

        result = scan(skill_path, config)

        # JSON output mode (for script parsing)
        if getattr(args, 'json', False):
            print(json.dumps(result, ensure_ascii=False, separators=(',', ':')))
            return 0 if result["status"] == "success" else 1

        # Default: human-readable output
        print(f"Scan: {skill_path}")
        print(f"\nStatus: {result['status']}")
        print(f"Severity: {result['severity']}")
        print(f"Threats found: {result['findings_count']}")

        if result.get("error"):
            print(f"\nError message: {result['error']}")

        if result.get("threats"):
            print("\nThreat details:")
            for threat in result["threats"]:
                print(f"  - [{threat['severity']}] {threat['title']}")
                if threat.get("file"):
                    print(f"    File: {threat['file']}:{threat.get('line', '?')}")

        if result.get("details"):
            print(f"\nScan duration: {result['details'].get('scan_duration', 0):.2f}s")
            print(f"Analyzers: {', '.join(result['details'].get('analyzers_used', []))}")

        return 0 if result["status"] == "success" else 1

    elif args.command == "scan-cache":
        # Scan new skills in cache directory (based on clone script output)
        if not CACHE_DIR.exists():
            print("Error: Cache directory does not exist")
            return 1

        # Prioritize reading .last_cloned_repo file (written by clone script)
        last_cloned_file = TEMP_DIR / ".last_cloned_repo"
        scan_dirs = []

        if last_cloned_file.exists():
            try:
                with open(last_cloned_file, "r", encoding="utf-8") as f:
                    repo_name = f.read().strip()
                target_repo = CACHE_DIR / repo_name
                if target_repo.exists() and target_repo.is_dir():
                    scan_dirs = [target_repo]
                    info(f"[SCAN] Scanning latest cloned repo: {repo_name}")
                else:
                    warn(f"Repository specified by .last_cloned_repo does not exist: {repo_name}")
                    scan_dirs = [d for d in CACHE_DIR.iterdir() if d.is_dir() and d.name != ".gitkeep"]
            except Exception as e:
                warn(f"Failed to read .last_cloned_repo: {e}")
                scan_dirs = [d for d in CACHE_DIR.iterdir() if d.is_dir() and d.name != ".gitkeep"]
        else:
            # File not found: scan all (backward compatibility)
            info("[SCAN] .last_cloned_repo marker not found, scanning all cache directories")
            scan_dirs = [d for d in CACHE_DIR.iterdir() if d.is_dir() and d.name != ".gitkeep"]

        # Find skill subdirectories
        cache_skills = []
        for repo_dir in scan_dirs:
            # Find skill directories under repo (containing SKILL.md)
            for skill_dir in repo_dir.rglob("*"):
                if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                    cache_skills.append(skill_dir)

        if not cache_skills:
            print("No skills found in cache directory")
            return 0

        print(f"Scanning {len(cache_skills)} skills in cache directory...\n")

        # Use batch concurrent scan
        scan_results = batch_scan(cache_skills, config, timeout=60, show_progress=True)

        # Summarize results
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

        # Display threat details
        if threatened_skills:
            print(f"Found {len(threatened_skills)} threatened skills:")
            for skill_name, result in threatened_skills:
                status = result.get("status", "unknown")
                severity = result.get("severity", "UNKNOWN")
                count = result.get("findings_count", 0)
                error = result.get("error", "")

                if error:
                    print(f"  [!] {skill_name}: {error}")
                else:
                    print(f"  [!] {skill_name}: {severity} ({count} threats)")

                    # Display threat list
                    for threat in result.get("threats", [])[:3]:
                        print(f"      - [{threat['severity']}] {threat['title']}")
                    if len(result.get("threats", [])) > 3:
                        print(f"      ... and {len(result.get('threats', [])) - 3} more")

        if all_safe:
            print("All skills passed scan")
            return 0
        else:
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

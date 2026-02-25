#!/usr/bin/env python3
"""
security_scanner.py - Agent Skills Security Scanner
Wraps cisco-ai-skill-scanner, integrated into project path system

Responsibilities:
1. Phase 1 security scan (StaticAnalyzer + BehavioralAnalyzer)
2. Batch scan (concurrent support)
3. Configuration management

Note: Clone functionality moved to clone_manager.py

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
# YARA Fix Patch (Windows Compatibility)
# =============================================================================

def _patch_yara_scanner() -> bool:
    """
    Fix yara-python filepaths compilation issue on Windows

    Note: This is Monkey Patching, if cisco-ai-skill-scanner updates internal implementation,
    patch may become invalid. Recommend periodically checking patch compatibility.

    Long-term solution: Submit PR upstream to fix Windows compatibility issues.
    """
    try:
        from skill_scanner.core.rules import yara_scanner
        import yara

        # Version check: ensure patch is compatible with library version (optional)
        # If specific version needed, add check here

        original_load = yara_scanner.YaraScanner._load_rules

        def patched_load_rules(self):
            """Patched _load_rules method"""
            if not self.rules_dir.exists():
                raise FileNotFoundError(f"YARA rules directory not found: {self.rules_dir}")

            yara_files = list(self.rules_dir.glob("*.yara"))
            if not yara_files:
                raise FileNotFoundError(f"No .yara files found in {self.rules_dir}")

            # Fix: Compile from file contents (Windows compatible)
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


# Patch application status flag (lazy load)
_patches_applied = False


def _ensure_patches_applied() -> None:
    """Ensure patches applied (lazy load, execute only on first need)"""
    global _patches_applied
    if not _patches_applied:
        _patch_yara_scanner()
        _patch_skill_loader()
        _patches_applied = True


# =============================================================================
# Frontmatter Forgiving Parse Patch (Solution A)
# =============================================================================

def _patch_skill_loader() -> bool:
    """
    Fix skill_scanner frontmatter parsing issue

    Problem: YAML format errors (e.g. key:value) cause entire scan to fail
    Solution: Forgiving parsing, use fallback on failure to continue code scanning

    Note: This is Monkey Patching, if cisco-ai-skill-scanner updates internal implementation,
    patch may become invalid. Recommend periodically checking patch compatibility.

    Long-term solution: Submit PR upstream to improve frontmatter error tolerance.
    """
    try:
        import re
        from skill_scanner.core.loader import SkillLoader

        # Save original method
        original_parse_skill_md = SkillLoader._parse_skill_md

        def _parse_frontmatter_forgiving(content: str):
            """Forgiving frontmatter parsing"""
            try:
                import frontmatter
                post = frontmatter.loads(content)
                return post.metadata, post.content, None
            except Exception as e:
                # frontmatter parsing failed, manually separate
                metadata, body = _split_frontmatter_raw(content)
                return metadata, body, str(e)

        def _split_frontmatter_raw(content: str):
            """Manually separate frontmatter and body (forgiving)"""
            if not content.startswith("---"):
                return {}, content

            # Find second ---
            parts = content.split("---", 2)
            if len(parts) < 3:
                return {}, content

            # Try lenient YAML parsing
            frontmatter_text = parts[1]
            body = parts[2].lstrip()

            # Use regex forgiving extraction (handle key:value format)
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
            """Infer metadata from filename and content"""
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

        def patched_parse_skill_md(self, skill_md_path):
            """Forgiving SKILL.md parsing"""
            try:
                with open(skill_md_path, encoding="utf-8") as f:
                    content = f.read()
            except (OSError, UnicodeDecodeError) as e:
                from skill_scanner.core.loader import SkillLoadError
                raise SkillLoadError(f"Failed to read SKILL.md: {e}")

            # Forgiving frontmatter parsing
            metadata, body, parse_error = _parse_frontmatter_forgiving(content)

            # If parsing failed, use fallback
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
    log("SUCCESS", msg, "✅")

def info(msg: str):
    log("INFO", msg, "🔄")

def warn(msg: str):
    log("WARN", msg, "⚠️")

def error(msg: str):
    log("ERROR", msg, "❌")


# =============================================================================
# Security Scan Interface
# =============================================================================

def scan(skill_path: Path, config: Optional[Dict] = None) -> Dict[str, Any]:
    """Scan skill or directory at specified path

    Uses StaticAnalyzer + BehavioralAnalyzer combination (default mode)
    - No network requests required
    - No API Key required
    - Detection coverage ~95%
    - Supports scanning regular directories without SKILL.md

    Args:
        skill_path: Skill directory path or any code directory
        config: Optional config dict (loads default config if not provided)

    Returns:
        Scan result dict
    """
    # Ensure patches applied (lazy load)
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

    # Load config
    if config is None:
        config = load_config()

    engines = config.get("engines", {})
    use_static = engines.get("static", True)
    use_behavioral = engines.get("behavioral", True)

    # Build analyzer list
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

    # Check if SKILL.md exists
    has_skill_md = (Path(skill_path) / "SKILL.md").exists()

    # Execute scan
    try:
        import time
        start_time = time.time()

        all_findings = []
        analyzers_used = []

        if has_skill_md:
            # Use SkillScanner (skill format)
            scanner = SkillScanner(analyzers=analyzers)
            result = scanner.scan_skill(Path(skill_path))
            all_findings = result.findings
            analyzers_used = result.analyzers_used
            scan_duration = result.scan_duration_seconds
        else:
            # Call analyzers directly (no SKILL.md)
            for analyzer in analyzers:
                try:
                    findings = analyzer.analyze(Path(skill_path))
                    all_findings.extend(findings)
                    analyzers_used.append(analyzer.get_name())
                except Exception as e:
                    warn(f"Analyzer {analyzer.get_name()} execution failed: {e}")
            scan_duration = time.time() - start_time

        # Extract threat info
        threats = [
            {
                "rule_id": f.rule_id,
                "severity": f.severity.value,
                "title": f.title,
                "file": str(f.file_path) if f.file_path else None,
                "line": f.line_number,
                "snippet": f.snippet
            }
            for f in all_findings
        ]

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


def batch_scan(skill_dirs: List[Path], config: Optional[Dict] = None) -> Dict[str, Dict]:
    """
    Batch scan skills (concurrent support)

    Args:
        skill_dirs: List of skill directories
        config: Optional config

    Returns:
        {skill_name: scan_result, ...}
    """
    if config is None:
        config = load_config()

    if not config.get("scan_enabled", True):
        return {d.name: {"status": "skipped"} for d in skill_dirs}

    scan_results = {}

    # Single skill: scan directly
    if len(skill_dirs) == 1:
        skill_dir = skill_dirs[0]
        info(f"🔄 Security scan: {skill_dir.name}")
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
    info(f"🔄 Batch parallel scan {len(skill_dirs)} skills (4 threads)...")

    batch_size = 8
    for i in range(0, len(skill_dirs), batch_size):
        batch = skill_dirs[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(skill_dirs) + batch_size - 1) // batch_size
        info(f"  Batch {batch_num}/{total_batches}: scanning {len(batch)} skills...")

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

        # Force garbage collection
        gc.collect()

    return scan_results


def is_safe(result: Dict[str, Any], allowed_severity: List[str]) -> bool:
    """Determine if scan result is within allowed security level"""
    severity = result.get("severity", "UNKNOWN")
    return severity in allowed_severity


def load_config() -> Dict[str, Any]:
    """Load security config"""
    if CONFIG_FILE.exists():
        import yaml
        try:
            return yaml.safe_load(CONFIG_FILE.read_text())
        except Exception:
            pass

    # Default config
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
# CLI Entry Point
# =============================================================================

def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="security_scanner.py - Agent Skills Security Scanner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan specific skill
  python bin/security_scanner.py scan my-skill

  # Scan all installed skills
  python bin/security_scanner.py scan-all

  # View current config
  python bin/security_scanner.py config

Note: Clone functionality moved to clone_manager.py
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # scan command
    scan_parser = subparsers.add_parser("scan", help="Scan specific skill")
    scan_parser.add_argument("target", help="Skill name or path")
    scan_parser.add_argument("--json", action="store_true", help="Output JSON format (for script parsing)")

    # scan-all command
    subparsers.add_parser("scan-all", help="Scan all installed skills")

    # config command
    subparsers.add_parser("config", help="View current config")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Load config
    config = load_config()

    if args.command == "config":
        print("Current security config:")
        print(json.dumps(config, ensure_ascii=False, indent=2))
        return 0

    elif args.command == "scan":
        target = args.target
        skill_path = None

        if not Path(target).is_absolute():
            skill_path = SKILLS_DIR / target
            if not skill_path.exists():
                print(f"Error: Skill not found: {target}")
                return 1
        else:
            skill_path = Path(target)

        result = scan(skill_path, config)

        # JSON output mode (for script parsing)
        if getattr(args, 'json', False):
            print(json.dumps(result, ensure_ascii=False, separators=(',', ':')))
            return 0 if result["status"] == "success" else 1

        # Default: human readable output
        print(f"Scan: {skill_path}")
        print(f"\nStatus: {result['status']}")
        print(f"Severity: {result['severity']}")
        print(f"Threats found: {result['findings_count']}")

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

    elif args.command == "scan-all":
        if not SKILLS_DIR.exists():
            print("Error: Skills directory not found")
            return 1

        skills = [d for d in SKILLS_DIR.iterdir() if d.is_dir()]

        if not skills:
            print("No installed skills")
            return 0

        print(f"Scanning {len(skills)} installed skills...\n")

        all_safe = True
        threatened_skills = []

        for skill_dir in skills:
            print(f"Scanning: {skill_dir.name}")
            result = scan(skill_dir, config)

            status_icon = "[OK]" if result["status"] == "success" else "[!]"
            print(f"  {status_icon} {result['severity']} - {result['findings_count']} threats")

            if result["status"] != "success":
                all_safe = False
                threatened_skills.append((skill_dir.name, result))
            print()

        if all_safe:
            print("All skills passed scan")
            return 0
        else:
            print(f"Found {len(threatened_skills)} threatened skills")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

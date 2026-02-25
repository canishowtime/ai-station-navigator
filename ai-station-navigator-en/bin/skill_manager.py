#!/usr/bin/env python3
"""
skill_manager.py - Skill Manager
----------------------------------------------
Skill installation, uninstallation, conversion and validation management

Responsibilities:
1. Format Detection - Detect input skill format type (GitHub/local/.skill package)
2. Normalization - Convert non-standard formats to official SKILL.md format
3. Structure Validation - Validate converted skill structure integrity
4. Auto Install - Copy to .claude/skills/ and verify availability
5. Auto Uninstall - Delete skill and sync database state

Architecture:
    Kernel (AI) → Skill Manager → Format Detector → Normalizer → Installer

Source: Inspired by Anthropic's skill-creator (Apache 2.0)
https://github.com/anthropics/skills/tree/main/skills/skill-creator

v1.0 - Feature Complete:
    - Support multiple input sources (GitHub URL, local directory, .skill package)
    - Auto-detect and fix common format issues
    - Batch conversion support
    - Complete validation flow
"""

import argparse
import concurrent.futures
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
import tempfile
import yaml

# Add project lib directory to sys.path (portable package dependencies)
_lib_dir = Path(__file__).parent.parent / "lib"
if _lib_dir.exists():
    sys.path.insert(0, str(_lib_dir))

# Add bin directory to sys.path (for hooks_manager only)
_bin_dir = Path(__file__).parent
if str(_bin_dir) not in sys.path:
    sys.path.insert(0, str(_bin_dir))

# TinyDB for database operations
try:
    from tinydb import TinyDB, Query
    from tinydb.storages import JSONStorage
    TINYDB_AVAILABLE = True
except ImportError:
    TINYDB_AVAILABLE = False

# =============================================================================
# Decoupling Note: No longer directly import clone_manager and security_scanner
# Call these independent modules via subprocess
# =============================================================================

# =============================================================================
# Configuration Constants
# =============================================================================

BASE_DIR = Path(__file__).parent.parent
CLAUDE_SKILLS_DIR = BASE_DIR / ".claude" / "skills"
TEMP_DIR = BASE_DIR / "mybox" / "temp"
SKILLS_DB_FILE = BASE_DIR / ".claude" / "skills" / "skills.db"
CACHE_DIR = BASE_DIR / "mybox" / "cache" / "repos"

# Official skill standards
REQUIRED_FIELDS = ["name", "description"]
SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
MAX_NAME_LENGTH = 128
MAX_DESC_LENGTH = 1024

# Processing threshold constants
SINGLE_SKILL_THRESHOLD = 1          # Single skill judgment threshold
FRONTMATTER_PREVIEW_LINES = 10      # Frontmatter preview lines
LIST_DESC_PREVIEW_CHARS = 500       # List command description preview characters

# Skill default value constants
DEFAULT_SKILL_DESC = "No description"       # Default skill description
DEFAULT_SKILL_CATEGORY = "utilities"  # Default category
DEFAULT_SKILL_TAGS = ["skill"]      # Default tags

# =============================================================================
# Format Registry
# =============================================================================
# When adding new format support, register format handler here
# See: docs/skill-formats-contribution-guide.md

SUPPORTED_FORMATS = {
    "official": {
        "name": "Claude Code Official",
        "markers": ["SKILL.md"],
        "handler": None,  # Official format, direct processing
    },
    "claude-plugin": {
        "name": "Claude Plugin",
        "markers": [".claude-plugin", "plugin.json", "marketplace.json"],
        "handler": None,  # Built-in processing
    },
    "agent-skills": {
        "name": "Anthropic Agent Skills",
        "markers": ["skills/", "SKILL.md"],
        "handler": None,  # Built-in processing
    },
    "cursor-rules": {
        "name": "Cursor Rules",
        "markers": [".cursor", "rules/"],
        "handler": None,  # Built-in processing
    },
    "plugin-marketplace": {
        "name": "Plugin Marketplace",
        "markers": ["plugins/", "MARKETPLACE.md"],
        "handler": None,  # Built-in processing
    },
    # Add new formats here, e.g.:
    # "cursor-plugin": {
    #     "name": "Cursor Plugin",
    #     "markers": ["package.json"],
    #     "handler": CursorPluginHandler,
    # },
}


# =============================================================================
# Temp Directory Cleanup Tool
# =============================================================================

def cleanup_old_install_dirs(max_age_hours: int = 24) -> int:
    """
    Clean up installer_* temp directories older than specified time

    Args:
        max_age_hours: Maximum retention time (hours), default 24 hours

    Returns:
        Number of directories cleaned
    """
    if not TEMP_DIR.exists():
        return 0

    cleaned_count = 0
    current_time = time.time()
    max_age_seconds = max_age_hours * 3600

    # Find all installer_* directories
    installer_dirs = list(TEMP_DIR.glob("installer_*"))

    for install_dir in installer_dirs:
        if not install_dir.is_dir():
            continue

        try:
            # Check directory age
            dir_age = current_time - install_dir.stat().st_mtime
            if dir_age > max_age_seconds:
                shutil.rmtree(install_dir, ignore_errors=True)
                cleaned_count += 1
                # info(f"Cleaned old temp directory: {install_dir.name}")  # P0 fix: info() not defined yet (L238)
        except Exception:
            pass  # P0 fix: log function not defined, skip silently

    return cleaned_count


# =============================================================================
# Log Utilities (Plain Text)
# =============================================================================

def log(level: str, message: str, emoji: str = ""):
    """Unified log output"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {emoji} [{level}] {message}")


def success(msg: str):
    log("OK", msg, "[OK]")


def info(msg: str):
    log("INFO", msg, "[i]")


def warn(msg: str):
    log("WARN", msg, "[!]")


def error(msg: str):
    log("ERROR", msg, "[X]")


def header(msg: str):
    print(f"\n{'='*60}")
    print(f"{msg.center(60)}")
    print(f"{'='*60}\n")


# =============================================================================
# Format Detector (Independent implementation, decoupled from clone_manager)
# =============================================================================

class FormatDetector:
    """Detect skill input source format type"""

    @staticmethod
    def validate_github_url(url: str) -> Tuple[bool, Optional[str]]:
        """
        Validate GitHub URL format security, prevent config injection attacks

        Args:
            url: GitHub URL to validate

        Returns:
            (is_valid, error_message)
        """
        import re
        # Basic format check
        github_pattern = r'^https?://github\.com/[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+(?:/tree/[^/\s]+(?:/[\w\-./]+)?)?$'
        if not re.match(github_pattern, url):
            return False, f"Invalid GitHub URL format: {url}"

        # Check for dangerous git config injection patterns
        dangerous_patterns = [
            '--config=', '-c=', '--upload-pack=', '--receive-pack=',
            '--exec=', '&&', '||', '|', '`', '$(', '\n', '\r', '\x00',
        ]

        url_lower = url.lower()
        for pattern in dangerous_patterns:
            if pattern in url_lower:
                return False, f"URL contains dangerous character or pattern: {pattern}"

        # Check for URL encoding bypass attempts
        if '%2' in url.lower():
            return False, "URL contains suspicious encoded characters"

        return True, None

    @staticmethod
    def detect_input_type(input_source: str) -> Tuple[str, str, Optional[str]]:
        """
        Detect input source type

        Returns:
            (type, path/URL, subpath)
        """
        from urllib.parse import urlparse

        info(f"Detecting input source: {input_source}")

        # 1. Check if it's a GitHub URL
        if input_source.startswith(("http://", "https://")):
            parsed = urlparse(input_source)
            if "github.com" in parsed.netloc:
                return "github", input_source, None

        # 1.5 Check if it's GitHub shorthand (user/repo)
        if "/" in input_source and not input_source.startswith((".", "/", "\\")):
            parts = input_source.split("/")
            if len(parts) == 2 and not any(c in input_source for c in ":\\"):
                return "github", f"https://github.com/{input_source}", None

        # 2. Check if it's a local path
        local_path = Path(input_source).expanduser().resolve()
        if local_path.exists():
            if local_path.is_file() and local_path.suffix == ".skill":
                return "skill-package", str(local_path), None
            elif local_path.is_dir():
                return "local", str(local_path), None

        # 3. Check if it's a relative path
        relative_path = BASE_DIR / input_source
        if relative_path.exists():
            if relative_path.is_file() and relative_path.suffix == ".skill":
                return "skill-package", str(relative_path), None
            elif relative_path.is_dir():
                return "local", str(relative_path), None

        warn("Unable to recognize input source type, trying as local directory")
        return "unknown", input_source, None

    @staticmethod
    def detect_skill_format(skill_dir: Path) -> Tuple[str, List[str]]:
        """
        Detect skill directory format type

        Returns:
            (format_type, detected_marker_files)
            Format: 'official', 'claude-plugin', 'agent-skills', 'cursor-rules', 'unknown'
        """
        detected_markers = []

        # Check official format
        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            try:
                with open(skill_md, "r", encoding="utf-8", errors="ignore") as f:
                    first_lines = "".join([f.readline() for _ in range(FRONTMATTER_PREVIEW_LINES)])
                    if "---" in first_lines and "name:" in first_lines:
                        return "official", ["SKILL.md"]
            except (OSError, IOError) as e:
                # P1 fix: Skip silently on file read failure, continue detecting other formats
                pass

        # Check third-party format markers
        for format_type, format_data in SUPPORTED_FORMATS.items():
            if format_type == "official":
                continue
            markers = format_data["markers"]
            found = []
            for marker in markers:
                marker_path = skill_dir / marker
                if marker_path.exists():
                    found.append(marker)
            if found:
                return format_type, found

        # Check if there are markdown files (may be old format)
        md_files = list(skill_dir.glob("*.md"))
        if md_files:
            return "unknown-md", [f.name for f in md_files]

        return "unknown", []


# =============================================================================
# Project Validator - Detect if it's a skill repository
# =============================================================================

class ProjectValidator:
    """Validate if project is a skill repository, not a tool/application"""

    # Positive indicators for skill repositories (root level) - check first
    SKILL_REPO_INDICATORS = [
        ("SKILL.md", "SKILL.md file in root directory"),
        ("_has_skills_dir", "skills/ directory contains multiple skills"),  # Special marker
        (".claude/skills", "Anthropic official skill repository structure"),
        # .skill package files (may have multiple, check with glob)
    ]

    # Skill package repository indicators (contains .skill files)
    SKILL_PACKAGE_EXTENSIONS = [".skill"]

    # Tool project indicator files (root level) - simplified to most common
    TOOL_PROJECT_FILES = [
        "setup.py",        # Python package config
        "Cargo.toml",      # Rust project
        "go.mod",          # Go project
    ]

    # Files needing further inspection (may be skill or tool)
    AMBIGUOUS_PROJECT_FILES = [
        "pyproject.toml",  # May be skill packaging or tool
        "package.json",    # May be skill or Node.js project
    ]

    # Tool component directory names (not skills) - simplified to most common
    TOOL_COMPONENT_NAMES = {
        "api", "src", "lib", "core", "utils",
        "scripts", "tools", "bin", "build", "target",
        "tests", "docs", "config",
        ".git", ".github",
    }

    # Non-skill project keywords (detect in README) - simplified to most common
    NON_SKILL_KEYWORDS = [
        "skill generator",
        "generates skills",
        "creates skills",
        "install via pip",
        "command-line interface",
        "cli tool",
    ]

    # Positive skill project indicator words (README)
    SKILL_INDICATORS = [
        "claude skill",
        "claude.ai skill",
        "claude code skill",
        "this skill helps",
        "use this skill to",
        "when to use this skill",
    ]

    @staticmethod
    def is_skill_repo_root(repo_dir: Path) -> Tuple[bool, str]:
        """
        Determine if root directory is a skill repository

        Returns:
            (is_skill, reason)
        """
        # 1. 检查技能仓库正面指示（优先级最高）
        for indicator, reason in ProjectValidator.SKILL_REPO_INDICATORS:
            if indicator == "_has_skills_dir":
                # 特殊处理：检查 skills/ 目录是否包含技能
                skills_dir = repo_dir / "skills"
                if skills_dir.exists() and skills_dir.is_dir():
                    # 检查是否有 3+ 个 SKILL.md
                    skill_count = len(list(skills_dir.glob("*/SKILL.md")))
                    if skill_count >= 3:
                        return True, f"skills/ 目录包含 {skill_count} 个技能"
            elif (repo_dir / indicator).exists():
                return True, f"{reason}"

        # 2. 检查是否有 .skill 包文件（技能包仓库）
        for ext in ProjectValidator.SKILL_PACKAGE_EXTENSIONS:
            skill_files = list(repo_dir.glob(f"*{ext}"))
            if skill_files:
                return True, f"包含技能包文件: {skill_files[0].name}"

        # 2.5 新增：检查子目录是否包含多个技能（monorepo 支持）
        # 在判定为工具项目之前，先检查子目录
        sub_skill_dirs = []
        exclude_dirs = {
            "tests", "test", "testing", "spec", "specs",
            "docs", "doc", "documentation", "examples", "example",
            "scripts", "tools", "bin", "build", "dist", "target",
            ".git", ".github", ".vscode", ".idea",
        }
        # 特殊优先级：skills/ 目录不排除
        for item in repo_dir.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                # skills/ 目录特殊处理：检查子目录中的技能
                if item.name == "skills":
                    skill_count = 0
                    for sub_item in item.iterdir():
                        if sub_item.is_dir() and (sub_item / "SKILL.md").exists():
                            sub_skill_dirs.append(sub_item)
                            skill_count += 1
                    if skill_count >= 2:
                        return True, f"skills/ 目录包含 {skill_count} 个技能（monorepo）"
                elif item.name not in exclude_dirs:
                    # 检查是否是技能目录（有 SKILL.md 或符合技能命名规范）
                    if (item / "SKILL.md").exists():
                        sub_skill_dirs.append(item)
                    elif re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", item.name):
                        # 检查是否有 markdown 文件（可能是技能内容）
                        md_files = list(item.glob("*.md"))
                        if md_files:
                            sub_skill_dirs.append(item)

        # 如果有 2+ 个子技能目录，判定为技能仓库
        if len(sub_skill_dirs) >= 2:
            return True, f"子目录包含 {len(sub_skill_dirs)} 个技能（monorepo）"

        # 3. 检查明确的工具项目文件
        for tool_file in ProjectValidator.TOOL_PROJECT_FILES:
            if (repo_dir / tool_file).exists():
                return False, f"检测到工具项目文件: {tool_file}"

        # 4. 检查模糊的项目文件（需要进一步判断）
        for ambiguous_file in ProjectValidator.AMBIGUOUS_PROJECT_FILES:
            file_path = repo_dir / ambiguous_file
            if file_path.exists():
                # 对于这些文件，需要检查内容和 README
                if ambiguous_file == "pyproject.toml":
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    # 检查是否明确是工具项目
                    if "tool.scripts" in content or "command-line" in content.lower():
                        return False, f"检测到工具项目配置: {ambiguous_file}"
                    # 如果有 [project] 且是工具（不是技能打包），检查子目录
                    if "[project]" in content:
                        # 检查子目录是否都是工具组件
                        subdirs = [d.name for d in repo_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
                        tool_components = ProjectValidator.TOOL_COMPONENT_NAMES & set(subdirs)
                        # 如果子目录大多是工具组件，判定为工具项目
                        if len(tool_components) >= 2 and len(tool_components) >= len(subdirs) * 0.5:
                            return False, f"检测到工具项目结构（包含工具组件目录）"
                    # 如果只是构建配置，继续检查 README
                elif ambiguous_file == "package.json":
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    # 如果有很多 scripts，可能是 Node.js 工具
                    if '"scripts"' in content and content.count('"') > 20:
                        return False, f"检测到 Node.js 工具项目: {ambiguous_file}"

        # 5. 检查 README 内容（关键判断）
        readme = ProjectValidator._read_readme(repo_dir)
        if readme:
            content_lower = readme.lower()

            # 优先检查技能正面指示词
            for indicator in ProjectValidator.SKILL_INDICATORS:
                if indicator in content_lower:
                    return True, f"README 包含技能指示词: {indicator}"

            # 检查工具关键词
            for keyword in ProjectValidator.NON_SKILL_KEYWORDS:
                if keyword in content_lower:
                    return False, f"README 包含工具项目关键词: {keyword}"

        # 6. 检查目录结构
        subdirs = [d.name for d in repo_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
        # 如果有典型的工具项目目录结构
        tool_dirs = ProjectValidator.TOOL_COMPONENT_NAMES & set(subdirs)
        if len(tool_dirs) >= 2:
            return False, f"检测到工具项目目录结构: {', '.join(list(tool_dirs)[:3])}"

        # 默认：不确定，假定可能是技能仓库
        return True, ""

    @staticmethod
    def is_skill_directory(subdir: Path) -> Tuple[bool, str]:
        """
        Determine if subdirectory is a skill directory

        Returns:
            (is_skill, reason)
        """
        dirname = subdir.name.lower()

        # 1. Check if it's a tool component directory
        if dirname in ProjectValidator.TOOL_COMPONENT_NAMES:
            return False, f"Directory name is tool component: {dirname}"

        # 2. Check if SKILL.md exists (most definitive skill marker)
        if (subdir / "SKILL.md").exists():
            return True, "Contains SKILL.md file"

        # 3. Check if it's a Python package directory (has __init__.py but no SKILL.md)
        if (subdir / "__init__.py").exists():
            return False, "Python package directory (no SKILL.md)"

        # 4. Check directory name format: skill names are usually kebab-case
        if not re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", dirname):
            return False, f"Directory name doesn't match skill naming convention: {dirname}"

        # 5. Check if there are .md files (may be skill content)
        md_files = list(subdir.glob("*.md"))
        if not md_files:
            return False, "No markdown files found"

        # Default: may be a skill
        return True, ""

    @staticmethod
    def _read_readme(directory: Path) -> str:
        """Read README file content"""
        for readme_name in ["README.md", "README.txt", "README.rst", "readme.md"]:
            readme_path = directory / readme_name
            if readme_path.exists():
                return readme_path.read_text(encoding="utf-8", errors="ignore")
        return ""

    @staticmethod
    def validate_root_repo(repo_dir: Path, repo_name: str, force: bool = False) -> bool:
        """
        Validate if root repository is a skill repository

        Returns:
            bool - True means continue, False means abort
        """
        is_skill, reason = ProjectValidator.is_skill_repo_root(repo_dir)

        if not is_skill:
            print("=" * 60)
            print("X Installation rejected: Not a skill project")
            print("=" * 60)
            print()
            print(f"Detection reason: {reason}")
            print(f"Repository: {repo_name}")
            print()
            print("System does not support installing tool projects.")
            print("Please confirm:")
            print(f"  1. Is it a tool/library? Please use pip/npm/cargo etc. to install")
            print(f"  2. Really need as skill? Please manually convert then install")

            return False

        return True

    @staticmethod
    def validate_subdirectory(subdir: Path, force: bool = False) -> Tuple[bool, str]:
        """
        Validate if subdirectory is a skill directory

        Returns:
            (should_install, skip_reason)
        """
        is_skill, reason = ProjectValidator.is_skill_directory(subdir)

        if not is_skill and not force:
            return False, reason

        return True, ""


# =============================================================================
# Skill Normalizer
# =============================================================================

class SkillNormalizer:
    """Normalize various formats to official SKILL.md format"""

    @staticmethod
    def validate_skill_name(name: str) -> Tuple[bool, str]:
        """Validate if skill name conforms to specification"""
        if not name:
            return False, "Skill name cannot be empty"

        if len(name) > MAX_NAME_LENGTH:
            return False, f"Skill name too long (max {MAX_NAME_LENGTH} characters)"

        if not SKILL_NAME_PATTERN.match(name):
            return False, "Skill name must be lowercase letters, numbers and hyphens, cannot start or end with hyphen"

        return True, ""


    @staticmethod
    def validate_description(desc: str) -> Tuple[bool, str]:
        """Validate if description conforms to specification"""
        if not desc:
            return False, "Description cannot be empty"

        if len(desc) > MAX_DESC_LENGTH:
            return False, f"Description too long (max {MAX_DESC_LENGTH} characters)"

        # Check for potential HTML tags (more precise pattern)
        # Allow standalone < and > characters (e.g., >5, C++, <3), but reject <tag> format
        if re.search(r'<[^>]+>', desc):
            return False, "Description cannot contain HTML tags"

        return True, ""


    @staticmethod
    def normalize_skill_name(original_name: str) -> str:
        """Normalize any name to hyphen-case format"""
        # Remove special characters, convert to lowercase, join with hyphens
        normalized = re.sub(r"[^a-zA-Z0-9]+", "-", original_name).strip("-").lower()
        # Remove leading digits
        if normalized and normalized[0].isdigit():
            normalized = "skill-" + normalized
        return normalized or "unnamed-skill"


    @staticmethod
    def extract_frontmatter(content: str) -> Dict[str, Any]:
        """
        Extract YAML frontmatter from SKILL.md

        Supports YAML parsing, falls back to manual parsing on failure
        """
        if not content.startswith("---"):
            return {}

        # 找到第二个 --- (兼容 \n--- 和 --- 两种格式)
        end_marker = content.find("\n---", 4)
        if end_marker == -1:
            end_marker = content.find("---", 3)
        if end_marker <= 0:
            return {}

        # 提取 frontmatter 内容
        yaml_content = content[4:end_marker].strip()

        # 优先使用 yaml.safe_load
        try:
            frontmatter = yaml.safe_load(yaml_content)
            if isinstance(frontmatter, dict):
                return frontmatter
        except (yaml.YAMLError, Exception):
            pass

        # 降级：手动解析（处理简单 key: value 格式）
        result = {}
        for line in yaml_content.split('\n'):
            if ':' in line and not line.strip().startswith('#'):
                key, value = line.split(':', 1)
                result[key.strip()] = value.strip().strip('"').strip("'")
        return result


    @staticmethod
    def fix_frontmatter(skill_dir: Path) -> Tuple[bool, str]:
        """
        Fix SKILL.md frontmatter

        Returns:
            (needs_fix, fixed_content_or_error_message)
        """
        skill_md = skill_dir / "SKILL.md"

        if not skill_md.exists():
            return False, "SKILL.md does not exist"

        with open(skill_md, "r", encoding="utf-8") as f:
            content = f.read()

        frontmatter = SkillNormalizer.extract_frontmatter(content)

        # Check required fields
        needs_fix = False
        if "name" not in frontmatter:
            # Use folder name as name
            folder_name = skill_dir.name
            normalized_name = SkillNormalizer.normalize_skill_name(folder_name)
            frontmatter["name"] = normalized_name
            needs_fix = True

        if "description" not in frontmatter:
            # Try to extract description from content
            desc = SkillNormalizer._extract_description_from_content(content)
            frontmatter["description"] = desc
            needs_fix = True

        if not needs_fix:
            # Validate existing fields
            valid, msg = SkillNormalizer.validate_skill_name(frontmatter.get("name", ""))
            if not valid:
                warn(f"Invalid skill name: {msg}, auto-fixing")
                frontmatter["name"] = SkillNormalizer.normalize_skill_name(skill_dir.name)
                needs_fix = True

            valid, msg = SkillNormalizer.validate_description(frontmatter.get("description", ""))
            if not valid:
                warn(f"Invalid description: {msg}, auto-fixing")
                frontmatter["description"] = "Skill description (please manually improve)"
                needs_fix = True

        if needs_fix:
            # 重建 frontmatter
            new_frontmatter = "---\n"
            new_frontmatter += f'name: {frontmatter["name"]}\n'
            new_frontmatter += f'description: "{frontmatter["description"]}"\n'
            new_frontmatter += "---\n\n"

            # 保留原有内容（移除旧 frontmatter）
            content_start = content.find("\n---", 4)
            if content_start != -1:
                old_content = content[content_start + 5:].lstrip("\n")
            else:
                old_content = content

            return True, new_frontmatter + old_content

        return False, content


    @staticmethod
    def _extract_description_from_content(content: str) -> str:
        """Extract description from content"""
        lines = content.split("\n")

        # Skip frontmatter
        start_idx = 0
        for i, line in enumerate(lines):
            if line.strip() == "---" and i > 0:
                start_idx = i + 1
                break

        # Find first heading or paragraph
        for i in range(start_idx, min(start_idx + 10, len(lines))):
            line = lines[i].strip()
            if line and not line.startswith("#"):
                # Return first non-empty line as description (limit length)
                return line[:200] + "..." if len(line) > 200 else line

        return "Auto-generated skill description, please manually improve"


    @staticmethod
    def convert_to_official_format(source_dir: Path, target_dir: Path) -> Tuple[bool, str]:
        """
        Convert third-party format to official format

        Returns:
            (success, message)
        """
        info(f"Converting skill: {source_dir.name}")

        # 1. Detect format
        format_type, markers = FormatDetector.detect_skill_format(source_dir)
        info(f"Detected format: {format_type}")

        # 2. 创建目标目录
        target_dir.mkdir(parents=True, exist_ok=True)

        # 3. 根据格式处理
        if format_type == "official":
            # 已经是官方格式，直接复制
            SkillNormalizer._copy_directory(source_dir, target_dir)
        elif format_type == "claude-plugin":
            # Claude Plugin 格式
            SkillNormalizer._convert_claude_plugin(source_dir, target_dir)
        elif format_type == "agent-skills":
            # Agent Skills 格式
            SkillNormalizer._convert_agent_skills(source_dir, target_dir)
        elif format_type == "cursor-rules":
            # Cursor Rules format
            SkillNormalizer._convert_cursor_rules(source_dir, target_dir)
        else:
            # Unknown format, try generic conversion
            SkillNormalizer._convert_generic(source_dir, target_dir)

        # 4. Fix frontmatter
        needs_fix, new_content = SkillNormalizer.fix_frontmatter(target_dir)
        if needs_fix:
            info("Fixing SKILL.md frontmatter")
            with open(target_dir / "SKILL.md", "w", encoding="utf-8") as f:
                f.write(new_content)

        return True, f"Conversion complete: {target_dir.name}"


    @staticmethod
    def _copy_directory(source: Path, target: Path) -> None:
        """复制目录内容"""
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target, dirs_exist_ok=True)


    @staticmethod
    def _convert_claude_plugin(source: Path, target: Path) -> None:
        """转换 Claude Plugin 格式"""
        # 查找 SKILL.md 或 README.md
        skill_md = source / "SKILL.md"
        if skill_md.exists():
            shutil.copy2(skill_md, target / "SKILL.md")
        else:
            # 从 plugin.json 或 marketplace.json 生成 SKILL.md
            plugin_json = source / ".claude-plugin" / "plugin.json"
            if plugin_json.exists():
                SkillNormalizer._generate_from_plugin_json(plugin_json, target)
            else:
                SkillNormalizer._create_default_skill_md(source, target)

        # 复制其他资源
        for item in source.iterdir():
            if item.name.startswith("."):
                continue
            if item.name == "SKILL.md" or item.is_file():
                continue
            dest = target / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)


    @staticmethod
    def _convert_agent_skills(source: Path, target: Path) -> None:
        """转换 Agent Skills 格式"""
        # Agent Skills 通常已经有 SKILL.md
        skill_md = source / "SKILL.md"
        if skill_md.exists():
            shutil.copy2(skill_md, target / "SKILL.md")

        # 复制 scripts/, references/, examples/ 等目录
        for subdir in ["scripts", "references", "examples", "templates"]:
            src_subdir = source / subdir
            if src_subdir.exists():
                shutil.copytree(src_subdir, target / subdir, dirs_exist_ok=True)


    @staticmethod
    def _convert_cursor_rules(source: Path, target: Path) -> None:
        """转换 Cursor Rules 格式"""
        # Cursor 的 rules/ 目录通常包含 .md 文件
        rules_dir = source / ".cursor" / "rules"
        if not rules_dir.exists():
            rules_dir = source / "rules"

        if rules_dir.exists():
            # 合并所有 .md 文件
            content_parts = []
            for md_file in sorted(rules_dir.glob("*.md")):
                with open(md_file, "r", encoding="utf-8") as f:
                    content_parts.append(f.read())

            if content_parts:
                SkillNormalizer._create_skill_md_from_content(
                    target, source.name, "\n\n".join(content_parts)
                )
        else:
            SkillNormalizer._convert_generic(source, target)


    @staticmethod
    def _convert_generic(source: Path, target: Path) -> None:
        """Generic conversion (unknown format)"""
        # Find SKILL.md or README.md
        skill_md = source / "SKILL.md"
        readme_md = source / "README.md"

        if skill_md.exists():
            shutil.copy2(skill_md, target / "SKILL.md")
        elif readme_md.exists():
            # 从 README.md 生成 SKILL.md
            with open(readme_md, "r", encoding="utf-8") as f:
                content = f.read()
            SkillNormalizer._create_skill_md_from_content(target, source.name, content)
        else:
            SkillNormalizer._create_default_skill_md(source, target)


    @staticmethod
    def _create_skill_md_from_content(target: Path, name: str, content: str) -> None:
        """Create SKILL.md from content"""
        normalized_name = SkillNormalizer.normalize_skill_name(name)

        # Extract description (first paragraph)
        desc = SkillNormalizer._extract_description_from_content(content)

        frontmatter = f"""---
name: {normalized_name}
description: "{desc}"
---

"""

        with open(target / "SKILL.md", "w", encoding="utf-8") as f:
            f.write(frontmatter + content)


    @staticmethod
    def _create_default_skill_md(source: Path, target: Path) -> None:
        """Create default SKILL.md"""
        name = SkillNormalizer.normalize_skill_name(source.name)

        content = f"""---
name: {name}
description: "Auto-converted skill from {source.name}, please manually improve description"
---

# {name.replace('-', ' ').title()}

## Overview

This skill was auto-converted from a third-party source, please improve this document based on actual functionality.

## Conversion Info

- **Source Name**: {source.name}
- **Conversion Time**: {datetime.now().isoformat()}
- **Status**: Needs manual improvement

## Usage

Please add usage instructions...

## Resources

List related resources...
"""

        with open(target / "SKILL.md", "w", encoding="utf-8") as f:
            f.write(content)

        # 复制其他文件
        for item in source.iterdir():
            if item.name != "SKILL.md" and not item.name.startswith("."):
                dest = target / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest)


    @staticmethod
    def _generate_from_plugin_json(plugin_json: Path, target: Path) -> None:
        """Generate SKILL.md from plugin.json"""
        try:
            with open(plugin_json, "r", encoding="utf-8") as f:
                plugin_data = json.load(f)

            name = SkillNormalizer.normalize_skill_name(
                plugin_data.get("name", target.parent.name)
            )
            description = plugin_data.get("description", "Auto-generated skill description")

            content = f"""---
name: {name}
description: "{description}"
---

# {name.replace('-', ' ').title()}

## Overview

{plugin_data.get("description", "")}

## Installation

This skill has been auto-converted and installed.

## Configuration

{plugin_data.get("configuration", "No special configuration")}

## Usage

Please add usage instructions...
"""

            with open(target / "SKILL.md", "w", encoding="utf-8") as f:
                f.write(content)

        except Exception as e:
            warn(f"Failed to parse plugin.json: {e}")
            SkillNormalizer._create_default_skill_md(plugin_json.parent.parent, target)


# =============================================================================
# Skill Installer
# =============================================================================


if TINYDB_AVAILABLE:
    class UTF8JSONStorage(JSONStorage):
        """Custom JSONStorage, force UTF-8 encoding (fix Windows GBK issue)"""

        def __init__(self, path, **kwargs):
            # Force UTF-8 encoding
            kwargs['encoding'] = 'utf-8'
            super().__init__(path, **kwargs)
else:
    UTF8JSONStorage = None


# =============================================================================
# Database Connection Manager
# =============================================================================

from contextlib import contextmanager

@contextmanager
def db_connection():
    """
    Database connection context manager

    Usage:
        with db_connection() as (db, Skill):
            # Use db and Skill
            result = db.search(Skill.name == "test")
    """
    if not TINYDB_AVAILABLE:
        yield None, None
        return

    db = None
    try:
        SKILLS_DB_FILE.parent.mkdir(parents=True, exist_ok=True)
        db = TinyDB(SKILLS_DB_FILE, storage=UTF8JSONStorage)
        yield db, Query()
    except Exception as e:
        warn(f"Database connection failed: {e}")
        yield None, None


# =============================================================================
# Skill Installer
# =============================================================================


class SkillInstaller:
    """Install converted skills to .claude/skills/"""

    @staticmethod
    def _extract_github_info(github_url: str) -> Tuple[Optional[str], Optional[str]]:
        """从 GitHub URL 提取 author 和 repo

        支持格式:
        - https://github.com/author/repo
        - author/repo (简写格式)

        Returns:
            (author, repo)
        """
        if "github.com" in github_url:
            # 完整 URL 格式
            parts = github_url.rstrip('/').split('/')
            for i, part in enumerate(parts):
                if part == "github.com" and i + 2 < len(parts):
                    return parts[i + 1], parts[i + 2]
        else:
            # 简写格式: author/repo
            if '/' in github_url:
                parts = github_url.rstrip('/').split('/')
                if len(parts) == 2:
                    return parts[0], parts[1]
        return None, None

    @staticmethod
    def _get_skill_name_from_md(skill_dir: Path) -> Optional[str]:
        """从 SKILL.md 读取 name 字段"""
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return None

        try:
            with open(skill_md, "r", encoding="utf-8") as f:
                content = f.read()
            frontmatter = SkillNormalizer.extract_frontmatter(content)
            return frontmatter.get("name")
        except Exception:
            return None

    @staticmethod
    def _extract_from_local_skill(skill_name: str) -> Optional[Dict]:
        """从本地 SKILL.md 提取完整元数据"""
        skill_path = CLAUDE_SKILLS_DIR / skill_name
        skill_md = skill_path / "SKILL.md"

        if not skill_md.exists():
            return None

        try:
            content = skill_md.read_text(encoding='utf-8')
            frontmatter = SkillNormalizer.extract_frontmatter(content)

            # 提取描述（如果 frontmatter 没有）
            description = frontmatter.get("description", "")
            if not description:
                description = SkillNormalizer._extract_description_from_content(content)

            return {
                "id": skill_name.lower().replace('_', '-'),
                "name": frontmatter.get("name", skill_name),
                "folder_name": skill_name,
                "description": description or f"{skill_name} 技能",
                "category": frontmatter.get("category", DEFAULT_SKILL_CATEGORY),
                "tags": frontmatter.get("tags", DEFAULT_SKILL_TAGS.copy()),
                "keywords_cn": [],
                "parent": "",
                "parent_repo": "",
                "repo": "",
                "stars": "",
                "install": f".claude/skills/{skill_name}",
                "source_file": "auto_created",
                "search_index": f"{skill_name} {frontmatter.get('category', '')} {' '.join(frontmatter.get('tags', DEFAULT_SKILL_TAGS.copy()))}".lower(),
                "last_updated": datetime.now().strftime("%Y-%m-%d"),
                "synced_at": datetime.now().strftime("%Y-%m-%d"),
            }
        except Exception as e:
            warn(f"提取技能元数据失败: {e}")
            return None

    @staticmethod
    def _sync_skill_to_db(skill_name: str, db=None, Skill=None) -> bool:
        """将技能同步到数据库（支持连接复用）

        Args:
            skill_name: 技能名称
            db: 可选的外部数据库连接（用于批量复用）
            Skill: 可选的外部 Query 对象（用于批量复用）
        """
        # 如果未提供外部连接，创建新的连接
        if db is None or Skill is None:
            with db_connection() as (conn_db, conn_Skill):
                if conn_db is None:
                    return False
                return SkillInstaller._sync_skill_to_db(skill_name, conn_db, conn_Skill)

        # 使用提供的连接进行数据库操作
        try:
            # 从本地 SKILL.md 提取元数据
            metadata = SkillInstaller._extract_from_local_skill(skill_name)
            if not metadata:
                warn(f"无法提取技能元数据: {skill_name}")
                return False

            # 检查是否已存在（按 folder_name 匹配）
            existing = db.get(Skill.folder_name == skill_name)
            if existing:
                # 更新现有记录
                metadata["installed"] = True
                metadata["installed_path"] = f".claude/skills/{skill_name}"
                # 保留原有的 keywords_cn
                if existing.get("keywords_cn"):
                    metadata["keywords_cn"] = existing["keywords_cn"]
                db.update(metadata, doc_ids=[existing.doc_id])
            else:
                # 新增记录
                metadata["installed"] = True
                metadata["installed_path"] = f".claude/skills/{skill_name}"
                db.insert(metadata)

            return True
        except Exception as e:
            warn(f"数据库同步失败: {e}")
            return False

    @staticmethod
    def _remove_skill_from_db(skill_name: str) -> bool:
        """从数据库移除技能记录"""
        with db_connection() as (db, Skill):
            if db is None:
                return False

            try:
                # 按 folder_name 删除
                removed = db.remove(Skill.folder_name == skill_name)
                return len(removed) > 0
            except Exception as e:
                warn(f"数据库删除失败: {e}")
                return False

    @staticmethod
    def _validate_skill_structure(skill_dir: Path) -> Tuple[bool, str]:
        """验证技能目录结构"""
        # 检查 SKILL.md 是否存在
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return False, "SKILL.md 不存在"

        # 检查 frontmatter
        with open(skill_md, "r", encoding="utf-8") as f:
            content = f.read()

        frontmatter = SkillNormalizer.extract_frontmatter(content)

        # 检查必需字段
        for field in REQUIRED_FIELDS:
            if field not in frontmatter:
                return False, f"缺少必需字段: {field}"

        # Validate field values
        valid, msg = SkillNormalizer.validate_skill_name(frontmatter["name"])
        if not valid:
            return False, f"name validation failed: {msg}"

        valid, msg = SkillNormalizer.validate_description(frontmatter["description"])
        if not valid:
            return False, f"description validation failed: {msg}"

        # 检查 name 是否与文件夹名一致
        if frontmatter["name"] != skill_dir.name:
            warn(f"技能名称与文件夹名不一致: {frontmatter['name']} != {skill_dir.name}")

        return True, ""


def batch_install(skill_dirs: List[Path], force: bool = False, author: Optional[str] = None, repo: Optional[str] = None, non_interactive: bool = False, scan_results: Optional[Dict] = None) -> Dict[str, Any]:
    """批量安装技能（重构版：仅负责安装，不进行扫描）

    Args:
        skill_dirs: 技能目录列表
        force: 是否强制覆盖
        author: GitHub 作者名
        repo: GitHub 仓库名
        scan_results: 可选的扫描结果（由 security_scanner 提供）

    Returns:
        {"success": [...], "failed": [...], "skipped": [...]}
    """
    results = {
        "success": [],
        "failed": [],
        "skipped": [],
    }

    # 批量复制所有技能文件
    copied_skills = []
    for skill_dir in skill_dirs:
        # 读取技能名称
        skill_name_from_md = SkillInstaller._get_skill_name_from_md(skill_dir)

        if skill_name_from_md and author:
            repo_part = f"-{repo}" if repo else ""
            skill_name = f"{author}{repo_part}-{skill_name_from_md}".lower()
        elif skill_name_from_md:
            skill_name = skill_name_from_md
        else:
            skill_name = skill_dir.name

        # Validate skill structure
        is_valid, msg = SkillInstaller._validate_skill_structure(skill_dir)
        if not is_valid:
            results["failed"].append({"name": skill_name, "message": f"Validation failed: {msg}"})
            continue

        # Validate skill name security
        is_valid, msg = validate_skill_name(skill_name)
        if not is_valid:
            results["failed"].append({"name": skill_name, "message": f"Name validation failed: {msg}"})
            continue

        # Check if already exists
        target_dir = CLAUDE_SKILLS_DIR / skill_name
        if target_dir.exists():
            if not force:
                results["skipped"].append({"name": skill_name, "message": f"技能已存在"})
                continue
            shutil.rmtree(target_dir)

        # 复制文件
        try:
            shutil.copytree(skill_dir, target_dir)
            copied_skills.append((skill_name, target_dir))
        except Exception as e:
            results["failed"].append({"name": skill_name, "message": f"复制失败: {e}"})

    if not copied_skills:
        return results

    # 如果提供了扫描结果，处理威胁
    threatened_skills = []
    safe_skills = []

    if scan_results:
        for skill_name, target_dir in copied_skills:
            scan_result = scan_results.get(skill_name, {"status": "skipped"})

            if scan_result.get("status") == "skipped":
                safe_skills.append((skill_name, target_dir))
            elif scan_result.get("severity") in ["SAFE", "LOW"]:
                safe_skills.append((skill_name, target_dir))
            else:
                threatened_skills.append((skill_name, target_dir, scan_result))
                safe_skills.append((skill_name, target_dir))

        # 构建威胁详情
        threat_details = []
        for skill_name, target_dir, scan_result in threatened_skills:
            severity = scan_result.get("severity", "UNKNOWN")
            threats = scan_result.get("threats", [])
            threat_info = {
                "name": skill_name,
                "severity": severity,
                "threats_count": len(threats),
                "threats": [
                    {
                        "severity": t.get("severity"),
                        "title": t.get("title"),
                        "description": t.get("description"),
                        "location": t.get("location")
                    }
                    for t in threats[:5]
                ],
                "target_dir": str(target_dir)
            }
            threat_details.append(threat_info)

        if threatened_skills:
            results["threatened_skills"] = threat_details
    else:
        safe_skills = copied_skills

    # 批量写入数据库
    with db_connection() as (db, Skill):
        for skill_name, target_dir in safe_skills:
            db_sync_success = SkillInstaller._sync_skill_to_db(skill_name, db, Skill)
            if db_sync_success:
                success(f"✅ Installation successful: {skill_name} (database synced)")
                results["success"].append({"name": skill_name, "message": "Installation successful"})
            else:
                # Database sync failed, rollback
                shutil.rmtree(target_dir)
                results["failed"].append({"name": skill_name, "message": "数据库同步失败，已回滚"})

    # 失效搜索索引缓存
    if results["success"]:
        SkillSearcher.invalidate_cache()

    return results


# =============================================================================
# 配置加载（独立实现）
# =============================================================================

_config_cache: Optional[dict] = None
_config_mtime: Optional[float] = None

def load_config(use_cache: bool = True) -> dict:
    """加载配置文件"""
    global _config_cache, _config_mtime
    config_file = BASE_DIR / "config.json"
    if not config_file.exists():
        return {}
    current_mtime = config_file.stat().st_mtime
    if use_cache and _config_cache is not None and _config_mtime == current_mtime:
        return _config_cache
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            _config_cache = json.load(f) or {}
            _config_mtime = current_mtime
        return _config_cache
    except Exception:
        return {}

def clear_config_cache() -> None:
    """清除配置缓存"""
    global _config_cache, _config_mtime
    _config_cache = None
    _config_mtime = None


def validate_skill_name(name: str) -> Tuple[bool, str]:
    """验证技能名称安全性，防止路径遍历攻击"""
    if not name:
        return False, "技能名称不能为空"
    # 检测路径遍历字符
    dangerous = ['..', '\\', '/', '\x00']
    if any(d in name for d in dangerous):
        return False, f"技能名称包含非法字符: {name}"
    # 检查长度
    if len(name) > MAX_NAME_LENGTH:
        return False, f"技能名称过长 (最多 {MAX_NAME_LENGTH} 字符)"
    # 检查符合命名规范
    if not SKILL_NAME_PATTERN.match(name):
        return False, f"技能名称不符合规范 (小写字母、数字、连字符): {name}"
    return True, ""


# =============================================================================
# 注意: RemoteSkillAnalyzer 已迁移到 clone_manager.py
# =============================================================================

# =============================================================================
# 共享逻辑 (Shared Logic)
# =============================================================================

# _extract_repo_from_url 已删除（功能已迁移到 clone_manager.py）

def _filter_skills_by_intent(
    skill_dirs: List[Path],
    skill_name: Optional[str] = None,
    batch: bool = False
) -> Tuple[List[Path], Optional[str]]:
    """
    根据用户意图过滤技能列表

    Args:
        skill_dirs: 检测到的所有技能目录
        skill_name: 用户指定的子技能名称
        batch: 是否批量处理

    Returns:
        (过滤后的技能列表, 错误信息)
    """
    if skill_name:
        # 用户指定了子技能：只处理指定的
        # 规范化技能名（转小写，处理连字符和下划线）
        normalized_target = skill_name.lower().replace('_', '-')

        # 第一轮：精确匹配目录名
        for skill_dir in skill_dirs:
            if skill_dir.name.lower().replace('_', '-') == normalized_target:
                return [skill_dir], None

        # 第二轮：路径匹配（检查相对路径中是否包含目标名称）
        for skill_dir in skill_dirs:
            path_parts = skill_dir.as_posix().split('/')
            if any(part.lower().replace('_', '-') == normalized_target for part in path_parts):
                return [skill_dir], None

        # 未找到匹配
        available = [s.name for s in skill_dirs]
        return [], f"未找到子技能: {skill_name}，可用: {available}"

    if len(skill_dirs) == SINGLE_SKILL_THRESHOLD or batch:
        # 只有 1 个技能 或 用户指定批量 → 处理所有
        return skill_dirs, None

    # 有多个技能且未指定批量 → 自动批量处理（兼容现有行为）
    return skill_dirs, None


# _dual_path_skill_check 和 _process_github_source 已删除
# GitHub 源处理现在统一使用 clone_manager._process_github_source


def _process_input_source(
    input_source: str,
    input_type: str,
    temp_dir: Path,
    skill_name: Optional[str] = None,
    batch: bool = False,
    subpath: Optional[str] = None,
    force_refresh: bool = False
) -> Tuple[List[Path], Optional[str]]:
    """
    统一的输入源处理逻辑

    Args:
        input_source: 输入源（URL 或路径字符串）
        input_type: 输入类型（github/local/skill-package/unknown）
        temp_dir: 临时目录
        skill_name: 指定的子技能名称
        batch: 是否批量处理
        subpath: GitHub 仓库的子路径
        force_refresh: 强制刷新缓存

    Returns:
        (待处理的技能列表, 错误信息)
    """
    if input_type == "github":
        # GitHub 源需要使用独立工具处理
        return [], f"GitHub 源需要先使用 clone_manager 处理\n请运行: python bin/clone_manager.py clone {input_source}"

    elif input_type == "local":
        return [Path(input_source)], None

    elif input_type == "skill-package":
        extract_ok, extracted_dir = SkillPackHandler.extract_pack(Path(input_source), temp_dir / "extracted")
        if not extract_ok:
            return [], "解压失败"
        return [extracted_dir], None

    else:
        return [], f"无法识别输入源类型: {input_type}"


# =============================================================================
# Skill Pack 处理器
# =============================================================================

class SkillPackHandler:
    """处理 .skill 打包文件"""

    @staticmethod
    def extract_pack(pack_file: Path, target_dir: Path) -> Tuple[bool, Path]:
        """
        解压 .skill 包

        Returns:
            (成功, 解压目录)
        """
        info(f"解压技能包: {pack_file}")

        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(pack_file, "r") as zip_ref:
                # ZIP Slip 防护: 验证所有路径都在目标目录内
                for member in zip_ref.infolist():
                    # 解析路径并解析为目标目录的绝对路径
                    member_path = (target_dir / member.filename).resolve()
                    # 确保解析后的路径以 target_dir 开头
                    if not str(member_path).startswith(str(target_dir.resolve())):
                        raise ValueError(f"ZIP Slip 检测: {member.filename} 试图跳出目标目录")
                zip_ref.extractall(target_dir)

            # 找到实际的技能目录（可能包含在根目录中）
            extracted_items = list(target_dir.iterdir())
            if len(extracted_items) == SINGLE_SKILL_THRESHOLD and extracted_items[0].is_dir():
                return True, extracted_items[0]

            return True, target_dir

        except Exception as e:
            error(f"解压失败: {e}")
            return False, target_dir


# =============================================================================
# Skill Searcher
# =============================================================================

class SkillSearcher:
    """Skill Searcher - Supports keyword, description, tag search

    Cache Strategy:
    - _skill_index: Cached skill index data
    - _index_mtime: 索引构建时的目录修改时间
    - 自动检测技能目录变化并失效缓存
    """

    # 类变量：索引缓存
    _skill_index: Optional[Dict[str, Dict]] = None
    _index_mtime: Optional[float] = None

    @staticmethod
    def _get_dir_mtime() -> Optional[float]:
        """获取技能目录的最新修改时间"""
        if not CLAUDE_SKILLS_DIR.exists():
            return None
        try:
            # 获取目录本身的 mtime
            return CLAUDE_SKILLS_DIR.stat().st_mtime
        except Exception:
            return None

    @staticmethod
    def _build_skill_index() -> Dict[str, Dict]:
        """
        Build skill search index

        Returns:
            {
                "skills": {
                    "skill_name": {
                        "name": "技能名",
                        "folder": "文件夹名",
                        "description": "描述(小写)",
                        "tags": ["标签列表"],
                        "category": "类别(小写)",
                        "keywords_cn": ["中文关键词"],
                        "description_raw": "原始描述"
                    }
                },
                "mtime": 目录修改时间
            }
        """
        if not CLAUDE_SKILLS_DIR.exists():
            return {"skills": {}, "mtime": 0}

        skills = {}
        for skill_dir in CLAUDE_SKILLS_DIR.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            try:
                with open(skill_md, "r", encoding="utf-8", errors="ignore") as f:
                    frontmatter = SkillNormalizer.extract_frontmatter(f.read())

                name = frontmatter.get("name", skill_dir.name)
                description = frontmatter.get("description", "")
                tags = frontmatter.get("tags", [])
                category = frontmatter.get("category", "")
                keywords_cn = frontmatter.get("keywords_cn", [])

                # keywords_cn 可能是字符串或列表
                if isinstance(keywords_cn, str):
                    keywords_cn = [k.strip() for k in keywords_cn.split(",") if k.strip()]

                skills[name] = {
                    "name": name,
                    "folder": skill_dir.name,
                    "description": description.lower(),
                    "tags": tags if isinstance(tags, list) else [tags],
                    "category": category.lower(),
                    "keywords_cn": keywords_cn,
                    "description_raw": description
                }
            except Exception:
                # 跳过读取失败的技能
                continue

        return {
            "skills": skills,
            "mtime": SkillSearcher._get_dir_mtime() or 0
        }

    @staticmethod
    def _get_skill_index() -> Dict[str, Dict]:
        """
        获取技能索引（带缓存）

        自动检测目录变化并重建索引
        """
        current_mtime = SkillSearcher._get_dir_mtime()

        # 检查缓存是否有效
        if (SkillSearcher._skill_index is not None and
            SkillSearcher._index_mtime is not None and
            current_mtime is not None and
            SkillSearcher._index_mtime >= current_mtime):
            # 缓存有效
            return SkillSearcher._skill_index

        # 缓存失效或不存在，重建索引
        SkillSearcher._skill_index = SkillSearcher._build_skill_index()
        SkillSearcher._index_mtime = current_mtime
        return SkillSearcher._skill_index

    @staticmethod
    def invalidate_cache() -> None:
        """手动失效缓存（用于安装/卸载技能后）"""
        SkillSearcher._skill_index = None
        SkillSearcher._index_mtime = None

    @staticmethod
    def search_skills(keywords: List[str], limit: int = 10) -> List[Dict]:
        """
        搜索技能（使用缓存索引）

        Args:
            keywords: 搜索关键词列表
            limit: 返回结果数量

        Returns:
            按相关度排序的技能列表 [(name, score, reasons), ...]
        """
        if not CLAUDE_SKILLS_DIR.exists():
            return []

        # 使用缓存索引（首次或目录变化时自动重建）
        index_data = SkillSearcher._get_skill_index()
        skills = index_data["skills"]

        results = []
        # 加载使用频率数据
        usage_data = SkillSearcher._load_usage_data()

        # 遍历索引数据（无需读取文件）
        for name, skill_data in skills.items():
            description = skill_data["description"]
            tags = skill_data["tags"]
            category = skill_data["category"]
            keywords_cn = skill_data["keywords_cn"]
            folder = skill_data["folder"]

            # 计算匹配分数
            total_score = 0
            match_reasons = []
            matched_keywords = set()

            for keyword in keywords:
                keyword_lower = keyword.lower()
                matched = False

                # 1. 名称完全匹配：100分
                if name.lower() == keyword_lower:
                    total_score += 100
                    match_reasons.append(f"名称完全匹配: {keyword}")
                    matched = True

                # 2. 名称前缀匹配：90分（高于包含）
                elif name.lower().startswith(keyword_lower) and len(keyword_lower) >= 2:
                    total_score += 90
                    match_reasons.append(f"名称前缀: {keyword}")
                    matched = True

                # 3. 名称包含：80分
                elif keyword_lower in name.lower():
                    total_score += 80
                    match_reasons.append(f"名称包含: {keyword}")
                    matched = True

                # 4. 中文关键词匹配：40分
                elif any(keyword_lower in k.lower() for k in keywords_cn):
                    total_score += 40
                    match_reasons.append(f"中文关键词: {keyword}")
                    matched = True

                # 5. 描述包含：50分
                elif keyword_lower in description:
                    total_score += 50
                    match_reasons.append(f"描述包含: {keyword}")
                    matched = True

                # 6. 标签匹配：30分
                elif keyword_lower in str(tags).lower():
                    total_score += 30
                    match_reasons.append(f"标签匹配: {keyword}")
                    matched = True

                # 7. 类别匹配：20分
                elif keyword_lower in category:
                    total_score += 20
                    match_reasons.append(f"类别匹配: {keyword}")
                    matched = True

                if matched:
                    matched_keywords.add(keyword_lower)

            # 8. 多关键词协同加成：20分
            if len(matched_keywords) >= 2:
                total_score += 20
                match_reasons.append(f"多关键词匹配加成({len(matched_keywords)})")

            # 9. 使用频率加权：最多+15分
            if name in usage_data:
                frequency_score = min(usage_data[name] * 3, 15)
                if frequency_score > 0:
                    total_score += frequency_score
                    match_reasons.append(f"使用频率加成(+{frequency_score})")

            if total_score > 0:
                results.append({
                    "name": name,
                    "folder": folder,
                    "score": total_score,
                    "reasons": match_reasons,
                    "description": skill_data["description_raw"]
                })

        # 按分数降序排序
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    @staticmethod
    def _load_usage_data() -> Dict[str, int]:
        """
        加载技能使用频率数据

        Returns:
            {skill_name: usage_count}
        """
        usage_file = BASE_DIR / ".claude" / "memory" / "skill_usage.json"
        default_data = {}

        if not usage_file.exists():
            return default_data

        try:
            with open(usage_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default_data

    @staticmethod
    def record_usage(skill_name: str) -> None:
        """
        记录技能使用（供 skills 子智能体调用）

        Args:
            skill_name: 技能名称
        """
        usage_file = BASE_DIR / ".claude" / "memory" / "skill_usage.json"
        usage_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            usage_data = SkillSearcher._load_usage_data()
            usage_data[skill_name] = usage_data.get(skill_name, 0) + 1

            with open(usage_file, "w", encoding="utf-8") as f:
                json.dump(usage_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            warn(f"记录使用失败: {e}")


# =============================================================================
# 威胁分析辅助函数
# =============================================================================

def _build_threat_analysis_prompt(threatened_skills: List[Dict]) -> str:
    """
    构建 LLM 二次确认提示词

    Args:
        threatened_skills: 威胁技能列表，每项包含 name, scan_result

    Returns:
        格式化的分析提示词
    """
    from datetime import datetime

    lines = []
    lines.append(f"# 安全扫描二次确认分析")
    lines.append(f"\n扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"威胁技能数量: {len(threatened_skills)}")
    lines.append("\n---")

    for i, threat in enumerate(threatened_skills, 1):
        scan_result = threat["scan_result"]
        skill_name = threat["name"]
        severity = scan_result.get("severity", "UNKNOWN")
        threats = scan_result.get("threats", [])

        lines.append(f"\n## {i}. {skill_name}")
        lines.append(f"**严重级别**: {severity}")
        lines.append(f"**威胁数量**: {len(threats)}")

        if threats:
            lines.append("\n**威胁详情**:")
            for t in threats[:10]:  # 最多显示 10 个
                title = t.get("title", "Unknown")
                t_severity = t.get("severity", "UNKNOWN")
                file = t.get("file", "")
                line = t.get("line", "")
                location = f"{file}:{line}" if file and line else (file or "")

                lines.append(f"  - [{t_severity}] {title}")
                if location:
                    lines.append(f"    位置: {location}")

    lines.append("\n---")
    lines.append("\n## 判断标准")
    lines.append("\n### 误报特征（允许安装）:")
    lines.append("- 技能描述包含工作流设计、开发工具、质量控制")
    lines.append("- 标准文档结构、模板文件")
    lines.append("- 测试代码、示例代码")
    lines.append("- 正常的 Python/JavaScript 代码结构")

    lines.append("\n### 确认威胁特征（应卸载）:")
    lines.append("- 明显的恶意代码（如 eval/exec 拼接用户输入）")
    lines.append("- 攻击载荷（如 shell 命令注入模式）")
    lines.append("- 敏感数据窃取（如上传本地文件到外部服务器）")
    lines.append("- 网络后门、反向 Shell")
    lines.append("- 加密货币挖矿代码")

    lines.append("\n## 操作建议")
    lines.append("\n对于确认威胁的技能，请执行:")
    lines.append("```bash")
    for threat in threatened_skills:
        lines.append(f"python bin/skill_manager.py uninstall {threat['name']}")
    lines.append("```")

    return "\n".join(lines)


# =============================================================================
# Main CLI Interface
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Skill Manager - Install, search, uninstall skills",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Install skill from GitHub repository
  python bin/skill_manager.py install https://github.com/user/repo

  # Install specific sub-skill
  python bin/skill_manager.py install https://github.com/user/repo --skill my-skill

  # Batch install all skills in repository
  python bin/skill_manager.py install https://github.com/user/repo --batch

  # Search skills (keywords)
  python bin/skill_manager.py search prompt

  # Search skills (multiple keywords)
  python bin/skill_manager.py search prompt optimize --score

  # List all installed skills
  python bin/skill_manager.py list

  # Uninstall skill (sync database)
  python bin/skill_manager.py uninstall my-skill

  # Validate installed skill
  python bin/skill_manager.py validate .claude/skills/my-skill
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # validate command
    validate_parser = subparsers.add_parser("validate", help="Validate skill structure")
    validate_parser.add_argument(
        "path",
        type=Path,
        help="Skill directory path"
    )

    # list command
    list_parser = subparsers.add_parser("list", help="List installed skills")
    list_parser.add_argument(
        "--color", "-c",
        action="store_true",
        help="Enable color output (default plain text)"
    )

    # search command
    search_parser = subparsers.add_parser("search", help="Search skills (keywords/description/tags)")
    search_parser.add_argument(
        "keywords",
        nargs="+",
        help="Search keywords (supports multiple keywords, AND logic)"
    )
    search_parser.add_argument(
        "--limit", "-l",
        type=int,
        default=10,
        help="Number of results (default 10)"
    )
    search_parser.add_argument(
        "--score", "-s",
        action="store_true",
        help="Show match scores"
    )

    # formats command
    formats_parser = subparsers.add_parser("formats", help="List supported skill formats")

    # uninstall command - Uninstall skill (sync database)
    uninstall_parser = subparsers.add_parser("uninstall", help="Uninstall skill and sync database state")
    uninstall_parser.add_argument(
        "name",
        nargs="+",
        help="Skill name (supports multiple, space separated)"
    )
    uninstall_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force delete without confirmation"
    )

    # install command - Unified install interface
    install_parser = subparsers.add_parser("install", help="Unified install interface (supports all formats)")
    install_parser.add_argument(
        "source",
        help="Install source (GitHub URL, local directory, .skill package)"
    )
    install_parser.add_argument(
        "--batch", "-b",
        action="store_true",
        help="Batch install all skills in repository"
    )
    install_parser.add_argument(
        "--skill", "-s",
        dest="skill_name",
        help="Specify sub-skill name to install (for multi-skill repositories)"
    )
    install_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force install (skip non-skill repo detection, overwrite existing skills)"
    )
    install_parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Force refresh repository cache (re-clone)"
    )
    install_parser.add_argument(
        "--author",
        help="GitHub author name (for building skill name)"
    )
    install_parser.add_argument(
        "--repo",
        help="GitHub repository name (for building skill name)"
    )

    # record command - Record skill usage
    record_parser = subparsers.add_parser("record", help="Record skill usage (for search weighting)")
    record_parser.add_argument(
        "name",
        help="Skill name"
    )

    # cache command - Repository cache management (route to clone_manager)
    cache_parser = subparsers.add_parser("cache", help="Repository cache management")
    cache_subparsers = cache_parser.add_subparsers(dest="cache_command", help="Cache operations")

    cache_subparsers.add_parser("list", help="List all caches")

    clear_cache_parser = cache_subparsers.add_parser("clear", help="Clear cache")
    clear_cache_parser.add_argument(
        "--older-than", type=int,
        help="Only clear cache older than specified hours"
    )

    update_cache_parser = cache_subparsers.add_parser("update", help="Update specified repository cache")
    update_cache_parser.add_argument("url", help="GitHub repository URL")

    # verify-config command
    verify_parser = subparsers.add_parser("verify-config", help="Verify config file")
    verify_parser.add_argument(
        "--fix",
        action="store_true",
        help="Auto-fix common config issues"
    )

    args = parser.parse_args()

    # =============================================================================
    # 执行命令
    # =============================================================================

    if args.command == "validate":
        is_valid, msg = SkillInstaller._validate_skill_structure(args.path)
        if is_valid:
            success(f"Validation passed: {args.path}")
            return 0
        else:
            error(f"Validation failed: {msg}")
            return 1

    elif args.command == "list":
        # Read directly from database
        skills_data = []
        if SKILLS_DB_FILE.exists():
            with open(SKILLS_DB_FILE, "r", encoding="utf-8") as f:
                db = json.load(f)
                for skill_id, skill in db.get("_default", {}).items():
                    if skill.get("installed", False):
                        skills_data.append(skill)

        use_color = args.color

        if use_color:
            header("Installed Skills List")

        if not skills_data:
            warn("No installed skills")
            return 0

        print(f"Total {len(skills_data)} skills:\n")

        for skill in skills_data:
            name = skill.get("name", "Unknown")
            desc = skill.get("description", "No description")
            desc_short = desc[:60] + "..." if len(desc) > 60 else desc

            if use_color:
                print(f"  [OK] {name}")
                print(f"     {desc_short}")
            else:
                print(f"[OK] {name}")
                print(f"     {desc_short}")

        return 0

    elif args.command == "search":
        header("Skill Search")

        results = SkillSearcher.search_skills(args.keywords, args.limit)

        if not results:
            warn(f"No matching skills found: {' '.join(args.keywords)}")
            return 0

        print(f"Found {len(results)} matching skills:\n")

        for i, result in enumerate(results, 1):
            score_str = f" ({result['score']}分)" if args.score else ""
            print(f"  {i}. {result['name']}{score_str}")

            if args.score:
                print(f"     匹配原因: {', '.join(result['reasons'])}")

            desc_short = result['description'][:60] + "..." if len(result['description']) > 60 else result['description']
            print(f"     {desc_short}\n")

        return 0

    elif args.command == "formats":
        header("支持的技能格式")

        print(f"共 {len(SUPPORTED_FORMATS)} 种格式:\n")

        for fmt_id, fmt_data in SUPPORTED_FORMATS.items():
            # 格式 ID 和名称
            print(f"  {fmt_id}")
            print(f"     名称: {fmt_data['name']}")

            # 识别标记
            markers = fmt_data.get('markers', [])
            if markers:
                print(f"     识别标记: {', '.join(markers)}")

            # 处理器状态
            handler = fmt_data.get('handler')
            if handler:
                print("     状态: 自定义处理器")
            else:
                print(f"     状态: 内置处理")

            print()

        print("提示: 遇到不支持的格式？")
        print("查看贡献指南: docs/skill-formats-contribution-guide.md")

        return 0

    elif args.command == "uninstall":
        header("Skill Uninstaller")

        # Normalize skill names to lowercase (fix case mismatch issue)
        skill_names = [name.lower() for name in args.name]
        success_count = 0
        failed_list = []

        # 遍历每个技能
        for skill_name in skill_names:
            # 1. 通过 name 查找 folder_name
            folder_name = None
            with db_connection() as (db, Skill):
                if db:
                    try:
                        result = db.get(Skill.name == skill_name)
                        if result:
                            folder_name = result.get("folder_name")
                    except Exception:
                        pass

            # 2. 如果找不到 folder_name，尝试直接用输入作为 folder_name
            if not folder_name:
                folder_name = skill_name

            skill_dir = CLAUDE_SKILLS_DIR / folder_name

            # 3. Check if skill exists
            if not skill_dir.exists():
                error(f"Skill not found: {skill_name} (lookup directory: {folder_name})")
                failed_list.append(skill_name)
                continue

            # 4. 确认删除
            if not args.force:
                print(f"即将删除技能: {skill_name}")
                print(f"路径: {skill_dir}")
                print("正在删除...")

            # 5. 删除目录（原子操作：文件 + 数据库）
            try:
                # 5.0 只读文件处理器（Windows 兼容）
                def _remove_readonly(func, path, excinfo):
                    """处理 Windows 只读文件删除问题"""
                    import os
                    os.chmod(path, 0o777)
                    func(path)

                # 5.1 删除文件
                shutil.rmtree(skill_dir, onerror=_remove_readonly)

                # 5.2 从数据库移除（使用 folder_name）
                db_remove_success = SkillInstaller._remove_skill_from_db(folder_name)
                if db_remove_success:
                    success(f"Deleted: {skill_name} (database synced)")
                    success_count += 1
                else:
                    # Database operation failed, file deleted but database not updated
                    warn(f"File deleted, but database sync failed: {skill_name}")
                    success_count += 1
            except Exception as e:
                error(f"删除失败: {skill_name} - {e}")
                failed_list.append(skill_name)

        # 汇总结果
        print()
        # 如果有成功删除的技能，失效搜索索引缓存
        if success_count > 0:
            SkillSearcher.invalidate_cache()
            # 更新技能映射表
            try:
                import subprocess
                result = subprocess.run(
                    [sys.executable, str(BASE_DIR / "bin" / "update_skills_mapping.py")],
                    cwd=BASE_DIR,
                    capture_output=True,
                    timeout=30
                )
                if result.returncode == 0:
                    info("技能映射表已同步更新")
                else:
                    warn(f"映射表更新失败: {result.stderr.decode()[:100]}")
            except subprocess.TimeoutExpired:
                warn("映射表更新超时")
            except Exception as e:
                warn(f"映射表更新失败: {e}")
        info(f"Batch deletion complete: Success {success_count}/{len(skill_names)}")
        if failed_list:
            error(f"Failed: {', '.join(failed_list)}")
            return 1
        return 0

    elif args.command == "install":
        header("Skill Installer")

        # 1. Detect input type
        input_type, input_source, subpath = FormatDetector.detect_input_type(args.source)
        info(f"输入类型: {input_type}")

        temp_dir = TEMP_DIR / f"installer_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        skills_to_process = []
        scan_results = None
        threatened_skills = []

        # 2. 对于 GitHub 源，需要先使用独立工具处理
        if input_type == "github":
            error("GitHub 源需要使用独立工具处理，请按以下步骤操作:")
            print()
            print("步骤 1: 克隆仓库")
            print(f"  python bin/clone_manager.py clone {input_source}")
            print()
            print("步骤 2: 安全扫描（可选）")
            print(f"  python bin/security_scanner.py scan-all")
            print()
            print("步骤 3: 安装技能")
            print(f"  python bin/skill_manager.py install <本地路径>")
            print()
            return 1

        else:
            # 非 GitHub 源，使用传统处理方式
            skills_to_process, error_msg = _process_input_source(
                input_source, input_type, temp_dir, args.skill_name,
                args.batch, subpath,
                force_refresh=getattr(args, "refresh_cache", False)
            )
            if error_msg:
                error(f"{error_msg}，退出")
                return 1

        if not skills_to_process:
            error("没有待处理的技能")
            return 1

        # 2.5 提取 GitHub 信息（优先使用命令行参数）
        github_author = getattr(args, "author", None)
        github_repo = getattr(args, "repo", None)
        if not github_author and input_type == "github":
            github_author, github_repo = SkillInstaller._extract_github_info(str(input_source))
            info(f"GitHub: {github_author}/{github_repo}")

        # 输出处理信息
        if args.skill_name:
            info(f"安装指定子技能: {args.skill_name}")
        elif len(skills_to_process) == SINGLE_SKILL_THRESHOLD:
            info(f"找到 1 个技能，自动安装")
        else:
            info(f"检测到 {len(skills_to_process)} 个技能，自动批量安装")

        # 3. 处理每个技能（格式转换）
        converted_skills = []

        for skill_dir in skills_to_process:
            skill_name = skill_dir.name
            info(f"\n处理技能: {skill_name}")

            # 验证子目录是否是技能目录
            should_install, skip_reason = ProjectValidator.validate_subdirectory(skill_dir, args.force)
            if not should_install:
                warn(f"跳过: {skill_name} - {skip_reason}")
                continue

            # 检测格式
            format_type, markers = FormatDetector.detect_skill_format(skill_dir)
            info(f"检测到格式: {format_type}")

            # 官方格式直接安装，其他格式转换
            if format_type == "official":
                info("官方格式，直接安装")
                target_dir = temp_dir / "processed" / skill_name
                shutil.copytree(skill_dir, target_dir)
                converted_skills.append(target_dir)
            else:
                info("需要转换")
                target_dir = temp_dir / "processed" / skill_name
                convert_ok, msg = SkillNormalizer.convert_to_official_format(skill_dir, target_dir)
                if convert_ok:
                    success(msg)
                    converted_skills.append(target_dir)
                else:
                    error(msg)

        # 4. 安装所有技能
        if converted_skills:
            info(f"\n安装 {len(converted_skills)} 个技能...")

            results = batch_install(converted_skills, args.force, github_author, github_repo, scan_results=scan_results)

            # 打印结果
            if results.get("success"):
                print()
                print(f"成功安装 ({len(results['success'])}):")
                for item in results["success"]:
                    print(f"  [OK] {item['name']}")

            if results.get("skipped"):
                print()
                print(f"跳过 ({len(results['skipped'])}):")
                for item in results["skipped"]:
                    print(f"  - {item['name']}: {item['message']}")

            if results.get("failed"):
                print()
                print(f"失败 ({len(results['failed'])}):")
                for item in results["failed"]:
                    print(f"  [X] {item['name']}: {item['message']}")

            # 处理威胁技能（需要二次分析）
            if results.get("threatened_skills"):
                print()
                print(f"⚠️  安全扫描发现 {len(results['threatened_skills'])} 个威胁技能，已安装但需要 LLM 二次分析")

        # 5. 清理临时文件
        old_cleaned = cleanup_old_install_dirs(max_age_hours=24)
        if old_cleaned > 0:
            info(f"清理了 {old_cleaned} 个旧临时目录")

        if temp_dir.exists():
            try:
                git_dir = temp_dir / "repo" / ".git"
                if git_dir.exists():
                    try:
                        for root, dirs, files in os.walk(git_dir):
                            for d in dirs:
                                os.chmod(os.path.join(root, d), 0o755)
                            for f in files:
                                os.chmod(os.path.join(root, f), 0o644)
                        shutil.rmtree(git_dir)
                    except Exception:
                        pass
                shutil.rmtree(temp_dir, ignore_errors=True)
                info(f"清理临时文件")
            except Exception as e:
                warn(f"清理临时文件失败: {e}")

        # 6. Summary
        header("Installation Complete")
        print(f"Install source: {args.source}")
        print(f"Skills processed: {len(skills_to_process)}")
        print(f"Successfully installed: {len(results.get('success', []))}")

        # 7. 更新技能映射表（仅当有成功安装时）
        if results.get('success'):
            try:
                import subprocess
                result = subprocess.run(
                    [sys.executable, str(BASE_DIR / "bin" / "update_skills_mapping.py")],
                    cwd=BASE_DIR,
                    capture_output=True,
                    timeout=30
                )
                if result.returncode == 0:
                    info("技能映射表已同步更新")
                else:
                    warn(f"映射表更新失败: {result.stderr.decode()[:100]}")
            except subprocess.TimeoutExpired:
                warn("映射表更新超时")
            except Exception as e:
                warn(f"映射表更新失败: {e}")

        return 0

    elif args.command == "record":
        SkillSearcher.record_usage(args.name)
        success(f"已记录使用: {args.name}")
        return 0

    elif args.command == "cache":
        # cache 命令已迁移到 clone_manager
        error("cache 命令已迁移到 clone_manager")
        print()
        print("请使用以下命令:")
        print(f"  python bin/clone_manager.py list-cache")
        print(f"  python bin/clone_manager.py clear-cache")
        print(f"  python bin/clone_manager.py clone <url> --force")
        print()
        return 1

    elif args.command == "verify-config":
        header("配置验证")

        result = {
            "valid": True,
            "issues": [],
            "fixed": []
        }

        config_file = BASE_DIR / "config.json"

        # 检查配置文件是否存在
        if not config_file.exists():
            result["valid"] = False
            result["issues"].append("配置文件不存在: config.json")

            if getattr(args, 'fix', False):
                default_config = {
                    "git": {
                        "proxies": [
                            "https://ghp.ci/{repo}",
                            "https://ghproxy.net/{repo}"
                        ],
                        "ssl_verify": True
                    },
                    "raw": {
                        "proxies": [
                            "https://ghp.ci/{path}",
                            "https://raw.fastgit.org/{path}"
                        ]
                    },
                    "security": {
                        "scan_enabled": True,
                        "scan_on_install": True,
                        "allowed_severity": ["SAFE", "LOW"],
                        "engines": {
                            "static": True,
                            "behavioral": True,
                            "llm": False,
                            "virustotal": False
                        }
                    }
                }
                with open(config_file, "w", encoding="utf-8") as f:
                    json.dump(default_config, f, indent=2, ensure_ascii=False)
                result["fixed"].append("已创建默认配置文件")

        # 验证配置内容
        else:
            try:
                config = load_config(use_cache=False)

                # 检查必需字段
                required_sections = ["git", "raw"]
                for section in required_sections:
                    if section not in config:
                        result["issues"].append(f"缺少配置节: {section}")
                        result["valid"] = False

                # 检查 proxies 格式
                if "git" in config and "proxies" in config["git"]:
                    proxies = config["git"]["proxies"]
                    if not isinstance(proxies, list) or not proxies:
                        result["issues"].append("git.proxies 必须是非空列表")
                        result["valid"] = False

                        if getattr(args, 'fix', False):
                            config["git"]["proxies"] = [
                                "https://ghp.ci/{repo}",
                                "https://ghproxy.net/{repo}"
                            ]
                            result["fixed"].append("已修复 git.proxies")

                # 如果有修复，写回文件
                if getattr(args, 'fix', False) and result["fixed"]:
                    with open(config_file, "w", encoding="utf-8") as f:
                        json.dump(config, f, indent=2, ensure_ascii=False)
                    result["valid"] = True

            except Exception as e:
                result["valid"] = False
                result["issues"].append(f"配置解析失败: {e}")

        if result["valid"]:
            success("配置文件有效")
        else:
            error("配置文件存在问题")

        if result["issues"]:
            print("\n发现问题:")
            for issue in result["issues"]:
                print(f"  [!] {issue}")

        if result["fixed"]:
            print("\n已修复:")
            for fix in result["fixed"]:
                print(f"  [OK] {fix}")

        return 0 if result["valid"] else 1

    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())

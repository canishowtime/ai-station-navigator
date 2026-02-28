#!/usr/bin/env python3
"""
skill_manager.py - Skill Manager
----------------------------------------------
Manages installation, uninstallation, conversion, and validation of skills

Responsibilities:
1. Format Detection - Detects input skill format types (GitHub/Local/.skill package)
2. Normalization - Converts non-standard formats to official SKILL.md format
3. Structure Validation - Validates structural integrity of converted skills
4. Auto Installation - Copies to .claude/skills/ and verifies availability
5. Auto Uninstallation - Deletes skills and synchronizes database state

Architecture:
    Kernel (AI) → Skill Manager → Format Detector → Normalizer → Installer

Source: Inspired by Anthropic's skill-creator (Apache 2.0)
https://github.com/anthropics/skills/tree/main/skills/skill-creator

v1.0 - Feature Complete:
    - Supports multiple input sources (GitHub URL, local directory, .skill package)
    - Automatically detects and fixes common format issues
    - Batch conversion support
    - Complete validation workflow
"""

import argparse
import sys
import os

# Windows UTF-8 compatibility (P0 - all scripts must include this)
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


import concurrent.futures
import glob
import json
import re
import shutil
import subprocess
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
import tempfile
import yaml

# Add project lib directory to sys.path (portable package pre-installed dependencies)
_lib_dir = Path(__file__).parent.parent / "lib"
if _lib_dir.exists():
    sys.path.insert(0, str(_lib_dir))

# Add bin directory to sys.path (only for hooks_manager)
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
# Decoupling Note: No longer directly importing clone_manager and security_scanner
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
SINGLE_SKILL_THRESHOLD = 1          # Single skill determination threshold
FRONTMATTER_PREVIEW_LINES = 10      # frontmatter preview lines
LIST_DESC_PREVIEW_CHARS = 500       # List command description preview character count

# Skill default value constants
DEFAULT_SKILL_DESC = "No description"       # Default skill description
DEFAULT_SKILL_CATEGORY = "utilities"  # Default category
DEFAULT_SKILL_TAGS = ["skill"]      # Default tags

# =============================================================================
# Format Registry
# =============================================================================
# When adding new format support, register format handlers here
# See: docs/skill-formats-contribution-guide.md for details

SUPPORTED_FORMATS = {
    "official": {
        "name": "Claude Code Official",
        "markers": ["SKILL.md"],
        "handler": None,  # Official format processed directly
    },
    "claude-plugin": {
        "name": "Claude Plugin",
        "markers": [".claude-plugin", "plugin.json", "marketplace.json"],
        "handler": None,  # Built-in handling
    },
    "agent-skills": {
        "name": "Anthropic Agent Skills",
        "markers": ["skills/", "SKILL.md"],
        "handler": None,  # Built-in handling
    },
    "cursor-rules": {
        "name": "Cursor Rules",
        "markers": [".cursor", "rules/"],
        "handler": None,  # Built-in handling
    },
    "plugin-marketplace": {
        "name": "Plugin Marketplace",
        "markers": ["plugins/", "MARKETPLACE.md"],
        "handler": None,  # Built-in handling
    },
    # Add new formats here, for example:
    # "cursor-plugin": {
    #     "name": "Cursor Plugin",
    #     "markers": ["package.json"],
    #     "handler": CursorPluginHandler,
    # },
}


# =============================================================================
# Temporary Directory Cleanup Utility
# =============================================================================

def cleanup_old_install_dirs(max_age_hours: int = 24) -> int:
    """
    Clean up installer_* temporary directories older than specified time

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
                # info(f"Cleaned old temp directory: {install_dir.name}")  # P0 fix: info() not yet defined (L238)
        except Exception:
            pass  # P0 fix: logging function not yet defined, skip silently

    return cleaned_count


# =============================================================================
# Logging Utilities (Plain Text)
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
    """Detects the format type of skill input sources"""

    @staticmethod
    def validate_github_url(url: str) -> Tuple[bool, Optional[str]]:
        """
        Validate GitHub URL format security to prevent config injection attacks

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
                return False, f"URL contains dangerous characters or patterns: {pattern}"

        # Check for URL encoding bypass attempts
        if '%2' in url.lower():
            return False, "URL contains suspicious encoded characters"

        return True, None

    @staticmethod
    def detect_input_type(input_source: str) -> Tuple[str, str, Optional[str]]:
        """
        Detect input source type

        Returns:
            (type, path/url, subpath)
        """
        from urllib.parse import urlparse

        info(f"Detecting input source: {input_source}")

        # 1. Check if it's a GitHub URL
        if input_source.startswith(("http://", "https://")):
            parsed = urlparse(input_source)
            if "github.com" in parsed.netloc:
                return "github", input_source, None

        # 1.5 Check if it's a GitHub shorthand (user/repo)
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

        warn("Cannot recognize input source type, trying as local directory")
        return "unknown", input_source, None

    @staticmethod
    def detect_skill_format(skill_dir: Path) -> Tuple[str, List[str]]:
        """
        Detect the format type of a skill directory

        Returns:
            (format_type, detected_marker_files)
            Format: 'official', 'claude-plugin', 'agent-skills', 'cursor-rules', 'unknown'
        """
        detected_markers = []

        # Check for official format
        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            try:
                with open(skill_md, "r", encoding="utf-8", errors="ignore") as f:
                    first_lines = "".join([f.readline() for _ in range(FRONTMATTER_PREVIEW_LINES)])
                    if "---" in first_lines and "name:" in first_lines:
                        return "official", ["SKILL.md"]
            except (OSError, IOError) as e:
                # P1 fix: silently skip on file read failure, continue detecting other formats
                pass

        # Check for third-party format markers
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

        # Check if there are markdown files (possibly old format)
        md_files = list(skill_dir.glob("*.md"))
        if md_files:
            return "unknown-md", [f.name for f in md_files]

        return "unknown", []


# =============================================================================
# Project Validator - Detects if it's a skill repository
# =============================================================================

class ProjectValidator:
    """Validates if a project is a skill repository, not a tool/application"""

    # Positive indicators for skill repository (root directory) - priority check
    SKILL_REPO_INDICATORS = [
        ("SKILL.md", "Root directory contains SKILL.md file"),
        ("_has_skills_dir", "skills/ directory contains multiple skills"),  # Special marker
        (".claude/skills", "Anthropic official skill repository structure"),
        # .skill package files (possibly multiple, checked with glob)
    ]

    # Skill package repository indicators (contains .skill files)
    SKILL_PACKAGE_EXTENSIONS = [".skill"]

    # Tool project indicator files (root directory) - simplified to most common
    TOOL_PROJECT_FILES = [
        "setup.py",        # Python package configuration
        "Cargo.toml",      # Rust project
        "go.mod",          # Go project
    ]

    # Files requiring further inspection (could be skill or tool)
    AMBIGUOUS_PROJECT_FILES = [
        "pyproject.toml",  # Could be skill packaging or tool
        "package.json",    # Could be skill or Node.js project
    ]

    # Tool component directory names (not skills) - simplified to most common
    TOOL_COMPONENT_NAMES = {
        "api", "src", "lib", "core", "utils",
        "scripts", "tools", "bin", "build", "target",
        "tests", "docs", "config",
        ".git", ".github",
    }

    # Keywords for non-skill projects (detected in README) - simplified to most common
    NON_SKILL_KEYWORDS = [
        "skill generator",
        "generates skills",
        "creates skills",
        "install via pip",
        "command-line interface",
        "cli tool",
    ]

    # Positive indicator words for skill projects (README)
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
        # 1. Check for positive skill repository indicators (highest priority)
        for indicator, reason in ProjectValidator.SKILL_REPO_INDICATORS:
            if indicator == "_has_skills_dir":
                # Special handling: check if skills/ directory contains skills
                skills_dir = repo_dir / "skills"
                if skills_dir.exists() and skills_dir.is_dir():
                    # Check if there are 3+ SKILL.md files
                    skill_count = len(list(skills_dir.glob("*/SKILL.md")))
                    if skill_count >= 3:
                        return True, f"skills/ directory contains {skill_count} skills"
            elif (repo_dir / indicator).exists():
                return True, f"{reason}"

        # 2. Check if there are .skill package files (skill package repository)
        for ext in ProjectValidator.SKILL_PACKAGE_EXTENSIONS:
            skill_files = list(repo_dir.glob(f"*{ext}"))
            if skill_files:
                return True, f"Contains skill package file: {skill_files[0].name}"

        # 2.5 New: Check if subdirectories contain multiple skills (monorepo support)
        # Before determining as tool project, check subdirectories first
        sub_skill_dirs = []
        exclude_dirs = {
            "tests", "test", "testing", "spec", "specs",
            "docs", "doc", "documentation", "examples", "example",
            "scripts", "tools", "bin", "build", "dist", "target",
            ".git", ".github", ".vscode", ".idea",
        }
        # Special priority: don't exclude skills/ directory
        for item in repo_dir.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                # Special handling for skills/ directory: check skills in subdirectories
                if item.name == "skills":
                    skill_count = 0
                    for sub_item in item.iterdir():
                        if sub_item.is_dir() and (sub_item / "SKILL.md").exists():
                            sub_skill_dirs.append(sub_item)
                            skill_count += 1
                    if skill_count >= 2:
                        return True, f"skills/ directory contains {skill_count} skills (monorepo)"
                elif item.name not in exclude_dirs:
                    # Check if it's a skill directory (has SKILL.md or follows skill naming convention)
                    if (item / "SKILL.md").exists():
                        sub_skill_dirs.append(item)
                    elif re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", item.name):
                        # Check if there are markdown files (possibly skill content)
                        md_files = list(item.glob("*.md"))
                        if md_files:
                            sub_skill_dirs.append(item)

        # If there are 2+ sub-skill directories, determine as skill repository
        if len(sub_skill_dirs) >= 2:
            return True, f"Subdirectories contain {len(sub_skill_dirs)} skills (monorepo)"

        # 3. Check for explicit tool project files
        for tool_file in ProjectValidator.TOOL_PROJECT_FILES:
            if (repo_dir / tool_file).exists():
                return False, f"Detected tool project file: {tool_file}"

        # 4. Check ambiguous project files (need further judgment)
        for ambiguous_file in ProjectValidator.AMBIGUOUS_PROJECT_FILES:
            file_path = repo_dir / ambiguous_file
            if file_path.exists():
                # For these files, need to check content and README
                if ambiguous_file == "pyproject.toml":
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    # Check if explicitly a tool project
                    if "tool.scripts" in content or "command-line" in content.lower():
                        return False, f"Detected tool project configuration: {ambiguous_file}"
                    # If has [project] and is a tool (not skill packaging), check subdirectories
                    if "[project]" in content:
                        # Check if subdirectories are all tool components
                        subdirs = [d.name for d in repo_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
                        tool_components = ProjectValidator.TOOL_COMPONENT_NAMES & set(subdirs)
                        # If most subdirectories are tool components, determine as tool project
                        if len(tool_components) >= 2 and len(tool_components) >= len(subdirs) * 0.5:
                            return False, f"Detected tool project structure (contains tool component directories)"
                    # If just build configuration, continue checking README
                elif ambiguous_file == "package.json":
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    # If has many scripts, possibly a Node.js tool
                    if '"scripts"' in content and content.count('"') > 20:
                        return False, f"Detected Node.js tool project: {ambiguous_file}"

        # 5. Check README content (key judgment)
        readme = ProjectValidator._read_readme(repo_dir)
        if readme:
            content_lower = readme.lower()

            # Priority check for positive skill indicator words
            for indicator in ProjectValidator.SKILL_INDICATORS:
                if indicator in content_lower:
                    return True, f"README contains skill indicator: {indicator}"

            # Check tool keywords
            for keyword in ProjectValidator.NON_SKILL_KEYWORDS:
                if keyword in content_lower:
                    return False, f"README contains tool project keyword: {keyword}"

        # 6. Check directory structure
        subdirs = [d.name for d in repo_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
        # If has typical tool project directory structure
        tool_dirs = ProjectValidator.TOOL_COMPONENT_NAMES & set(subdirs)
        if len(tool_dirs) >= 2:
            return False, f"Detected tool project directory structure: {', '.join(list(tool_dirs)[:3])}"

        # Default: uncertain, assume possibly a skill repository
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

        # 2. Check if has SKILL.md (most clear skill indicator)
        if (subdir / "SKILL.md").exists():
            return True, "Contains SKILL.md file"

        # 3. Check if it's a Python package directory (has __init__.py but no SKILL.md)
        if (subdir / "__init__.py").exists():
            return False, "Python package directory (no SKILL.md)"

        # 4. Check directory name format: skill names usually kebab-case
        if not re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", dirname):
            return False, f"Directory name doesn't match skill naming convention: {dirname}"

        # 5. Check if there are .md files (possibly skill content)
        md_files = list(subdir.glob("*.md"))
        if not md_files:
            return False, "No markdown files found"

        # Default: possibly a skill
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
            bool - True to continue, False to abort
        """
        is_skill, reason = ProjectValidator.is_skill_repo_root(repo_dir)

        if not is_skill:
            print("=" * 60)
            print("X Installation rejected: This is not a skill project")
            print("=" * 60)
            print()
            print(f"Detection reason: {reason}")
            print(f"Repository: {repo_name}")
            print()
            print("The system does not support installing tool projects.")
            print("Please confirm:")
            print(f"  1. Is it a tool/library? Please use pip/npm/cargo etc. to install")
            print(f"  2. Really need to install as a skill? Please manually convert then install")

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
    """Normalizes various formats to official SKILL.md format"""

    @staticmethod
    def validate_skill_name(name: str) -> Tuple[bool, str]:
        """Validate if skill name conforms to specifications"""
        if not name:
            return False, "Skill name cannot be empty"

        if len(name) > MAX_NAME_LENGTH:
            return False, f"Skill name too long (max {MAX_NAME_LENGTH} characters)"

        if not SKILL_NAME_PATTERN.match(name):
            return False, "Skill name must be lowercase letters, numbers and hyphens, cannot start or end with hyphen"

        return True, ""


    @staticmethod
    def validate_description(desc: str) -> Tuple[bool, str]:
        """Validate if description conforms to specifications"""
        if not desc:
            return False, "Description cannot be empty"

        if len(desc) > MAX_DESC_LENGTH:
            return False, f"Description too long (max {MAX_DESC_LENGTH} characters)"

        # Check if contains potential HTML tags (more precise pattern)
        # Allow standalone < and > characters (like >5, C++, <3), but reject <tag> format
        if re.search(r'<[^>]+>', desc):
            return False, "Description cannot contain HTML tags"

        return True, ""


    @staticmethod
    def normalize_skill_name(original_name: str) -> str:
        """Normalize any name to hyphen-case format"""
        # Remove special characters, convert to lowercase, join with hyphens
        normalized = re.sub(r"[^a-zA-Z0-9]+", "-", original_name).strip("-").lower()
        # Remove leading numbers
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

        # Find the second --- (compatible with \n--- and --- formats)
        end_marker = content.find("\n---", 4)
        if end_marker == -1:
            end_marker = content.find("---", 3)
        if end_marker <= 0:
            return {}

        # Extract frontmatter content
        yaml_content = content[4:end_marker].strip()

        # Prefer using yaml.safe_load
        try:
            frontmatter = yaml.safe_load(yaml_content)
            if isinstance(frontmatter, dict):
                return frontmatter
        except (yaml.YAMLError, Exception):
            pass

        # Fallback: manual parsing (handle simple key: value format)
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
            (needs_fix, fixed_content or error_message)
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
                frontmatter["description"] = "Skill description (please improve manually)"
                needs_fix = True

        if needs_fix:
            # Rebuild frontmatter
            new_frontmatter = "---\n"
            new_frontmatter += f'name: {frontmatter["name"]}\n'
            new_frontmatter += f'description: "{frontmatter["description"]}"\n'
            new_frontmatter += "---\n\n"

            # Preserve original content (remove old frontmatter)
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

        return "Auto-generated skill description, please improve manually"


    @staticmethod
    def convert_to_official_format(source_dir: Path, target_dir: Path) -> Tuple[bool, str]:
        """
        Convert third-party formats to official format

        Returns:
            (success, message)
        """
        info(f"Converting skill: {source_dir.name}")

        # 1. Detect format
        format_type, markers = FormatDetector.detect_skill_format(source_dir)
        info(f"Detected format: {format_type}")

        # 2. Create target directory
        target_dir.mkdir(parents=True, exist_ok=True)

        # 3. Process according to format
        if format_type == "official":
            # Already official format, copy directly
            SkillNormalizer._copy_directory(source_dir, target_dir)
        elif format_type == "claude-plugin":
            # Claude Plugin format
            SkillNormalizer._convert_claude_plugin(source_dir, target_dir)
        elif format_type == "agent-skills":
            # Agent Skills format
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
        """Copy directory contents"""
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target, dirs_exist_ok=True)


    @staticmethod
    def _convert_claude_plugin(source: Path, target: Path) -> None:
        """Convert Claude Plugin format"""
        # Find SKILL.md or README.md
        skill_md = source / "SKILL.md"
        if skill_md.exists():
            shutil.copy2(skill_md, target / "SKILL.md")
        else:
            # Generate SKILL.md from plugin.json or marketplace.json
            plugin_json = source / ".claude-plugin" / "plugin.json"
            if plugin_json.exists():
                SkillNormalizer._generate_from_plugin_json(plugin_json, target)
            else:
                SkillNormalizer._create_default_skill_md(source, target)

        # Copy other resources
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
        """Convert Agent Skills format"""
        # Agent Skills usually already have SKILL.md
        skill_md = source / "SKILL.md"
        if skill_md.exists():
            shutil.copy2(skill_md, target / "SKILL.md")

        # Copy scripts/, references/, examples/ etc. directories
        for subdir in ["scripts", "references", "examples", "templates"]:
            src_subdir = source / subdir
            if src_subdir.exists():
                shutil.copytree(src_subdir, target / subdir, dirs_exist_ok=True)


    @staticmethod
    def _convert_cursor_rules(source: Path, target: Path) -> None:
        """Convert Cursor Rules format"""
        # Cursor's rules/ directory usually contains .md files
        rules_dir = source / ".cursor" / "rules"
        if not rules_dir.exists():
            rules_dir = source / "rules"

        if rules_dir.exists():
            # Merge all .md files
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
            # Generate SKILL.md from README.md
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
description: "Skill auto-converted from {source.name}, please improve description manually"
---

# {name.replace('-', ' ').title()}

## Overview

This skill was automatically converted from a third-party source, please improve this document according to actual functionality.

## Conversion Info

- **Source Name**: {source.name}
- **Conversion Time**: {datetime.now().isoformat()}
- **Status**: Requires manual improvement

## Usage

Please add usage instructions...

## Resources

List related resources...
"""

        with open(target / "SKILL.md", "w", encoding="utf-8") as f:
            f.write(content)

        # Copy other files
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

This skill has been automatically converted and installed.

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
        """Custom JSONStorage, enforces UTF-8 encoding (fixes Windows GBK issue)"""

        def __init__(self, path, **kwargs):
            # Enforce UTF-8 encoding
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
    """Installs converted skills to .claude/skills/"""

    @staticmethod
    def _extract_github_info(github_url: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract author and repo from GitHub URL

        Supported formats:
        - https://github.com/author/repo
        - author/repo (shorthand format)

        Returns:
            (author, repo)
        """
        if "github.com" in github_url:
            # Full URL format
            parts = github_url.rstrip('/').split('/')
            for i, part in enumerate(parts):
                if part == "github.com" and i + 2 < len(parts):
                    return parts[i + 1], parts[i + 2]
        else:
            # Shorthand format: author/repo
            if '/' in github_url:
                parts = github_url.rstrip('/').split('/')
                if len(parts) == 2:
                    return parts[0], parts[1]
        return None, None

    @staticmethod
    def _get_skill_name_from_md(skill_dir: Path) -> Optional[str]:
        """Read name field from SKILL.md"""
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
        """Extract complete metadata from local SKILL.md"""
        skill_path = CLAUDE_SKILLS_DIR / skill_name
        skill_md = skill_path / "SKILL.md"

        if not skill_md.exists():
            return None

        try:
            content = skill_md.read_text(encoding='utf-8')
            frontmatter = SkillNormalizer.extract_frontmatter(content)

            # Extract description (if frontmatter doesn't have it)
            description = frontmatter.get("description", "")
            if not description:
                description = SkillNormalizer._extract_description_from_content(content)

            return {
                "id": skill_name.lower().replace('_', '-'),
                "name": frontmatter.get("name", skill_name),
                "folder_name": skill_name,
                "description": description or f"{skill_name} skill",
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
            warn(f"Failed to extract skill metadata: {e}")
            return None

    @staticmethod
    def _sync_skill_to_db(skill_name: str, db=None, Skill=None) -> bool:
        """Sync skill to database (supports connection reuse)

        Args:
            skill_name: Skill name
            db: Optional external database connection (for batch reuse)
            Skill: Optional external Query object (for batch reuse)
        """
        # If no external connection provided, create new connection
        if db is None or Skill is None:
            with db_connection() as (conn_db, conn_Skill):
                if conn_db is None:
                    return False
                return SkillInstaller._sync_skill_to_db(skill_name, conn_db, conn_Skill)

        # Use provided connection for database operations
        try:
            # Extract metadata from local SKILL.md
            metadata = SkillInstaller._extract_from_local_skill(skill_name)
            if not metadata:
                warn(f"Cannot extract skill metadata: {skill_name}")
                return False

            # Check if already exists (match by folder_name)
            existing = db.get(Skill.folder_name == skill_name)
            if existing:
                # Update existing record
                metadata["installed"] = True
                metadata["installed_path"] = f".claude/skills/{skill_name}"
                # Preserve original keywords_cn
                if existing.get("keywords_cn"):
                    metadata["keywords_cn"] = existing["keywords_cn"]
                db.update(metadata, doc_ids=[existing.doc_id])
            else:
                # Insert new record
                metadata["installed"] = True
                metadata["installed_path"] = f".claude/skills/{skill_name}"
                db.insert(metadata)

            return True
        except Exception as e:
            warn(f"Database sync failed: {e}")
            return False

    @staticmethod
    def _remove_skill_from_db(skill_name: str) -> bool:
        """Remove skill record from database"""
        with db_connection() as (db, Skill):
            if db is None:
                return False

            try:
                # Delete by folder_name
                removed = db.remove(Skill.folder_name == skill_name)
                return len(removed) > 0
            except Exception as e:
                warn(f"Database deletion failed: {e}")
                return False

    @staticmethod
    def batch_remove_from_db(folder_names: List[str]) -> Dict[str, bool]:
        """Batch delete skill records from database (single connection optimization)

        Args:
            folder_names: List of skill folder names

        Returns:
            {folder_name: success_flag}
        """
        results = {}
        with db_connection() as (db, Skill):
            if db is None:
                return {name: False for name in folder_names}

            for folder_name in folder_names:
                try:
                    removed = db.remove(Skill.folder_name == folder_name)
                    results[folder_name] = len(removed) > 0
                except Exception as e:
                    warn(f"Database deletion failed {folder_name}: {e}")
                    results[folder_name] = False

        return results

    @staticmethod
    def _validate_skill_structure(skill_dir: Path) -> Tuple[bool, str]:
        """Validate skill directory structure"""
        # Check if SKILL.md exists
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return False, "SKILL.md does not exist"

        # Check frontmatter
        with open(skill_md, "r", encoding="utf-8") as f:
            content = f.read()

        frontmatter = SkillNormalizer.extract_frontmatter(content)

        # Check required fields
        for field in REQUIRED_FIELDS:
            if field not in frontmatter:
                return False, f"Missing required field: {field}"

        # Validate field values
        valid, msg = SkillNormalizer.validate_skill_name(frontmatter["name"])
        if not valid:
            return False, f"name validation failed: {msg}"

        valid, msg = SkillNormalizer.validate_description(frontmatter["description"])
        if not valid:
            return False, f"description validation failed: {msg}"

        # Check if name matches folder name
        if frontmatter["name"] != skill_dir.name:
            warn(f"Skill name doesn't match folder name: {frontmatter['name']} != {skill_dir.name}")

        return True, ""


def batch_install(skill_dirs: List[Path], force: bool = False, author: Optional[str] = None, repo: Optional[str] = None, non_interactive: bool = False, scan_results: Optional[Dict] = None) -> Dict[str, Any]:
    """Batch install skills (refactored: only handles installation, no scanning)

    Args:
        skill_dirs: List of skill directories
        force: Whether to force overwrite
        author: GitHub author name
        repo: GitHub repository name
        scan_results: Optional scan results (provided by security_scanner)

    Returns:
        {"success": [...], "failed": [...], "skipped": [...]}
    """
    results = {
        "success": [],
        "failed": [],
        "skipped": [],
    }

    # Batch copy all skill files
    copied_skills = []
    for skill_dir in skill_dirs:
        # Read skill name
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
                results["skipped"].append({"name": skill_name, "message": f"Skill already exists"})
                continue
            shutil.rmtree(target_dir)

        # Copy files
        try:
            shutil.copytree(skill_dir, target_dir)
            copied_skills.append((skill_name, target_dir))
        except Exception as e:
            results["failed"].append({"name": skill_name, "message": f"Copy failed: {e}"})

    if not copied_skills:
        return results

    # If scan results provided, handle threats
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

        # Build threat details
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

    # Batch write to database
    with db_connection() as (db, Skill):
        for skill_name, target_dir in safe_skills:
            db_sync_success = SkillInstaller._sync_skill_to_db(skill_name, db, Skill)
            if db_sync_success:
                success(f"[OK] Installation successful: {skill_name} (database synced)")
                results["success"].append({"name": skill_name, "message": "Installation successful"})
            else:
                # Database sync failed, rollback
                shutil.rmtree(target_dir)
                results["failed"].append({"name": skill_name, "message": "Database sync failed, rolled back"})

    # Invalidate search index cache
    if results["success"]:
        SkillSearcher.invalidate_cache()

    return results


# =============================================================================
# Configuration Loading (Independent Implementation)
# =============================================================================

_config_cache: Optional[dict] = None
_config_mtime: Optional[float] = None

def load_config(use_cache: bool = True) -> dict:
    """Load configuration file"""
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
    """Clear configuration cache"""
    global _config_cache, _config_mtime
    _config_cache = None
    _config_mtime = None


def validate_skill_name(name: str) -> Tuple[bool, str]:
    """Validate skill name security to prevent path traversal attacks"""
    if not name:
        return False, "Skill name cannot be empty"
    # Detect path traversal characters
    dangerous = ['..', '\\', '/', '\x00']
    if any(d in name for d in dangerous):
        return False, f"Skill name contains illegal characters: {name}"
    # Check length
    if len(name) > MAX_NAME_LENGTH:
        return False, f"Skill name too long (max {MAX_NAME_LENGTH} characters)"
    # Check naming convention
    if not SKILL_NAME_PATTERN.match(name):
        return False, f"Skill name doesn't follow convention (lowercase letters, numbers, hyphens): {name}"
    return True, ""


# =============================================================================
# Note: RemoteSkillAnalyzer has been migrated to clone_manager.py
# =============================================================================

# =============================================================================
# Shared Logic
# =============================================================================

# _extract_repo_from_url has been deleted (functionality migrated to clone_manager.py)

def _filter_skills_by_intent(
    skill_dirs: List[Path],
    skill_name: Optional[str] = None,
    batch: bool = False
) -> Tuple[List[Path], Optional[str]]:
    """
    Filter skill list based on user intent

    Args:
        skill_dirs: All detected skill directories
        skill_name: User-specified sub-skill name
        batch: Whether to process in batch

    Returns:
        (filtered_skill_list, error_message)
    """
    if skill_name:
        # User specified sub-skill: only process the specified one
        # Normalize skill name (lowercase, handle hyphens and underscores)
        normalized_target = skill_name.lower().replace('_', '-')

        # First round: exact directory name match
        for skill_dir in skill_dirs:
            if skill_dir.name.lower().replace('_', '-') == normalized_target:
                return [skill_dir], None

        # Second round: path match (check if relative path contains target name)
        for skill_dir in skill_dirs:
            path_parts = skill_dir.as_posix().split('/')
            if any(part.lower().replace('_', '-') == normalized_target for part in path_parts):
                return [skill_dir], None

        # No match found
        available = [s.name for s in skill_dirs]
        return [], f"Sub-skill not found: {skill_name}, available: {available}"

    if len(skill_dirs) == SINGLE_SKILL_THRESHOLD or batch:
        # Only 1 skill or user specified batch → process all
        return skill_dirs, None

    # Multiple skills and batch not specified → auto batch process (compatible with existing behavior)
    return skill_dirs, None


# _dual_path_skill_check and _process_github_source have been deleted
# GitHub source processing now uniformly uses clone_manager._process_github_source


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
    Unified input source processing logic

    Args:
        input_source: Input source (URL or path string)
        input_type: Input type (github/local/skill-package/unknown)
        temp_dir: Temporary directory
        skill_name: Specified sub-skill name
        batch: Whether to process in batch
        subpath: Subpath of GitHub repository
        force_refresh: Force refresh cache

    Returns:
        (skill_list_to_process, error_message)
    """
    if input_type == "github":
        # GitHub source needs to be processed by independent tool first
        return [], f"GitHub source needs to be processed by clone_manager first\nPlease run: python bin/clone_manager.py clone {input_source}"

    elif input_type == "local":
        return [Path(input_source)], None

    elif input_type == "skill-package":
        extract_ok, extracted_dir = SkillPackHandler.extract_pack(Path(input_source), temp_dir / "extracted")
        if not extract_ok:
            return [], "Extraction failed"
        return [extracted_dir], None

    else:
        return [], f"Cannot recognize input source type: {input_type}"


# =============================================================================
# Skill Pack Handler
# =============================================================================

class SkillPackHandler:
    """Handles .skill package files"""

    @staticmethod
    def extract_pack(pack_file: Path, target_dir: Path) -> Tuple[bool, Path]:
        """
        Extract .skill package

        Returns:
            (success, extracted_directory)
        """
        info(f"Extracting skill package: {pack_file}")

        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(pack_file, "r") as zip_ref:
                # ZIP Slip protection: verify all paths are within target directory
                for member in zip_ref.infolist():
                    # Resolve path and parse to absolute path of target directory
                    member_path = (target_dir / member.filename).resolve()
                    # Ensure resolved path starts with target_dir
                    if not str(member_path).startswith(str(target_dir.resolve())):
                        raise ValueError(f"ZIP Slip detected: {member.filename} attempts to escape target directory")
                zip_ref.extractall(target_dir)

            # Find actual skill directory (possibly contained in root directory)
            extracted_items = list(target_dir.iterdir())
            if len(extracted_items) == SINGLE_SKILL_THRESHOLD and extracted_items[0].is_dir():
                return True, extracted_items[0]

            return True, target_dir

        except Exception as e:
            error(f"Extraction failed: {e}")
            return False, target_dir


# =============================================================================
# Skill Searcher
# =============================================================================

class SkillSearcher:
    """Skill searcher - supports keyword, description, tag search

    Cache strategy:
    - _skill_index: Cached skill index data
    - _index_mtime: Directory modification time when index was built
    - Automatically detects skill directory changes and invalidates cache
    """

    # Class variables: index cache
    _skill_index: Optional[Dict[str, Dict]] = None
    _index_mtime: Optional[float] = None

    @staticmethod
    def _get_dir_mtime() -> Optional[float]:
        """Get latest modification time of skills directory"""
        if not CLAUDE_SKILLS_DIR.exists():
            return None
        try:
            # Get directory's own mtime
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
                        "name": "skill_name",
                        "folder": "folder_name",
                        "description": "description(lowercase)",
                        "tags": ["tag_list"],
                        "category": "category(lowercase)",
                        "keywords_cn": ["chinese_keywords"],
                        "description_raw": "original_description"
                    }
                },
                "mtime": directory_modification_time
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

                # keywords_cn may be string or list
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
                # Skip skills that failed to read
                continue

        return {
            "skills": skills,
            "mtime": SkillSearcher._get_dir_mtime() or 0
        }

    @staticmethod
    def _get_skill_index() -> Dict[str, Dict]:
        """
        Get skill index (with cache)

        Automatically detects directory changes and rebuilds index
        """
        current_mtime = SkillSearcher._get_dir_mtime()

        # Check if cache is valid
        if (SkillSearcher._skill_index is not None and
            SkillSearcher._index_mtime is not None and
            current_mtime is not None and
            SkillSearcher._index_mtime >= current_mtime):
            # Cache is valid
            return SkillSearcher._skill_index

        # Cache invalid or doesn't exist, rebuild index
        SkillSearcher._skill_index = SkillSearcher._build_skill_index()
        SkillSearcher._index_mtime = current_mtime
        return SkillSearcher._skill_index

    @staticmethod
    def invalidate_cache() -> None:
        """Manually invalidate cache (used after installing/uninstalling skills)"""
        SkillSearcher._skill_index = None
        SkillSearcher._index_mtime = None

    @staticmethod
    def search_skills(keywords: List[str], limit: int = 10) -> List[Dict]:
        """
        Search skills (using cached index)

        Args:
            keywords: List of search keywords
            limit: Number of results to return

        Returns:
            Skill list sorted by relevance [(name, score, reasons), ...]
        """
        if not CLAUDE_SKILLS_DIR.exists():
            return []

        # Use cached index (auto-rebuild on first use or directory change)
        index_data = SkillSearcher._get_skill_index()
        skills = index_data["skills"]

        results = []
        # Load usage frequency data
        usage_data = SkillSearcher._load_usage_data()

        # Iterate through index data (no file reading needed)
        for name, skill_data in skills.items():
            description = skill_data["description"]
            tags = skill_data["tags"]
            category = skill_data["category"]
            keywords_cn = skill_data["keywords_cn"]
            folder = skill_data["folder"]

            # Calculate match score
            total_score = 0
            match_reasons = []
            matched_keywords = set()

            for keyword in keywords:
                keyword_lower = keyword.lower()
                matched = False

                # 1. Exact name match: 100 points
                if name.lower() == keyword_lower:
                    total_score += 100
                    match_reasons.append(f"Exact name match: {keyword}")
                    matched = True

                # 2. Name prefix match: 90 points (higher than contains)
                elif name.lower().startswith(keyword_lower) and len(keyword_lower) >= 2:
                    total_score += 90
                    match_reasons.append(f"Name prefix: {keyword}")
                    matched = True

                # 3. Name contains: 80 points
                elif keyword_lower in name.lower():
                    total_score += 80
                    match_reasons.append(f"Name contains: {keyword}")
                    matched = True

                # 4. Chinese keyword match: 40 points
                elif any(keyword_lower in k.lower() for k in keywords_cn):
                    total_score += 40
                    match_reasons.append(f"Chinese keyword: {keyword}")
                    matched = True

                # 5. Description contains: 50 points
                elif keyword_lower in description:
                    total_score += 50
                    match_reasons.append(f"Description contains: {keyword}")
                    matched = True

                # 6. Tag match: 30 points
                elif keyword_lower in str(tags).lower():
                    total_score += 30
                    match_reasons.append(f"Tag match: {keyword}")
                    matched = True

                # 7. Category match: 20 points
                elif keyword_lower in category:
                    total_score += 20
                    match_reasons.append(f"Category match: {keyword}")
                    matched = True

                if matched:
                    matched_keywords.add(keyword_lower)

            # 8. Multi-keyword synergy bonus: 20 points
            if len(matched_keywords) >= 2:
                total_score += 20
                match_reasons.append(f"Multi-keyword match bonus({len(matched_keywords)})")

            # 9. Usage frequency weighting: max +15 points
            if name in usage_data:
                frequency_score = min(usage_data[name] * 3, 15)
                if frequency_score > 0:
                    total_score += frequency_score
                    match_reasons.append(f"Usage frequency bonus(+{frequency_score})")

            if total_score > 0:
                results.append({
                    "name": name,
                    "folder": folder,
                    "score": total_score,
                    "reasons": match_reasons,
                    "description": skill_data["description_raw"]
                })

        # Sort by score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    @staticmethod
    def _load_usage_data() -> Dict[str, int]:
        """
        Load skill usage frequency data

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
        Record skill usage (called by skills sub-agent)

        Args:
            skill_name: Skill name
        """
        usage_file = BASE_DIR / ".claude" / "memory" / "skill_usage.json"
        usage_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            usage_data = SkillSearcher._load_usage_data()
            usage_data[skill_name] = usage_data.get(skill_name, 0) + 1

            with open(usage_file, "w", encoding="utf-8") as f:
                json.dump(usage_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            warn(f"Failed to record usage: {e}")


# =============================================================================
# Threat Analysis Helper Functions
# =============================================================================

def _build_threat_analysis_prompt(threatened_skills: List[Dict]) -> str:
    """
    Build LLM secondary confirmation prompt

    Args:
        threatened_skills: List of threatened skills, each containing name, scan_result

    Returns:
        Formatted analysis prompt
    """
    from datetime import datetime

    lines = []
    lines.append(f"# Security Scan Secondary Confirmation Analysis")
    lines.append(f"\nScan time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Number of threatened skills: {len(threatened_skills)}")
    lines.append("\n---")

    for i, threat in enumerate(threatened_skills, 1):
        scan_result = threat["scan_result"]
        skill_name = threat["name"]
        severity = scan_result.get("severity", "UNKNOWN")
        threats = scan_result.get("threats", [])

        lines.append(f"\n## {i}. {skill_name}")
        lines.append(f"**Severity Level**: {severity}")
        lines.append(f"**Number of Threats**: {len(threats)}")

        if threats:
            lines.append("\n**Threat Details**:")
            for t in threats[:10]:  # Show max 10
                title = t.get("title", "Unknown")
                t_severity = t.get("severity", "UNKNOWN")
                file = t.get("file", "")
                line = t.get("line", "")
                location = f"{file}:{line}" if file and line else (file or "")

                lines.append(f"  - [{t_severity}] {title}")
                if location:
                    lines.append(f"    Location: {location}")

    lines.append("\n---")
    lines.append("\n## Judgment Criteria")
    lines.append("\n### False Positive Characteristics (Allow Installation):")
    lines.append("- Skill description contains workflow design, development tools, quality control")
    lines.append("- Standard document structure, template files")
    lines.append("- Test code, example code")
    lines.append("- Normal Python/JavaScript code structure")

    lines.append("\n### Confirmed Threat Characteristics (Should Uninstall):")
    lines.append("- Obvious malicious code (e.g., eval/exec concatenating user input)")
    lines.append("- Attack payloads (e.g., shell command injection patterns)")
    lines.append("- Sensitive data theft (e.g., uploading local files to external servers)")
    lines.append("- Network backdoors, reverse shells")
    lines.append("- Cryptocurrency mining code")

    lines.append("\n## Action Recommendations")
    lines.append("\nFor confirmed threat skills, please execute:")
    lines.append("```bash")
    for threat in threatened_skills:
        lines.append(f"python bin/skill_manager.py uninstall {threat['name']}")
    lines.append("```")

    return "\n".join(lines)


# =============================================================================
# Main Command Line Interface
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

  # Batch install all skills from repository
  python bin/skill_manager.py install https://github.com/user/repo --batch

  # Search skills (keyword)
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
        help="Enable colored output (default is plain text)"
    )

    # search command
    search_parser = subparsers.add_parser("search", help="Search skills (keyword/description/tag)")
    search_parser.add_argument(
        "keywords",
        nargs="+",
        help="Search keywords (supports multiple keywords, AND logic)"
    )
    search_parser.add_argument(
        "--limit", "-l",
        type=int,
        default=10,
        help="Number of results to return (default 10)"
    )
    search_parser.add_argument(
        "--score", "-s",
        action="store_true",
        help="Show match scores"
    )

    # formats command
    formats_parser = subparsers.add_parser("formats", help="List supported skill formats")

    # uninstall command - uninstall skill (sync database)
    uninstall_parser = subparsers.add_parser("uninstall", help="Uninstall skill and sync database state")
    uninstall_parser.add_argument(
        "name",
        nargs="+",
        help="Skill name (supports multiple, space-separated)"
    )
    uninstall_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force deletion without confirmation"
    )

    # install command - unified installation interface
    install_parser = subparsers.add_parser("install", help="Unified installation interface (supports all formats)")
    install_parser.add_argument(
        "source",
        help="Installation source (GitHub URL, local directory, .skill package)"
    )
    install_parser.add_argument(
        "--batch", "-b",
        action="store_true",
        help="Batch install all skills from repository"
    )
    install_parser.add_argument(
        "--skill", "-s",
        dest="skill_name",
        help="Specify sub-skill name to install (for multi-skill repositories)"
    )
    install_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force installation (skip non-skill repository detection, overwrite existing skills)"
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

    # record command - record skill usage
    record_parser = subparsers.add_parser("record", help="Record skill usage (for search weighting)")
    record_parser.add_argument(
        "name",
        help="Skill name"
    )

    # cache command - repository cache management (route to clone_manager)
    cache_parser = subparsers.add_parser("cache", help="Repository cache management")
    cache_subparsers = cache_parser.add_subparsers(dest="cache_command", help="Cache operations")

    cache_subparsers.add_parser("list", help="List all caches")

    clear_cache_parser = cache_subparsers.add_parser("clear", help="Clear cache")
    clear_cache_parser.add_argument(
        "--older-than", type=int,
        help="Only clear caches older than specified hours"
    )

    update_cache_parser = cache_subparsers.add_parser("update", help="Update specified repository cache")
    update_cache_parser.add_argument("url", help="GitHub repository URL")

    # verify-config command
    verify_parser = subparsers.add_parser("verify-config", help="Verify configuration file")
    verify_parser.add_argument(
        "--fix",
        action="store_true",
        help="Automatically fix common configuration issues"
    )

    args = parser.parse_args()

    # =============================================================================
    # Execute Commands
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
            score_str = f" ({result['score']} points)" if args.score else ""
            print(f"  {i}. {result['name']}{score_str}")

            if args.score:
                print(f"     Match reasons: {', '.join(result['reasons'])}")

            desc_short = result['description'][:60] + "..." if len(result['description']) > 60 else result['description']
            print(f"     {desc_short}\n")

        return 0

    elif args.command == "formats":
        header("Supported Skill Formats")

        print(f"Total {len(SUPPORTED_FORMATS)} formats:\n")

        for fmt_id, fmt_data in SUPPORTED_FORMATS.items():
            # Format ID and name
            print(f"  {fmt_id}")
            print(f"     Name: {fmt_data['name']}")

            # Recognition markers
            markers = fmt_data.get('markers', [])
            if markers:
                print(f"     Recognition markers: {', '.join(markers)}")

            # Handler status
            handler = fmt_data.get('handler')
            if handler:
                print("     Status: Custom handler")
            else:
                print(f"     Status: Built-in handling")

            print()

        print("Tip: Encounter unsupported format?")
        print("See contribution guide: docs/skill-formats-contribution-guide.md")

        return 0

    elif args.command == "uninstall":
        header("Skill Uninstaller")

        # Normalize skill names to lowercase (fix case mismatch issues)
        skill_names = [name.lower() for name in args.name]
        success_count = 0
        failed_list = []

        # Phase 1: Batch query folder_name (single DB connection)
        to_uninstall = []  # [(skill_name, folder_name, skill_dir)]
        with db_connection() as (db, Skill):
            if db:
                for skill_name in skill_names:
                    folder_name = None
                    try:
                        result = db.get(Skill.folder_name == skill_name) or db.get(Skill.name == skill_name)
                        if result:
                            folder_name = result.get("folder_name")
                    except Exception:
                        pass

                    if not folder_name:
                        folder_name = skill_name

                    skill_dir = CLAUDE_SKILLS_DIR / folder_name
                    if not skill_dir.exists():
                        error(f"Skill does not exist: {skill_name} (searching directory: {folder_name})")
                        failed_list.append(skill_name)
                    else:
                        to_uninstall.append((skill_name, folder_name, skill_dir))

        # Phase 2: Delete files
        success_folders = []  # Record successfully deleted folder names
        for skill_name, folder_name, skill_dir in to_uninstall:
            # Confirm deletion
            if not args.force:
                print(f"About to delete skill: {skill_name}")
                print(f"Path: {skill_dir}")
                print("Deleting...")

            try:
                # Read-only file handler (Windows compatible)
                def _remove_readonly(func, path, excinfo):
                    """Handle Windows read-only file deletion issues"""
                    import os
                    os.chmod(path, 0o777)
                    func(path)

                shutil.rmtree(skill_dir, onerror=_remove_readonly)
                success_folders.append(folder_name)
            except Exception as e:
                error(f"Deletion failed: {skill_name} - {e}")
                failed_list.append(skill_name)

        # Phase 3: Batch delete from DB (single connection)
        if success_folders:
            db_results = SkillInstaller.batch_remove_from_db(success_folders)
            for folder_name, db_success in db_results.items():
                if db_success:
                    success(f"Deleted: {folder_name} (database synced)")
                    success_count += 1
                else:
                    warn(f"File deleted but database sync failed: {folder_name}")
                    # File deleted, count as success even if DB failed
                    success_count += 1

        # Summary results
        print()
        # If any skills successfully deleted, invalidate search index cache
        if success_count > 0:
            SkillSearcher.invalidate_cache()
            # Update skills mapping table
            try:
                import subprocess
                result = subprocess.run(
                    [sys.executable, str(BASE_DIR / "bin" / "update_skills_mapping.py")],
                    cwd=BASE_DIR,
                    capture_output=True,
                    timeout=30
                )
                if result.returncode == 0:
                    info("Skills mapping table synced and updated")
                else:
                    warn(f"Mapping table update failed: {result.stderr.decode()[:100]}")
            except subprocess.TimeoutExpired:
                warn("Mapping table update timeout")
            except Exception as e:
                warn(f"Mapping table update failed: {e}")
        info(f"Batch deletion complete: success {success_count}/{len(skill_names)}")
        if failed_list:
            error(f"Failed: {', '.join(failed_list)}")
            return 1
        return 0

    elif args.command == "install":
        header("Skill Installer")

        # 1. Detect input type
        input_type, input_source, subpath = FormatDetector.detect_input_type(args.source)
        info(f"Input type: {input_type}")

        temp_dir = TEMP_DIR / f"installer_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        skills_to_process = []
        scan_results = None
        threatened_skills = []

        # 2. For GitHub sources, need to use independent tool first
        if input_type == "github":
            error("GitHub source needs to be processed by independent tool, please follow these steps:")
            print()
            print("Step 1: Clone repository")
            print(f"  python bin/clone_manager.py clone {input_source}")
            print()
            print("Step 2: Security scan (optional)")
            print(f"  python bin/security_scanner.py scan-all")
            print()
            print("Step 3: Install skills")
            print(f"  python bin/skill_manager.py install <local_path>")
            print()
            return 1

        else:
            # Non-GitHub source, use traditional processing method
            skills_to_process, error_msg = _process_input_source(
                input_source, input_type, temp_dir, args.skill_name,
                args.batch, subpath,
                force_refresh=getattr(args, "refresh_cache", False)
            )
            if error_msg:
                error(f"{error_msg}, exiting")
                return 1

        if not skills_to_process:
            error("No skills to process")
            return 1

        # 2.5 Extract GitHub info (prefer command line arguments)
        github_author = getattr(args, "author", None)
        github_repo = getattr(args, "repo", None)
        if not github_author and input_type == "github":
            github_author, github_repo = SkillInstaller._extract_github_info(str(input_source))
            info(f"GitHub: {github_author}/{github_repo}")

        # Output processing info
        if args.skill_name:
            info(f"Installing specified sub-skill: {args.skill_name}")
        elif len(skills_to_process) == SINGLE_SKILL_THRESHOLD:
            info(f"Found 1 skill, auto-installing")
        else:
            info(f"Detected {len(skills_to_process)} skills, auto-batch installing")

        # 3. Process each skill (format conversion)
        converted_skills = []

        for skill_dir in skills_to_process:
            skill_name = skill_dir.name
            info(f"\nProcessing skill: {skill_name}")

            # Validate if subdirectory is a skill directory
            should_install, skip_reason = ProjectValidator.validate_subdirectory(skill_dir, args.force)
            if not should_install:
                warn(f"Skip: {skill_name} - {skip_reason}")
                continue

            # Detect format
            format_type, markers = FormatDetector.detect_skill_format(skill_dir)
            info(f"Detected format: {format_type}")

            # Official format installs directly, other formats need conversion
            if format_type == "official":
                info("Official format, installing directly")
                target_dir = temp_dir / "processed" / skill_name
                shutil.copytree(skill_dir, target_dir)
                converted_skills.append(target_dir)
            else:
                info("Needs conversion")
                target_dir = temp_dir / "processed" / skill_name
                convert_ok, msg = SkillNormalizer.convert_to_official_format(skill_dir, target_dir)
                if convert_ok:
                    success(msg)
                    converted_skills.append(target_dir)
                else:
                    error(msg)

        # 4. Install all skills
        if converted_skills:
            info(f"\nInstalling {len(converted_skills)} skills...")

            results = batch_install(converted_skills, args.force, github_author, github_repo, scan_results=scan_results)

            # Print results
            if results.get("success"):
                print()
                print(f"Successfully installed ({len(results['success'])}):")
                for item in results["success"]:
                    print(f"  [OK] {item['name']}")

            if results.get("skipped"):
                print()
                print(f"Skipped ({len(results['skipped'])}):")
                for item in results["skipped"]:
                    print(f"  - {item['name']}: {item['message']}")

            if results.get("failed"):
                print()
                print(f"Failed ({len(results['failed'])}):")
                for item in results["failed"]:
                    print(f"  [X] {item['name']}: {item['message']}")

            # Handle threatened skills (need secondary analysis)
            if results.get("threatened_skills"):
                print()
                print(f"! Security scan found {len(results['threatened_skills'])} threatened skills, installed but require LLM secondary analysis")

        # 5. Clean up temporary files
        old_cleaned = cleanup_old_install_dirs(max_age_hours=24)
        if old_cleaned > 0:
            info(f"Cleaned {old_cleaned} old temporary directories")

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
                info(f"Cleaned temporary files")
            except Exception as e:
                warn(f"Failed to clean temporary files: {e}")

        # 6. Summary
        header("Installation Complete")
        print(f"Installation source: {args.source}")
        print(f"Skills processed: {len(skills_to_process)}")
        print(f"Successfully installed: {len(results.get('success', []))}")

        # 7. Update skills mapping table (only when there are successful installations)
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
                    info("Skills mapping table synced and updated")
                else:
                    warn(f"Mapping table update failed: {result.stderr.decode()[:100]}")
            except subprocess.TimeoutExpired:
                warn("Mapping table update timeout")
            except Exception as e:
                warn(f"Mapping table update failed: {e}")

        return 0

    elif args.command == "record":
        SkillSearcher.record_usage(args.name)
        success(f"Recorded usage: {args.name}")
        return 0

    elif args.command == "cache":
        # cache command has been migrated to clone_manager
        error("cache command has been migrated to clone_manager")
        print()
        print("Please use the following commands:")
        print(f"  python bin/clone_manager.py list-cache")
        print(f"  python bin/clone_manager.py clear-cache")
        print(f"  python bin/clone_manager.py clone <url> --force")
        print()
        return 1

    elif args.command == "verify-config":
        header("Configuration Verification")

        result = {
            "valid": True,
            "issues": [],
            "fixed": []
        }

        config_file = BASE_DIR / "config.json"

        # Check if configuration file exists
        if not config_file.exists():
            result["valid"] = False
            result["issues"].append("Configuration file does not exist: config.json")

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
                result["fixed"].append("Created default configuration file")

        # Verify configuration content
        else:
            try:
                config = load_config(use_cache=False)

                # Check required fields
                required_sections = ["git", "raw"]
                for section in required_sections:
                    if section not in config:
                        result["issues"].append(f"Missing configuration section: {section}")
                        result["valid"] = False

                # Check proxies format
                if "git" in config and "proxies" in config["git"]:
                    proxies = config["git"]["proxies"]
                    if not isinstance(proxies, list) or not proxies:
                        result["issues"].append("git.proxies must be a non-empty list")
                        result["valid"] = False

                        if getattr(args, 'fix', False):
                            config["git"]["proxies"] = [
                                "https://ghp.ci/{repo}",
                                "https://ghproxy.net/{repo}"
                            ]
                            result["fixed"].append("Fixed git.proxies")

                # If there are fixes, write back to file
                if getattr(args, 'fix', False) and result["fixed"]:
                    with open(config_file, "w", encoding="utf-8") as f:
                        json.dump(config, f, indent=2, ensure_ascii=False)
                    result["valid"] = True

            except Exception as e:
                result["valid"] = False
                result["issues"].append(f"Configuration parsing failed: {e}")

        if result["valid"]:
            success("Configuration file is valid")
        else:
            error("Configuration file has issues")

        if result["issues"]:
            print("\nIssues found:")
            for issue in result["issues"]:
                print(f"  [!] {issue}")

        if result["fixed"]:
            print("\nFixed:")
            for fix in result["fixed"]:
                print(f"  [OK] {fix}")

        return 0 if result["valid"] else 1

    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())

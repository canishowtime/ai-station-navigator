#!/usr/bin/env python3
"""
skill_manager.py - Skill Manager (技能管理器)
----------------------------------------------
技能的安装、卸载、转换和验证管理

职责：
1. 格式检测 - 检测输入技能的格式类型（GitHub/本地/.skill包）
2. 标准化转换 - 将非标准格式转换为官方 SKILL.md 格式
3. 结构验证 - 验证转换后的技能结构完整性
4. 自动安装 - 复制到 .claude/skills/ 并验证可用性
5. 自动卸载 - 删除技能并同步数据库状态

Architecture:
    Kernel (AI) → Skill Manager → Format Detector → Normalizer → Installer

Source: Inspired by Anthropic's skill-creator (Apache 2.0)
https://github.com/anthropics/skills/tree/main/skills/skill-creator

v1.0 - Feature Complete:
    - 支持多种输入源（GitHub URL、本地目录、.skill 包）
    - 自动检测和修复常见格式问题
    - 批量转换支持
    - 完整的验证流程
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

# TinyDB for database operations
try:
    from tinydb import TinyDB, Query
    from tinydb.storages import JSONStorage
    TINYDB_AVAILABLE = True
except ImportError:
    TINYDB_AVAILABLE = False

# =============================================================================
# 配置常量
# =============================================================================

BASE_DIR = Path(__file__).parent.parent
CLAUDE_SKILLS_DIR = BASE_DIR / ".claude" / "skills"
TEMP_DIR = BASE_DIR / "mybox" / "temp"
SKILLS_DB_FILE = BASE_DIR / ".claude" / "skills" / "skills.db"

# 官方技能标准
REQUIRED_FIELDS = ["name", "description"]
SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
MAX_NAME_LENGTH = 64
MAX_DESC_LENGTH = 1024

# 处理阈值常量
SINGLE_SKILL_THRESHOLD = 1          # 单技能判断阈值
FRONTMATTER_PREVIEW_LINES = 10      # frontmatter 预览行数
LIST_DESC_PREVIEW_CHARS = 500       # 列表命令描述预览字符数

# =============================================================================
# 格式注册表 (Format Registry)
# =============================================================================
# 添加新格式支持时，在此处注册格式处理器
# 详细说明见: docs/skill-formats-contribution-guide.md

SUPPORTED_FORMATS = {
    "official": {
        "name": "Claude Code Official",
        "markers": ["SKILL.md"],
        "handler": None,  # 官方格式直接处理
    },
    "claude-plugin": {
        "name": "Claude Plugin",
        "markers": [".claude-plugin", "plugin.json", "marketplace.json"],
        "handler": None,  # 内置处理
    },
    "agent-skills": {
        "name": "Anthropic Agent Skills",
        "markers": ["skills/", "SKILL.md"],
        "handler": None,  # 内置处理
    },
    "cursor-rules": {
        "name": "Cursor Rules",
        "markers": [".cursor", "rules/"],
        "handler": None,  # 内置处理
    },
    "plugin-marketplace": {
        "name": "Plugin Marketplace",
        "markers": ["plugins/", "MARKETPLACE.md"],
        "handler": None,  # 内置处理
    },
    # 新格式在这里添加，例如:
    # "cursor-plugin": {
    #     "name": "Cursor Plugin",
    #     "markers": ["package.json"],
    #     "handler": CursorPluginHandler,
    # },
}

# 兼容性：保留旧的标记字典
THIRD_PARTY_MARKERS = {
    fmt: data["markers"] for fmt, data in SUPPORTED_FORMATS.items()
    if fmt != "official"
}


# =============================================================================
# 临时目录清理工具
# =============================================================================

def cleanup_old_install_dirs(max_age_hours: int = 24) -> int:
    """
    清理超过指定时间的 installer_* 临时目录

    Args:
        max_age_hours: 最大保留时间（小时），默认 24 小时

    Returns:
        清理的目录数量
    """
    if not TEMP_DIR.exists():
        return 0

    cleaned_count = 0
    current_time = time.time()
    max_age_seconds = max_age_hours * 3600

    # 查找所有 installer_* 目录
    installer_dirs = list(TEMP_DIR.glob("installer_*"))

    for install_dir in installer_dirs:
        if not install_dir.is_dir():
            continue

        try:
            # 检查目录年龄
            dir_age = current_time - install_dir.stat().st_mtime
            if dir_age > max_age_seconds:
                shutil.rmtree(install_dir, ignore_errors=True)
                cleaned_count += 1
                info(f"清理旧临时目录: {install_dir.name}")
        except Exception as e:
            warn(f"清理失败 {install_dir.name}: {e}")

    return cleaned_count


# =============================================================================
# 日志工具
# =============================================================================

class Colors:
    """终端颜色代码"""
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def log(level: str, message: str, emoji: str = ""):
    """统一日志输出"""
    timestamp = datetime.now().strftime("%H:%M:%S")

    color_map = {
        "OK": Colors.OKGREEN,
        "INFO": Colors.OKCYAN,
        "WARN": Colors.WARNING,
        "ERROR": Colors.FAIL,
    }

    color = color_map.get(level, "")
    reset = Colors.ENDC if color else ""

    try:
        print(f"{color}[{timestamp}] {emoji} [{level}]{reset} {message}")
    except Exception:
        print(f"[{timestamp}] [{level}] {message}")


def success(msg: str):
    log("OK", msg, "[OK]")


def info(msg: str):
    log("INFO", msg, "[i]")


def warn(msg: str):
    log("WARN", msg, "[!]")


def error(msg: str):
    log("ERROR", msg, "[X]")


def header(msg: str):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{msg.center(60)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")


# =============================================================================
# 格式检测器
# =============================================================================

class FormatDetector:
    """检测技能输入源的格式类型"""

    @staticmethod
    def parse_github_subpath(github_url: str) -> Tuple[str, Optional[str]]:
        """
        解析 GitHub URL，提取子路径

        支持格式:
        - https://github.com/user/repo
        - https://github.com/user/repo/tree/main/subdir
        - https://github.com/user/repo/tree/branch/path/to/skills

        Returns:
            (仓库URL, 子路径)
            子路径示例: "scientific-skills", "path/to/skills"
        """
        parsed = urlparse(github_url)
        path_parts = parsed.path.strip('/').split('/')

        # 查找 /tree/ 分隔符
        if 'tree' in path_parts:
            tree_idx = path_parts.index('tree')
            if tree_idx >= 2:  # user/repo/tree/...
                # 仓库部分: user/repo
                repo_url = f"{parsed.scheme}://{parsed.netloc}/{'/'.join(path_parts[:tree_idx])}"
                # 子路径: tree/branch/后面的所有部分
                if len(path_parts) > tree_idx + 2:  # 至少有 branch/subdir
                    subpath = '/'.join(path_parts[tree_idx + 2:])
                    return repo_url, subpath
                # 只有 branch，没有子路径
                return repo_url, None

        # 没有 /tree/，返回原 URL
        return github_url, None

    @staticmethod
    def detect_input_type(input_source: str) -> Tuple[str, str, Optional[str]]:
        """
        检测输入源类型

        Returns:
            (类型, 路径/URL, 子路径)
            类型: 'github', 'local', 'skill-package', 'unknown'
            路径/URL: 统一返回字符串（避免 Windows Path 类型处理 URL 问题）
            子路径: GitHub 仓库的子目录路径（如 "scientific-skills"）
        """
        info(f"检测输入源: {input_source}")

        # 1. 检查是否是 GitHub URL
        if input_source.startswith(("http://", "https://")):
            parsed = urlparse(input_source)
            if "github.com" in parsed.netloc:
                repo_url, subpath = FormatDetector.parse_github_subpath(input_source)
                if subpath:
                    info(f"检测到子路径: {subpath}")
                return "github", repo_url, subpath

        # 1.5 检查是否是 GitHub 简写 (user/repo)
        if "/" in input_source and not input_source.startswith((".", "/", "\\")):
            parts = input_source.split("/")
            if len(parts) == 2 and not any(c in input_source for c in ":\\"):
                # 可能是 user/repo 格式
                return "github", f"https://github.com/{input_source}", None

        # 2. 检查是否是本地路径
        local_path = Path(input_source).expanduser().resolve()
        if local_path.exists():
            if local_path.is_file() and local_path.suffix == ".skill":
                return "skill-package", str(local_path), None
            elif local_path.is_dir():
                return "local", str(local_path), None

        # 3. 检查是否是相对路径
        relative_path = BASE_DIR / input_source
        if relative_path.exists():
            if relative_path.is_file() and relative_path.suffix == ".skill":
                return "skill-package", str(relative_path), None
            elif relative_path.is_dir():
                return "local", str(relative_path), None

        warn("无法识别输入源类型，尝试作为本地目录处理")
        return "unknown", input_source, None


    @staticmethod
    def detect_skill_format(skill_dir: Path) -> Tuple[str, List[str]]:
        """
        检测技能目录的格式类型

        Returns:
            (格式类型, 检测到的标记文件)
            格式: 'official', 'claude-plugin', 'agent-skills', 'cursor-rules', 'unknown'
        """
        detected_markers = []

        # 检查官方格式
        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            with open(skill_md, "r", encoding="utf-8", errors="ignore") as f:
                first_lines = "".join([f.readline() for _ in range(FRONTMATTER_PREVIEW_LINES)])
                if "---" in first_lines and "name:" in first_lines:
                    return "official", ["SKILL.md"]

        # 检查第三方格式标记
        for format_type, markers in THIRD_PARTY_MARKERS.items():
            found = []
            for marker in markers:
                marker_path = skill_dir / marker
                if marker_path.exists():
                    found.append(marker)
            if found:
                return format_type, found

        # 检查是否有 markdown 文件（可能是旧格式）
        md_files = list(skill_dir.glob("*.md"))
        if md_files:
            return "unknown-md", [f.name for f in md_files]

        return "unknown", []


# =============================================================================
# 项目验证器 - 检测是否为技能仓库
# =============================================================================

class ProjectValidator:
    """验证项目是否为技能仓库，而非工具/应用程序"""

    # 技能仓库的正面指示（根目录）- 优先检查
    SKILL_REPO_INDICATORS = [
        ("SKILL.md", "根目录有 SKILL.md 文件"),
        ("_has_skills_dir", "skills/ 目录包含多个技能"),  # 特殊标记
        (".claude/skills", "Anthropic 官方技能仓库结构"),
        # .skill 包文件（可能有多个，用 glob 检查）
    ]

    # 技能包仓库指示（包含 .skill 文件）
    SKILL_PACKAGE_EXTENSIONS = [".skill"]

    # 工具项目的指示文件（根目录）
    TOOL_PROJECT_FILES = [
        "setup.py",        # Python 包配置
        "setup.cfg",       # Python 包配置
        "Cargo.toml",      # Rust 项目
        "go.mod",          # Go 项目
    ]

    # 需要进一步检查的文件（可能是技能或工具）
    AMBIGUOUS_PROJECT_FILES = [
        "pyproject.toml",  # 可能是技能打包，也可能是工具
        "package.json",    # 可能是技能，也可能是 Node.js 项目
    ]

    # 工具组件目录名（不是技能）
    TOOL_COMPONENT_NAMES = {
        "api", "cli", "src", "lib", "core", "utils", "common",
        "scripts", "tools", "bin", "build", "dist", "target",
        "tests", "test", "testing", "spec", "specs",
        "docs", "doc", "documentation", "examples",
        "migrations", "seed", "config", "configs",
        "assets", "static", "public", "templates",
        "packages",  # monorepo 工具项目
        ".git", ".github", ".vscode", ".idea",
    }

    # 非技能项目的关键词（在 README 中检测）
    NON_SKILL_KEYWORDS = [
        "convert documentation to skill",
        "convert docs to skill",
        "documentation scraper",
        "skill generator",
        "skill builder",
        "generates skills",
        "creates skills",
        "tool for generating",
        "tool for creating",
        "install via pip",
        "python package",
        "python utility",
        "lightweight python",
        "command-line interface",
        "cli tool",
        "pypi.org",
    ]

    # 技能项目的正面指示词（README）
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
        判断根目录是否是技能仓库

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
        判断子目录是否是技能目录

        Returns:
            (is_skill, reason)
        """
        dirname = subdir.name.lower()

        # 1. 检查是否是工具组件目录
        if dirname in ProjectValidator.TOOL_COMPONENT_NAMES:
            return False, f"目录名是工具组件: {dirname}"

        # 2. 检查是否有 SKILL.md（最明确的技能标志）
        if (subdir / "SKILL.md").exists():
            return True, "包含 SKILL.md 文件"

        # 3. 检查是否是 Python 包目录（有 __init__.py 但无 SKILL.md）
        if (subdir / "__init__.py").exists():
            return False, "Python 包目录（无 SKILL.md）"

        # 4. 检查目录名格式：技能名通常是 kebab-case
        if not re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", dirname):
            return False, f"目录名不符合技能命名规范: {dirname}"

        # 5. 检查是否有 .md 文件（可能是技能内容）
        md_files = list(subdir.glob("*.md"))
        if not md_files:
            return False, "没有找到 markdown 文件"

        # 默认：可能是技能
        return True, ""

    @staticmethod
    def _read_readme(directory: Path) -> str:
        """读取 README 文件内容"""
        for readme_name in ["README.md", "README.txt", "README.rst", "readme.md"]:
            readme_path = directory / readme_name
            if readme_path.exists():
                return readme_path.read_text(encoding="utf-8", errors="ignore")
        return ""

    @staticmethod
    def validate_root_repo(repo_dir: Path, repo_name: str, force: bool = False) -> bool:
        """
        验证根仓库是否是技能仓库

        Returns:
            bool - True 表示继续，False 表示中止
        """
        is_skill, reason = ProjectValidator.is_skill_repo_root(repo_dir)

        if not is_skill:
            print(f"\n{Colors.WARNING}{'='*60}{Colors.ENDC}")
            print(f"{Colors.WARNING}❌ 拒绝安装：这不是技能项目{Colors.ENDC}")
            print(f"{Colors.WARNING}{'='*60}{Colors.ENDC}")
            print(f"\n{Colors.FAIL}检测原因: {Colors.ENDC}{reason}")
            print(f"{Colors.OKBLUE}仓库: {Colors.ENDC}{repo_name}")

            print(f"\n{Colors.HEADER}系统不支持安装工具项目。{Colors.ENDC}")
            print(f"{Colors.HEADER}请确认：{Colors.ENDC}")
            print(f"  1. 是否为工具/库？请使用 pip/npm/cargo 等安装")
            print(f"  2. 确实需要作为技能？请手动转换后安装")

            return False

        return True

    @staticmethod
    def validate_subdirectory(subdir: Path, force: bool = False) -> Tuple[bool, str]:
        """
        验证子目录是否是技能目录

        Returns:
            (should_install, skip_reason)
        """
        is_skill, reason = ProjectValidator.is_skill_directory(subdir)

        if not is_skill and not force:
            return False, reason

        return True, ""


# =============================================================================
# 技能标准化器
# =============================================================================

class SkillNormalizer:
    """将各种格式标准化为官方 SKILL.md 格式"""

    @staticmethod
    def validate_skill_name(name: str) -> Tuple[bool, str]:
        """验证技能名称是否符合规范"""
        if not name:
            return False, "技能名称不能为空"

        if len(name) > MAX_NAME_LENGTH:
            return False, f"技能名称过长（最多 {MAX_NAME_LENGTH} 字符）"

        if not SKILL_NAME_PATTERN.match(name):
            return False, "技能名称必须是小写字母、数字和连字符，不能以连字符开头或结尾"

        return True, ""


    @staticmethod
    def validate_description(desc: str) -> Tuple[bool, str]:
        """验证描述是否符合规范"""
        if not desc:
            return False, "描述不能为空"

        if len(desc) > MAX_DESC_LENGTH:
            return False, f"描述过长（最多 {MAX_DESC_LENGTH} 字符）"

        # 检查是否包含潜在的 HTML 标签（更精确的模式）
        # 允许单独的 < 和 > 字符（如 >5, C++, <3），但拒绝 <tag> 格式
        if re.search(r'<[^>]+>', desc):
            return False, "描述不能包含 HTML 标签"

        return True, ""


    @staticmethod
    def normalize_skill_name(original_name: str) -> str:
        """将任意名称标准化为 hyphen-case 格式"""
        # 移除特殊字符，转为小写，用连字符连接
        normalized = re.sub(r"[^a-zA-Z0-9]+", "-", original_name).strip("-").lower()
        # 移除开头的数字
        if normalized and normalized[0].isdigit():
            normalized = "skill-" + normalized
        return normalized or "unnamed-skill"


    @staticmethod
    def extract_frontmatter(content: str) -> Dict[str, Any]:
        """从 SKILL.md 提取 YAML frontmatter"""
        frontmatter = {}

        if not content.startswith("---"):
            return frontmatter

        # 找到第二个 ---
        end_marker = content.find("\n---", 4)
        if end_marker == -1:
            return frontmatter

        # 使用 yaml.safe_load 安全解析
        yaml_content = content[4:end_marker]
        try:
            frontmatter = yaml.safe_load(yaml_content) or {}
        except yaml.YAMLError as e:
            warn(f"YAML 解析失败: {e}")
            return {}

        # 确保返回 dict
        return frontmatter if isinstance(frontmatter, dict) else {}


    @staticmethod
    def fix_frontmatter(skill_dir: Path) -> Tuple[bool, str]:
        """
        修复 SKILL.md 的 frontmatter

        Returns:
            (是否需要修复, 修复后的内容或错误信息)
        """
        skill_md = skill_dir / "SKILL.md"

        if not skill_md.exists():
            return False, "SKILL.md 不存在"

        with open(skill_md, "r", encoding="utf-8") as f:
            content = f.read()

        frontmatter = SkillNormalizer.extract_frontmatter(content)

        # 检查必需字段
        needs_fix = False
        if "name" not in frontmatter:
            # 使用文件夹名作为 name
            folder_name = skill_dir.name
            normalized_name = SkillNormalizer.normalize_skill_name(folder_name)
            frontmatter["name"] = normalized_name
            needs_fix = True

        if "description" not in frontmatter:
            # 尝试从内容中提取描述
            desc = SkillNormalizer._extract_description_from_content(content)
            frontmatter["description"] = desc
            needs_fix = True

        if not needs_fix:
            # 验证现有字段
            valid, msg = SkillNormalizer.validate_skill_name(frontmatter.get("name", ""))
            if not valid:
                warn(f"技能名称无效: {msg}，自动修复")
                frontmatter["name"] = SkillNormalizer.normalize_skill_name(skill_dir.name)
                needs_fix = True

            valid, msg = SkillNormalizer.validate_description(frontmatter.get("description", ""))
            if not valid:
                warn(f"描述无效: {msg}，自动修复")
                frontmatter["description"] = "技能描述（请手动完善）"
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
        """从内容中提取描述"""
        lines = content.split("\n")

        # 跳过 frontmatter
        start_idx = 0
        for i, line in enumerate(lines):
            if line.strip() == "---" and i > 0:
                start_idx = i + 1
                break

        # 查找第一个标题或段落
        for i in range(start_idx, min(start_idx + 10, len(lines))):
            line = lines[i].strip()
            if line and not line.startswith("#"):
                # 返回第一个非空行作为描述（限制长度）
                return line[:200] + "..." if len(line) > 200 else line

        return "自动生成的技能描述，请手动完善"


    @staticmethod
    def convert_to_official_format(source_dir: Path, target_dir: Path) -> Tuple[bool, str]:
        """
        将第三方格式转换为官方格式

        Returns:
            (成功, 消息)
        """
        info(f"转换技能: {source_dir.name}")

        # 1. 检测格式
        format_type, markers = FormatDetector.detect_skill_format(source_dir)
        info(f"检测到格式: {format_type}")

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
            # Cursor Rules 格式
            SkillNormalizer._convert_cursor_rules(source_dir, target_dir)
        else:
            # 未知格式，尝试通用转换
            SkillNormalizer._convert_generic(source_dir, target_dir)

        # 4. 修复 frontmatter
        needs_fix, new_content = SkillNormalizer.fix_frontmatter(target_dir)
        if needs_fix:
            info("修复 SKILL.md frontmatter")
            with open(target_dir / "SKILL.md", "w", encoding="utf-8") as f:
                f.write(new_content)

        return True, f"转换完成: {target_dir.name}"


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
        """通用转换（未知格式）"""
        # 查找 SKILL.md 或 README.md
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
        """从内容创建 SKILL.md"""
        normalized_name = SkillNormalizer.normalize_skill_name(name)

        # 提取描述（第一段）
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
        """创建默认的 SKILL.md"""
        name = SkillNormalizer.normalize_skill_name(source.name)

        content = f"""---
name: {name}
description: "从 {source.name} 自动转换的技能，请手动完善描述"
---

# {name.replace('-', ' ').title()}

## Overview

此技能从第三方来源自动转换而来，请根据实际功能完善此文档。

## Conversion Info

- **来源名称**: {source.name}
- **转换时间**: {datetime.now().isoformat()}
- **状态**: 需要手动完善

## Usage

请添加使用说明...

## Resources

列出相关资源...
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
        """从 plugin.json 生成 SKILL.md"""
        try:
            with open(plugin_json, "r", encoding="utf-8") as f:
                plugin_data = json.load(f)

            name = SkillNormalizer.normalize_skill_name(
                plugin_data.get("name", target.parent.name)
            )
            description = plugin_data.get("description", "自动生成的技能描述")

            content = f"""---
name: {name}
description: "{description}"
---

# {name.replace('-', ' ').title()}

## Overview

{plugin_data.get("description", "")}

## Installation

此技能已自动转换并安装。

## Configuration

{plugin_data.get("configuration", "无特殊配置")}

## Usage

请添加使用说明...
"""

            with open(target / "SKILL.md", "w", encoding="utf-8") as f:
                f.write(content)

        except Exception as e:
            warn(f"解析 plugin.json 失败: {e}")
            SkillNormalizer._create_default_skill_md(plugin_json.parent.parent, target)


# =============================================================================
# 技能安装器
# =============================================================================


class UTF8JSONStorage(JSONStorage):
    """自定义 JSONStorage，强制使用 UTF-8 编码（修复 Windows GBK 问题）"""

    def __init__(self, path, **kwargs):
        # 强制使用 UTF-8 编码
        kwargs['encoding'] = 'utf-8'
        super().__init__(path, **kwargs)

    def read(self):
        """读取数据（已由父类使用 UTF-8 处理）"""
        return super().read()

    def write(self, data):
        """写入数据（已由父类使用 UTF-8 处理）"""
        return super().write(data)


class SkillInstaller:
    """将转换后的技能安装到 .claude/skills/"""

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
    def _init_db():
        """初始化数据库连接"""
        if not TINYDB_AVAILABLE:
            return None, None
        try:
            SKILLS_DB_FILE.parent.mkdir(parents=True, exist_ok=True)
            db = TinyDB(SKILLS_DB_FILE, storage=UTF8JSONStorage)
            return db, Query()
        except Exception as e:
            warn(f"数据库初始化失败: {e}")
            return None, None

    @staticmethod
    def _parse_frontmatter(content: str) -> Dict:
        """解析 YAML frontmatter"""
        if not content.startswith('---'):
            return {}

        end = content.find('---', 3)
        if end <= 0:
            return {}

        frontmatter_str = content[3:end].strip()

        # 尝试 YAML
        try:
            import yaml
            return yaml.safe_load(frontmatter_str) or {}
        except ImportError:
            pass

        # 手动解析
        result = {}
        for line in frontmatter_str.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                result[key.strip()] = value.strip().strip('"').strip("'")
        return result

    @staticmethod
    def _extract_from_local_skill(skill_name: str) -> Optional[Dict]:
        """从本地 SKILL.md 提取完整元数据"""
        skill_path = CLAUDE_SKILLS_DIR / skill_name
        skill_md = skill_path / "SKILL.md"

        if not skill_md.exists():
            return None

        try:
            content = skill_md.read_text(encoding='utf-8')
            frontmatter = SkillInstaller._parse_frontmatter(content)

            # 提取描述（如果 frontmatter 没有）
            description = frontmatter.get("description", "")
            if not description:
                # 从内容第一段提取
                lines = content.split('\n')
                for line in lines[10:30]:  # 跳过 frontmatter
                    line = line.strip()
                    if line and not line.startswith('#'):
                        description = line[:100]
                        break

            return {
                "id": skill_name.lower().replace('_', '-'),
                "name": frontmatter.get("name", skill_name),
                "folder_name": skill_name,
                "description": description or f"{skill_name} 技能",
                "category": frontmatter.get("category", "utilities"),
                "tags": frontmatter.get("tags", ["skill"]),
                "keywords_cn": [],
                "parent": "",
                "parent_repo": "",
                "repo": "",
                "stars": "",
                "install": f".claude/skills/{skill_name}",
                "source_file": "auto_created",
                "search_index": f"{skill_name} {frontmatter.get('category', '')} {' '.join(frontmatter.get('tags', ['skill']))}".lower(),
                "last_updated": datetime.now().strftime("%Y-%m-%d"),
                "synced_at": datetime.now().strftime("%Y-%m-%d"),
            }
        except Exception as e:
            warn(f"提取技能元数据失败: {e}")
            return None

    @staticmethod
    def _sync_skill_to_db(skill_name: str) -> bool:
        """将技能同步到数据库（原子操作）"""
        if not TINYDB_AVAILABLE:
            warn("TinyDB 不可用，跳过数据库同步")
            return False

        db, Skill = SkillInstaller._init_db()
        if db is None:
            return False

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
        if not TINYDB_AVAILABLE:
            return False

        db, Skill = SkillInstaller._init_db()
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
    def install(skill_dir: Path, force: bool = False, author: Optional[str] = None, repo: Optional[str] = None) -> Tuple[bool, str]:
        """
        安装技能到 .claude/skills/

        Args:
            skill_dir: 技能目录
            force: 是否强制覆盖
            author: GitHub 作者名（用于构建 folder_name）
            repo: GitHub 仓库名（用于构建 folder_name）

        Returns:
            (成功, 消息)
        """
        # 优先从 SKILL.md 读取 name，其次使用目录名
        skill_name_from_md = SkillInstaller._get_skill_name_from_md(skill_dir)

        if skill_name_from_md and author:
            # GitHub 源: 使用 author-repo-name 格式
            repo_part = f"-{repo}" if repo else ""
            skill_name = f"{author}{repo_part}-{skill_name_from_md}"
        elif skill_name_from_md:
            # 有 SKILL.md 但无 author
            skill_name = skill_name_from_md
        else:
            # 无 SKILL.md，回退到目录名
            skill_name = skill_dir.name

        # 1. 验证技能结构
        is_valid, msg = SkillInstaller._validate_skill_structure(skill_dir)
        if not is_valid:
            return False, f"验证失败: {msg}"

        # 2. 检查是否已存在
        target_dir = CLAUDE_SKILLS_DIR / skill_name
        if target_dir.exists():
            if not force:
                return False, f"技能已存在: {skill_name}（使用 --force 覆盖）"
            warn(f"覆盖已存在的技能: {skill_name}")
            shutil.rmtree(target_dir)

        # 3. 安装（原子操作：文件 + 数据库）
        try:
            # 3.1 复制文件
            shutil.copytree(skill_dir, target_dir)

            # 3.2 同步数据库
            db_sync_success = SkillInstaller._sync_skill_to_db(skill_name)
            if db_sync_success:
                success(f"安装成功: {skill_name} (数据库已同步)")
            else:
                # 数据库同步失败，回滚文件操作
                shutil.rmtree(target_dir)
                return False, f"数据库同步失败，安装已回退: {skill_name}"

            return True, f"已安装到: {target_dir}"
        except Exception as e:
            # 清理可能残留的文件
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            return False, f"安装失败: {e}"


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

        # 验证字段值
        valid, msg = SkillNormalizer.validate_skill_name(frontmatter["name"])
        if not valid:
            return False, f"name 验证失败: {msg}"

        valid, msg = SkillNormalizer.validate_description(frontmatter["description"])
        if not valid:
            return False, f"description 验证失败: {msg}"

        # 检查 name 是否与文件夹名一致
        if frontmatter["name"] != skill_dir.name:
            warn(f"技能名称与文件夹名不一致: {frontmatter['name']} != {skill_dir.name}")

        return True, ""


    @staticmethod
    def batch_install(skill_dirs: List[Path], force: bool = False, author: Optional[str] = None, repo: Optional[str] = None) -> Dict[str, Any]:
        """批量安装技能"""
        results = {
            "success": [],
            "failed": [],
            "skipped": [],
        }

        for skill_dir in skill_dirs:
            install_ok, msg = SkillInstaller.install(skill_dir, force, author, repo)
            # 解析实际安装的技能名（从 msg 中提取）
            installed_name = skill_dir.name
            if "安装成功: " in msg:
                installed_name = msg.split("安装成功: ")[1].split("\n")[0].strip()

            if install_ok:
                results["success"].append({"name": installed_name, "message": msg})
            else:
                if "已存在" in msg and not force:
                    results["skipped"].append({"name": installed_name, "message": msg})
                else:
                    results["failed"].append({"name": installed_name, "message": msg})

        return results


# =============================================================================
# 配置加载（共享）
# =============================================================================

_config_cache: Optional[dict] = None
_config_mtime: Optional[float] = None


def load_config(use_cache: bool = True) -> dict:
    """
    加载配置文件（支持缓存）

    Args:
        use_cache: 是否使用缓存（默认 True）
    """
    global _config_cache, _config_mtime

    config_file = BASE_DIR / "config.json"
    if not config_file.exists():
        return {}

    # 检查文件是否被修改
    current_mtime = config_file.stat().st_mtime
    if use_cache and _config_cache is not None and _config_mtime == current_mtime:
        return _config_cache

    # 重新加载配置
    with open(config_file, "r", encoding="utf-8") as f:
        _config_cache = json.load(f)
        _config_mtime = current_mtime
    return _config_cache


def clear_config_cache() -> None:
    """清除配置缓存（用于测试或配置更新后）"""
    global _config_cache, _config_mtime
    _config_cache = None
    _config_mtime = None


def get_git_proxies() -> list:
    """获取 git 加速器列表"""
    config = load_config()
    return config.get("git", {}).get("proxies", [])


def get_ssl_verify() -> bool:
    """获取 SSL 验证设置"""
    config = load_config()
    return config.get("git", {}).get("ssl_verify", True)


def get_raw_proxies() -> list:
    """获取 raw 文件加速器列表"""
    config = load_config()
    return config.get("raw", {}).get("proxies", [])


# =============================================================================
# Quick Fetcher - 快速文件获取器（用于 info 命令）
# =============================================================================

class QuickFetcher:
    """快速获取 GitHub 文件内容（不克隆仓库）"""

    def __init__(self, repo: str, branch: str = "main"):
        """
        Args:
            repo: user/repo 格式
            branch: 分支名，默认 main
        """
        self.repo = repo
        self.branch = branch
        self.raw_base = "https://raw.githubusercontent.com"
        self.proxies = get_raw_proxies()

    def fetch_file(self, file_path: str) -> Optional[str]:
        """
        获取文件内容 - 优先使用加速器，失败回退源站

        Args:
            file_path: 文件路径（如 "SKILL.md" 或 "skills/doc-coauthoring/SKILL.md"）

        Returns:
            文件内容字符串，失败返回 None
        """
        path = f"{self.repo}/{self.branch}/{file_path}"

        # 1. 尝试加速器
        for proxy_template in self.proxies:
            proxy_url = proxy_template.replace("{path}", path)
            try:
                result = subprocess.run(
                    ["curl", "-s", "--max-time", "30", proxy_url],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False
                )
                if result.returncode == 0 and result.stdout:
                    content = result.stdout
                    # 检查 404
                    if not content or "404: Not Found" in content or "<title>404" in content:
                        continue
                    return content
            except Exception:
                continue

        # 2. 回退到原始地址
        raw_url = f"{self.raw_base}/{path}"
        try:
            result = subprocess.run(
                ["curl", "-s", "--max-time", "30", raw_url],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False
            )
            if result.returncode == 0:
                content = result.stdout
                if not content or "404: Not Found" in content or "<title>404" in content:
                    return None
                return content
        except Exception as e:
            if "404" not in str(e):
                warn(f"获取文件失败 {file_path}: {e}")

        return None


# =============================================================================
# Remote Skill Analyzer - 远程技能仓库分析器
# =============================================================================

class RemoteSkillAnalyzer:
    """分析远程 GitHub 仓库的技能信息"""

    def __init__(self, repo: str):
        """
        Args:
            repo: user/repo 格式
        """
        self.repo = repo
        self.fetcher = None

    def analyze(self) -> Dict[str, Any]:
        """
        分析仓库，返回技能信息

        Returns:
            {
                "repo": "user/repo",
                "branch": "main",
                "skills": [
                    {
                        "name": "skill-name",
                        "folder": "folder/name",
                        "description": "...",
                        "category": "...",
                        "tags": [...],
                        "url": "https://github.com/...",
                        "is_root": False
                    },
                    ...
                ]
            }
        """
        result = {
            "repo": self.repo,
            "branch": "main",
            "skills": []
        }

        # 1. 尝试检测默认分支（通过尝试获取根目录 SKILL.md）
        branches_to_try = ["main", "master"]
        found_branch = None

        for branch in branches_to_try:
            self.fetcher = QuickFetcher(self.repo, branch)
            # 尝试获取 SKILL.md
            content = self.fetcher.fetch_file("SKILL.md")
            if content:
                found_branch = branch
                break

        if not found_branch:
            # 尝试通过目录结构判断
            self.fetcher = QuickFetcher(self.repo, "main")
            tree = self._get_tree_structure()
            if tree:
                found_branch = "main"
            else:
                # 尝试 master
                self.fetcher = QuickFetcher(self.repo, "master")
                tree = self._get_tree_structure()
                if tree:
                    found_branch = "master"

        if not found_branch:
            return result

        result["branch"] = found_branch

        # 2. 检测技能结构
        skills = []

        # 检测是否是 Plugin Marketplace 格式
        marketplace_readme = self.fetcher.fetch_file("MARKETPLACE.md")
        plugins_tree = self._get_tree_structure()
        has_plugins_dir = any(item["path"].startswith("plugins/") for item in plugins_tree) if plugins_tree else False

        if marketplace_readme or has_plugins_dir:
            # Plugin Marketplace 格式
            plugin_packages = self._parse_plugin_marketplace()
            for pkg in plugin_packages:
                pkg["url"] = f"https://github.com/{self.repo}/tree/main/plugins/{pkg['name']}"
                pkg["is_root"] = False
            skills.extend(plugin_packages)
            result["format"] = "plugin-marketplace"
        else:
            # 标准格式检测
            # 检查根目录是否有 SKILL.md（单技能或多技能容器）
            root_skill = self.fetcher.fetch_file("SKILL.md")
            if root_skill:
                # 根目录有 SKILL.md
                root_info = self._parse_skill_md(root_skill, "")
                if root_info:
                    # 检查是否有子技能
                    tree = self._get_tree_structure()
                    sub_skills = self._find_sub_skills(tree) if tree else []

                    if sub_skills:
                        # 多技能容器
                        root_info["is_root"] = True
                        root_info["url"] = f"https://github.com/{self.repo}"
                        skills.append(root_info)

                        # 并发获取子技能
                        sub_skill_infos = self._fetch_sub_skills_concurrent(sub_skills, found_branch)
                        skills.extend(sub_skill_infos)
                    else:
                        # 单技能
                        root_info["is_root"] = True
                        root_info["url"] = f"https://github.com/{self.repo}"
                        skills.append(root_info)
            else:
                # 根目录无 SKILL.md，并发查找子技能
                tree = self._get_tree_structure()
                if tree:
                    sub_skills = self._find_sub_skills(tree)
                    sub_skill_infos = self._fetch_sub_skills_concurrent(sub_skills, found_branch)
                    skills.extend(sub_skill_infos)

        result["skills"] = skills
        return result

    def _get_tree_structure(self) -> Optional[List[Dict]]:
        """
        获取目录树结构

        Returns:
            文件列表 [{"path": "...", "type": "blob|tree"}, ...]
        """
        import urllib.request

        api_url = f"https://api.github.com/repos/{self.repo}/git/trees/{self.fetcher.branch}?recursive=1"

        # 尝试从 config 加载 token
        config = load_config()
        access_token = config.get("github_access_token", "")

        headers = {"Accept": "application/vnd.github.v3+json"}
        if access_token:
            headers["Authorization"] = f"token {access_token}"

        try:
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())

            if "tree" in data:
                # 只返回前 2 层，减少数据量
                result = []
                for item in data["tree"]:
                    depth = item["path"].count("/")
                    if depth <= 2:
                        result.append({
                            "path": item["path"],
                            "type": item["type"]
                        })
                return result
        except Exception as e:
            warn(f"获取目录树失败: {e}")

        return None

    def _find_sub_skills(self, tree: List[Dict]) -> List[str]:
        """
        从目录树中查找子技能路径

        Returns:
            SKILL.md 路径列表（如 ["skills/doc-coauthoring/SKILL.md"]）
        """
        skill_paths = []
        for item in tree:
            if item["type"] == "blob" and item["path"].endswith("SKILL.md"):
                # 排除根目录的 SKILL.md
                if "/" in item["path"]:
                    skill_paths.append(item["path"])

        return sorted(skill_paths)

    def _parse_skill_md(self, content: str, file_path: str) -> Optional[Dict]:
        """
        解析 SKILL.md 内容

        Args:
            content: SKILL.md 内容
            file_path: 文件路径（用于提取 folder）

        Returns:
            技能信息字典
        """
        frontmatter = SkillNormalizer.extract_frontmatter(content)

        name = frontmatter.get("name", "")
        if not name:
            # 从 file_path 提取名称
            if file_path:
                folder = file_path.rsplit("/", 1)[0] if "/" in file_path else ""
                name = folder.split("/")[-1] if folder else ""
            if not name:
                name = "unknown"

        return {
            "name": name,
            "folder": file_path.rsplit("/", 1)[0] if "/" in file_path else "",
            "description": frontmatter.get("description", "无描述"),
            "category": frontmatter.get("category", "utilities"),
            "tags": frontmatter.get("tags", ["skill"])
        }

    def _fetch_sub_skills_concurrent(self, sub_paths: List[str], branch: str) -> List[Dict]:
        """
        并发获取多个子技能的 SKILL.md 内容

        Args:
            sub_paths: SKILL.md 文件路径列表
            branch: 分支名

        Returns:
            技能信息字典列表
        """
        skills = []

        def fetch_and_parse(sub_path: str) -> Optional[Dict]:
            """获取并解析单个技能"""
            content = self.fetcher.fetch_file(sub_path)
            if content:
                info = self._parse_skill_md(content, sub_path)
                if info:
                    info["is_root"] = False
                    info["url"] = f"https://github.com/{self.repo}/tree/{branch}/{sub_path.rsplit('/', 1)[0]}"
                    return info
            return None

        # 使用线程池并发获取，max_workers=7 限制并发数
        with concurrent.futures.ThreadPoolExecutor(max_workers=7) as executor:
            futures = {executor.submit(fetch_and_parse, path): path for path in sub_paths}
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result:
                    skills.append(result)

        return sorted(skills, key=lambda x: x["name"])

    def _parse_plugin_marketplace(self) -> List[Dict]:
        """
        解析 Plugin Marketplace 格式的仓库

        Returns:
            插件包列表 [{"name": "...", "description": "...", "category": "..."}, ...]
        """
        plugin_packages = []

        # 获取 README.md 来解析插件包信息
        readme_content = self.fetcher.fetch_file("README.md")
        if not readme_content:
            return plugin_packages

        lines = readme_content.split("\n")
        in_plugin_list = False

        for i, line in enumerate(lines):
            # 检测 "Available Plugin Categories:" 部分
            if "**Available Plugin Categories:**" in line or "Available Plugin Categories:" in line:
                in_plugin_list = True
                continue

            # 如果到达下一个部分，停止解析
            if in_plugin_list and line.startswith("## ") and "Categories" not in line:
                break

            # 检测插件包列表项（格式：- `package-name` - description）
            if in_plugin_list:
                plugin_match = re.match(r'^-\s`([a-z-]+)`\s+-\s+(.+)$', line)
                if plugin_match:
                    plugin_name = plugin_match.group(1)
                    description = plugin_match.group(2).strip()

                    plugin_packages.append({
                        "name": plugin_name,
                        "description": description[:100],
                        "category": "Plugin Package",
                        "type": "plugin-package"
                    })

        return plugin_packages


# =============================================================================
# GitHub 处理器
# =============================================================================

class GitHubHandler:
    """处理 GitHub 仓库的克隆和提取"""

    @staticmethod
    def clone_repo(github_url: str, target_dir: Path) -> Tuple[bool, Path]:
        """
        克隆 GitHub 仓库（支持加速器）

        Returns:
            (成功, 克隆目录)
        """
        info(f"克隆仓库: {github_url}")

        target_dir.mkdir(parents=True, exist_ok=True)

        # 构建基础 git 命令
        cmd = ["git"]
        if not get_ssl_verify():
            cmd.extend(["-c", "http.sslVerify=false"])

        # 尝试加速器
        proxies = get_git_proxies()
        for proxy_template in proxies:
            # 将 URL 转换为加速器 URL
            repo_path = github_url.replace("https://github.com/", "").replace("http://github.com/", "")
            proxy_url = proxy_template.replace("{repo}", repo_path)

            try:
                clone_cmd = cmd + ["clone", "--depth", "1", proxy_url, str(target_dir)]
                result = subprocess.run(
                    clone_cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=300,
                )

                if result.returncode == 0:
                    success(f"克隆成功（使用加速器）: {target_dir}")
                    return True, target_dir
            except subprocess.TimeoutExpired:
                warn(f"加速器超时: {proxy_url}")
                continue
            except Exception as e:
                warn(f"加速器异常: {e}")
                continue

        # 回退到原始地址
        try:
            clone_cmd = cmd + ["clone", "--depth", "1", github_url, str(target_dir)]
            result = subprocess.run(
                clone_cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,
            )

            if result.returncode == 0:
                success(f"克隆成功: {target_dir}")
                return True, target_dir
            else:
                error(f"克隆失败: {result.stderr}")
                return False, target_dir

        except subprocess.TimeoutExpired:
            error("克隆超时")
            return False, target_dir
        except Exception as e:
            error(f"克隆异常: {e}")
            return False, target_dir


    @staticmethod
    def extract_skills(repo_dir: Path) -> List[Path]:
        """从仓库中提取所有技能目录

        智能识别：
        1. 优先检测 .skill 包文件（技能包仓库）
        2. 当检测到多平台版本时，优先选择 Claude Code 版本
        3. 过滤掉 examples/templates 等非技能目录
        """
        skill_dirs = []

        # 排除目录列表（非技能目录）
        exclude_dirs = {"examples", "templates", "test", "tests", "docs", "reference"}

        # 第零轮：检测 .skill 包文件（技能包仓库）
        skill_packages = list(repo_dir.glob("*.skill"))
        if skill_packages:
            info(f"检测到技能包文件: {skill_packages[0].name}")
            # 解压 .skill 包到临时目录
            extract_dir = repo_dir.parent / f"{repo_dir.name}_extracted"
            extract_ok, extracted = SkillPackHandler.extract_pack(skill_packages[0], extract_dir)
            if extract_ok:
                skill_dirs.append(extracted)
            return skill_dirs

        # 平台优先级配置（高到低）
        # Claude Code 官方路径优先，其次是通用路径
        platform_priority = [
            repo_dir / ".agent" / "skills",   # Claude Code (最高优先级)
            repo_dir / ".claude" / "skills",   # ClaudeKit 多技能仓库
            repo_dir / "skills",               # 通用技能目录
            repo_dir / ".claude-plugin",       # Claude Plugin
            repo_dir / ".cursor" / "rules",    # Cursor
            repo_dir,                          # 根目录
        ]

        # 第一轮：检测是否有 Claude Code 版本
        claude_code_skills = []
        agent_skills_dir = repo_dir / ".agent" / "skills"
        if agent_skills_dir.exists():
            for item in agent_skills_dir.glob("*/SKILL.md"):
                # 排除非技能目录
                if item.parent.name not in exclude_dirs:
                    claude_code_skills.append(item.parent)

        # 如果找到 Claude Code 版本，优先使用
        if claude_code_skills:
            return claude_code_skills

        # 第二轮：按优先级扫描其他位置
        for location in platform_priority[1:]:  # 跳过 .agent（已检查）
            if location.exists() and location.is_dir():
                # 特殊处理1：根目录直接包含 SKILL.md（单技能或多技能容器）
                if location == repo_dir:
                    if (location / "SKILL.md").exists():
                        # 检测是否为"多技能容器"（包含多个子技能）
                        sub_skill_dirs = [
                            item.parent for item in repo_dir.glob("*/SKILL.md")
                            if item.parent.name not in exclude_dirs
                        ]
                        # 阈值：3 个及以上子技能判定为多技能容器
                        MULTI_SKILL_THRESHOLD = 3
                        if len(sub_skill_dirs) >= MULTI_SKILL_THRESHOLD:
                            info(f"检测到多技能容器: {repo_dir.name} (包含 {len(sub_skill_dirs)} 个子技能)")
                            skill_dirs.extend(sub_skill_dirs)
                        else:
                            # 单技能，添加容器目录
                            skill_dirs.append(location)
                        continue
                    else:
                        # 根目录没有 SKILL.md：检查是否为 monorepo（子目录包含技能）
                        # 特殊检查 skills/ 目录（常见于 monorepo）
                        skills_dir = repo_dir / "skills"
                        if skills_dir.exists() and skills_dir.is_dir():
                            sub_skill_count = 0
                            sub_skill_candidates = []
                            for item in skills_dir.iterdir():
                                if item.is_dir() and (item / "SKILL.md").exists():
                                    sub_skill_candidates.append(item)
                                    sub_skill_count += 1
                            # skills/ 目录有 1+ 个技能就认为是 monorepo
                            if sub_skill_count >= 1:
                                info(f"检测到 monorepo: skills/ 目录包含 {sub_skill_count} 个技能")
                                skill_dirs.extend(sub_skill_candidates)
                                continue
                        # 检查根目录子目录是否包含技能（2+ 个判定为 monorepo）
                        root_sub_skills = []
                        for item in repo_dir.iterdir():
                            if item.is_dir() and not item.name.startswith(".") and item.name not in exclude_dirs:
                                if (item / "SKILL.md").exists():
                                    root_sub_skills.append(item)
                        if len(root_sub_skills) >= 2:
                            info(f"检测到 monorepo: 根目录包含 {len(root_sub_skills)} 个子技能")
                            skill_dirs.extend(root_sub_skills)
                            continue

                # 特殊处理2：检查是否为多技能容器子目录（如 skills/）
                # 注意：如果是 skills/ 目录，且已在"特殊处理1"中处理过，跳过
                if location.name == "skills" and location.parent == repo_dir:
                    continue
                # 检测子目录下是否包含 3+ 个技能（多技能容器）
                sub_skill_count = 0
                sub_skill_candidates = []
                for item in location.iterdir():
                    if item.is_dir() and item.name not in exclude_dirs:
                        if (item / "SKILL.md").exists():
                            sub_skill_count += 1
                            sub_skill_candidates.append(item)

                MULTI_SKILL_THRESHOLD = 3
                if sub_skill_count >= MULTI_SKILL_THRESHOLD:
                    info(f"检测到多技能子目录: {location.name} (包含 {sub_skill_count} 个子技能)")
                    skill_dirs.extend(sub_skill_candidates)
                    continue

                for item in location.iterdir():
                    # 允许 .claude 目录（多技能仓库结构），跳过其他隐藏目录
                    if item.is_dir() and (not item.name.startswith(".") or item.name == ".claude"):
                        # 排除非技能目录
                        if item.name in exclude_dirs:
                            continue
                        # 检查是否包含 SKILL.md 或 .md 文件
                        has_skill = (item / "SKILL.md").exists() or list(item.glob("*.md"))
                        if has_skill:
                            skill_dirs.append(item)

        # 回退机制：如果未找到技能，检查是否有子目录包含 SKILL.md（支持任意结构的 monorepo）
        if not skill_dirs:
            fallback_skills = []
            for item in repo_dir.iterdir():
                if item.is_dir() and not item.name.startswith(".") and item.name not in exclude_dirs:
                    if (item / "SKILL.md").exists():
                        fallback_skills.append(item)
            if fallback_skills:
                info(f"回退检测: 发现 {len(fallback_skills)} 个子技能")
                skill_dirs.extend(fallback_skills)

        return skill_dirs


# =============================================================================
# 共享逻辑 (Shared Logic)
# =============================================================================

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
        for skill_dir in skill_dirs:
            if skill_dir.name == skill_name:
                return [skill_dir], None
        available = [s.name for s in skill_dirs]
        return [], f"未找到子技能: {skill_name}，可用: {available}"

    if len(skill_dirs) == SINGLE_SKILL_THRESHOLD or batch:
        # 只有 1 个技能 或 用户指定批量 → 处理所有
        return skill_dirs, None

    # 有多个技能且未指定批量 → 自动批量处理（兼容现有行为）
    return skill_dirs, None


def _process_github_source(
    github_url: str,
    temp_dir: Path,
    skill_name: Optional[str] = None,
    batch: bool = False,
    subpath: Optional[str] = None
) -> Tuple[List[Path], Optional[str]]:
    """
    统一的 GitHub 源处理逻辑

    Args:
        github_url: GitHub 仓库 URL
        temp_dir: 临时目录
        skill_name: 指定的子技能名称
        batch: 是否批量处理
        subpath: 仓库内的子路径（如 "scientific-skills"）

    Returns:
        (待处理的技能列表, 错误信息)
    """
    # 克隆仓库
    clone_ok, repo_dir = GitHubHandler.clone_repo(github_url, temp_dir / "repo")
    if not clone_ok:
        return [], "克隆失败"

    # 如果有子路径，定位到子目录
    scan_dir = repo_dir
    if subpath:
        scan_dir = repo_dir / subpath
        if not scan_dir.exists():
            return [], f"子路径不存在: {subpath}"
        info(f"定位到子路径: {subpath}")

    # 提取所有技能
    skill_dirs = GitHubHandler.extract_skills(scan_dir)
    if not skill_dirs:
        # 只有在没有子路径时才检查根目录是否为工具项目
        # 如果指定了子路径，说明用户知道技能的具体位置
        if not subpath:
            # 检查是否为工具项目
            is_skill, reason = ProjectValidator.is_skill_repo_root(repo_dir)
            if not is_skill:
                # 输出拒绝信息（复用 validate_root_repo 的逻辑）
                repo_name = github_url.split('/')[-1] if '/' in github_url else github_url
                print(f"\n{Colors.WARNING}{'='*60}{Colors.ENDC}")
                print(f"{Colors.WARNING}❌ 拒绝安装：这不是技能项目{Colors.ENDC}")
                print(f"{Colors.WARNING}{'='*60}{Colors.ENDC}")
                print(f"\n{Colors.FAIL}检测原因: {Colors.ENDC}{reason}")
                print(f"{Colors.OKBLUE}仓库: {Colors.ENDC}{repo_name}")

                print(f"\n{Colors.HEADER}系统不支持安装工具项目。{Colors.ENDC}")
                print(f"{Colors.HEADER}请确认：{Colors.ENDC}")
                print(f"  1. 是否为工具/库？请使用 pip/npm/cargo 等安装")
                print(f"  2. 确实需要作为技能？请手动转换后安装")
                return [], "不是技能项目"
        return [], "未找到技能目录"

    # 根据意图过滤
    return _filter_skills_by_intent(skill_dirs, skill_name, batch)


def _process_input_source(
    input_source: str,
    input_type: str,
    temp_dir: Path,
    skill_name: Optional[str] = None,
    batch: bool = False,
    subpath: Optional[str] = None
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

    Returns:
        (待处理的技能列表, 错误信息)
    """
    if input_type == "github":
        return _process_github_source(input_source, temp_dir, skill_name, batch, subpath)

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
# 技能搜索器
# =============================================================================

class SkillSearcher:
    """技能搜索器 - 支持关键词、描述、标签搜索"""

    @staticmethod
    def search_skills(keywords: List[str], limit: int = 10) -> List[Dict]:
        """
        搜索技能

        Args:
            keywords: 搜索关键词列表
            limit: 返回结果数量

        Returns:
            按相关度排序的技能列表 [(name, score, reasons), ...]
        """
        if not CLAUDE_SKILLS_DIR.exists():
            return []

        results = []
        # 加载使用频率数据
        usage_data = SkillSearcher._load_usage_data()

        for skill_dir in sorted(CLAUDE_SKILLS_DIR.iterdir()):
            if not skill_dir.is_dir():
                continue

            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            # 读取 frontmatter
            with open(skill_md, "r", encoding="utf-8", errors="ignore") as f:
                frontmatter = SkillNormalizer.extract_frontmatter(f.read())

            name = frontmatter.get("name", skill_dir.name)
            description = frontmatter.get("description", "").lower()
            tags = frontmatter.get("tags", [])
            category = frontmatter.get("category", "").lower()
            keywords_cn = frontmatter.get("keywords_cn", [])
            # keywords_cn 可能是字符串或列表
            if isinstance(keywords_cn, str):
                keywords_cn = [k.strip() for k in keywords_cn.split(",") if k.strip()]

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
                    "folder": skill_dir.name,
                    "score": total_score,
                    "reasons": match_reasons,
                    "description": frontmatter.get("description", "无描述")
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
# 主命令行界面
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="技能转换器 - 将第三方技能转换为官方格式并安装",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 搜索技能（关键词）
  python bin/skill_manager.py search prompt

  # 搜索技能（多关键词）
  python bin/skill_manager.py search prompt optimize --score

  # 转换并安装 GitHub 仓库中的技能
  python bin/skill_manager.py convert https://github.com/user/repo

  # 转换本地目录
  python bin/skill_manager.py convert path/to/skill

  # 解压并安装 .skill 包
  python bin/skill_manager.py convert path/to/skill.skill

  # 批量转换（指定仓库中的所有技能）
  python bin/skill_manager.py convert https://github.com/user/repo --batch

  # 强制覆盖已存在的技能
  python bin/skill_manager.py convert https://github.com/user/repo --force

  # 仅转换不安裝（输出到临时目录）
  python bin/skill_manager.py convert https://github.com/user/repo --no-install

  # 验证已安装的技能
  python bin/skill_manager.py validate .claude/skills/my-skill

  # 列出所有已安装技能
  python bin/skill_manager.py list

  # 卸载技能（同步数据库）
  python bin/skill_manager.py uninstall my-skill
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # convert 命令
    convert_parser = subparsers.add_parser("convert", help="转换并安装技能")
    convert_parser.add_argument(
        "input",
        help="输入源（GitHub URL、本地目录、.skill 包）"
    )
    convert_parser.add_argument(
        "--output", "-o",
        type=Path,
        default=TEMP_DIR / "converted_skills",
        help="转换输出目录（默认: mybox/temp/converted_skills）"
    )
    convert_parser.add_argument(
        "--batch", "-b",
        action="store_true",
        help="批量处理（转换所有找到的技能）"
    )
    convert_parser.add_argument(
        "--skill", "-s",
        dest="skill_name",
        help="指定要处理的子技能名称（用于多技能仓库）"
    )
    convert_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="强制覆盖已存在的技能"
    )
    convert_parser.add_argument(
        "--no-install",
        action="store_true",
        help="仅转换，不安装到 .claude/skills/"
    )
    convert_parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="保留临时文件"
    )

    # validate 命令
    validate_parser = subparsers.add_parser("validate", help="验证技能结构")
    validate_parser.add_argument(
        "path",
        type=Path,
        help="技能目录路径"
    )

    # list 命令
    list_parser = subparsers.add_parser("list", help="列出已安装的技能")
    list_parser.add_argument(
        "--color", "-c",
        action="store_true",
        help="启用颜色输出（默认为纯文本）"
    )

    # search 命令
    search_parser = subparsers.add_parser("search", help="搜索技能（关键词/描述/标签）")
    search_parser.add_argument(
        "keywords",
        nargs="+",
        help="搜索关键词（支持多个关键词，AND 逻辑）"
    )
    search_parser.add_argument(
        "--limit", "-l",
        type=int,
        default=10,
        help="返回结果数量（默认 10）"
    )
    search_parser.add_argument(
        "--score", "-s",
        action="store_true",
        help="显示匹配分数"
    )

    # formats 命令
    formats_parser = subparsers.add_parser("formats", help="列出支持的技能格式")

    # uninstall 命令 - 卸载技能（同步数据库）
    uninstall_parser = subparsers.add_parser("uninstall", help="卸载技能并同步数据库状态")
    uninstall_parser.add_argument(
        "name",
        help="技能名称"
    )
    uninstall_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="强制删除，不询问确认"
    )

    # install 命令 - 统一安装接口
    install_parser = subparsers.add_parser("install", help="统一安装接口（支持所有格式）")
    install_parser.add_argument(
        "source",
        help="安装源（GitHub URL、本地目录、.skill 包）"
    )
    install_parser.add_argument(
        "--batch", "-b",
        action="store_true",
        help="批量安装仓库中所有技能"
    )
    install_parser.add_argument(
        "--skill", "-s",
        dest="skill_name",
        help="指定要安装的子技能名称（用于多技能仓库）"
    )
    install_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="强制安装（跳过非技能仓库检测、覆盖已存在的技能）"
    )

    # record 命令 - 记录技能使用
    record_parser = subparsers.add_parser("record", help="记录技能使用（用于搜索加权）")
    record_parser.add_argument(
        "name",
        help="技能名称"
    )

    # info 命令 - 分析远程技能仓库
    info_parser = subparsers.add_parser("info", help="分析远程技能仓库（获取技能信息）")
    info_parser.add_argument(
        "source",
        help="仓库名或 URL（如 anthropics/skills 或 https://github.com/anthropics/skills）"
    )

    args = parser.parse_args()

    # =============================================================================
    # 执行命令
    # =============================================================================

    if args.command == "convert":
        header("技能转换器")

        # 1. 检测输入类型
        input_type, input_source, subpath = FormatDetector.detect_input_type(args.input)
        info(f"输入类型: {input_type}")

        temp_dir = TEMP_DIR / f"converter_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        skills_to_process = []

        # 2. 根据输入类型处理
        skills_to_process, error_msg = _process_input_source(
            input_source,
            input_type,
            temp_dir,
            args.skill_name,
            args.batch,
            subpath
        )

        if error_msg:
            error(f"{error_msg}，退出")
            return 1

        # 2.5 对于 GitHub 仓库，提取 author 和 repo 并检查是否是技能仓库
        github_author = None
        github_repo = None
        if input_type == "github":
            github_author, github_repo = SkillInstaller._extract_github_info(str(input_source))
            info(f"GitHub: {github_author}/{github_repo}")

            # 只有在没有子路径时才验证根目录
            # 如果指定了子路径，说明用户知道技能的具体位置，跳过根目录验证
            if not subpath:
                repo_root = temp_dir / "repo"
                if repo_root.exists():
                    if not ProjectValidator.validate_root_repo(repo_root, args.input, False):
                        error("这不是一个技能仓库，退出")
                        return 1

        # 输出处理信息
        if args.skill_name:
            info(f"处理指定子技能: {args.skill_name}")
        elif len(skills_to_process) == SINGLE_SKILL_THRESHOLD:
            info(f"找到 1 个技能，自动处理")
        else:
            info(f"批量处理: {len(skills_to_process)} 个技能")
            if not args.batch:
                info(f"(使用 --skill <name> 只处理特定子技能)")

        # 3. 转换技能
        output_dir = args.output
        output_dir.mkdir(parents=True, exist_ok=True)

        converted_skills = []

        for skill_dir in skills_to_process:
            skill_name = skill_dir.name
            info(f"\n处理技能: {skill_name}")

            # 验证子目录是否是技能目录
            should_install, skip_reason = ProjectValidator.validate_subdirectory(skill_dir, args.force)
            if not should_install:
                warn(f"跳过: {skill_name} - {skip_reason}")
                continue

            # 转换为官方格式
            target_dir = output_dir / skill_name
            convert_ok, msg = SkillNormalizer.convert_to_official_format(skill_dir, target_dir)

            if convert_ok:
                success(msg)
                converted_skills.append(target_dir)
            else:
                error(msg)

        # 4. 安装技能
        if not args.no_install and converted_skills:
            info(f"\n安装 {len(converted_skills)} 个技能...")

            results = SkillInstaller.batch_install(converted_skills, args.force, github_author, github_repo)

            # 打印结果
            if results["success"]:
                print(f"\n{Colors.OKGREEN}成功安装 ({len(results['success'])}):{Colors.ENDC}")
                for item in results["success"]:
                    print(f"  [OK] {item['name']}")

            if results["skipped"]:
                print(f"\n{Colors.WARNING}跳过 ({len(results['skipped'])}):{Colors.ENDC}")
                for item in results["skipped"]:
                    print(f"  - {item['name']}: {item['message']}")

            if results["failed"]:
                print(f"\n{Colors.FAIL}失败 ({len(results['failed'])}):{Colors.ENDC}")
                for item in results["failed"]:
                    print(f"  [X] {item['name']}: {item['message']}")

        # 5. 清理临时文件
        if not args.keep_temp:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
                info(f"清理临时文件: {temp_dir}")

        # 6. 总结
        header("转换完成")
        print(f"输入源: {args.input}")
        print(f"处理技能数: {len(skills_to_process)}")
        print(f"转换成功: {len(converted_skills)}")
        if not args.no_install:
            print(f"安装成功: {len(results.get('success', []))}")

        return 0

    elif args.command == "validate":
        is_valid, msg = SkillInstaller._validate_skill_structure(args.path)
        if is_valid:
            success(f"验证通过: {args.path}")
            return 0
        else:
            error(f"验证失败: {msg}")
            return 1

    elif args.command == "list":
        # 直接从数据库读取
        skills_data = []
        if SKILLS_DB_FILE.exists():
            with open(SKILLS_DB_FILE, "r", encoding="utf-8") as f:
                db = json.load(f)
                for skill_id, skill in db.get("_default", {}).items():
                    if skill.get("installed", False):
                        skills_data.append(skill)

        use_color = args.color

        if use_color:
            header("已安装技能列表")

        if not skills_data:
            warn("无已安装技能")
            return 0

        print(f"共 {len(skills_data)} 个技能:\n")

        for skill in skills_data:
            name = skill.get("name", "未知")
            desc = skill.get("description", "无描述")
            desc_short = desc[:60] + "..." if len(desc) > 60 else desc

            if use_color:
                print(f"  {Colors.OKGREEN}[OK]{Colors.ENDC} {name}")
                print(f"     {desc_short}")
            else:
                print(f"[OK] {name}")
                print(f"     {desc_short}")

        return 0

    elif args.command == "search":
        header("技能搜索")

        results = SkillSearcher.search_skills(args.keywords, args.limit)

        if not results:
            warn(f"未找到匹配技能: {' '.join(args.keywords)}")
            return 0

        print(f"找到 {len(results)} 个匹配技能:\n")

        for i, result in enumerate(results, 1):
            score_str = f" ({result['score']}分)" if args.score else ""
            print(f"  {Colors.OKGREEN}{i}.{Colors.ENDC} {result['name']}{score_str}")

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
            print(f"  {Colors.OKCYAN}{fmt_id}{Colors.ENDC}")
            print(f"     名称: {fmt_data['name']}")

            # 识别标记
            markers = fmt_data.get('markers', [])
            if markers:
                print(f"     识别标记: {', '.join(markers)}")

            # 处理器状态
            handler = fmt_data.get('handler')
            if handler:
                print(f"     状态: {Colors.OKGREEN}自定义处理器{Colors.ENDC}")
            else:
                print(f"     状态: 内置处理")

            print()

        print(f"{Colors.WARNING}提示:{Colors.ENDC} 遇到不支持的格式？")
        print(f"查看贡献指南: docs/skill-formats-contribution-guide.md")

        return 0

    elif args.command == "uninstall":
        header("技能卸载器")

        skill_name = args.name
        skill_dir = CLAUDE_SKILLS_DIR / skill_name

        # 1. 检查技能是否存在
        if not skill_dir.exists():
            error(f"技能不存在: {skill_name}")
            return 1

        # 2. 确认删除
        if not args.force:
            print(f"{Colors.WARNING}即将删除技能: {skill_name}{Colors.ENDC}")
            print(f"路径: {skill_dir}")
            # 简单确认（非交互环境默认确认）
            print(f"{Colors.OKGREEN}正在删除...{Colors.ENDC}")

        # 3. 删除目录（原子操作：文件 + 数据库）
        try:
            # 3.1 删除文件
            shutil.rmtree(skill_dir)

            # 3.2 从数据库移除
            db_remove_success = SkillInstaller._remove_skill_from_db(skill_name)
            if db_remove_success:
                success(f"已删除: {skill_name} (数据库已同步)")
            else:
                # 数据库操作失败，文件已删除但数据库未更新
                warn(f"文件已删除，但数据库同步失败: {skill_name}")

            return 0
        except Exception as e:
            error(f"删除失败: {e}")
            return 1

    elif args.command == "install":
        header("技能安装器")

        # install 命令 = convert 命令的简化版（总是安装）
        # 1. 检测输入类型
        input_type, input_source, subpath = FormatDetector.detect_input_type(args.source)
        info(f"输入类型: {input_type}")

        temp_dir = TEMP_DIR / f"installer_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        skills_to_process = []

        # 2. 根据输入类型处理
        skills_to_process, error_msg = _process_input_source(
            input_source,
            input_type,
            temp_dir,
            args.skill_name,
            args.batch,
            subpath
        )

        if error_msg:
            error(f"{error_msg}，退出")
            return 1

        # 2.5 对于 GitHub 仓库，提取 author 和 repo 并检查是否是技能仓库
        github_author = None
        github_repo = None
        if input_type == "github":
            github_author, github_repo = SkillInstaller._extract_github_info(str(input_source))
            info(f"GitHub: {github_author}/{github_repo}")

            # 只有在没有子路径时才验证根目录
            # 如果指定了子路径，说明用户知道技能的具体位置，跳过根目录验证
            if not subpath:
                repo_root = temp_dir / "repo"
                if repo_root.exists():
                    if not ProjectValidator.validate_root_repo(repo_root, args.source, False):
                        error("这不是一个技能仓库，退出")
                        return 1

        # 输出处理信息
        if args.skill_name:
            info(f"安装指定子技能: {args.skill_name}")
        elif len(skills_to_process) == SINGLE_SKILL_THRESHOLD:
            info(f"找到 1 个技能，自动安装")
        else:
            # 多技能自动批量安装（无需 --batch 参数）
            info(f"检测到 {len(skills_to_process)} 个技能，自动批量安装")
            if not args.batch:
                info(f"(提示: 使用 --skill <name> 只安装特定子技能)")

        # 3. 处理每个技能
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

            results = SkillInstaller.batch_install(converted_skills, args.force, github_author, github_repo)

            # 打印结果
            if results.get("success"):
                print(f"\n{Colors.OKGREEN}成功安装 ({len(results['success'])}):{Colors.ENDC}")
                for item in results["success"]:
                    print(f"  [OK] {item['name']}")

            if results.get("skipped"):
                print(f"\n{Colors.WARNING}跳过 ({len(results['skipped'])}):{Colors.ENDC}")
                for item in results["skipped"]:
                    print(f"  - {item['name']}: {item['message']}")

            if results.get("failed"):
                print(f"\n{Colors.FAIL}失败 ({len(results['failed'])}):{Colors.ENDC}")
                for item in results["failed"]:
                    print(f"  [X] {item['name']}: {item['message']}")

        # 5. 清理临时文件（Windows 安全处理）
        # 先清理旧的 installer_* 目录
        old_cleaned = cleanup_old_install_dirs(max_age_hours=24)
        if old_cleaned > 0:
            info(f"清理了 {old_cleaned} 个旧临时目录")

        if temp_dir.exists():
            try:
                # Windows: 先尝试删除 .git 目录（可能只读）
                git_dir = temp_dir / "repo" / ".git"
                if git_dir.exists():
                    try:
                        # 递归修改权限后删除
                        for root, dirs, files in os.walk(git_dir):
                            for d in dirs:
                                os.chmod(os.path.join(root, d), 0o777)
                            for f in files:
                                os.chmod(os.path.join(root, f), 0o777)
                        shutil.rmtree(git_dir)
                    except Exception:
                        pass  # 忽略 .git 删除失败
                shutil.rmtree(temp_dir, ignore_errors=True)
                info(f"清理临时文件")
            except Exception as e:
                warn(f"清理临时文件失败: {e}")

        # 6. 总结
        header("安装完成")
        print(f"安装源: {args.source}")
        print(f"处理技能数: {len(skills_to_process)}")
        print(f"安装成功: {len(results.get('success', []))}")

        return 0

    elif args.command == "record":
        SkillSearcher.record_usage(args.name)
        success(f"已记录使用: {args.name}")
        return 0

    elif args.command == "info":
        header("技能仓库分析")

        # 1. 检测输入类型
        input_type, url, subpath = FormatDetector.detect_input_type(args.source)
        info(f"输入类型: {input_type}")

        if input_type != "github":
            error("info 命令仅支持 GitHub 仓库")
            return 1

        # 2. 提取 repo 信息（复用现有函数）
        author, repo_name = SkillInstaller._extract_github_info(url)
        if not author or not repo_name:
            error(f"无法解析仓库地址: {args.source}")
            return 1

        repo = f"{author}/{repo_name}"
        info(f"分析仓库: {repo}")

        # 3. 如果有子路径，附加到 repo
        if subpath:
            info(f"子路径: {subpath}")
            # 对于子路径，我们需要特殊处理
            # 暂时标记为需要手动指定
            print(f"\n{Colors.WARNING}提示: 检测到子路径，建议直接访问:{Colors.ENDC}")
            print(f"  {url}")
            return 0

        # 4. 分析仓库
        analyzer = RemoteSkillAnalyzer(repo)
        result = analyzer.analyze()

        # 5. 输出报告
        print(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
        print(f"{Colors.HEADER}📊 技能仓库分析: {repo}{Colors.ENDC}")
        print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}\n")

        skills = result.get("skills", [])
        if not skills:
            warn(f"未找到技能")
            print(f"\n提示: 访问 {Colors.OKCYAN}https://github.com/{repo}{Colors.ENDC} 查看仓库")
            return 0

        if len(skills) == 1:
            print(f"找到 1 个技能:\n")
        else:
            print(f"找到 {len(skills)} 个技能:\n")

        for i, skill in enumerate(skills, 1):
            name = skill.get("name", "unknown")
            category = skill.get("category", "utilities")
            description = skill.get("description", "无描述")
            url = skill.get("url", f"https://github.com/{repo}")

            print(f"  {Colors.OKGREEN}{i}.{Colors.ENDC} {Colors.BOLD}{name}{Colors.ENDC}")
            print(f"     分类: {category}")
            desc_short = description[:60] + "..." if len(description) > 60 else description
            print(f"     描述: {desc_short}")
            print(f"     建议安装链接: {Colors.OKCYAN}{url}{Colors.ENDC}\n")

        print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}")
        print(f"{Colors.WARNING}提示: 复制链接到浏览器查看，或使用命令安装{Colors.ENDC}")
        print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}")

        return 0

    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())

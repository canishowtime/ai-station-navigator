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

# 添加项目 lib 目录到 sys.path（绿色包预置依赖）
_lib_dir = Path(__file__).parent.parent / "lib"
if _lib_dir.exists():
    sys.path.insert(0, str(_lib_dir))

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
CACHE_DIR = BASE_DIR / "mybox" / "cache" / "repos"

# 官方技能标准
REQUIRED_FIELDS = ["name", "description"]
SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
MAX_NAME_LENGTH = 128
MAX_DESC_LENGTH = 1024

# 处理阈值常量
SINGLE_SKILL_THRESHOLD = 1          # 单技能判断阈值
FRONTMATTER_PREVIEW_LINES = 10      # frontmatter 预览行数
LIST_DESC_PREVIEW_CHARS = 500       # 列表命令描述预览字符数

# 技能默认值常量
DEFAULT_SKILL_DESC = "无描述"       # 默认技能描述
DEFAULT_SKILL_CATEGORY = "utilities"  # 默认分类
DEFAULT_SKILL_TAGS = ["skill"]      # 默认标签

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
                # info(f"清理旧临时目录: {install_dir.name}")  # P0 fix: info() 尚未定义 (L238)
        except Exception:
            pass  # P0 fix: 日志函数尚未定义，静默跳过

    return cleaned_count


# =============================================================================
# 日志工具 (纯文本)
# =============================================================================

def log(level: str, message: str, emoji: str = ""):
    """统一日志输出"""
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
            try:
                with open(skill_md, "r", encoding="utf-8", errors="ignore") as f:
                    first_lines = "".join([f.readline() for _ in range(FRONTMATTER_PREVIEW_LINES)])
                    if "---" in first_lines and "name:" in first_lines:
                        return "official", ["SKILL.md"]
            except (OSError, IOError) as e:
                # P1 fix: 文件读取失败时静默跳过，继续检测其他格式
                pass

        # 检查第三方格式标记
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

    # 工具项目的指示文件（根目录）- 精简到最常见的
    TOOL_PROJECT_FILES = [
        "setup.py",        # Python 包配置
        "Cargo.toml",      # Rust 项目
        "go.mod",          # Go 项目
    ]

    # 需要进一步检查的文件（可能是技能或工具）
    AMBIGUOUS_PROJECT_FILES = [
        "pyproject.toml",  # 可能是技能打包，也可能是工具
        "package.json",    # 可能是技能，也可能是 Node.js 项目
    ]

    # 工具组件目录名（不是技能）- 精简到最常见的
    TOOL_COMPONENT_NAMES = {
        "api", "src", "lib", "core", "utils",
        "scripts", "tools", "bin", "build", "target",
        "tests", "docs", "config",
        ".git", ".github",
    }

    # 非技能项目的关键词（在 README 中检测）- 精简到最常见的
    NON_SKILL_KEYWORDS = [
        "skill generator",
        "generates skills",
        "creates skills",
        "install via pip",
        "command-line interface",
        "cli tool",
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
            print("=" * 60)
            print("❌ 拒绝安装：这不是技能项目")
            print("=" * 60)
            print()
            print(f"检测原因: {reason}")
            print(f"仓库: {repo_name}")
            print()
            print("系统不支持安装工具项目。")
            print("请确认：")
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
        """
        从 SKILL.md 提取 YAML frontmatter

        支持 YAML 解析，失败时降级为手动解析
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


if TINYDB_AVAILABLE:
    class UTF8JSONStorage(JSONStorage):
        """自定义 JSONStorage，强制使用 UTF-8 编码（修复 Windows GBK 问题）"""

        def __init__(self, path, **kwargs):
            # 强制使用 UTF-8 编码
            kwargs['encoding'] = 'utf-8'
            super().__init__(path, **kwargs)
else:
    UTF8JSONStorage = None


# =============================================================================
# 数据库连接管理器
# =============================================================================

from contextlib import contextmanager

@contextmanager
def db_connection():
    """
    数据库连接上下文管理器

    用法:
        with db_connection() as (db, Skill):
            # 使用 db 和 Skill
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
        warn(f"数据库连接失败: {e}")
        yield None, None


# =============================================================================
# 技能安装器
# =============================================================================


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
    def _sync_skill_to_db(skill_name: str) -> bool:
        """将技能同步到数据库（原子操作）"""
        with db_connection() as (db, Skill):
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
            skill_name = f"{author}{repo_part}-{skill_name_from_md}".lower()
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

        # 1.5 验证技能名称安全性
        is_valid, msg = validate_skill_name(skill_name)
        if not is_valid:
            return False, f"技能名称验证失败: {msg}"

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
# Quick Fetcher - 快速文件获取器（用于 info 命令）
# =============================================================================
# Remote Skill Analyzer - 远程技能仓库分析器
# =============================================================================

class RemoteSkillAnalyzer:
    """分析远程 GitHub 仓库的技能信息（统一入口，自动选择最佳探测方式）

    合并了原 QuickFetcher 和 GitHubAPIAnalyzer 的功能：
    - 智能选择：GitHub API (有 token) 或 Raw URL + 加速器
    - 统一预检：check_is_skill_repo() 替代原双路预检
    - 保持规则：总超时 8s，限流不重试，失败降级到 clone
    """

    API_BASE = "https://api.github.com"
    RAW_BASE = "https://raw.githubusercontent.com"

    def __init__(self, repo: str, branch: str = "main", token: Optional[str] = None):
        """
        Args:
            repo: user/repo 格式
            branch: 分支名，默认 main
            token: GitHub personal access token (可选，优先使用环境变量)
        """
        self.repo = repo
        self.branch = branch
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self._use_cache = True  # 是否使用缓存
        self.github_url = f"https://github.com/{repo}"
        # Raw URL 相关
        self.proxies = get_raw_proxies()
        self._cache = {}
        self._working_proxy = None

    def analyze(self) -> Dict[str, Any]:
        """
        分析仓库，返回技能信息

        Returns:
            {
                "repo": "user/repo",
                "branch": "main",
                "skills": [...],
                "source": "cache|network"
            }
        """
        result = {
            "repo": self.repo,
            "branch": "main",
            "skills": [],
            "source": "unknown"
        }

        # 1. 优先检查本地缓存（精确匹配）
        cache_dir = RepoCacheManager._get_cache_dir(self.github_url)
        if cache_dir.exists() and self._use_cache:
            meta = RepoCacheManager.load_meta(cache_dir)
            if meta and meta.get("url") == self.github_url:
                result["source"] = "cache"
                info(f"使用本地缓存分析: {self.repo}")
                return self._analyze_from_cache(cache_dir, result)

        # 1.5. 尝试模糊匹配缓存（处理仓库名变体）
        matched_cache = self._find_fuzzy_cache_match()
        if matched_cache and self._use_cache:
            result["source"] = "cache"
            info(f"使用匹配缓存分析: {self.repo} → {matched_cache.name}")
            return self._analyze_from_cache(matched_cache, result)

        # 2. 缓存不存在，使用网络探测
        result["source"] = "network"
        return self._analyze_from_network(result)

    def _find_fuzzy_cache_match(self) -> Optional[Path]:
        """尝试模糊匹配缓存目录"""
        if not CACHE_DIR.exists():
            return None

        # 提取用户和仓库名
        parts = self.repo.split("/")
        if len(parts) != 2:
            return None

        user, repo_name = parts
        # 标准化仓库名（移除连字符等）
        normalized_repo = repo_name.replace("-", "").replace("_", "")

        # 遍历缓存目录查找匹配
        for cache_dir in CACHE_DIR.iterdir():
            if not cache_dir.is_dir():
                continue

            meta = RepoCacheManager.load_meta(cache_dir)
            if not meta:
                continue

            cached_url = meta.get("url", "")
            # 检查是否是同一用户的仓库
            if f"/{user}/" in cached_url or f"\\{user}\\" in cached_url:
                # 标准化缓存中的仓库名
                cached_repo = cached_url.split("/")[-1].replace("-", "").replace("_", "")
                if cached_repo == normalized_repo:
                    return cache_dir

        return None

    def _analyze_from_cache(self, cache_dir: Path, result: Dict) -> Dict:
        """从本地缓存分析仓库"""
        skills = []

        # 扫描缓存目录，查找所有 SKILL.md
        for skill_md in cache_dir.rglob("SKILL.md"):
            # 获取相对路径
            rel_path = skill_md.relative_to(cache_dir)

            # 读取 SKILL.md
            try:
                with open(skill_md, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                info = self._parse_skill_md(content, str(rel_path.parent))
                if info:
                    # 构造 URL
                    info["url"] = f"{self.github_url}/tree/{result['branch']}/{rel_path.parent}"
                    info["is_root"] = (str(rel_path.parent) == ".")
                    skills.append(info)
            except Exception as e:
                warn(f"读取 {rel_path} 失败: {e}")

        result["skills"] = sorted(skills, key=lambda x: x["name"])
        return result

    def _analyze_from_network(self, result: Dict) -> Dict:
        """通过网络分析仓库"""
        skills = []

        # 1. 检测分支
        branches_to_try = ["main", "master"]
        found_branch = None

        for branch in branches_to_try:
            self.branch = branch  # 更新分支
            if self.fetch_file("SKILL.md") or self.fetch_file("README.md"):
                found_branch = branch
                break

        if not found_branch:
            return result

        result["branch"] = found_branch

        # 2. 检测格式
        marketplace_readme = self.fetch_file("MARKETPLACE.md")

        if marketplace_readme:
            # Plugin Marketplace 格式
            result["format"] = "plugin-marketplace"
            plugin_packages = self._parse_plugin_marketplace()
            for pkg in plugin_packages:
                pkg["url"] = f"{self.github_url}/tree/main/plugins/{pkg['name']}"
                pkg["is_root"] = False
            skills.extend(plugin_packages)
        else:
            # 标准格式：直接探测 SKILL.md 位置
            root_skill_content = self.fetch_file("SKILL.md")

            if root_skill_content:
                # 根目录有 SKILL.md
                root_info = self._parse_skill_md(root_skill_content, "")
                if root_info:
                    root_info["is_root"] = True
                    root_info["url"] = self.github_url
                    skills.append(root_info)

            # 探测子技能：扫描常见目录
            sub_skill_paths = self._discover_skill_paths()

            if sub_skill_paths:
                # 获取子技能信息
                for path in sub_skill_paths:
                    content = self.fetch_file(path)
                    if content:
                        info = self._parse_skill_md(content, path)
                        if info:
                            folder = path.rsplit("/", 1)[0] if "/" in path else ""
                            info["url"] = f"{self.github_url}/tree/{found_branch}/{folder}"
                            info["is_root"] = False
                            skills.append(info)

        result["skills"] = sorted(skills, key=lambda x: x["name"])
        return result

    def _discover_skill_paths(self) -> List[str]:
        """
        探测子技能 SKILL.md 路径

        Returns:
            SKILL.md 路径列表
        """
        skill_paths = []
        checked = set()

        # 定义要探测的常见位置
        patterns = [
            # Plugin Marketplace 格式
            "plugins/{name}/SKILL.md",
            # 子技能目录格式
            "skills/{name}/SKILL.md",
            # 根目录子技能格式
            "{name}/SKILL.md",
        ]

        # 常见技能名称
        common_names = [
            "commit", "review-pr", "pdf", "web-search", "image-analysis",
            "doc-coauthoring", "copywriting", "email-sequence", "popup-cro",
            "translator", "summarizer", "code-run", "terminal"
        ]

        # 从 README 提取可能的目录名
        readme = self.fetch_file("README.md")
        discovered_names = set()

        if readme:
            import re
            links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', readme)
            for name, link in links:
                link = link.strip().lstrip("./").rstrip("/")
                if not link.startswith("http") and "/" in link:
                    dir_name = link.split("/")[0]
                    discovered_names.add(dir_name)

        # 合并探测列表：README 发现的 + 常见名称
        names_to_check = list(discovered_names) + common_names

        # 探测每个可能的路径
        for pattern in patterns:
            for name in names_to_check:
                if "{name}" in pattern:
                    path = pattern.replace("{name}", name)
                else:
                    continue

                if path in checked:
                    continue

                if self.fetch_file(path):
                    skill_paths.append(path)
                    checked.add(path)

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
                folder = file_path.replace("\\", "/").rsplit("/", 1)[-1] if "/" in file_path else ""
                name = folder if folder else "unknown"
            else:
                name = "unknown"

        return {
            "name": name,
            "folder": file_path.replace("\\", "/") if file_path else "",
            "description": frontmatter.get("description", DEFAULT_SKILL_DESC),
            "category": frontmatter.get("category", DEFAULT_SKILL_CATEGORY),
            "tags": frontmatter.get("tags", DEFAULT_SKILL_TAGS.copy())
        }

    def _parse_plugin_marketplace(self) -> List[Dict]:
        """
        解析 Plugin Marketplace 格式的仓库

        Returns:
            插件包列表 [{"name": "...", "description": "...", "category": "..."}, ...]
        """
        plugin_packages = []

        readme_content = self.fetch_file("README.md")
        if not readme_content:
            return plugin_packages

        import re
        lines = readme_content.split("\n")
        in_plugin_list = False

        for line in lines:
            if "**Available Plugin Categories:**" in line or "Available Plugin Categories:" in line:
                in_plugin_list = True
                continue

            if in_plugin_list and line.startswith("## ") and "Categories" not in line:
                break

            if in_plugin_list:
                plugin_match = re.match(r'^-\s`([a-z-]+)`\s+-\s+(.+)$', line)
                if plugin_match:
                    plugin_packages.append({
                        "name": plugin_match.group(1),
                        "description": plugin_match.group(2).strip()[:100],
                        "category": "Plugin Package",
                        "type": "plugin-package"
                    })

        return plugin_packages

    # =============================================================================
    # 统一探测方法 (合并 QuickFetcher + GitHubAPIAnalyzer)
    # =============================================================================

    @staticmethod
    def _validate_url(url: str) -> bool:
        """验证 URL 安全性，防止命令注入"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if parsed.scheme not in ('http', 'https'):
                return False
            if not parsed.netloc:
                return False
            dangerous = [';', '&', '|', '$', '`', '\n', '\r']
            return not any(c in url for c in dangerous)
        except Exception:
            return False

    def fetch_file(self, file_path: str, prefer_api: bool = False) -> Optional[str]:
        """
        获取文件内容 - 自动选择最佳方式

        Args:
            file_path: 文件路径
            prefer_api: 是否优先使用 API (默认 False，优先 Raw)

        Returns:
            文件内容字符串，失败返回 None
        """
        # 检查缓存
        if file_path in self._cache:
            return self._cache[file_path]

        # 策略选择
        if prefer_api and self.token:
            # 有 token，优先 API
            content = self._fetch_via_api(file_path)
            if content is not None:
                self._cache[file_path] = content
                return content

        # 默认使用 Raw URL (带加速器)
        content = self._fetch_via_raw(file_path)
        if content is not None:
            self._cache[file_path] = content
            return content

        # Raw 失败，有 token 则尝试 API
        if self.token and not prefer_api:
            content = self._fetch_via_api(file_path)
            if content is not None:
                self._cache[file_path] = content
                return content

        return None

    def _fetch_via_raw(self, file_path: str) -> Optional[str]:
        """
        通过 Raw URL 获取文件 (支持加速器)

        Returns:
            文件内容，失败返回 None
        """
        path = f"{self.repo}/{self.branch}/{file_path}"

        # 1. 优先使用已知可用代理
        if self._working_proxy:
            proxy_url = self._working_proxy.replace("{path}", path)
            content = self._try_fetch_url(proxy_url)
            if content is not None:
                return content
            self._working_proxy = None

        # 2. 尝试加速器列表
        for proxy_template in self.proxies:
            proxy_url = proxy_template.replace("{path}", path)
            content = self._try_fetch_url(proxy_url)
            if content is not None:
                self._working_proxy = proxy_template
                return content

        # 3. 回退到原始地址
        raw_url = f"{self.RAW_BASE}/{path}"
        return self._try_fetch_url(raw_url)

    def _try_fetch_url(self, url: str) -> Optional[str]:
        """尝试从指定 URL 获取文件"""
        if not self._validate_url(url):
            return None
        try:
            result = subprocess.run(
                ["curl", "-s", "--max-time", "5", "--connect-timeout", "3", url],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False
            )
            if result.returncode == 0 and result.stdout:
                content = result.stdout
                if not content or "404: Not Found" in content or "<title>404" in content:
                    return None
                return content
        except Exception:
            pass
        return None

    def _fetch_via_api(self, file_path: str) -> Optional[str]:
        """
        通过 GitHub API 获取文件

        Returns:
            文件内容，失败或限流返回 None
        """
        url = f"{self.API_BASE}/repos/{self.repo}/contents/{file_path}"
        headers = {"Accept": "application/vnd.github.v3.raw"}
        if self.token:
            headers["Authorization"] = f"token {self.token}"

        cmd = ["curl", "-s", "--max-time", "3", url]
        for k, v in headers.items():
            cmd.extend(["-H", f"{k}: {v}"])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False
            )

            # 检查限流 (限流不重试，直接返回 None)
            if result.returncode == 403:
                if "rate limit exceeded" in result.stdout.lower() or "api rate limit" in result.stdout.lower():
                    return None  # 限流，切换到 Raw
                return None  # 其他 403

            if result.returncode == 200 and result.stdout:
                # 检查是否是 base64 编码
                if result.stdout.startswith("{"):
                    try:
                        import json
                        import base64
                        data = json.loads(result.stdout)
                        if "content" in data:
                            return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
                    except Exception:
                        pass
                return result.stdout
            return None
        except Exception:
            return None

    def check_is_skill_repo(self) -> Tuple[Optional[bool], str]:
        """
        统一的技能仓库预检 (替代原双路预检)

        规则：
        - 总超时：3s (API) + 5s (Raw) = 8s
        - 限流：检测到限流立即切换方式，不重试
        - 重试：0 次
        - 降级：两者都失败 → 返回 None，降级到 clone

        Returns:
            (True, "通过")     → 判定为技能，继续 clone
            (False, "非技能")  → 拒绝安装
            (None, "超时/限流") → 降级到 clone
        """
        # 1. 尝试 GitHub API (3s 超时)
        api_result = self._check_via_api()
        if api_result is not None:
            is_skill, reason = api_result
            if is_skill is False:
                # API 明确判定为非技能
                return False, reason
            # is_skill is True 或 is_skill is None (API 超时/限流)
            # 继续尝试 Raw

        # 2. API 未明确判定非技能，尝试 Raw URL (5s 超时)
        raw_result = self._check_via_raw()
        if raw_result is not None:
            is_skill, reason = raw_result
            if is_skill is True:
                # Raw 判定为技能
                return True, reason
            # Raw 未找到技能标记，但不一定是非技能（可能探测不完整）
            # 继续降级

        # 3. 判决逻辑
        if api_result and api_result[0] is True:
            return True, api_result[1]
        if raw_result and raw_result[0] is True:
            return True, raw_result[1]

        # 4. 两者都未找到明确证据 → 降级
        return None, "预检超时或失败，降级到 clone"

    def _check_via_api(self) -> Optional[Tuple[bool, str]]:
        """通过 API 检查是否为技能仓库"""
        # 1. 检查根目录 SKILL.md
        result = self._api_exists("SKILL.md")
        if result is True:
            return True, "根目录存在 SKILL.md"
        elif result is False:
            # 404，继续检查其他
            pass
        else:
            # 超时/限流
            return None

        # 2. 检查 skills/ 目录
        result = self._api_exists("skills")
        if result is True:
            return True, "存在 skills/ 目录"

        # 3. 检查 .claude/skills
        result = self._api_exists(".claude/skills")
        if result is True:
            return True, "存在 .claude/skills 目录"

        # 4. 检查工具项目文件（判定为非技能）
        for tool_file in ProjectValidator.TOOL_PROJECT_FILES:
            result = self._api_exists(tool_file)
            if result is True:
                return False, f"检测到工具项目文件: {tool_file}"

        # 5. 检查模糊项目文件
        for ambiguous_file in ProjectValidator.AMBIGUOUS_PROJECT_FILES:
            result = self._api_exists(ambiguous_file)
            if result is True:
                content = self.fetch_file(ambiguous_file, prefer_api=True)
                if content and ("tool.scripts" in content or "command-line" in content.lower()):
                    return False, f"检测到工具项目配置: {ambiguous_file}"

        return None  # 无法判定

    def _api_exists(self, path: str) -> Optional[bool]:
        """
        检查文件/目录是否存在 (通过 API)

        Returns:
            True=存在, False=不存在(404), None=超时/失败/限流
        """
        url = f"{self.API_BASE}/repos/{self.repo}/contents/{path}"
        headers = {}
        if self.token:
            headers["Authorization"] = f"token {self.token}"

        cmd = ["curl", "-s", "--max-time", "3", url]
        for k, v in headers.items():
            cmd.extend(["-H", f"{k}: {v}"])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False
            )

            if result.returncode == 403:
                if "rate limit exceeded" in result.stdout.lower() or "api rate limit" in result.stdout.lower():
                    return None  # 限流
                return None  # 其他 403

            if result.returncode == 200:
                return True
            elif result.returncode == 404:
                return False
            return None
        except Exception:
            return None

    def _check_via_raw(self) -> Optional[Tuple[bool, str]]:
        """通过 Raw URL 检查是否为技能仓库"""
        # 检查根目录 SKILL.md
        content = self.fetch_file("SKILL.md")
        if content:
            return True, f"Raw 发现 SKILL.md (分支: {self.branch})"

        # 检查 skills/ 目录
        if self.fetch_file("skills/commit/SKILL.md"):
            return True, f"Raw 发现 skills/ 目录 (分支: {self.branch})"

        return None  # 未找到技能标记


# =============================================================================
# 仓库缓存管理器
# =============================================================================

class RepoCacheManager:
    """管理 GitHub 仓库的持久化缓存"""

    @staticmethod
    def _sanitize_url(url: str) -> str:
        """将 URL 转换为安全的目录名"""
        # 移除协议和特殊字符
        clean = url.replace("https://", "").replace("http://", "")
        clean = clean.replace("/", "_").replace("\\", "_")
        # 限制长度
        return clean[:100]

    @staticmethod
    def _get_cache_dir(github_url: str) -> Path:
        """获取仓库的缓存目录"""
        cache_name = RepoCacheManager._sanitize_url(github_url)
        return CACHE_DIR / cache_name

    @staticmethod
    def _get_meta_file(cache_dir: Path) -> Path:
        """获取缓存元数据文件路径"""
        return cache_dir / ".meta.json"

    @staticmethod
    def load_meta(cache_dir: Path) -> Optional[Dict]:
        """加载缓存元数据"""
        meta_file = RepoCacheManager._get_meta_file(cache_dir)
        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    @staticmethod
    def save_meta(cache_dir: Path, meta: Dict):
        """保存缓存元数据"""
        meta_file = RepoCacheManager._get_meta_file(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

    @staticmethod
    def get_or_clone(
        github_url: str,
        force_refresh: bool = False,
        timeout: int = 300
    ) -> Tuple[bool, Optional[Path], str]:
        """
        获取仓库（优先从缓存）

        Args:
            github_url: 仓库 URL
            force_refresh: 强制刷新缓存
            timeout: 克隆超时时间（秒）

        Returns:
            (成功, 仓库路径, 消息)
        """
        cache_dir = RepoCacheManager._get_cache_dir(github_url)

        # 1. 检查缓存是否存在
        if cache_dir.exists() and not force_refresh:
            meta = RepoCacheManager.load_meta(cache_dir)
            if meta and meta.get("url") == github_url:
                # 缓存有效
                cached_time = meta.get("cached_at", "")
                return True, cache_dir, f"使用缓存 (缓存于 {cached_time})"

        # 2. 缓存不存在或强制刷新，执行克隆
        info(f"克隆仓库到缓存: {github_url}")

        # 如果旧缓存存在，先删除
        if cache_dir.exists():
            # 使用系统命令删除（避免 Windows 文件锁定问题）
            try:
                subprocess.run(["rm", "-rf", str(cache_dir)], capture_output=True, timeout=10)
            except:
                pass
            # 验证清理是否成功
            if cache_dir.exists():
                warn(f"缓存清理失败，使用 shutil 强制重试: {cache_dir}")
                import time
                time.sleep(0.5)
                try:
                    shutil.rmtree(cache_dir, ignore_errors=False)
                except Exception as e:
                    error(f"无法删除缓存目录，请手动删除后重试: {cache_dir}")
                    error(f"错误信息: {e}")
                    return False, None, f"缓存清理失败: {e}"

        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # 执行克隆
        clone_ok, _ = GitHubHandler.clone_repo(github_url, cache_dir)

        if not clone_ok:
            return False, None, "仓库不存在或路径错误，请确认:\n1. 仓库 URL 是否正确\n2. 是否为子技能（尝试使用 --skill 参数）\n3. 查看映射表: docs/skills-mapping.md"

        # 保存元数据
        meta = {
            "url": github_url,
            "cached_at": datetime.now().isoformat(),
            "branch": "main"  # 默认分支
        }
        RepoCacheManager.save_meta(cache_dir, meta)

        return True, cache_dir, "缓存创建成功"

    @staticmethod
    def update_cache(github_url: str) -> Tuple[bool, str]:
        """
        更新已有缓存（git pull）

        Args:
            github_url: 仓库 URL

        Returns:
            (成功, 消息)
        """
        cache_dir = RepoCacheManager._get_cache_dir(github_url)

        if not cache_dir.exists():
            return False, "缓存不存在"

        try:
            import subprocess
            result = subprocess.run(
                ["git", "-C", str(cache_dir), "pull"],
                capture_output=True,
                text=True,
                timeout=60,
                encoding="utf-8",
                errors="replace"
            )

            if result.returncode == 0:
                # 更新元数据
                meta = RepoCacheManager.load_meta(cache_dir) or {}
                meta["last_updated"] = datetime.now().isoformat()
                RepoCacheManager.save_meta(cache_dir, meta)
                return True, "缓存更新成功"
            else:
                return False, f"更新失败: {result.stderr}"

        except Exception as e:
            return False, f"更新异常: {e}"

    @staticmethod
    def clear_cache(older_than_hours: Optional[int] = None) -> Dict[str, int]:
        """
        清理缓存

        Args:
            older_than_hours: 只清理超过指定小时数的缓存，None 表示全部清理

        Returns:
            统计信息 {"cleared": 清理数量, "kept": 保留数量}
        """
        if not CACHE_DIR.exists():
            return {"cleared": 0, "kept": 0}

        cleared = 0
        kept = 0
        current_time = time.time()

        for cache_dir in CACHE_DIR.iterdir():
            if not cache_dir.is_dir():
                continue

            try:
                if older_than_hours is None:
                    # 全部清理
                    shutil.rmtree(cache_dir)
                    cleared += 1
                else:
                    # 检查年龄
                    meta = RepoCacheManager.load_meta(cache_dir)
                    if meta:
                        cached_at_str = meta.get("cached_at", "")
                        try:
                            from datetime import datetime
                            cached_at = datetime.fromisoformat(cached_at_str)
                            age_hours = (current_time - cached_at.timestamp()) / 3600

                            if age_hours > older_than_hours:
                                shutil.rmtree(cache_dir)
                                cleared += 1
                            else:
                                kept += 1
                        except Exception:
                            kept += 1
                    else:
                        # 无元数据，删除
                        shutil.rmtree(cache_dir)
                        cleared += 1
            except Exception:
                kept += 1

        return {"cleared": cleared, "kept": kept}

    @staticmethod
    def list_cache() -> List[Dict]:
        """
        列出所有缓存

        Returns:
            缓存列表 [{"url": ..., "cached_at": ..., "size_mb": ...}, ...]
        """
        if not CACHE_DIR.exists():
            return []

        caches = []
        for cache_dir in CACHE_DIR.iterdir():
            if not cache_dir.is_dir():
                continue

            meta = RepoCacheManager.load_meta(cache_dir)
            if meta:
                # 计算大小
                try:
                    size_bytes = sum(
                        f.stat().st_size
                        for f in cache_dir.rglob("*")
                        if f.is_file()
                    )
                    size_mb = round(size_bytes / (1024 * 1024), 2)
                except Exception:
                    size_mb = 0

                caches.append({
                    "url": meta.get("url", "Unknown"),
                    "cached_at": meta.get("cached_at", "Unknown"),
                    "last_updated": meta.get("last_updated", "Never"),
                    "size_mb": size_mb,
                    "path": str(cache_dir)
                })

        # 按缓存时间排序
        caches.sort(key=lambda x: x["cached_at"], reverse=True)
        return caches


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

        # 预清理：若目标目录已存在（如上次超时残留），先删除
        if target_dir.exists():
            info(f"目标目录已存在，清理: {target_dir}")
            # 使用系统命令删除（避免 Windows 文件锁定问题）
            try:
                subprocess.run(["rm", "-rf", str(target_dir)], capture_output=True, timeout=10)
            except:
                pass
            # 验证清理是否成功
            if target_dir.exists():
                warn(f"目录清理失败，使用 shutil 强制重试: {target_dir}")
                import time
                time.sleep(0.5)
                shutil.rmtree(target_dir, ignore_errors=False)

        # 构建基础 git 命令
        cmd = ["git"]
        if not get_ssl_verify():
            cmd.extend(["-c", "http.sslVerify=false"])
        # 启用长路径支持（Windows 260字符限制）
        cmd.extend(["-c", "core.longPaths=true"])

        # 设置环境变量：禁用 Git 交互式提示（避免 askpass 错误）
        import os
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GIT_ASKPASS"] = "true"

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
                    timeout=20,
                    env=env,
                )

                if result.returncode == 0:
                    success(f"克隆成功（使用加速器）: {target_dir}")
                    return True, target_dir
                else:
                    warn(f"加速器克隆失败: {proxy_url}")
                    warn(f"错误: {result.stderr}")
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
                env=env,
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
    def _recursive_skill_scan(
        root_dir: Path,
        max_depth: int = 5,
        exclude_dirs: Optional[set] = None
    ) -> List[Dict[str, Path]]:
        """递归扫描所有子目录，查找 SKILL.md 文件

        支持任意深度嵌套的子技能检测（如 plugins/yc-advisor/skills/yc-advisor）

        Args:
            root_dir: 仓库根目录
            max_depth: 最大递归深度
            exclude_dirs: 排除的目录名集合

        Returns:
            [{"path": Path, "relative_path": str}, ...]
            - path: 技能目录绝对路径
            - relative_path: 相对于 root_dir 的路径
        """
        if exclude_dirs is None:
            exclude_dirs = {"examples", "templates", "test", "tests", "docs", "reference", ".git", "node_modules", "__pycache__"}

        results = []

        def _scan_recursive(current_dir: Path, current_depth: int, rel_path: str = ""):
            if current_depth > max_depth:
                return

            try:
                for item in current_dir.iterdir():
                    # 跳过排除目录和隐藏文件
                    if item.name in exclude_dirs or item.name.startswith('.'):
                        continue

                    if item.is_dir():
                        new_rel_path = f"{rel_path}/{item.name}" if rel_path else item.name

                        # 检查是否包含 SKILL.md
                        if (item / "SKILL.md").exists():
                            results.append({
                                "path": item,
                                "relative_path": new_rel_path
                            })
                            info(f"发现深层技能: {new_rel_path}")

                        # 继续递归
                        _scan_recursive(item, current_depth + 1, new_rel_path)
            except (PermissionError, OSError):
                pass

        _scan_recursive(root_dir, 0)
        return results

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

        # 回退机制1：递归深度扫描（支持任意深度嵌套的子技能）
        if not skill_dirs:
            recursive_results = GitHubHandler._recursive_skill_scan(repo_dir, max_depth=5)
            if recursive_results:
                # 按深度排序，优先选择较浅的技能
                recursive_results.sort(key=lambda x: x["relative_path"].count('/'))
                skill_dirs = [r["path"] for r in recursive_results]
                info(f"递归扫描: 发现 {len(skill_dirs)} 个深层子技能")

        # 回退机制2：如果仍未找到技能，检查单层子目录（原有逻辑）
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

def _extract_repo_from_url(github_url: str) -> Optional[str]:
    """从 GitHub URL 提取 user/repo 格式

    Returns:
        "user/repo" 格式的字符串，失败返回 None
    """
    author, repo = SkillInstaller._extract_github_info(github_url)
    if author and repo:
        return f"{author}/{repo}"
    return None

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


def _dual_path_skill_check(github_url: str) -> Tuple[bool, str, List[str]]:
    """
    统一的技能判定 (合并后：使用 RemoteSkillAnalyzer)

    判决规则:
    - 判定为技能项目 → 继续 clone
    - 判定为非技能项目 → 拒绝安装
    - 预检超时/失败 → 降级到 clone

    Returns:
        (should_proceed, reason, sources)
        - should_proceed: True=继续clone, False=拒绝安装
        - reason: 判定原因
        - sources: 成功的判定源 ["analyzer", "fallback"]
    """
    from urllib.parse import urlparse

    # 提取 user/repo
    parsed = urlparse(github_url)
    if "github.com" not in parsed.netloc:
        return True, "非 GitHub URL，跳过预检", ["fallback"]

    repo = _extract_repo_from_url(github_url)
    if not repo:
        return True, "无法解析仓库，跳过预检", ["fallback"]

    # 使用统一的分析器
    analyzer = RemoteSkillAnalyzer(repo)
    is_skill, reason = analyzer.check_is_skill_repo()

    # 判定规则
    if is_skill is True:
        # 判定为技能 → 继续
        return True, reason, ["analyzer"]
    elif is_skill is False:
        # 判定为非技能 → 拒绝
        return False, reason, []
    else:
        # is_skill is None，预检超时/失败 → 降级到 clone
        return True, reason, ["fallback"]


def _process_github_source(
    github_url: str,
    temp_dir: Path,
    skill_name: Optional[str] = None,
    batch: bool = False,
    subpath: Optional[str] = None,
    use_cache: bool = True,
    force_refresh: bool = False
) -> Tuple[List[Path], Optional[str]]:
    """
    统一的 GitHub 源处理逻辑

    Args:
        github_url: GitHub 仓库 URL
        temp_dir: 临时目录
        skill_name: 指定的子技能名称
        batch: 是否批量处理
        subpath: 仓库内的子路径（如 "scientific-skills"）
        use_cache: 是否使用缓存
        force_refresh: 强制刷新缓存

    Returns:
        (待处理的技能列表, 错误信息)
    """
    # === 方案0: 双路技能判定 ===
    # 在没有子路径时进行预检（检查是否为技能仓库）
    if not subpath:
        should_proceed, reason, sources = _dual_path_skill_check(github_url)

        if not should_proceed:
            # 拒绝安装
            print("=" * 60)
            print("❌ 拒绝安装：这不是技能项目")
            print("=" * 60)
            print()
            print(f"检测原因: {reason}")
            print()
            print("系统不支持安装工具项目。")
            return [], "不是技能项目"

        info(f"预检通过 ({'+'.join(sources)}): {reason}")

    # === 方案1: 子技能预检机制 ===
    # 当指定了子技能名称时，先通过 API 预检，避免无效克隆
    if skill_name:
        info(f"预检子技能: {skill_name}")
        # 从 URL 提取 repo 格式 (user/repo)
        repo = _extract_repo_from_url(github_url)
        if repo:
            try:
                analyzer = RemoteSkillAnalyzer(repo)
                repo_info = analyzer.analyze()
                available_skills = {s["name"] for s in repo_info.get("skills", [])}

                if skill_name not in available_skills:
                    available_list = ", ".join(sorted(available_skills))
                    return [], f"子技能不存在: {skill_name}\n可用子技能: {available_list}"

                info(f"预检通过: {skill_name} 存在")
            except Exception as e:
                # 预检失败（网络问题等），回退到直接克隆
                warn(f"预检失败，继续克隆: {e}")

    # === 方案2B: 缓存机制 ===
    if use_cache:
        cache_ok, cache_dir, cache_msg = RepoCacheManager.get_or_clone(
            github_url,
            force_refresh=force_refresh
        )
        if cache_ok:
            info(cache_msg)
            # 从缓存复制到临时目录
            repo_dir = temp_dir / "repo"
            if repo_dir.exists():
                shutil.rmtree(repo_dir)
            shutil.copytree(cache_dir, repo_dir)
        else:
            return [], cache_msg
    else:
        # 不使用缓存，直接克隆
        clone_ok, repo_dir = GitHubHandler.clone_repo(github_url, temp_dir / "repo")
        if not clone_ok:
            return [], "仓库不存在或路径错误\n提示: 查看 docs/skills-mapping.md 确认正确的仓库路径"

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
                # 输出拒绝信息
                repo_name = github_url.split('/')[-1] if '/' in github_url else github_url
                print("=" * 60)
                print("❌ 拒绝安装：这不是技能项目")
                print("=" * 60)
                print()
                print(f"检测原因: {reason}")
                print(f"仓库: {repo_name}")
                print()
                print("系统不支持安装工具项目。")
                print("请确认：")
                print("  1. 是否为工具/库？请使用 pip/npm/cargo 等安装")
                print("  2. 确实需要作为技能？请手动转换后安装")
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
        return _process_github_source(input_source, temp_dir, skill_name, batch, subpath, force_refresh=force_refresh)

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
        description="技能管理器 - 安装、搜索、卸载技能",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 安装 GitHub 仓库中的技能
  python bin/skill_manager.py install https://github.com/user/repo

  # 安装指定子技能
  python bin/skill_manager.py install https://github.com/user/repo --skill my-skill

  # 批量安装仓库中所有技能
  python bin/skill_manager.py install https://github.com/user/repo --batch

  # 搜索技能（关键词）
  python bin/skill_manager.py search prompt

  # 搜索技能（多关键词）
  python bin/skill_manager.py search prompt optimize --score

  # 列出所有已安装技能
  python bin/skill_manager.py list

  # 卸载技能（同步数据库）
  python bin/skill_manager.py uninstall my-skill

  # 验证已安装的技能
  python bin/skill_manager.py validate .claude/skills/my-skill
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

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
        nargs="+",
        help="技能名称（支持多个，空格分隔）"
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
    install_parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="强制刷新仓库缓存（重新克隆）"
    )

    # record 命令 - 记录技能使用
    record_parser = subparsers.add_parser("record", help="记录技能使用（用于搜索加权）")
    record_parser.add_argument(
        "name",
        help="技能名称"
    )

    # cache 命令 - 管理仓库缓存
    cache_parser = subparsers.add_parser("cache", help="管理仓库缓存")
    cache_parser.add_argument(
        "action",
        choices=["list", "clear", "update"],
        help="操作: list=列出缓存, clear=清理缓存, update=更新指定缓存"
    )
    cache_parser.add_argument(
        "url",
        nargs="?",
        help="仓库 URL（用于 update 操作）"
    )
    cache_parser.add_argument(
        "--older-than", "-o",
        type=int,
        default=None,
        help="清理超过指定小时数的缓存（用于 clear 操作），默认全部清理"
    )

    args = parser.parse_args()

    # =============================================================================
    # 执行命令
    # =============================================================================

    if args.command == "validate":
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
                print(f"  [OK] {name}")
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
        header("技能卸载器")

        skill_names = args.name
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

            # 3. 检查技能是否存在
            if not skill_dir.exists():
                error(f"技能不存在: {skill_name} (查找目录: {folder_name})")
                failed_list.append(skill_name)
                continue

            # 4. 确认删除
            if not args.force:
                print(f"即将删除技能: {skill_name}")
                print(f"路径: {skill_dir}")
                print("正在删除...")

            # 5. 删除目录（原子操作：文件 + 数据库）
            try:
                # 5.1 删除文件
                shutil.rmtree(skill_dir)

                # 5.2 从数据库移除（使用 folder_name）
                db_remove_success = SkillInstaller._remove_skill_from_db(folder_name)
                if db_remove_success:
                    success(f"已删除: {skill_name} (数据库已同步)")
                    success_count += 1
                else:
                    # 数据库操作失败，文件已删除但数据库未更新
                    warn(f"文件已删除，但数据库同步失败: {skill_name}")
                    success_count += 1
            except Exception as e:
                error(f"删除失败: {skill_name} - {e}")
                failed_list.append(skill_name)

        # 汇总结果
        print()
        info(f"批量删除完成: 成功 {success_count}/{len(skill_names)}")
        if failed_list:
            error(f"失败: {', '.join(failed_list)}")
            return 1
        return 0

    elif args.command == "install":
        header("技能安装器")

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
            subpath,
            force_refresh=getattr(args, "refresh_cache", False)
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
                        # 递归修改权限后删除 (使用 0o755 而非 0o777)
                        for root, dirs, files in os.walk(git_dir):
                            for d in dirs:
                                os.chmod(os.path.join(root, d), 0o755)
                            for f in files:
                                os.chmod(os.path.join(root, f), 0o644)
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

    elif args.command == "cache":
        header("缓存管理")

        if args.action == "list":
            caches = RepoCacheManager.list_cache()
            if not caches:
                info("无缓存")
                return 0

            print(f"\n共 {len(caches)} 个缓存:\n")
            for i, cache in enumerate(caches, 1):
                print(f"  {i}. {cache['url']}")
                print(f"     大小: {cache['size_mb']} MB")
                print(f"     缓存时间: {cache['cached_at']}")
                if cache['last_updated'] != 'Never':
                    print(f"     更新时间: {cache['last_updated']}")
                print()

        elif args.action == "clear":
            if args.older_than is None:
                print("确认清理所有缓存? (y/N): ", end="")
                confirm = input()
                if confirm.lower() != 'y':
                    info("已取消")
                    return 0
            else:
                info(f"清理超过 {args.older_than} 小时的缓存")

            result = RepoCacheManager.clear_cache(args.older_than)
            success(f"清理完成: 清理 {result['cleared']} 个, 保留 {result['kept']} 个")

        elif args.action == "update":
            if not args.url:
                error("请指定要更新的仓库 URL")
                return 1

            info(f"更新缓存: {args.url}")
            ok, msg = RepoCacheManager.update_cache(args.url)
            if ok:
                success(msg)
            else:
                error(msg)

        return 0

    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())

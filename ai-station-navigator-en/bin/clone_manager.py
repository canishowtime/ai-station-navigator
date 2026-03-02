#!/usr/bin/env python3
"""
clone_manager.py - GitHub Repository Clone Manager
-----------------------------------------
Responsible for cloning skill repositories from GitHub to local staging area

Responsibilities:
1. GitHub repository cloning (with accelerator support)
2. Remote repository analysis (pre-check, caching)
3. Skill directory extraction
4. Repository cache management

Architecture:
    skill_manager → clone_manager → security_scanner
                       ↓
                  Staging Space (mybox/cache/repos/)

Source: Refactored from skill_manager.py (Apache 2.0)
"""

import argparse
import sys
import os

# Windows UTF-8 Compatibility (P0 - All scripts must include)
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


import json
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
import urllib.request
import urllib.error
import yaml

# =============================================================================
# Path Configuration
# =============================================================================

BASE_DIR = Path(__file__).parent.parent
CACHE_DIR = BASE_DIR / "mybox" / "cache" / "repos"
TEMP_DIR = BASE_DIR / "mybox" / "temp"

# Skill default value constants
DEFAULT_SKILL_DESC = "No description"
DEFAULT_SKILL_CATEGORY = "utilities"
DEFAULT_SKILL_TAGS = ["skill"]

# Add project lib directory to sys.path (green package bundled dependencies)
_lib_dir = Path(__file__).parent.parent / "lib"
if _lib_dir.exists():
    sys.path.insert(0, str(_lib_dir))

# Add bin directory to sys.path (for importing other modules)
_bin_dir = Path(__file__).parent
if str(_bin_dir) not in sys.path:
    sys.path.insert(0, str(_bin_dir))


# =============================================================================
# Logging Utilities
# =============================================================================

def log(level: str, message: str, emoji: str = ""):
    """Unified log output"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"{timestamp} [{level}] {emoji} {message}")

def success(msg: str):
    log("SUCCESS", msg, "[OK]")

def info(msg: str):
    log("INFO", msg, "[i]")

def warn(msg: str):
    log("WARN", msg, "[!]")

def error(msg: str):
    log("ERROR", msg, "[X]")

# =============================================================================
# Configuration Loading (shared)
# =============================================================================

_config_cache: Optional[dict] = None
_config_mtime: Optional[float] = None

def load_config(use_cache: bool = True) -> dict:
    """
    Load configuration file (with cache support)

    Configuration file priority (in order):
    1. <BASE_DIR>/config.json (recommended, JSON format)
    2. <BASE_DIR>/.claude/config/config.yml (backward compatible, YAML format)

    Args:
        use_cache: Whether to use cache (default True)

    Returns:
        Configuration dictionary
    """
    global _config_cache, _config_mtime

    # Configuration file path list (by priority)
    config_files = [
        BASE_DIR / "config.json",
        BASE_DIR / ".claude" / "config" / "config.yml"
    ]

    # Find existing configuration file
    config_file = None
    for cf in config_files:
        if cf.exists():
            config_file = cf
            break

    if not config_file:
        return {}

    # Check cache validity
    if use_cache and _config_cache is not None:
        current_mtime = config_file.stat().st_mtime
        if current_mtime == _config_mtime:
            return _config_cache

    # Load configuration (choose method based on file type)
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            if config_file.suffix == ".json":
                _config_cache = json.load(f)
            else:
                _config_cache = yaml.safe_load(f) or {}
            _config_mtime = config_file.stat().st_mtime
            return _config_cache
    except Exception as e:
        warn(f"Configuration file load failed: {e}")
        return {}

def clear_config_cache() -> None:
    """Clear configuration cache"""
    global _config_cache, _config_mtime
    _config_cache = None
    _config_mtime = None

def get_git_proxies() -> list:
    """Get Git accelerator list"""
    config = load_config()
    return config.get("git", {}).get("proxies", [
        "https://ghp.ci/{repo}",
        "https://ghproxy.net/{repo}",
    ])

def get_ssl_verify() -> bool:
    """Get SSL verification setting"""
    config = load_config()
    return config.get("git", {}).get("ssl_verify", True)

def get_raw_proxies() -> list:
    """Get Raw URL accelerator list"""
    config = load_config()
    return config.get("raw", {}).get("proxies", [
        "https://ghp.ci/{path}",
        "https://raw.fastgit.org/{path}",
    ])

# =============================================================================
# Format Detector
# =============================================================================

class FormatDetector:
    """Detect format type of input source"""

    @staticmethod
    def validate_github_url(url: str) -> Tuple[bool, Optional[str]]:
        """
        Validate GitHub URL format security, prevent config injection attacks

        Args:
            url: GitHub URL to validate

        Returns:
            (is_valid, error_message)
        """
        # Basic format check
        github_pattern = r'^https?://github\.com/[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+(?:/tree/[^/\s]+(?:/[\w\-./]+)?)?/?$'
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
    def parse_github_subpath(github_url: str) -> Tuple[str, Optional[str]]:
        """
        Parse GitHub URL, extract subpath

        Returns:
            (repo_url, subpath)
        """
        is_valid, error_msg = FormatDetector.validate_github_url(github_url)
        if not is_valid:
            raise ValueError(f"GitHub URL security validation failed: {error_msg}")

        parsed = urlparse(github_url)
        path_parts = parsed.path.strip('/').split('/')

        # Find /tree/ separator
        if 'tree' in path_parts:
            tree_idx = path_parts.index('tree')
            if tree_idx >= 2:
                repo_url = f"{parsed.scheme}://{parsed.netloc}/{'/'.join(path_parts[:tree_idx])}"
                if len(path_parts) > tree_idx + 2:
                    subpath = '/'.join(path_parts[tree_idx + 2:])
                    return repo_url, subpath
                return repo_url, None

        return github_url, None

    @staticmethod
    def detect_input_type(input_source: str) -> Tuple[str, str, Optional[str]]:
        """
        Detect input source type

        Returns:
            (type, path/URL, subpath)
        """
        info(f"Detecting input source: {input_source}")

        # 1. Check if it's a GitHub URL
        if input_source.startswith(("http://", "https://")):
            parsed = urlparse(input_source)
            if "github.com" in parsed.netloc:
                repo_url, subpath = FormatDetector.parse_github_subpath(input_source)
                if subpath:
                    info(f"Detected subpath: {subpath}")
                return "github", repo_url, subpath

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

        warn("Unable to recognize input source type, trying as local directory")
        return "unknown", input_source, None

# =============================================================================
# Skill Normalizer (extract required parts)
# =============================================================================

class SkillNormalizer:
    """Normalize various formats to official SKILL.md format"""

    @staticmethod
    def extract_frontmatter(content: str) -> Dict[str, Any]:
        """Extract YAML frontmatter from SKILL.md"""
        if not content.startswith("---"):
            return {}

        end_marker = content.find("\n---", 4)
        if end_marker == -1:
            end_marker = content.find("---", 3)
        if end_marker <= 0:
            return {}

        yaml_content = content[4:end_marker].strip()

        try:
            frontmatter = yaml.safe_load(yaml_content)
            if isinstance(frontmatter, dict):
                return frontmatter
        except (yaml.YAMLError, Exception):
            pass

        # Fallback: manual parsing
        result = {}
        for line in yaml_content.split('\n'):
            if ':' in line and not line.strip().startswith('#'):
                key, value = line.split(':', 1)
                result[key.strip()] = value.strip().strip('"').strip("'")
        return result

# =============================================================================
# Project Validator
# =============================================================================

class ProjectValidator:
    """Verify if project is a skill repository"""

    TOOL_PROJECT_FILES = [
        "setup.py", "Cargo.toml", "go.mod",
    ]

    AMBIGUOUS_PROJECT_FILES = [
        "pyproject.toml", "package.json",
    ]

# =============================================================================
# Skill Pack Handler
# =============================================================================

class SkillPackHandler:
    """Handle .skill skill pack"""

    @staticmethod
    def extract_pack(pack_file: Path, extract_dir: Path) -> Tuple[bool, Optional[Path]]:
        """
        解压 .skill 技能包

        Returns:
            (成功, 解压目录)
        """
        try:
            with zipfile.ZipFile(pack_file, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            return True, extract_dir
        except Exception as e:
            error(f"解压技能包失败: {e}")
            return False, None

# =============================================================================
# Remote Skill Analyzer
# =============================================================================

class RemoteSkillAnalyzer:
    """Analyze skill information from remote GitHub repository"""

    API_BASE = "https://api.github.com"
    RAW_BASE = "https://raw.githubusercontent.com"

    def __init__(self, repo: str, branch: str = "main", token: Optional[str] = None):
        """
        Args:
            repo: user/repo format
            branch: Branch name
            token: GitHub personal access token
        """
        self.repo = repo
        self.branch = branch
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self._use_cache = True
        self.github_url = f"https://github.com/{repo}"
        self.proxies = get_raw_proxies()
        self._cache = {}
        self._working_proxy = None

    def analyze(self) -> Dict[str, Any]:
        """Analyze repository, return skill information"""
        result = {
            "repo": self.repo,
            "branch": "main",
            "skills": [],
            "source": "unknown"
        }

        # 检查缓存
        cache_dir = RepoCacheManager._get_cache_dir(self.github_url)
        if cache_dir.exists() and self._use_cache:
            meta = RepoCacheManager.load_meta(cache_dir)
            if meta and meta.get("url") == self.github_url:
                result["source"] = "cache"
                info(f"Using local cache for analysis: {self.repo}")
                return self._analyze_from_cache(cache_dir, result)

        # 网络探测
        result["source"] = "network"
        return self._analyze_from_network(result)

    def _analyze_from_cache(self, cache_dir: Path, result: Dict) -> Dict:
        """Analyze repository from local cache"""
        skills = []
        for skill_md in cache_dir.rglob("SKILL.md"):
            rel_path = skill_md.relative_to(cache_dir)
            try:
                with open(skill_md, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                info = self._parse_skill_md(content, str(rel_path.parent))
                if info:
                    info["url"] = f"{self.github_url}/tree/{result['branch']}/{rel_path.parent}"
                    info["is_root"] = (str(rel_path.parent) == ".")
                    skills.append(info)
            except Exception as e:
                warn(f"读取 {rel_path} 失败: {e}")

        result["skills"] = sorted(skills, key=lambda x: x["name"])
        return result

    def _analyze_from_network(self, result: Dict) -> Dict:
        """Analyze repository via network"""
        skills = []

        # Detect branches
        branches_to_try = ["main", "master"]
        found_branch = None

        for branch in branches_to_try:
            self.branch = branch
            if self.fetch_file("SKILL.md") or self.fetch_file("README.md"):
                found_branch = branch
                break

        if not found_branch:
            return result

        result["branch"] = found_branch

        # 检测根目录 SKILL.md
        root_skill_content = self.fetch_file("SKILL.md")
        if root_skill_content:
            root_info = self._parse_skill_md(root_skill_content, "")
            if root_info:
                root_info["is_root"] = True
                root_info["url"] = self.github_url
                skills.append(root_info)

        # Explore sub-skills
        sub_skill_paths = self._discover_skill_paths()
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
        """Explore sub-skill SKILL.md paths"""
        skill_paths = []
        checked = set()

        # Common skill names
        common_names = [
            "commit", "review-pr", "pdf", "web-search", "image-analysis",
            "doc-coauthoring", "copywriting", "email-sequence", "popup-cro",
            "translator", "summarizer", "code-run", "terminal"
        ]

        patterns = [
            "plugins/{name}/SKILL.md",
            "skills/{name}/SKILL.md",
            "{name}/SKILL.md",
        ]

        names_to_check = common_names

        for pattern in patterns:
            for name in names_to_check:
                path = pattern.replace("{name}", name)
                if path in checked:
                    continue
                if self.fetch_file(path):
                    skill_paths.append(path)
                    checked.add(path)

        return sorted(skill_paths)

    def _parse_skill_md(self, content: str, file_path: str) -> Optional[Dict]:
        """Parse SKILL.md content"""
        frontmatter = SkillNormalizer.extract_frontmatter(content)

        name = frontmatter.get("name", "")
        if not name:
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

    @staticmethod
    def _validate_url(url: str) -> bool:
        """验证 URL 安全性"""
        try:
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
        """获取文件内容 - 自动选择最佳方式"""
        if file_path in self._cache:
            return self._cache[file_path]

        if prefer_api and self.token:
            content = self._fetch_via_api(file_path)
            if content is not None:
                self._cache[file_path] = content
                return content

        content = self._fetch_via_raw(file_path)
        if content is not None:
            self._cache[file_path] = content
            return content

        if self.token and not prefer_api:
            content = self._fetch_via_api(file_path)
            if content is not None:
                self._cache[file_path] = content
                return content

        return None

    def _fetch_via_raw(self, file_path: str) -> Optional[str]:
        """通过 Raw URL 获取文件"""
        path = f"{self.repo}/{self.branch}/{file_path}"

        if self._working_proxy:
            proxy_url = self._working_proxy.replace("{path}", path)
            content = self._try_fetch_url(proxy_url)
            if content is not None:
                return content
            self._working_proxy = None

        for proxy_template in self.proxies:
            proxy_url = proxy_template.replace("{path}", path)
            content = self._try_fetch_url(proxy_url)
            if content is not None:
                self._working_proxy = proxy_template
                return content

        raw_url = f"{self.RAW_BASE}/{path}"
        return self._try_fetch_url(raw_url)

    def _try_fetch_url(self, url: str) -> Optional[str]:
        """尝试从指定 URL 获取文件（跨平台兼容）"""
        if not self._validate_url(url):
            return None
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                content = response.read().decode("utf-8", errors="replace")
                if not content or "404: Not Found" in content or "<title>404" in content:
                    return None
                return content
        except (urllib.error.URLError, urllib.error.HTTPError, Exception):
            pass
        return None

    def _fetch_via_api(self, file_path: str) -> Optional[str]:
        """通过 GitHub API 获取文件（跨平台兼容）"""
        url = f"{self.API_BASE}/repos/{self.repo}/contents/{file_path}"
        headers = {"Accept": "application/vnd.github.v3.raw"}
        if self.token:
            headers["Authorization"] = f"token {self.token}"

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=3) as response:
                # 检查状态码（urllib会自动处理重定向，200-299表示成功）
                if response.status == 403:
                    return None

                content = response.read().decode("utf-8", errors="replace")
                if content.startswith("{"):
                    try:
                        import base64
                        data = json.loads(content)
                        if "content" in data:
                            return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
                    except Exception:
                        pass
                return content
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            if hasattr(e, 'code') and e.code == 403:
                return None
            return None
        except Exception:
            return None

    def check_is_skill_repo(self) -> Tuple[Optional[bool], str]:
        """统一的技能仓库预检"""
        # 尝试 Raw URL
        content = self.fetch_file("SKILL.md")
        if content:
            return True, f"Raw 发现 SKILL.md (分支: {self.branch})"

        if self.fetch_file("skills/commit/SKILL.md"):
            return True, f"Raw 发现 skills/ 目录 (分支: {self.branch})"

        return None, "预检超时或失败，降级到 clone"

    def _verify_single_skill(self, skill_name: str) -> bool:
        """轻量级验证：仅检查指定技能是否存在"""
        normalized = skill_name.lower().replace('_', '-')

        patterns = [
            f"skills/{skill_name}/SKILL.md",
            f"plugins/{skill_name}/SKILL.md",
            f"{skill_name}/SKILL.md",
        ]

        if '-' in skill_name or '_' in skill_name:
            alt_patterns = [
                f"skills/{normalized}/SKILL.md",
                f"plugins/{normalized}/SKILL.md",
                f"{normalized}/SKILL.md",
            ]
            patterns.extend(alt_patterns)

        for pattern in patterns:
            if self.fetch_file(pattern):
                return True

        return False


# =============================================================================
# GitHub URL 解析工具
# =============================================================================

def _extract_github_info(github_url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """从 GitHub URL 提取 author、repo 和子路径

    支持格式:
    - https://github.com/author/repo
    - https://github.com/author/repo/tree/branch
    - https://github.com/author/repo/tree/branch/skills/skill-name

    Returns:
        (author, repo, subpath)
    """
    from urllib.parse import urlparse

    subpath = None

    if "github.com" in github_url:
        # 完整 URL 格式
        parsed = urlparse(github_url)
        path_parts = parsed.path.rstrip('/').split('/')

        # 基本结构: /author/repo/...
        if len(path_parts) >= 3 and path_parts[0] == '':
            author = path_parts[1]
            repo = path_parts[2]

            # 检查是否有子路径 (tree/branch/skills/...)
            if len(path_parts) > 3:
                # 跳过 "tree" 和分支名
                if len(path_parts) > 4 and path_parts[3] == "tree":
                    # 子路径从分支名之后开始
                    subpath = '/'.join(path_parts[5:]) if len(path_parts) > 5 else None
                else:
                    # 其他格式的子路径
                    subpath = '/'.join(path_parts[3:]) if len(path_parts) > 3 else None

            return author, repo, subpath

    return None, None, None


# =============================================================================
# 仓库缓存管理器
# =============================================================================

class RepoCacheManager:
    """管理 GitHub 仓库的持久化缓存"""

    @staticmethod
    def _sanitize_url(url: str) -> str:
        """Convert URL to safe directory name"""
        clean = url.replace("https://", "").replace("http://", "")
        clean = clean.replace("/", "_").replace("\\", "_")
        return clean[:100]

    @staticmethod
    def _get_cache_dir(github_url: str) -> Path:
        """Get cache directory for repository"""
        cache_name = RepoCacheManager._sanitize_url(github_url)
        return CACHE_DIR / cache_name

    @staticmethod
    def _get_meta_file(cache_dir: Path) -> Path:
        """Get cache metadata file path"""
        return cache_dir / ".meta.json"

    @staticmethod
    def _get_last_cloned_file() -> Path:
        """Get last cloned repository marker file path"""
        return TEMP_DIR / ".last_cloned_repo"

    @staticmethod
    def write_last_cloned(cache_dir_name: str) -> None:
        """Write last cloned repository marker (for scan-cache location)"""
        last_cloned_file = RepoCacheManager._get_last_cloned_file()
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        with open(last_cloned_file, "w", encoding="utf-8") as f:
            f.write(cache_dir_name)

    @staticmethod
    def load_meta(cache_dir: Path) -> Optional[Dict]:
        """Load cache metadata"""
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
        """Save cache metadata"""
        meta_file = RepoCacheManager._get_meta_file(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

    @staticmethod
    def get_or_clone(
        github_url: str,
        force_refresh: bool = False,
        timeout: int = 300,
        user_input: Optional[str] = None,
        requested_skill: Optional[str] = None,
        install_params: Optional[Dict] = None
    ) -> Tuple[bool, Optional[Path], str]:
        """
        Get repository (prioritize from cache)

        Args:
            github_url: GitHub repository URL
            force_refresh: Whether to force refresh cache
            timeout: Timeout (seconds)
            user_input: User's original input URL/path
            requested_skill: User specified skill_name
            install_params: Other installation parameters

        Returns:
            (success, repository_path, message)
        """
        cache_dir = RepoCacheManager._get_cache_dir(github_url)

        # 1. Check if cache exists
        if cache_dir.exists() and not force_refresh:
            meta = RepoCacheManager.load_meta(cache_dir)
            if meta and meta.get("url") == github_url:
                # Update meta (user may request with different parameters again)
                updated_meta = meta.copy()
                # Always update user_input (keep latest complete URL)
                updated_meta["user_input"] = user_input or github_url
                # If requested_skill not specified, try extracting from user_input
                if requested_skill is None and user_input:
                    _, subpath = FormatDetector.parse_github_subpath(user_input)
                    if subpath:
                        extracted_name = subpath.rstrip('/').split('/')[-1]
                        if extracted_name:
                            requested_skill = extracted_name
                updated_meta["requested_skill"] = requested_skill or ""
                if install_params is not None:
                    updated_meta["install_params"] = install_params
                updated_meta["last_accessed"] = datetime.now().isoformat()
                RepoCacheManager.save_meta(cache_dir, updated_meta)

                # Write last cloned repository marker
                RepoCacheManager.write_last_cloned(cache_dir.name)

                cached_time = meta.get("cached_at", "")
                return True, cache_dir, f"Using cache (cached at {cached_time})"

        # 2. Cache doesn't exist or force refresh, execute clone
        info(f"Cloning repository to cache: {github_url}")

        # If old cache exists, delete first
        if cache_dir.exists():
            try:
                shutil.rmtree(cache_dir, ignore_errors=False)
            except Exception as e:
                error(f"Cannot delete cache directory, please delete manually and retry: {cache_dir}")
                error(f"Error message: {e}")
                return False, None, f"Cache cleanup failed: {e}"

        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # Execute clone
        clone_ok, _ = GitHubHandler.clone_repo(github_url, cache_dir)

        if not clone_ok:
            return False, None, "Repository does not exist or path is incorrect, please confirm:\n1. Repository URL is correct\n2. Is it a sub-skill (try using --skill parameter)\n3. Check mapping table: docs/skills-mapping.md"

        # Save metadata (includes author and repo information)
        # Extract author and repo from URL
        author, repo, _ = _extract_github_info(github_url)

        # Fix: Ensure user_input prioritizes passed value (keep original complete URL)
        # Only fallback to github_url when completely None
        final_user_input = user_input if user_input is not None else github_url

        meta = {
            "url": github_url,
            "author": author or "",
            "repo": repo or "",
            "cached_at": datetime.now().isoformat(),
            "branch": "main",
            "user_input": final_user_input,
            "requested_skill": requested_skill or "",
            "install_params": install_params or {},
            "last_accessed": datetime.now().isoformat()
        }
        RepoCacheManager.save_meta(cache_dir, meta)

        # Write last cloned repository marker
        RepoCacheManager.write_last_cloned(cache_dir.name)

        return True, cache_dir, "Cache created successfully"

    @staticmethod
    def list_cache() -> List[Dict]:
        """
        列出所有缓存

        Returns:
            缓存信息列表
        """
        caches = []
        if not CACHE_DIR.exists():
            return caches

        for cache_dir in CACHE_DIR.iterdir():
            if not cache_dir.is_dir():
                continue

            meta = RepoCacheManager.load_meta(cache_dir)
            if meta:
                # 计算缓存大小
                size_mb = 0
                try:
                    size = sum(f.stat().st_size for f in cache_dir.rglob('*') if f.is_file())
                    size_mb = round(size / (1024 * 1024), 2)
                except Exception:
                    pass

                caches.append({
                    "url": meta.get("url", "unknown"),
                    "cached_at": meta.get("cached_at", ""),
                    "size_mb": size_mb
                })

        return caches

    @staticmethod
    def clear_cache(older_than_hours: Optional[int] = None) -> Dict[str, int]:
        """
        清理缓存

        Args:
            older_than_hours: 只清理超过指定小时数的缓存，None 表示全部清理

        Returns:
            {"cleared": 清理数量, "kept": 保留数量}
        """
        import time
        from datetime import datetime, timedelta

        if not CACHE_DIR.exists():
            return {"cleared": 0, "kept": 0}

        cleared = 0
        kept = 0
        now = time.time()

        for cache_dir in CACHE_DIR.iterdir():
            if not cache_dir.is_dir():
                continue

            should_delete = True

            if older_than_hours is not None:
                meta = RepoCacheManager.load_meta(cache_dir)
                if meta:
                    try:
                        cached_at = datetime.fromisoformat(meta.get("cached_at", ""))
                        age_hours = (now - cached_at.timestamp()) / 3600
                        if age_hours < older_than_hours:
                            should_delete = False
                    except Exception as e:
                        # 日期解析失败时保守保留缓存
                        warn(f"缓存元数据解析失败: {cache_dir.name} - {e}")
                        should_delete = False

            if should_delete:
                try:
                    shutil.rmtree(cache_dir, ignore_errors=False)
                    cleared += 1
                except Exception as e:
                    warn(f"删除缓存失败: {cache_dir.name} - {e}")
            else:
                kept += 1

        return {"cleared": cleared, "kept": kept}

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

        # 安全验证
        is_valid, error_msg = FormatDetector.validate_github_url(github_url)
        if not is_valid:
            error(f"GitHub URL 安全验证失败: {error_msg}")
            return False, target_dir

        # 预清理
        if target_dir.exists():
            info(f"目标目录已存在，清理: {target_dir}")
            try:
                shutil.rmtree(target_dir, ignore_errors=False)
            except Exception as e:
                warn(f"目录清理失败: {target_dir}")
                warn(f"错误信息: {e}")

        # 构建 git 命令
        cmd = ["git"]
        if not get_ssl_verify():
            cmd.extend(["-c", "http.sslVerify=false"])
        cmd.extend(["-c", "core.longPaths=true"])

        # 环境变量
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GIT_ASKPASS"] = "true"

        # 快速探测直连可行性（5秒超时）
        can_direct_connect = False
        try:
            probe_cmd = cmd + ["ls-remote", "--heads", github_url]
            probe_result = subprocess.run(
                probe_cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
                env=env,
            )
            if probe_result.returncode == 0:
                can_direct_connect = True
                info("直连探测成功，优先直连克隆")
        except (subprocess.TimeoutExpired, Exception):
            info("直连探测失败，将使用加速器")

        # 根据探测结果选择克隆策略
        if can_direct_connect:
            # 直连可用，直接克隆
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
                    success(f"克隆成功（直连）: {target_dir}")
                    return True, target_dir
            except Exception as e:
                warn(f"直连克隆失败: {e}")

        # 直连不可用或失败，尝试加速器
        proxies = get_git_proxies()
        for proxy_template in proxies:
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
            except subprocess.TimeoutExpired:
                warn(f"加速器超时: {proxy_url}")
                continue
            except Exception as e:
                warn(f"加速器异常: {e}")
                continue

        # 所有方式均失败
        error("克隆失败：直连和所有加速器均无法连接")
        return False, target_dir

    @staticmethod
    def _recursive_skill_scan(
        root_dir: Path,
        max_depth: int = 5,
        exclude_dirs: Optional[set] = None
    ) -> List[Dict[str, Path]]:
        """递归扫描所有子目录，查找 SKILL.md 文件"""
        if exclude_dirs is None:
            exclude_dirs = {"examples", "templates", "test", "tests", "docs", "reference", ".git", "node_modules", "__pycache__"}

        results = []

        def _scan_recursive(current_dir: Path, current_depth: int, rel_path: str = ""):
            if current_depth > max_depth:
                return

            try:
                for item in current_dir.iterdir():
                    if item.name in exclude_dirs or item.name.startswith('.'):
                        continue

                    if item.is_dir():
                        new_rel_path = f"{rel_path}/{item.name}" if rel_path else item.name

                        if (item / "SKILL.md").exists():
                            results.append({
                                "path": item,
                                "relative_path": new_rel_path
                            })
                            info(f"发现深层技能: {new_rel_path}")

                        _scan_recursive(item, current_depth + 1, new_rel_path)
            except (PermissionError, OSError):
                pass

        _scan_recursive(root_dir, 0)
        return results

    @staticmethod
    def extract_skills(repo_dir: Path, skill_name: Optional[str] = None) -> List[Path]:
        """从仓库中提取技能目录

        Args:
            repo_dir: 仓库目录
            skill_name: 可选，仅提取指定的技能名

        Returns:
            技能目录列表
        """
        skill_dirs = []
        exclude_dirs = {"examples", "templates", "test", "tests", "docs", "reference"}

        # 检测 .skill 包文件
        skill_packages = list(repo_dir.glob("*.skill"))
        if skill_packages:
            info(f"检测到技能包文件: {skill_packages[0].name}")
            extract_dir = repo_dir.parent / f"{repo_dir.name}_extracted"
            extract_ok, extracted = SkillPackHandler.extract_pack(skill_packages[0], extract_dir)
            if extract_ok:
                # 解压成功，把 extracted 当作新的 repo_dir 继续检测
                # （复用后面的多层检测逻辑：递归、多平台、回退机制）
                repo_dir = extracted
            else:
                return skill_dirs

        # 平台优先级配置
        platform_priority = [
            repo_dir / ".agent" / "skills",
            repo_dir / ".claude" / "skills",
            repo_dir / "skills",
            repo_dir / ".claude-plugin",
            repo_dir / ".cursor" / "rules",
            repo_dir,
        ]

        # 检测 Claude Code 版本
        claude_code_skills = []
        agent_skills_dir = repo_dir / ".agent" / "skills"
        if agent_skills_dir.exists():
            for item in agent_skills_dir.glob("*/SKILL.md"):
                if item.parent.name not in exclude_dirs:
                    claude_code_skills.append(item.parent)

        if claude_code_skills:
            return claude_code_skills

        # 按优先级扫描
        for location in platform_priority[1:]:
            if location.exists() and location.is_dir():
                if location == repo_dir:
                    if (location / "SKILL.md").exists():
                        sub_skill_dirs = [
                            item.parent for item in repo_dir.glob("*/SKILL.md")
                            if item.parent.name not in exclude_dirs
                        ]
                        MULTI_SKILL_THRESHOLD = 3
                        if len(sub_skill_dirs) >= MULTI_SKILL_THRESHOLD:
                            info(f"检测到多技能容器: {repo_dir.name} (包含 {len(sub_skill_dirs)} 个子技能)")
                            skill_dirs.extend(sub_skill_dirs)
                        else:
                            skill_dirs.append(location)
                        continue
                    else:
                        skills_dir = repo_dir / "skills"
                        if skills_dir.exists() and skills_dir.is_dir():
                            sub_skill_count = 0
                            sub_skill_candidates = []
                            for item in skills_dir.iterdir():
                                if item.is_dir() and (item / "SKILL.md").exists():
                                    sub_skill_candidates.append(item)
                                    sub_skill_count += 1
                            if sub_skill_count >= 1:
                                info(f"检测到 monorepo: skills/ 目录包含 {sub_skill_count} 个技能")
                                skill_dirs.extend(sub_skill_candidates)
                                continue

                        root_sub_skills = []
                        for item in repo_dir.iterdir():
                            if item.is_dir() and not item.name.startswith(".") and item.name not in exclude_dirs:
                                if (item / "SKILL.md").exists():
                                    root_sub_skills.append(item)
                        if len(root_sub_skills) >= 2:
                            info(f"检测到 monorepo: 根目录包含 {len(root_sub_skills)} 个子技能")
                            skill_dirs.extend(root_sub_skills)
                            continue

                if location.name == "skills" and location.parent == repo_dir:
                    continue

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
                    if item.is_dir() and (not item.name.startswith(".") or item.name == ".claude"):
                        if item.name in exclude_dirs:
                            continue
                        has_skill = (item / "SKILL.md").exists() or list(item.glob("*.md"))
                        if has_skill:
                            skill_dirs.append(item)

        # 回退机制1：递归深度扫描
        if not skill_dirs:
            recursive_results = GitHubHandler._recursive_skill_scan(repo_dir, max_depth=5)
            if recursive_results:
                recursive_results.sort(key=lambda x: x["relative_path"].count('/'))
                skill_dirs = [r["path"] for r in recursive_results]
                info(f"递归扫描: 发现 {len(skill_dirs)} 个深层子技能")

        # 回退机制2：单层子目录
        if not skill_dirs:
            fallback_skills = []
            for item in repo_dir.iterdir():
                if item.is_dir() and not item.name.startswith(".") and item.name not in exclude_dirs:
                    if (item / "SKILL.md").exists():
                        fallback_skills.append(item)
            if fallback_skills:
                info(f"回退检测: 发现 {len(fallback_skills)} 个子技能")
                skill_dirs.extend(fallback_skills)

        # 根据 skill_name 过滤
        if skill_name:
            normalized_target = skill_name.lower().replace('_', '-')
            filtered = []
            for skill_dir in skill_dirs:
                dir_name = skill_dir.name
                # 支持直接匹配和 _/- 变体匹配
                if dir_name.lower() == skill_name.lower() or \
                   dir_name.lower().replace('_', '-') == normalized_target or \
                   dir_name.lower().replace('-', '_') == normalized_target:
                    filtered.append(skill_dir)
                    info(f"过滤匹配: {dir_name}")
            if filtered:
                info(f"已过滤: {len(skill_dirs)} -> {len(filtered)} 个技能")
                skill_dirs = filtered
            else:
                error(f"未找到匹配的技能: {skill_name}")
                error(f"可用技能: {', '.join([s.name for s in skill_dirs[:5]])}{'...' if len(skill_dirs) > 5 else ''}")
                return []  # 返回空列表，不返回全部技能

        return skill_dirs

# =============================================================================
# 共享逻辑
# =============================================================================

def _extract_repo_from_url(github_url: str) -> Optional[str]:
    """从 GitHub URL 提取 user/repo 格式"""
    parsed = urlparse(github_url)
    if "github.com" not in parsed.netloc:
        return None
    path_parts = parsed.path.strip('/').split('/')
    if len(path_parts) >= 2:
        return f"{path_parts[0]}/{path_parts[1]}"
    return None

def _dual_path_skill_check(github_url: str) -> Tuple[bool, str, List[str]]:
    """统一的技能判定"""
    parsed = urlparse(github_url)
    if "github.com" not in parsed.netloc:
        return True, "非 GitHub URL，跳过预检", ["fallback"]

    repo = _extract_repo_from_url(github_url)
    if not repo:
        return True, "无法解析仓库，跳过预检", ["fallback"]

    analyzer = RemoteSkillAnalyzer(repo)
    is_skill, reason = analyzer.check_is_skill_repo()

    if is_skill is True:
        return True, reason, ["analyzer"]
    elif is_skill is False:
        return False, reason, []
    else:
        return True, reason, ["fallback"]

def _process_github_source(
    github_url: str,
    skill_name: Optional[str] = None,
    use_cache: bool = True,
    force_refresh: bool = False,
    temp_dir: Optional[Path] = None,
    user_input: Optional[str] = None,
    install_params: Optional[Dict] = None,
    original_url: Optional[str] = None
) -> Tuple[List[Path], str]:
    """
    处理 GitHub 源（克隆 + 提取技能）

    Args:
        github_url: GitHub 仓库 URL (用于克隆)
        skill_name: 可选，仅提取指定的技能名
        use_cache: 是否使用缓存
        force_refresh: 是否强制刷新缓存
        temp_dir: 临时目录
        user_input: 用户原始输入的 URL/路径 (已废弃，兼容保留)
        install_params: 安装时的其他参数
        original_url: 原始完整 URL (用于 meta 记录和 skill_name 提取)

    Returns:
        (技能目录列表, 消息)
    """
    if temp_dir is None:
        temp_dir = TEMP_DIR
        temp_dir.mkdir(parents=True, exist_ok=True)

    # 统一使用 original_url (兼容旧的 user_input 参数名)
    effective_input = original_url or user_input or github_url

    # 修复: 如果 skill_name 为空，尝试从原始 URL 的 subpath 中提取
    if not skill_name:
        _, subpath = FormatDetector.parse_github_subpath(effective_input)
        if subpath:
            # 提取最后一部分作为 skill_name
            # 例如: skills/baoyu-article-illustrator -> baoyu-article-illustrator
            extracted_name = subpath.rstrip('/').split('/')[-1]
            if extracted_name:
                skill_name = extracted_name
                info(f"从 URL 提取子技能名: {skill_name}")

    # 1. 技能仓库预检
    should_proceed, reason, sources = _dual_path_skill_check(github_url)
    if not should_proceed:
        return [], reason

    # 2. 子技能预检（仅当指定了子技能名）
    if skill_name:
        repo = _extract_repo_from_url(github_url)
        if repo:
            try:
                analyzer = RemoteSkillAnalyzer(repo)
                if not analyzer._verify_single_skill(skill_name):
                    warn(f"子技能预检失败: {skill_name}")
            except Exception:
                pass

    # 3. 缓存机制
    if use_cache:
        cache_ok, cache_dir, cache_msg = RepoCacheManager.get_or_clone(
            github_url,
            force_refresh=force_refresh,
            user_input=effective_input,  # 使用原始完整 URL
            requested_skill=skill_name,
            install_params=install_params
        )
        if cache_ok and cache_dir:
            info(cache_msg)  # 输出缓存状态消息
            scan_dir = cache_dir
        else:
            return [], cache_msg
    else:
        clone_ok, repo_dir = GitHubHandler.clone_repo(github_url, temp_dir / "repo")
        if not clone_ok:
            return [], "仓库不存在或路径错误\n提示: 查看 docs/skills-mapping.md 确认正确的仓库路径"
        scan_dir = repo_dir

    # 4. 处理子路径
    parsed = urlparse(github_url)
    if 'tree' in parsed.path:
        path_parts = parsed.path.strip('/').split('/')
        tree_idx = path_parts.index('tree')
        if len(path_parts) > tree_idx + 2:
            subpath = Path(scan_dir) / '/'.join(path_parts[tree_idx + 2:])
            if subpath.exists():
                scan_dir = subpath
            else:
                return [], f"子路径不存在: {subpath}"

    # 5. 提取技能（应用 skill_name 过滤）
    skill_dirs = GitHubHandler.extract_skills(scan_dir, skill_name)
    if not skill_dirs:
        return [], f"未找到技能，请确认仓库是否为技能仓库"

    return skill_dirs, f"成功获取 {len(skill_dirs)} 个技能"

# =============================================================================
# CLI 入口
# =============================================================================

def main():
    """CLI 入口"""
    parser = argparse.ArgumentParser(
        description="clone_manager.py - GitHub 仓库克隆管理器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 克隆仓库到缓存
  python bin/clone_manager.py clone https://github.com/user/repo

  # 克隆并指定子技能
  python bin/clone_manager.py clone https://github.com/user/repo --skill my-skill

  # 列出缓存
  python bin/clone_manager.py list-cache

  # 清理缓存
  python bin/clone_manager.py clear-cache
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # clone 命令
    clone_parser = subparsers.add_parser("clone", help="克隆 GitHub 仓库")
    clone_parser.add_argument("url", help="GitHub 仓库 URL")
    clone_parser.add_argument("--skill", help="指定子技能名称")
    clone_parser.add_argument("--force", action="store_true", help="强制刷新缓存")
    clone_parser.add_argument("--no-cache", action="store_true", help="不使用缓存")

    # list-cache 命令
    subparsers.add_parser("list-cache", help="列出所有缓存")

    # clear-cache 命令
    clear_parser = subparsers.add_parser("clear-cache", help="清理缓存")
    clear_parser.add_argument("--older-than", type=int, help="只清理超过指定小时数的缓存")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "clone":
        # user_input 始终使用原始 URL (保留完整路径信息)
        original_url = args.url
        requested_skill = getattr(args, 'skill', None)
        install_params = {
            "force": getattr(args, 'force', False),
            "no_cache": getattr(args, 'no_cache', False)
        }

        # 解析根仓库 URL (git clone 只支持根仓库)
        repo_url, _ = FormatDetector.parse_github_subpath(original_url)

        skill_dirs, msg = _process_github_source(
            repo_url,  # 克隆使用根仓库 URL
            skill_name=requested_skill,
            use_cache=not install_params["no_cache"],
            force_refresh=install_params["force"],
            user_input=original_url,  # 兼容旧参数
            install_params=install_params,
            original_url=original_url  # 传递原始完整 URL
        )

        if not skill_dirs:
            error(msg)
            return 1

        success(msg)
        print("技能目录:")
        for skill_dir in skill_dirs:
            print(f"  - {skill_dir}")

        # 打印缓存信息
        cache_dir = RepoCacheManager._get_cache_dir(args.url)
        if cache_dir.exists():
            print("\n缓存信息:")
            print(f"  缓存项目路径: {cache_dir}")
            meta_file = RepoCacheManager._get_meta_file(cache_dir)
            print(f"  .meta.json 文件路径: {meta_file}")
            print("  提示: 用于安全扫描")

        return 0

    elif args.command == "list-cache":
        caches = RepoCacheManager.list_cache()
        if not caches:
            print("没有缓存")
            return 0

        print(f"共有 {len(caches)} 个缓存:")
        for cache in caches:
            print(f"  - {cache['url']}")
            print(f"    缓存时间: {cache['cached_at']}")
            print(f"    大小: {cache['size_mb']} MB")
        return 0

    elif args.command == "clear-cache":
        result = RepoCacheManager.clear_cache(
            older_than_hours=getattr(args, 'older_than', None)
        )
        print(f"清理完成: {result['cleared']} 个已删除, {result['kept']} 个已保留")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
clone_manager.py - GitHub Repository Clone Manager
-----------------------------------------
Responsible for cloning skill repositories from GitHub to local staging

Responsibilities:
1. GitHub repository cloning (with accelerator support)
2. Remote repository analysis (pre-check, caching)
3. Skill directory extraction
4. Repository cache management

Architecture:
    skill_manager -> clone_manager -> security_scanner
                       ↓
                  Staging space (mybox/cache/repos/)

Source: Refactored from skill_manager.py (Apache 2.0)
"""

import argparse
import sys
import os

# Windows UTF-8 compatibility (P0 - must be included in all scripts)
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

# Skill default constants
DEFAULT_SKILL_DESC = "No description"
DEFAULT_SKILL_CATEGORY = "utilities"
DEFAULT_SKILL_TAGS = ["skill"]

# Add project lib directory to sys.path (pre-built dependencies for portable package)
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
    log("INFO", msg, "[INFO]")

def warn(msg: str):
    log("WARN", msg, "[WARN]")

def error(msg: str):
    log("ERROR", msg, "[ERROR]")

# =============================================================================
# Configuration Loading (shared)
# =============================================================================

_config_cache: Optional[dict] = None
_config_mtime: Optional[float] = None

def load_config(use_cache: bool = True) -> dict:
    """
    Load configuration file (supports caching)

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

    # Load configuration (select loading method based on file type)
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            if config_file.suffix == ".json":
                _config_cache = json.load(f)
            else:
                _config_cache = yaml.safe_load(f) or {}
            _config_mtime = config_file.stat().st_mtime
            return _config_cache
    except Exception as e:
        warn(f"Configuration file loading failed: {e}")
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
    """Detect input source format type"""

    @staticmethod
    def validate_github_url(url: str) -> Tuple[bool, Optional[str]]:
        """
        Validate GitHub URL format security, prevent configuration injection attacks

        Args:
            url: GitHub URL to validate

        Returns:
            (is_valid, error_message)
        """
        # Basic format check
        github_pattern = r'^https?://github\.com/[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+(?:/tree/[^/\s]+(?:/[\w\-./]+)?)?/?$'
        if not re.match(github_pattern, url):
            return False, f"Invalid GitHub URL format: {url}"

        # Check for dangerous git configuration injection patterns
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
            (type, path/url, subpath)
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

        warn("Unable to recognize input source type, treating as local directory")
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

        # Fallback: manually parse
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
    """Validate if project is a skill repository"""

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
    """Handle .skill skill packages"""

    @staticmethod
    def extract_pack(pack_file: Path, extract_dir: Path) -> Tuple[bool, Optional[Path]]:
        """
        Extract .skill package

        Returns:
            (success, extract_dir)
        """
        try:
            with zipfile.ZipFile(pack_file, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            return True, extract_dir
        except Exception as e:
            error(f"Skill package extraction failed: {e}")
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

        # Check cache
        cache_dir = RepoCacheManager._get_cache_dir(self.github_url)
        if cache_dir.exists() and self._use_cache:
            meta = RepoCacheManager.load_meta(cache_dir)
            if meta and meta.get("url") == self.github_url:
                result["source"] = "cache"
                info(f"Using local cache for analysis: {self.repo}")
                return self._analyze_from_cache(cache_dir, result)

        # Network probing
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
                warn(f"Failed to read {rel_path}: {e}")

        result["skills"] = sorted(skills, key=lambda x: x["name"])
        return result

    def _analyze_from_network(self, result: Dict) -> Dict:
        """Analyze repository via network"""
        skills = []

        # Detect branch
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

        # Detect root directory SKILL.md
        root_skill_content = self.fetch_file("SKILL.md")
        if root_skill_content:
            root_info = self._parse_skill_md(root_skill_content, "")
            if root_info:
                root_info["is_root"] = True
                root_info["url"] = self.github_url
                skills.append(root_info)

        # Discover sub-skills
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
        """Discover sub-skill SKILL.md paths"""
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
        """Validate URL security"""
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
        """Get file content - automatically select best method"""
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
        """Get file via Raw URL"""
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
        """Try fetching file from specified URL (cross-platform compatible)"""
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
        """Get file via GitHub API (cross-platform compatible)"""
        url = f"{self.API_BASE}/repos/{self.repo}/contents/{file_path}"
        headers = {"Accept": "application/vnd.github.v3.raw"}
        if self.token:
            headers["Authorization"] = f"token {self.token}"

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=3) as response:
                # Check status code (urllib auto-handles redirects, 200-299 means success)
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
        """Unified skill repository pre-check"""
        # Try Raw URL
        content = self.fetch_file("SKILL.md")
        if content:
            return True, f"Raw found SKILL.md (branch: {self.branch})"

        if self.fetch_file("skills/commit/SKILL.md"):
            return True, f"Raw found skills/ directory (branch: {self.branch})"

        return None, "Pre-check timeout or failure, downgrading to clone"

    def _verify_single_skill(self, skill_name: str) -> bool:
        """Lightweight verification: only check if specified skill exists"""
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
# Repository Cache Manager
# =============================================================================

class RepoCacheManager:
    """Manage persistent cache of GitHub repositories"""

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
        timeout: int = 300
    ) -> Tuple[bool, Optional[Path], str]:
        """
        Get repository (prioritize cache)

        Returns:
            (success, repo_path, message)
        """
        cache_dir = RepoCacheManager._get_cache_dir(github_url)

        # 1. Check if cache exists
        if cache_dir.exists() and not force_refresh:
            meta = RepoCacheManager.load_meta(cache_dir)
            if meta and meta.get("url") == github_url:
                cached_time = meta.get("cached_at", "")
                return True, cache_dir, f"Using cache (cached at {cached_time})"

        # 2. Cache doesn't exist or force refresh, execute clone
        info(f"Cloning repository to cache: {github_url}")

        # If old cache exists, delete first
        if cache_dir.exists():
            try:
                subprocess.run(["rm", "-rf", str(cache_dir)], capture_output=True, timeout=10)
            except:
                pass
            if cache_dir.exists():
                warn(f"Cache cleanup failed, using shutil for retry: {cache_dir}")
                time.sleep(0.5)
                try:
                    shutil.rmtree(cache_dir, ignore_errors=False)
                except Exception as e:
                    error(f"Unable to delete cache directory, please manually delete and retry: {cache_dir}")
                    error(f"Error message: {e}")
                    return False, None, f"Cache cleanup failed: {e}"

        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # Execute clone
        clone_ok, _ = GitHubHandler.clone_repo(github_url, cache_dir)

        if not clone_ok:
            return False, None, "Repository does not exist or path error, please confirm:\n1. Repository URL is correct\n2. Is it a sub-skill (try using --skill parameter)\n3. Check mapping table: docs/skills-mapping.md"

        # Save metadata
        meta = {
            "url": github_url,
            "cached_at": datetime.now().isoformat(),
            "branch": "main"
        }
        RepoCacheManager.save_meta(cache_dir, meta)

        return True, cache_dir, "Cache created successfully"

    @staticmethod
    def list_cache() -> List[Dict]:
        """
        List all caches

        Returns:
            Cache information list
        """
        caches = []
        if not CACHE_DIR.exists():
            return caches

        for cache_dir in CACHE_DIR.iterdir():
            if not cache_dir.is_dir():
                continue

            meta = RepoCacheManager.load_meta(cache_dir)
            if meta:
                # Calculate cache size
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
        Clear cache

        Args:
            older_than_hours: Only clear caches older than specified hours, None means clear all

        Returns:
            {"cleared": cleared_count, "kept": kept_count}
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
                        # Date parsing failed, conservatively keep cache
                        warn(f"Cache metadata parsing failed: {cache_dir.name} - {e}")
                        should_delete = False

            if should_delete:
                try:
                    shutil.rmtree(cache_dir, ignore_errors=False)
                    cleared += 1
                except Exception as e:
                    warn(f"Failed to delete cache: {cache_dir.name} - {e}")
            else:
                kept += 1

        return {"cleared": cleared, "kept": kept}

# =============================================================================
# GitHub Handler
# =============================================================================

class GitHubHandler:
    """Handle GitHub repository cloning and extraction"""

    @staticmethod
    def clone_repo(github_url: str, target_dir: Path) -> Tuple[bool, Path]:
        """
        Clone GitHub repository (with accelerator support)

        Returns:
            (success, clone_dir)
        """
        info(f"Cloning repository: {github_url}")

        # Security validation
        is_valid, error_msg = FormatDetector.validate_github_url(github_url)
        if not is_valid:
            error(f"GitHub URL security validation failed: {error_msg}")
            return False, target_dir

        # Pre-cleanup
        if target_dir.exists():
            info(f"Target directory exists, cleaning: {target_dir}")
            try:
                subprocess.run(["rm", "-rf", str(target_dir)], capture_output=True, timeout=10)
            except:
                pass
            if target_dir.exists():
                warn(f"Directory cleanup failed, using shutil for retry: {target_dir}")
                time.sleep(0.5)
                shutil.rmtree(target_dir, ignore_errors=False)

        # Build git command
        cmd = ["git"]
        if not get_ssl_verify():
            cmd.extend(["-c", "http.sslVerify=false"])
        cmd.extend(["-c", "core.longPaths=true"])

        # Environment variables
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GIT_ASKPASS"] = "true"

        # Fast direct connection probe (5 second timeout)
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
                info("Direct connection probe successful, prioritizing direct clone")
        except (subprocess.TimeoutExpired, Exception):
            info("Direct connection probe failed, will use accelerator")

        # Select clone strategy based on probe result
        if can_direct_connect:
            # Direct connection available, clone directly
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
                    success(f"Clone successful (direct): {target_dir}")
                    return True, target_dir
            except Exception as e:
                warn(f"Direct clone failed: {e}")

        # Direct connection unavailable or failed, try accelerators
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
                    success(f"Clone successful (using accelerator): {target_dir}")
                    return True, target_dir
            except subprocess.TimeoutExpired:
                warn(f"Accelerator timeout: {proxy_url}")
                continue
            except Exception as e:
                warn(f"Accelerator exception: {e}")
                continue

        # All methods failed
        error("Clone failed: direct connection and all accelerators unable to connect")
        return False, target_dir

    @staticmethod
    def _recursive_skill_scan(
        root_dir: Path,
        max_depth: int = 5,
        exclude_dirs: Optional[set] = None
    ) -> List[Dict[str, Path]]:
        """Recursively scan all subdirectories for SKILL.md files"""
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
                            info(f"Found deep skill: {new_rel_path}")

                        _scan_recursive(item, current_depth + 1, new_rel_path)
            except (PermissionError, OSError):
                pass

        _scan_recursive(root_dir, 0)
        return results

    @staticmethod
    def extract_skills(repo_dir: Path, skill_name: Optional[str] = None) -> List[Path]:
        """Extract skill directories from repository

        Args:
            repo_dir: Repository directory
            skill_name: Optional, only extract specified skill name

        Returns:
            List of skill directories
        """
        skill_dirs = []
        exclude_dirs = {"examples", "templates", "test", "tests", "docs", "reference"}

        # Check for .skill package files
        skill_packages = list(repo_dir.glob("*.skill"))
        if skill_packages:
            info(f"Detected skill package file: {skill_packages[0].name}")
            extract_dir = repo_dir.parent / f"{repo_dir.name}_extracted"
            extract_ok, extracted = SkillPackHandler.extract_pack(skill_packages[0], extract_dir)
            if extract_ok:
                # Extraction successful, treat extracted as new repo_dir
                # (Reuse following multi-layer detection logic: recursive, multi-platform, fallback mechanism)
                repo_dir = extracted
            else:
                return skill_dirs

        # Platform priority configuration
        platform_priority = [
            repo_dir / ".agent" / "skills",
            repo_dir / ".claude" / "skills",
            repo_dir / "skills",
            repo_dir / ".claude-plugin",
            repo_dir / ".cursor" / "rules",
            repo_dir,
        ]

        # Detect Claude Code version
        claude_code_skills = []
        agent_skills_dir = repo_dir / ".agent" / "skills"
        if agent_skills_dir.exists():
            for item in agent_skills_dir.glob("*/SKILL.md"):
                if item.parent.name not in exclude_dirs:
                    claude_code_skills.append(item.parent)

        if claude_code_skills:
            return claude_code_skills

        # Scan by priority
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
                            info(f"Detected multi-skill container: {repo_dir.name} (contains {len(sub_skill_dirs)} sub-skills)")
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
                                info(f"Detected monorepo: skills/ directory contains {sub_skill_count} skills")
                                skill_dirs.extend(sub_skill_candidates)
                                continue

                        root_sub_skills = []
                        for item in repo_dir.iterdir():
                            if item.is_dir() and not item.name.startswith(".") and item.name not in exclude_dirs:
                                if (item / "SKILL.md").exists():
                                    root_sub_skills.append(item)
                        if len(root_sub_skills) >= 2:
                            info(f"Detected monorepo: root directory contains {len(root_sub_skills)} sub-skills")
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
                    info(f"Detected multi-skill subdirectory: {location.name} (contains {sub_skill_count} sub-skills)")
                    skill_dirs.extend(sub_skill_candidates)
                    continue

                for item in location.iterdir():
                    if item.is_dir() and (not item.name.startswith(".") or item.name == ".claude"):
                        if item.name in exclude_dirs:
                            continue
                        has_skill = (item / "SKILL.md").exists() or list(item.glob("*.md"))
                        if has_skill:
                            skill_dirs.append(item)

        # Fallback mechanism 1: recursive depth scan
        if not skill_dirs:
            recursive_results = GitHubHandler._recursive_skill_scan(repo_dir, max_depth=5)
            if recursive_results:
                recursive_results.sort(key=lambda x: x["relative_path"].count('/'))
                skill_dirs = [r["path"] for r in recursive_results]
                info(f"Recursive scan: found {len(skill_dirs)} deep sub-skills")

        # Fallback mechanism 2: single-layer subdirectories
        if not skill_dirs:
            fallback_skills = []
            for item in repo_dir.iterdir():
                if item.is_dir() and not item.name.startswith(".") and item.name not in exclude_dirs:
                    if (item / "SKILL.md").exists():
                        fallback_skills.append(item)
            if fallback_skills:
                info(f"Fallback detection: found {len(fallback_skills)} sub-skills")
                skill_dirs.extend(fallback_skills)

        # Filter by skill_name
        if skill_name:
            normalized_target = skill_name.lower().replace('_', '-')
            filtered = []
            for skill_dir in skill_dirs:
                dir_name = skill_dir.name
                # Support direct match and _/- variant matching
                if dir_name.lower() == skill_name.lower() or \
                   dir_name.lower().replace('_', '-') == normalized_target or \
                   dir_name.lower().replace('-', '_') == normalized_target:
                    filtered.append(skill_dir)
                    info(f"Filter match: {dir_name}")
            if filtered:
                info(f"Filtered: {len(skill_dirs)} -> {len(filtered)} skills")
                skill_dirs = filtered
            else:
                error(f"No matching skill found: {skill_name}")
                error(f"Available skills: {', '.join([s.name for s in skill_dirs[:5]])}{'...' if len(skill_dirs) > 5 else ''}")
                return []  # Return empty list, not all skills

        return skill_dirs

# =============================================================================
# Shared Logic
# =============================================================================

def _extract_repo_from_url(github_url: str) -> Optional[str]:
    """Extract user/repo format from GitHub URL"""
    parsed = urlparse(github_url)
    if "github.com" not in parsed.netloc:
        return None
    path_parts = parsed.path.strip('/').split('/')
    if len(path_parts) >= 2:
        return f"{path_parts[0]}/{path_parts[1]}"
    return None

def _dual_path_skill_check(github_url: str) -> Tuple[bool, str, List[str]]:
    """Unified skill determination"""
    parsed = urlparse(github_url)
    if "github.com" not in parsed.netloc:
        return True, "Non-GitHub URL, skip pre-check", ["fallback"]

    repo = _extract_repo_from_url(github_url)
    if not repo:
        return True, "Unable to parse repository, skip pre-check", ["fallback"]

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
    temp_dir: Optional[Path] = None
) -> Tuple[List[Path], str]:
    """
    Process GitHub source (clone + extract skills)

    Returns:
        (skill_directory_list, message)
    """
    if temp_dir is None:
        temp_dir = TEMP_DIR
        temp_dir.mkdir(parents=True, exist_ok=True)

    # 1. Skill repository pre-check
    should_proceed, reason, sources = _dual_path_skill_check(github_url)
    if not should_proceed:
        return [], reason

    # 2. Sub-skill pre-check (only when sub-skill name is specified)
    if skill_name:
        repo = _extract_repo_from_url(github_url)
        if repo:
            try:
                analyzer = RemoteSkillAnalyzer(repo)
                if not analyzer._verify_single_skill(skill_name):
                    warn(f"Sub-skill pre-check failed: {skill_name}")
            except Exception:
                pass

    # 3. Cache mechanism
    if use_cache:
        cache_ok, cache_dir, cache_msg = RepoCacheManager.get_or_clone(
            github_url,
            force_refresh=force_refresh
        )
        if cache_ok and cache_dir:
            scan_dir = cache_dir
        else:
            return [], cache_msg
    else:
        clone_ok, repo_dir = GitHubHandler.clone_repo(github_url, temp_dir / "repo")
        if not clone_ok:
            return [], "Repository does not exist or path error\nHint: Check docs/skills-mapping.md to confirm correct repository path"
        scan_dir = repo_dir

    # 4. Handle subpath
    parsed = urlparse(github_url)
    if 'tree' in parsed.path:
        path_parts = parsed.path.strip('/').split('/')
        tree_idx = path_parts.index('tree')
        if len(path_parts) > tree_idx + 2:
            subpath = Path(scan_dir) / '/'.join(path_parts[tree_idx + 2:])
            if subpath.exists():
                scan_dir = subpath
            else:
                return [], f"Subpath does not exist: {subpath}"

    # 5. Extract skills (apply skill_name filter)
    skill_dirs = GitHubHandler.extract_skills(scan_dir, skill_name)
    if not skill_dirs:
        return [], f"No skills found, please confirm if repository is a skill repository"

    return skill_dirs, f"Successfully obtained {len(skill_dirs)} skills"

# =============================================================================
# CLI Entry
# =============================================================================

def main():
    """CLI entry"""
    parser = argparse.ArgumentParser(
        description="clone_manager.py - GitHub Repository Clone Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Clone repository to cache
  python bin/clone_manager.py clone https://github.com/user/repo

  # Clone and specify sub-skill
  python bin/clone_manager.py clone https://github.com/user/repo --skill my-skill

  # List caches
  python bin/clone_manager.py list-cache

  # Clear cache
  python bin/clone_manager.py clear-cache
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # clone command
    clone_parser = subparsers.add_parser("clone", help="Clone GitHub repository")
    clone_parser.add_argument("url", help="GitHub repository URL")
    clone_parser.add_argument("--skill", help="Specify sub-skill name")
    clone_parser.add_argument("--force", action="store_true", help="Force refresh cache")
    clone_parser.add_argument("--no-cache", action="store_true", help="Do not use cache")

    # list-cache command
    subparsers.add_parser("list-cache", help="List all caches")

    # clear-cache command
    clear_parser = subparsers.add_parser("clear-cache", help="Clear cache")
    clear_parser.add_argument("--older-than", type=int, help="Only clear caches older than specified hours")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "clone":
        skill_dirs, msg = _process_github_source(
            args.url,
            skill_name=getattr(args, 'skill', None),
            use_cache=not getattr(args, 'no_cache', False),
            force_refresh=getattr(args, 'force', False)
        )

        if not skill_dirs:
            error(msg)
            return 1

        success(msg)
        print("Skill directories:")
        for skill_dir in skill_dirs:
            print(f"  - {skill_dir}")
        return 0

    elif args.command == "list-cache":
        caches = RepoCacheManager.list_cache()
        if not caches:
            print("No cache")
            return 0

        print(f"Total {len(caches)} caches:")
        for cache in caches:
            print(f"  - {cache['url']}")
            print(f"    Cached at: {cache['cached_at']}")
            print(f"    Size: {cache['size_mb']} MB")
        return 0

    elif args.command == "clear-cache":
        result = RepoCacheManager.clear_cache(
            older_than_hours=getattr(args, 'older_than', None)
        )
        print(f"Clear complete: {result['cleared']} deleted, {result['kept']} kept")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
clone_manager.py - GitHub 仓库克隆管理器
-----------------------------------------
负责从 GitHub 克隆技能仓库到本地暂存空间

职责:
1. GitHub 仓库克隆（支持加速器）
2. 远程仓库分析（预检、缓存）
3. 技能目录提取
4. 仓库缓存管理

Architecture:
    skill_manager → clone_manager → security_scanner
                       ↓
                  暂存空间 (mybox/cache/repos/)

Source: Refactored from skill_manager.py (Apache 2.0)
"""

import argparse
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
# 路径配置
# =============================================================================

BASE_DIR = Path(__file__).parent.parent
CACHE_DIR = BASE_DIR / "mybox" / "cache" / "repos"
TEMP_DIR = BASE_DIR / "mybox" / "temp"

# 技能默认值常量
DEFAULT_SKILL_DESC = "无描述"
DEFAULT_SKILL_CATEGORY = "utilities"
DEFAULT_SKILL_TAGS = ["skill"]

# 添加项目 lib 目录到 sys.path（绿色包预置依赖）
_lib_dir = Path(__file__).parent.parent / "lib"
if _lib_dir.exists():
    sys.path.insert(0, str(_lib_dir))

# 添加 bin 目录到 sys.path（用于导入其他模块）
_bin_dir = Path(__file__).parent
if str(_bin_dir) not in sys.path:
    sys.path.insert(0, str(_bin_dir))

# =============================================================================
# 日志工具
# =============================================================================

def log(level: str, message: str, emoji: str = ""):
    """统一的日志输出"""
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
# 配置加载（共享）
# =============================================================================

_config_cache: Optional[dict] = None
_config_mtime: Optional[float] = None

def load_config(use_cache: bool = True) -> dict:
    """
    加载配置文件（支持缓存）

    配置文件优先级（按顺序）：
    1. <BASE_DIR>/config.json（推荐，JSON格式）
    2. <BASE_DIR>/.claude/config/config.yml（向后兼容，YAML格式）

    Args:
        use_cache: 是否使用缓存（默认 True）

    Returns:
        配置字典
    """
    global _config_cache, _config_mtime

    # 配置文件路径列表（按优先级）
    config_files = [
        BASE_DIR / "config.json",
        BASE_DIR / ".claude" / "config" / "config.yml"
    ]

    # 查找存在的配置文件
    config_file = None
    for cf in config_files:
        if cf.exists():
            config_file = cf
            break

    if not config_file:
        return {}

    # 检查缓存有效性
    if use_cache and _config_cache is not None:
        current_mtime = config_file.stat().st_mtime
        if current_mtime == _config_mtime:
            return _config_cache

    # 加载配置（根据文件类型选择加载方式）
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            if config_file.suffix == ".json":
                _config_cache = json.load(f)
            else:
                _config_cache = yaml.safe_load(f) or {}
            _config_mtime = config_file.stat().st_mtime
            return _config_cache
    except Exception as e:
        warn(f"配置文件加载失败: {e}")
        return {}

def clear_config_cache() -> None:
    """清除配置缓存"""
    global _config_cache, _config_mtime
    _config_cache = None
    _config_mtime = None

def get_git_proxies() -> list:
    """获取 Git 加速器列表"""
    config = load_config()
    return config.get("git", {}).get("proxies", [
        "https://ghp.ci/{repo}",
        "https://ghproxy.net/{repo}",
    ])

def get_ssl_verify() -> bool:
    """获取 SSL 验证设置"""
    config = load_config()
    return config.get("git", {}).get("ssl_verify", True)

def get_raw_proxies() -> list:
    """获取 Raw URL 加速器列表"""
    config = load_config()
    return config.get("raw", {}).get("proxies", [
        "https://ghp.ci/{path}",
        "https://raw.fastgit.org/{path}",
    ])

# =============================================================================
# 格式检测器
# =============================================================================

class FormatDetector:
    """检测输入源的格式类型"""

    @staticmethod
    def validate_github_url(url: str) -> Tuple[bool, Optional[str]]:
        """
        验证 GitHub URL 格式安全性，防止配置注入攻击

        Args:
            url: 待验证的 GitHub URL

        Returns:
            (是否有效, 错误信息)
        """
        # 基础格式检查
        github_pattern = r'^https?://github\.com/[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+(?:/tree/[^/\s]+(?:/[\w\-./]+)?)?/?$'
        if not re.match(github_pattern, url):
            return False, f"无效的 GitHub URL 格式: {url}"

        # 检查危险的 git 配置注入模式
        dangerous_patterns = [
            '--config=', '-c=', '--upload-pack=', '--receive-pack=',
            '--exec=', '&&', '||', '|', '`', '$(', '\n', '\r', '\x00',
        ]

        url_lower = url.lower()
        for pattern in dangerous_patterns:
            if pattern in url_lower:
                return False, f"URL 包含危险字符或模式: {pattern}"

        # 检查 URL 编码绕过尝试
        if '%2' in url.lower():
            return False, "URL 包含可疑的编码字符"

        return True, None

    @staticmethod
    def parse_github_subpath(github_url: str) -> Tuple[str, Optional[str]]:
        """
        解析 GitHub URL，提取子路径

        Returns:
            (仓库URL, 子路径)
        """
        is_valid, error_msg = FormatDetector.validate_github_url(github_url)
        if not is_valid:
            raise ValueError(f"GitHub URL 安全验证失败: {error_msg}")

        parsed = urlparse(github_url)
        path_parts = parsed.path.strip('/').split('/')

        # 查找 /tree/ 分隔符
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
        检测输入源类型

        Returns:
            (类型, 路径/URL, 子路径)
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

# =============================================================================
# 技能标准化器（提取所需部分）
# =============================================================================

class SkillNormalizer:
    """将各种格式标准化为官方 SKILL.md 格式"""

    @staticmethod
    def extract_frontmatter(content: str) -> Dict[str, Any]:
        """从 SKILL.md 提取 YAML frontmatter"""
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

        # 降级：手动解析
        result = {}
        for line in yaml_content.split('\n'):
            if ':' in line and not line.strip().startswith('#'):
                key, value = line.split(':', 1)
                result[key.strip()] = value.strip().strip('"').strip("'")
        return result

# =============================================================================
# 项目验证器
# =============================================================================

class ProjectValidator:
    """验证项目是否为技能仓库"""

    TOOL_PROJECT_FILES = [
        "setup.py", "Cargo.toml", "go.mod",
    ]

    AMBIGUOUS_PROJECT_FILES = [
        "pyproject.toml", "package.json",
    ]

# =============================================================================
# 技能包处理器
# =============================================================================

class SkillPackHandler:
    """处理 .skill 技能包"""

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
# 远程技能分析器
# =============================================================================

class RemoteSkillAnalyzer:
    """分析远程 GitHub 仓库的技能信息"""

    API_BASE = "https://api.github.com"
    RAW_BASE = "https://raw.githubusercontent.com"

    def __init__(self, repo: str, branch: str = "main", token: Optional[str] = None):
        """
        Args:
            repo: user/repo 格式
            branch: 分支名
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
        """分析仓库，返回技能信息"""
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
                info(f"使用本地缓存分析: {self.repo}")
                return self._analyze_from_cache(cache_dir, result)

        # 网络探测
        result["source"] = "network"
        return self._analyze_from_network(result)

    def _analyze_from_cache(self, cache_dir: Path, result: Dict) -> Dict:
        """从本地缓存分析仓库"""
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
        """通过网络分析仓库"""
        skills = []

        # 检测分支
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

        # 探测子技能
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
        """探测子技能 SKILL.md 路径"""
        skill_paths = []
        checked = set()

        # 常见技能名称
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
        """解析 SKILL.md 内容"""
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
# 仓库缓存管理器
# =============================================================================

class RepoCacheManager:
    """管理 GitHub 仓库的持久化缓存"""

    @staticmethod
    def _sanitize_url(url: str) -> str:
        """将 URL 转换为安全的目录名"""
        clean = url.replace("https://", "").replace("http://", "")
        clean = clean.replace("/", "_").replace("\\", "_")
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

        Returns:
            (成功, 仓库路径, 消息)
        """
        cache_dir = RepoCacheManager._get_cache_dir(github_url)

        # 1. 检查缓存是否存在
        if cache_dir.exists() and not force_refresh:
            meta = RepoCacheManager.load_meta(cache_dir)
            if meta and meta.get("url") == github_url:
                cached_time = meta.get("cached_at", "")
                return True, cache_dir, f"使用缓存 (缓存于 {cached_time})"

        # 2. 缓存不存在或强制刷新，执行克隆
        info(f"克隆仓库到缓存: {github_url}")

        # 如果旧缓存存在，先删除
        if cache_dir.exists():
            try:
                subprocess.run(["rm", "-rf", str(cache_dir)], capture_output=True, timeout=10)
            except:
                pass
            if cache_dir.exists():
                warn(f"缓存清理失败，使用 shutil 强制重试: {cache_dir}")
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
            "branch": "main"
        }
        RepoCacheManager.save_meta(cache_dir, meta)

        return True, cache_dir, "缓存创建成功"

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
                subprocess.run(["rm", "-rf", str(target_dir)], capture_output=True, timeout=10)
            except:
                pass
            if target_dir.exists():
                warn(f"目录清理失败，使用 shutil 强制重试: {target_dir}")
                time.sleep(0.5)
                shutil.rmtree(target_dir, ignore_errors=False)

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
    temp_dir: Optional[Path] = None
) -> Tuple[List[Path], str]:
    """
    处理 GitHub 源（克隆 + 提取技能）

    Returns:
        (技能目录列表, 消息)
    """
    if temp_dir is None:
        temp_dir = TEMP_DIR
        temp_dir.mkdir(parents=True, exist_ok=True)

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
            force_refresh=force_refresh
        )
        if cache_ok and cache_dir:
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
        print("技能目录:")
        for skill_dir in skill_dirs:
            print(f"  - {skill_dir}")
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

"""
初始化检查脚本 - 跨平台离线安装支持
支持 Windows (win32) 和 macOS (darwin)
"""
import json
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


import ssl
import subprocess
import time
import site
from pathlib import Path
import urllib.request
import zipfile
import shlex

# =============================================================================
# 路径配置
# =============================================================================

BASE_DIR = Path(__file__).parent.parent
SKILLS_DB_FILE = BASE_DIR / ".claude" / "skills" / "skills.db"
VERSION_CACHE = BASE_DIR / ".claude" / "state" / ".version"
UPDATE_CACHE = BASE_DIR / ".claude" / "state" / ".update_cache"
OFFLINE_PACKAGES = BASE_DIR / "mybox" / "cache" / "packages"

# =============================================================================
# 依赖配置
# =============================================================================

# PyPI 核心依赖 (模块名 -> 包名)
# pip 必须在最前面，因为它用于安装其他包
CORE_DEPS = [
    ('pip', 'pip'),
    ('tinydb', 'TinyDB'),
    ('yaml', 'PyYAML'),
    ('yara_x', 'yara-x'),
    ('frontmatter', 'python-frontmatter'),
    ('confusable_homoglyphs', 'confusable-homoglyphs'),
    # cisco-ai-skill-scanner 传递依赖
    ('httpx', 'httpx'),
    ('httpcore', 'httpcore'),
    ('h11', 'h11'),
    ('anyio', 'anyio'),
    ('certifi', 'certifi'),
    ('idna', 'idna'),
    ('typing_extensions', 'typing_extensions'),
]

# GitHub/源码包依赖
# 格式: (模块名, 包名, zip文件, 是否仅本地安装, github_repo)
SOURCE_DEPS = [
    ('skill_scanner', 'cisco-ai-skill-scanner', 'cisco-skill-scanner-lite.zip', True, 'cisco-ai-defense/skill-scanner'),
]

# =============================================================================
# 平台检测
# =============================================================================

def get_platform_info():
    """获取平台信息

    Returns:
        (platform_dir, platform_name) 或 (None, None)
    """
    if sys.platform == 'win32':
        return 'windows', 'Windows'
    elif sys.platform == 'darwin':
        return 'darwin', 'macOS'
    return None, 'Unknown'


def get_site_packages_path():
    """获取 site-packages 路径（优先使用标准 Lib/site-packages）"""
    try:
        site_packages = site.getsitepackages()
        if site_packages:
            # 优先返回标准的 Lib/site-packages 路径
            # 便携版 Python 通常有多个路径，最后一个是 Lib/site-packages
            for sp in reversed(site_packages):
                if 'Lib/site-packages' in str(sp):
                    return Path(sp)
            # 如果没有找到 Lib/site-packages，返回最后一个
            return Path(site_packages[-1])
    except (AttributeError, OSError):
        pass
    return None


# =============================================================================
# 镜像源
# =============================================================================

PYPI_MIRRORS = [
    ('官方 (全球)', 'https://pypi.org/simple'),
    ('清华 (中国)', 'https://pypi.tuna.tsinghua.edu.cn/simple'),
    ('阿里云 (中国)', 'https://mirrors.aliyun.com/pypi/simple/'),
]

def get_fastest_mirror(timeout=3):
    """测速选择最快镜像源"""
    results = []
    for name, url in PYPI_MIRRORS:
        try:
            start = time.time()
            urllib.request.urlopen(url, timeout=timeout)
            elapsed = time.time() - start
            results.append((elapsed, name, url))
        except (urllib.error.URLError, OSError):
            pass
    if results:
        results.sort()
        return results[0][1], results[0][2]
    return '官方 (全球)', 'https://pypi.org/simple'


# =============================================================================
# 依赖检查
# =============================================================================

def check_pypi_deps():
    """检查 PyPI 核心依赖

    Returns:
        list: 缺失的包名列表
    """
    missing = []
    for module, pkg in CORE_DEPS:
        try:
            __import__(module)
        except ImportError:
            missing.append(pkg)
    return missing


def check_source_deps():
    """检查源码包依赖

    Returns:
        list: 缺失的依赖信息字典列表
    """
    missing = []
    source_dir = OFFLINE_PACKAGES / "source"

    for item in SOURCE_DEPS:
        # 兼容新旧格式: (module, pkg, zip_file, local_only, github_repo?)
        module = item[0]
        pkg = item[1]
        zip_file = item[2]
        local_only = item[3] if len(item) > 3 else False
        github_repo = item[4] if len(item) > 4 else None

        try:
            __import__(module)
        except ImportError:
            zip_path = source_dir / zip_file
            has_offline = zip_path.exists() if source_dir.exists() else False

            install_info = {
                "name": pkg,
                "module": module,
                "has_offline": has_offline,
                "local_only": local_only,
            }

            if has_offline:
                install_info["offline_path"] = str(zip_path)
                install_info["install_method"] = "extract"
                install_info["install_hint"] = "解压到 site-packages 目录"
            elif not local_only and github_repo:
                # 仅非本地安装限制的包才生成在线安装命令
                install_info["online_install"] = f"pip install git+https://github.com/{github_repo}.git"

            missing.append(install_info)

    return missing


# =============================================================================
# 自动安装
# =============================================================================

def install_pip_wheel(offline_dir, site_packages):
    """直接解压 pip wheel 到 site-packages（无需 pip 自身）

    Args:
        offline_dir: 本地缓存目录
        site_packages: site-packages 路径

    Returns:
        bool: 是否成功
    """
    if not offline_dir or not offline_dir.exists():
        return False

    if not site_packages:
        return False

    # 查找 pip wheel 文件
    pip_wheels = list(offline_dir.glob("pip-*-py3-none-any.whl"))
    if not pip_wheels:
        return False

    try:
        with zipfile.ZipFile(pip_wheels[0]) as zf:
            zf.extractall(site_packages)
        return True
    except (zipfile.BadZipFile, OSError, IOError):
        return False


def install_package(pkg_name, offline_dir=None):
    """安装单个包，优先本地缓存

    Args:
        pkg_name: 包名
        offline_dir: 本地缓存目录

    Returns:
        (success, method): (是否成功, 安装方法)
    """
    # 1. 尝试本地安装
    if offline_dir and offline_dir.exists():
        try:
            cmd = [sys.executable, "-m", "pip", "install", "--no-index",
                   f"--find-links={offline_dir}", pkg_name]
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode == 0:
                return True, "offline"
        except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
            pass

    # 2. 尝试在线安装
    try:
        cmd = [sys.executable, "-m", "pip", "install", pkg_name]
        result = subprocess.run(cmd, capture_output=True, timeout=180)
        return result.returncode == 0, "online"
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        return False, "failed"


def install_source_package(zip_path, site_packages):
    """解压安装源码包（安全版本，防止 Zip Slip）

    Args:
        zip_path: 压缩包路径
        site_packages: site-packages 路径

    Returns:
        bool: 是否成功
    """
    if not site_packages:
        return False
    try:
        with zipfile.ZipFile(zip_path) as zf:
            # 检查 zip 顶层目录结构
            top_dirs = set()
            for name in zf.namelist():
                if name.endswith('/'):
                    continue
                parts = name.split('/')
                if len(parts) > 1:
                    top_dirs.add(parts[0])

            # 确定前缀
            if len(top_dirs) == 1:
                prefix = list(top_dirs)[0] + '/'
            else:
                prefix = ''

            # 安全解压：验证路径，防止 Zip Slip
            for member in zf.namelist():
                if not member.startswith(prefix):
                    continue

                # 获取相对路径
                rel_path = member[len(prefix):] if prefix else member
                if not rel_path or rel_path.startswith('/'):
                    continue

                # 验证目标路径在 site-packages 内
                target_path = (site_packages / rel_path).resolve()
                try:
                    target_path.relative_to(site_packages.resolve())
                except ValueError:
                    # 路径逃逸，跳过
                    continue

                if member.endswith('/'):
                    target_path.mkdir(parents=True, exist_ok=True)
                else:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(target_path, 'wb') as f:
                        f.write(zf.read(member))
        return True
    except (zipfile.BadZipFile, OSError, IOError):
        return False


def auto_install_deps(missing_pypi, missing_source):
    """自动安装缺失依赖

    Args:
        missing_pypi: 缺失的 PyPI 包列表
        missing_source: 缺失的源码包信息列表

    Returns:
        dict: {pypi_failed: [], source_failed: [], installed: []}
    """
    # 缓存平台信息和 site-packages 路径
    platform_dir, _ = get_platform_info()
    offline_dir = OFFLINE_PACKAGES / platform_dir if platform_dir else None
    site_packages = get_site_packages_path()

    result = {
        "pypi_failed": [],
        "source_failed": [],
        "installed": []
    }

    # 优先处理 pip（如果缺失）
    pip_missing = 'pip' in missing_pypi
    other_packages = [p for p in missing_pypi if p != 'pip']

    if pip_missing:
        # 直接解压 pip wheel，无需 pip 自身
        success = install_pip_wheel(offline_dir, site_packages)
        if success:
            result["installed"].append("pip (offline)")
        else:
            result["pypi_failed"].append("pip")
            # pip 安装失败，无法继续安装其他包
            other_packages = []

    # 安装其他 PyPI 包（需要 pip）
    for pkg in other_packages:
        success, method = install_package(pkg, offline_dir)
        if success:
            result["installed"].append(f"{pkg} ({method})")
        else:
            result["pypi_failed"].append(pkg)

    # 安装源码包
    for dep in missing_source:
        if dep.get("has_offline"):
            zip_path = Path(dep["offline_path"])
            success = install_source_package(zip_path, site_packages)
            if success:
                result["installed"].append(f"{dep['name']} (offline)")
            else:
                result["source_failed"].append(dep["name"])
        else:
            result["source_failed"].append(dep["name"])

    return result


# =============================================================================
# 离线安装命令生成 (保留用于手动安装场景)
# =============================================================================

def generate_install_commands(missing_pypi, missing_source):
    """生成离线优先的安装命令（安全版本，防止命令注入）

    Returns:
        dict: {pypi_commands: [], source_commands: [], extract_commands: []}
    """
    # 缓存平台信息和 site-packages 路径
    platform_dir, platform_name = get_platform_info()
    offline_dir = OFFLINE_PACKAGES / platform_dir if platform_dir else None
    site_packages = get_site_packages_path()

    commands = {
        "pypi_commands": [],
        "source_commands": [],
        "extract_commands": [],
        "platform": platform_name,
        "offline_available": offline_dir.exists() if offline_dir else False,
    }

    # PyPI 包安装命令
    for pkg in missing_pypi:
        # 使用 shlex.quote() 防止命令注入
        safe_pkg = shlex.quote(pkg)
        if offline_dir and offline_dir.exists():
            # 离线优先
            safe_platform = shlex.quote(str(offline_dir))
            cmd = f"python -m pip install --no-index --find-links={safe_platform} {safe_pkg}"
            fallback = f"python -m pip install {safe_pkg}"
            commands["pypi_commands"].append(f"{cmd} || {fallback}")
        else:
            # 在线安装
            commands["pypi_commands"].append(f"python -m pip install {safe_pkg}")

    # 源码包安装命令
    for dep in missing_source:
        if dep.get("has_offline"):
            zip_path = dep["offline_path"]
            if site_packages:
                # 生成安全的解压命令（使用脚本方式，避免命令注入）
                safe_zip = shlex.quote(str(zip_path))
                safe_site = shlex.quote(str(site_packages))
                # 使用 heredoc 方式生成临时脚本
                commands["extract_commands"].append(
                    f"python - << 'EOF'\n"
                    f"import zipfile\n"
                    f"from pathlib import Path\n"
                    f"zip_path = Path({safe_zip})\n"
                    f"site_pkgs = Path({safe_site})\n"
                    f"with zipfile.ZipFile(zip_path) as zf:\n"
                    f"    for m in zf.namelist():\n"
                    f"        p = m.split('/', 1)[1] if m.count('/') > 0 else m\n"
                    f"        if p and not p.startswith('/'):\n"
                    f"            target = (site_pkgs / p).resolve()\n"
                    f"            try:\n"
                    f"                target.relative_to(site_pkgs.resolve())\n"
                    f"                if m.endswith('/'):\n"
                    f"                    target.mkdir(parents=True, exist_ok=True)\n"
                    f"                else:\n"
                    f"                    target.parent.mkdir(parents=True, exist_ok=True)\n"
                    f"                    target.write_bytes(zf.read(m))\n"
                    f"            except ValueError:\n"
                    f"                pass  # 跳过路径逃逸的文件\n"
                    f"EOF"
                )
            else:
                commands["source_commands"].append(
                    f"# 解压 {dep['name']} 到 python/Lib/site-packages"
                )
        elif dep.get("online_install"):
            commands["source_commands"].append(dep["online_install"])

    return commands


# =============================================================================
# 版本更新检测
# =============================================================================

def get_local_version():
    """获取本地版本号"""
    config_file = BASE_DIR / "config.json"
    if config_file.exists():
        try:
            config = json.loads(config_file.read_text(encoding="utf-8"))
            version = config.get("version", "").strip()
            if version:
                return version
        except (json.JSONDecodeError, OSError, IOError):
            pass
    if VERSION_CACHE.exists():
        try:
            return VERSION_CACHE.read_text().strip()
        except (OSError, IOError):
            pass
    return "0.0.0"


def check_update():
    """检查版本更新"""
    # 冷却检查：7天内不重复请求
    if UPDATE_CACHE.exists() and time.time() - UPDATE_CACHE.stat().st_mtime < 604800:
        return None

    local = get_local_version()

    try:
        ssl_context = ssl.create_default_context()
        with urllib.request.urlopen(
            "https://api.github.com/repos/canishowtime/ai-station-navigator/releases/latest",
            timeout=5,
            context=ssl_context
        ) as r:
            release = json.loads(r.read())
            remote = release["tag_name"].lstrip("v")

            local_parts = list(map(int, local.split(".")))
            remote_parts = list(map(int, remote.split(".")))

            # 更新缓存
            VERSION_CACHE.parent.mkdir(parents=True, exist_ok=True)
            VERSION_CACHE.write_text(remote)
            UPDATE_CACHE.touch()

            if remote_parts > local_parts:
                return {
                    "has_update": True,
                    "local": local,
                    "remote": remote,
                    "url": release['html_url'],
                    "notes": release.get('body', '')[:200]
                }
            else:
                return {"has_update": False, "version": local}
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError, ValueError, OSError) as e:
        # 网络错误或解析错误，静默忽略
        pass
    return None


# =============================================================================
# 技能列表
# =============================================================================

def refresh_mapping():
    """刷新技能映射表"""
    script_path = BASE_DIR / 'bin' / 'register_missing_skills.py'
    if not script_path.exists():
        return False
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        return False


def get_skills_list():
    """从数据库获取技能名称列表"""
    if not SKILLS_DB_FILE.exists():
        return []

    try:
        with open(SKILLS_DB_FILE, 'r', encoding='utf-8') as f:
            db = json.load(f)

        skills = []
        for doc in db.get("_default", {}).values():
            name = doc.get("name", "")
            if name:
                skills.append(name)
        return sorted(skills)
    except (json.JSONDecodeError, OSError, IOError):
        return []


# =============================================================================
# 主函数
# =============================================================================

def main():
    output = {
        "platform": None,
        "deps": None,
        "install": None,
        "update": None,
        "skills": [],
        "skills_count": 0,
        "need_install_reminder": False
    }

    # 平台信息（只调用一次）
    platform_dir, platform_name = get_platform_info()
    output["platform"] = platform_name

    # 1. 检查 PyPI 依赖
    missing_pypi = check_pypi_deps()

    # 2. 检查源码依赖
    missing_source = check_source_deps()

    # 3. 自动安装缺失依赖
    if missing_pypi or missing_source:
        install_result = auto_install_deps(missing_pypi, missing_source)

        # 只报告安装失败的
        if install_result["pypi_failed"] or install_result["source_failed"]:
            output["deps"] = {
                "pypi_failed": install_result["pypi_failed"],
                "source_failed": install_result["source_failed"],
            }
            # 失败时生成手动安装命令
            # 传递完整的 missing_source 信息，让 generate_install_commands 自己过滤
            failed_source_deps = [d for d in missing_source if d["name"] in install_result["source_failed"]]
            commands = generate_install_commands(
                install_result["pypi_failed"],
                failed_source_deps
            )
            output["install"] = commands

            if not commands["offline_available"]:
                _, mirror_url = get_fastest_mirror()
                output["install"]["fallback_mirror"] = mirror_url

        # 报告安装成功的
        if install_result["installed"]:
            output["install"] = output.get("install") or {}
            output["install"]["installed"] = install_result["installed"]

    # 4. 刷新映射表
    refresh_mapping()

    # 5. 版本检测
    update_info = check_update()
    if update_info:
        output["update"] = update_info

    # 6. 获取技能列表
    skills = get_skills_list()
    output["skills"] = skills
    output["skills_count"] = len(skills)
    output["need_install_reminder"] = len(skills) < 10

    # 输出
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

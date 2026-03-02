"""
Initialization Check Script - Cross-platform Offline Installation Support
Supports Windows (win32) and macOS (darwin)
"""
import json
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


import ssl
import subprocess
import time
import site
from pathlib import Path
import urllib.request
import zipfile
import shlex

# =============================================================================
# Path Configuration
# =============================================================================

BASE_DIR = Path(__file__).parent.parent
SKILLS_DB_FILE = BASE_DIR / ".claude" / "skills" / "skills.db"
VERSION_CACHE = BASE_DIR / ".claude" / "state" / ".version"
UPDATE_CACHE = BASE_DIR / ".claude" / "state" / ".update_cache"
OFFLINE_PACKAGES = BASE_DIR / "mybox" / "cache" / "packages"

# =============================================================================
# Dependency Configuration
# =============================================================================

# PyPI Core Dependencies (module name -> package name)
# pip must be first as it's used to install other packages
CORE_DEPS = [
    ('pip', 'pip'),
    ('tinydb', 'TinyDB'),
    ('yaml', 'PyYAML'),
    ('yara_x', 'yara-x'),
    ('frontmatter', 'python-frontmatter'),
    ('confusable_homoglyphs', 'confusable-homoglyphs'),
    # cisco-ai-skill-scanner transitive dependencies
    ('httpx', 'httpx'),
    ('httpcore', 'httpcore'),
    ('h11', 'h11'),
    ('anyio', 'anyio'),
    ('certifi', 'certifi'),
    ('idna', 'idna'),
    ('typing_extensions', 'typing_extensions'),
]

# GitHub/Source Package Dependencies
# Format: (module_name, package_name, zip_file, local_only, github_repo)
SOURCE_DEPS = [
    ('skill_scanner', 'cisco-ai-skill-scanner', 'cisco-skill-scanner-lite.zip', True, 'cisco-ai-defense/skill-scanner'),
]

# =============================================================================
# Platform Detection
# =============================================================================

def get_platform_info():
    """Get platform information

    Returns:
        (platform_dir, platform_name) or (None, None)
    """
    if sys.platform == 'win32':
        return 'windows', 'Windows'
    elif sys.platform == 'darwin':
        return 'darwin', 'macOS'
    return None, 'Unknown'


def get_site_packages_path():
    """Get site-packages path (prefer standard Lib/site-packages)"""
    try:
        # macOS: prioritize user directory to avoid permission issues
        if sys.platform == 'darwin' and site.USER_SITE:
            user_site = Path(site.USER_SITE)
            if user_site.exists() or user_site.parent.exists():
                return user_site

        site_packages = site.getsitepackages()
        if site_packages:
            # Prefer standard Lib/site-packages path
            # Portable Python usually has multiple paths, last is Lib/site-packages
            for sp in reversed(site_packages):
                if 'Lib/site-packages' in str(sp):
                    return Path(sp)
            # If no Lib/site-packages found, return last one
            return Path(site_packages[-1])
    except (AttributeError, OSError):
        pass
    return None


# =============================================================================
# Mirror Sources
# =============================================================================

PYPI_MIRRORS = [
    ('Official (Global)', 'https://pypi.org/simple'),
    ('Tsinghua (China)', 'https://pypi.tuna.tsinghua.edu.cn/simple'),
    ('Aliyun (China)', 'https://mirrors.aliyun.com/pypi/simple/'),
]

def get_fastest_mirror(timeout=3):
    """Speed test to select fastest mirror"""
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
    return 'Official (Global)', 'https://pypi.org/simple'


# =============================================================================
# Dependency Check
# =============================================================================

def check_pypi_deps():
    """Check PyPI core dependencies

    Returns:
        list: List of missing package names
    """
    missing = []
    for module, pkg in CORE_DEPS:
        try:
            __import__(module)
        except ImportError:
            missing.append(pkg)
    return missing


def check_source_deps():
    """Check source package dependencies

    Returns:
        list: List of missing dependency info dicts
    """
    missing = []
    source_dir = OFFLINE_PACKAGES / "source"

    for item in SOURCE_DEPS:
        # Compatible with new and old format: (module, pkg, zip_file, local_only, github_repo?)
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
                install_info["install_hint"] = "Extract to site-packages directory"
            elif not local_only and github_repo:
                # Only generate online install command for non-local-only packages
                install_info["online_install"] = f"pip install git+https://github.com/{github_repo}.git"

            missing.append(install_info)

    return missing


# =============================================================================
# Auto Install
# =============================================================================

def install_pip_wheel(offline_dir, site_packages):
    """Directly extract pip wheel to site-packages (no pip required)

    Args:
        offline_dir: Local cache directory
        site_packages: site-packages path

    Returns:
        bool: Success
    """
    if not offline_dir or not offline_dir.exists():
        return False

    if not site_packages:
        return False

    # Find pip wheel file
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
    """Install single package, prefer local cache

    Args:
        pkg_name: Package name
        offline_dir: Local cache directory

    Returns:
        (success, method): (success, install_method)
    """
    # 1. Try local install
    if offline_dir and offline_dir.exists():
        try:
            cmd = [sys.executable, "-m", "pip", "install", "--no-index",
                   f"--find-links={offline_dir}", pkg_name]
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode == 0:
                return True, "offline"
        except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
            pass

    # 2. Try online install
    try:
        cmd = [sys.executable, "-m", "pip", "install", pkg_name]
        result = subprocess.run(cmd, capture_output=True, timeout=180)
        return result.returncode == 0, "online"
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        return False, "failed"


def install_source_package(zip_path, site_packages):
    """Extract and install source package (safe version, prevents Zip Slip)

    Args:
        zip_path: Package zip path
        site_packages: site-packages path

    Returns:
        bool: Success
    """
    if not site_packages:
        return False
    try:
        with zipfile.ZipFile(zip_path) as zf:
            # Check zip top-level directory structure
            top_dirs = set()
            for name in zf.namelist():
                if name.endswith('/'):
                    continue
                parts = name.split('/')
                if len(parts) > 1:
                    top_dirs.add(parts[0])

            # Determine prefix: detect if single root dir is a Python package (contains __init__.py)
            # If so, preserve directory structure, otherwise strip (compatible with distribution structure)
            if len(top_dirs) == 1:
                root_dir = list(top_dirs)[0]
                # Check if root directory contains __init__.py (Python package marker)
                has_init = any(
                    name == f"{root_dir}/__init__.py"
                    for name in zf.namelist()
                )
                prefix = '' if has_init else (root_dir + '/')
            else:
                prefix = ''

            # Safe extraction: validate path, prevent Zip Slip
            for member in zf.namelist():
                if not member.startswith(prefix):
                    continue

                # Get relative path
                rel_path = member[len(prefix):] if prefix else member
                if not rel_path or rel_path.startswith('/'):
                    continue

                # Verify target path is within site-packages
                target_path = (site_packages / rel_path).resolve()
                try:
                    target_path.relative_to(site_packages.resolve())
                except ValueError:
                    # Path escape, skip
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
    """Auto-install missing dependencies

    Args:
        missing_pypi: List of missing PyPI packages
        missing_source: List of missing source package info

    Returns:
        dict: {pypi_failed: [], source_failed: [], installed: []}
    """
    # Cache platform info and site-packages path
    platform_dir, _ = get_platform_info()
    offline_dir = OFFLINE_PACKAGES / platform_dir if platform_dir else None
    site_packages = get_site_packages_path()

    result = {
        "pypi_failed": [],
        "source_failed": [],
        "installed": []
    }

    # Prioritize pip (if missing)
    pip_missing = 'pip' in missing_pypi
    other_packages = [p for p in missing_pypi if p != 'pip']

    if pip_missing:
        # Directly extract pip wheel, no pip required
        success = install_pip_wheel(offline_dir, site_packages)
        if success:
            result["installed"].append("pip (offline)")
        else:
            result["pypi_failed"].append("pip")
            # pip install failed, cannot continue installing other packages
            other_packages = []

    # Install other PyPI packages (requires pip)
    for pkg in other_packages:
        success, method = install_package(pkg, offline_dir)
        if success:
            result["installed"].append(f"{pkg} ({method})")
        else:
            result["pypi_failed"].append(pkg)

    # Install source packages
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
# Offline Install Command Generation (for manual installation scenarios)
# =============================================================================

def generate_install_commands(missing_pypi, missing_source):
    """Generate offline-priority install commands (safe version, prevents command injection)

    Returns:
        dict: {pypi_commands: [], source_commands: [], extract_commands: []}
    """
    # Cache platform info and site-packages path
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

    # PyPI package install commands
    for pkg in missing_pypi:
        # Use shlex.quote() to prevent command injection
        safe_pkg = shlex.quote(pkg)
        if offline_dir and offline_dir.exists():
            # Offline first
            safe_platform = shlex.quote(str(offline_dir))
            cmd = f"python -m pip install --no-index --find-links={safe_platform} {safe_pkg}"
            fallback = f"python -m pip install {safe_pkg}"
            commands["pypi_commands"].append(f"{cmd} || {fallback}")
        else:
            # Online install
            commands["pypi_commands"].append(f"python -m pip install {safe_pkg}")

    # Source package install commands
    for dep in missing_source:
        if dep.get("has_offline"):
            zip_path = dep["offline_path"]
            if site_packages:
                # Generate safe extraction command (use script approach to avoid command injection)
                safe_zip = shlex.quote(str(zip_path))
                safe_site = shlex.quote(str(site_packages))
                # Use heredoc to generate temporary script
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
                    f"                pass  # Skip files with path escape\n"
                    f"EOF"
                )
            else:
                commands["source_commands"].append(
                    f"# Extract {dep['name']} to python/Lib/site-packages"
                )
        elif dep.get("online_install"):
            commands["source_commands"].append(dep["online_install"])

    return commands


# =============================================================================
# Version Update Detection
# =============================================================================

def get_local_version():
    """Get local version number"""
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
    """Check for version updates"""
    # Cooldown check: no duplicate requests within 7 days
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

            # Update cache
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
        # Network or parse error, silently ignore
        pass
    return None


# =============================================================================
# Skills List
# =============================================================================

def refresh_mapping():
    """Refresh skills mapping table"""
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
    """Get skills name list from database"""
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
# Main Function
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

    # Platform info (call once)
    platform_dir, platform_name = get_platform_info()
    output["platform"] = platform_name

    # 1. Check PyPI dependencies
    missing_pypi = check_pypi_deps()

    # 2. Check source dependencies
    missing_source = check_source_deps()

    # 3. Auto-install missing dependencies
    if missing_pypi or missing_source:
        install_result = auto_install_deps(missing_pypi, missing_source)

        # Only report installation failures
        if install_result["pypi_failed"] or install_result["source_failed"]:
            output["deps"] = {
                "pypi_failed": install_result["pypi_failed"],
                "source_failed": install_result["source_failed"],
            }
            # Generate manual install commands on failure
            # Pass complete missing_source info, let generate_install_commands filter itself
            failed_source_deps = [d for d in missing_source if d["name"] in install_result["source_failed"]]
            commands = generate_install_commands(
                install_result["pypi_failed"],
                failed_source_deps
            )
            output["install"] = commands

            if not commands["offline_available"]:
                _, mirror_url = get_fastest_mirror()
                output["install"]["fallback_mirror"] = mirror_url

        # Report successful installations
        if install_result["installed"]:
            output["install"] = output.get("install") or {}
            output["install"]["installed"] = install_result["installed"]

    # 4. Refresh mapping table
    refresh_mapping()

    # 5. Version detection
    update_info = check_update()
    if update_info:
        output["update"] = update_info

    # 6. Get skills list
    skills = get_skills_list()
    output["skills"] = skills
    output["skills_count"] = len(skills)
    output["need_install_reminder"] = len(skills) < 10

    # Output
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

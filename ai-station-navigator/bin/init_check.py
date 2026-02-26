"""
初始化检查脚本 - 合并版本检测与技能列表输出
避免 Kernel 多步串行执行错误
"""
import json
import ssl
import subprocess
import sys
import time
from pathlib import Path
import urllib.request

# 项目根目录
BASE_DIR = Path(__file__).parent.parent

# 数据库文件
SKILLS_DB_FILE = BASE_DIR / ".claude" / "skills" / "skills.db"

# 版本缓存
VERSION_CACHE = BASE_DIR / ".claude" / "state" / ".version"
UPDATE_CACHE = BASE_DIR / ".claude" / "state" / ".update_cache"

# 镜像源
PYPI_MIRRORS = [
    ('官方 (全球)', 'https://pypi.org/simple'),
    ('清华 (中国)', 'https://pypi.tuna.tsinghua.edu.cn/simple'),
    ('阿里云 (中国)', 'https://mirrors.aliyun.com/pypi/simple/'),
]

# 核心依赖
CORE_DEPS = [
    ('tinydb', 'TinyDB'),
    ('yaml', 'PyYAML'),
    ('yara', 'yara-python'),
    ('frontmatter', 'python-frontmatter'),
    ('langgraph', 'langgraph'),
    ('typing_extensions', 'typing-extensions'),
    ('skill_scanner', 'cisco-ai-skill-scanner'),
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
        except:
            pass
    if results:
        results.sort()
        return results[0][1], results[0][2]
    return '官方 (全球)', 'https://pypi.org/simple'


def check_deps():
    """检查核心依赖"""
    missing = []
    for module, pkg in CORE_DEPS:
        try:
            __import__(module)
        except ImportError:
            missing.append(pkg)
    return missing


def get_local_version():
    """获取本地版本号"""
    config_file = BASE_DIR / "config.json"
    if config_file.exists():
        try:
            config = json.loads(config_file.read_text(encoding="utf-8"))
            version = config.get("version", "").strip()
            if version:
                return version
        except:
            pass
    if VERSION_CACHE.exists():
        return VERSION_CACHE.read_text().strip()
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
    except Exception as e:
        if "404" not in str(e):
            pass
    return None


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
    except:
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
    except:
        return []


def main():
    output = {
        "deps": None,
        "update": None,
        "skills": [],
        "skills_count": 0,
        "need_install_reminder": False
    }

    # 1. 依赖检查
    missing = check_deps()
    if missing:
        name, url = get_fastest_mirror()
        output["deps"] = {
            "missing": missing,
            "mirror_name": name,
            "mirror_url": url
        }

    # 2. 刷新映射表
    refresh_mapping()

    # 3. 版本检测
    update_info = check_update()
    if update_info:
        output["update"] = update_info

    # 4. 获取技能列表
    skills = get_skills_list()
    output["skills"] = skills
    output["skills_count"] = len(skills)
    output["need_install_reminder"] = len(skills) < 10

    # 输出
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

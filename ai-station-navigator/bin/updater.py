import json
import ssl
import time
from pathlib import Path
import urllib.request

def get_local_version() -> str:
    """获取本地版本号，优先从 config.json 读取"""
    # 优先读取 config.json
    config_file = Path(__file__).parent.parent / "config.json"
    if config_file.exists():
        try:
            config = json.loads(config_file.read_text(encoding="utf-8"))
            version = config.get("version", "").strip()
            if version:
                return version
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    # 回退到 .version 缓存文件
    version_cache = Path(".claude/state/.version")
    if version_cache.exists():
        return version_cache.read_text().strip()

    # 默认版本
    return "0.0.0"

def check_update():
    cache_file = Path(".claude/state/.update_cache")

    # 冷却检查：7天内不重复请求
    if cache_file.exists() and time.time() - cache_file.stat().st_mtime < 604800:
        print("[跳过检测] 冷却中（距上次检测不足7天）")
        return

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

            # 版本比较
            local_parts = list(map(int, local.split(".")))
            remote_parts = list(map(int, remote.split(".")))

            if remote_parts > local_parts:
                print(f"\n【新版本可用】{local} -> {remote}")
                body = release.get('body', '')[:300]
                if body:
                    print(f"【更新内容】\n{body}...")
                print(f"【详情】{release['html_url']}\n")

            # 更新缓存
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            Path(".claude/state/.version").write_text(remote)
            cache_file.touch()
    except Exception as e:
        # 404 表示仓库无 release，首次安装
        if "404" not in str(e):
            pass  # 其他错误静默

if __name__ == "__main__":
    check_update()

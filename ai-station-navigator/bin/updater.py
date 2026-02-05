import json
import time
from pathlib import Path
import urllib.request

def check_update():
    cache_file = Path(".claude/state/.update_cache")
    version_cache = Path(".claude/state/.version")

    # 冷却检查：12小时内不重复请求
    if cache_file.exists() and time.time() - cache_file.stat().st_mtime < 43200:
        return

    local = version_cache.read_text().strip() if version_cache.exists() else "0.0.0"

    try:
        with urllib.request.urlopen(
            "https://api.github.com/repos/canishowtime/ai-station-navigator/releases/latest",
            timeout=5
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

            # 更新版本缓存
            version_cache.parent.mkdir(parents=True, exist_ok=True)
            version_cache.write_text(remote)
            cache_file.touch()
    except Exception as e:
        # 404 表示仓库无 release，首次安装
        if "404" not in str(e):
            pass  # 其他错误静默

if __name__ == "__main__":
    check_update()

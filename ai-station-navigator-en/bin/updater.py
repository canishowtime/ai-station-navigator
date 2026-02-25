import json
import ssl
import time
from pathlib import Path
import urllib.request

def get_local_version() -> str:
    """Get local version, prioritize reading from config.json"""
    # Prioritize reading config.json
    config_file = Path(__file__).parent.parent / "config.json"
    if config_file.exists():
        try:
            config = json.loads(config_file.read_text(encoding="utf-8"))
            version = config.get("version", "").strip()
            if version:
                return version
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    # Fallback to .version cache file
    version_cache = Path(".claude/state/.version")
    if version_cache.exists():
        return version_cache.read_text().strip()

    # Default version
    return "0.0.0"

def check_update():
    cache_file = Path(".claude/state/.update_cache")

    # Cooldown check: no repeat requests within 7 days
    if cache_file.exists() and time.time() - cache_file.stat().st_mtime < 604800:
        print("[Skip Check] Cooldown active (less than 7 days since last check)")
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

            # Version comparison
            local_parts = list(map(int, local.split(".")))
            remote_parts = list(map(int, remote.split(".")))

            if remote_parts > local_parts:
                print(f"\n[New Version Available] {local} -> {remote}")
                body = release.get('body', '')[:300]
                if body:
                    print(f"[Release Notes]\n{body}...")
                print(f"[Details] {release['html_url']}\n")

            # Update cache
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            Path(".claude/state/.version").write_text(remote)
            cache_file.touch()
    except Exception as e:
        # 404 means repo has no release, first install
        if "404" not in str(e):
            pass  # Other errors silent

if __name__ == "__main__":
    check_update()

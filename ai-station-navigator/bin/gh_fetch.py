#!/usr/bin/env python3
"""
gh_fetch.py - GitHub 内容获取工具（支持加速器）
-----------------------------------------------
自动读取 config.json 中的加速器配置，优先使用镜像

Usage:
    python bin/gh_fetch.py raw <user>/<repo>/<branch>/<path>
    python bin/gh_fetch.py clone <url> [dest]
    python bin/gh_fetch.py ls-remote <url>

Examples:
    python bin/gh_fetch.py raw mrgoonie/claudekit-skills/main/.claude/skills/mermaidjs-v11/skill.md
    python bin/gh_fetch.py clone https://github.com/user/repo.git
"""

import json
import sys
import subprocess
from pathlib import Path

# 添加项目 lib 目录到 sys.path（绿色包预置依赖）
_lib_dir = Path(__file__).parent.parent / "lib"
if _lib_dir.exists():
    sys.path.insert(0, str(_lib_dir))

# =============================================================================
# 配置加载
# =============================================================================

BASE_DIR = Path(__file__).parent.parent
CONFIG_FILE = BASE_DIR / "config.json"


def load_config() -> dict:
    """加载配置文件"""
    if not CONFIG_FILE.exists():
        return {}

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_raw_proxies() -> list:
    """获取 raw 文件加速器列表"""
    config = load_config()
    return config.get("raw", {}).get("proxies", [])


def get_git_proxies() -> list:
    """获取 git 加速器列表"""
    config = load_config()
    return config.get("git", {}).get("proxies", [])


def get_ssl_verify() -> bool:
    """获取 SSL 验证设置"""
    config = load_config()
    return config.get("git", {}).get("ssl_verify", True)


# =============================================================================
# 命令执行
# =============================================================================

def fetch_raw(path: str) -> str:
    """
    获取 raw 文件内容
    path 格式: user/repo/branch/file_path
    """
    proxies = get_raw_proxies()

    # 如果有加速器配置，优先使用
    for proxy_template in proxies:
        proxy_url = proxy_template.replace("{path}", path)
        try:
            result = subprocess.run(
                ["curl", "-s", "--max-time", "30", proxy_url],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout
        except Exception:
            continue

    # 加速器失败，回退到原始地址
    raw_url = f"https://raw.githubusercontent.com/{path}"
    result = subprocess.run(
        ["curl", "-s", "--max-time", "30", raw_url],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False
    )
    return result.stdout


def git_clone(url: str, dest: str = None) -> bool:
    """使用加速器克隆仓库"""
    proxies = get_git_proxies()
    ssl_verify = get_ssl_verify()

    # 构建命令
    cmd = ["git"]
    if not ssl_verify:
        cmd.extend(["-c", "http.sslVerify=false"])

    # 尝试加速器
    for proxy_template in proxies:
        proxy_url = proxy_template.replace("{repo}", url.replace("https://github.com/", ""))
        try:
            clone_cmd = cmd + ["clone", proxy_url]
            if dest:
                clone_cmd.append(dest)
            result = subprocess.run(clone_cmd, check=False)
            if result.returncode == 0:
                return True
        except Exception:
            continue

    # 回退到原始地址
    clone_cmd = cmd + ["clone", url]
    if dest:
        clone_cmd.append(dest)
    result = subprocess.run(clone_cmd, check=False)
    return result.returncode == 0


def git_ls_remote(url: str) -> str:
    """列出远程分支"""
    proxies = get_git_proxies()
    ssl_verify = get_ssl_verify()

    cmd = ["git"]
    if not ssl_verify:
        cmd.extend(["-c", "http.sslVerify=false"])

    # 尝试加速器
    for proxy_template in proxies:
        proxy_url = proxy_template.replace("{repo}", url.replace("https://github.com/", ""))
        try:
            result = subprocess.run(
                cmd + ["ls-remote", "--heads", proxy_url],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout
        except Exception:
            continue

    # 回退
    result = subprocess.run(
        cmd + ["ls-remote", "--heads", url],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False
    )
    return result.stdout


# =============================================================================
# CLI 入口
# =============================================================================

def main():
    # 设置 stdout 编码为 UTF-8
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python bin/gh_fetch.py raw <user/repo/branch/path>")
        print("  python bin/gh_fetch.py clone <url> [dest]")
        print("  python bin/gh_fetch.py ls-remote <url>")
        sys.exit(1)

    command = sys.argv[1]

    if command == "raw":
        if len(sys.argv) < 3:
            print("Error: raw command requires path argument")
            sys.exit(1)
        result = fetch_raw(sys.argv[2])
        print(result, end="")

    elif command == "clone":
        if len(sys.argv) < 3:
            print("Error: clone command requires url argument")
            sys.exit(1)
        dest = sys.argv[3] if len(sys.argv) > 3 else None
        success = git_clone(sys.argv[2], dest)
        sys.exit(0 if success else 1)

    elif command == "ls-remote":
        if len(sys.argv) < 3:
            print("Error: ls-remote command requires url argument")
            sys.exit(1)
        result = git_ls_remote(sys.argv[2])
        print(result, end="")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()

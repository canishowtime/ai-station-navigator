#!/usr/bin/env python3
"""
mcp_manager.py - MCP Manager (MCP 服务器管理器)
--------------------------------------------------
统一管理 Model Context Protocol (MCP) 服务器的生命周期

职责：
1. 服务器管理 - 添加、移除、列出 MCP 服务器
2. 权限配置 - 自动管理 MCP 工具的权限配置
3. 连接测试 - 验证 MCP 服务器连接状态
4. 备份回滚 - 操作前自动备份，失败自动回滚

Architecture:
    Kernel (AI) → MCP Manager → Config Handler → Backup System

Usage:
    python bin/mcp_manager.py list
    python bin/mcp_manager.py add <name> [options]
    python bin/mcp_manager.py remove <name>
    python bin/mcp_manager.py test <name>

v2.1 - Feature Complete:
    - 支持 MCP 服务器的安装与配置
    - 支持 MCP 服务器的连接测试与健康检查
    - 支持启用/禁用 MCP 服务器（通过 add/remove）
    - 支持卸除 MCP 服务器
    - 列出所有可用/已安装的 MCP 服务器
    - 支持预设模板系统（context7, tavily等）
    - 支持多种 API Key 配置方式（--env/交互式/环境变量）
    - 自动备份与回滚机制
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# 添加项目 lib 目录到 sys.path（绿色包预置依赖）
_lib_dir = Path(__file__).parent.parent / "lib"
if _lib_dir.exists():
    sys.path.insert(0, str(_lib_dir))

# =============================================================================
# 配置常量
# =============================================================================

BASE_DIR = Path(__file__).parent.parent
MCP_CONFIG_FILE = BASE_DIR / ".mcp.json"
SETTINGS_FILE = BASE_DIR / ".claude" / "settings.local.json"
BACKUP_DIR = BASE_DIR / "mybox" / "backups" / "mcp"

# =============================================================================
# 预设模板注册表 (Preset Templates Registry)
# =============================================================================

PRESET_TEMPLATES = {
    "context7": {
        "command": "npx.cmd",
        "args": ["-y", "@upstash/context7-mcp@latest"],
        "env": {},
        "tools": ["mcp__context7__resolve-library-id", "mcp__context7__query-docs"],
        "description": "Context7 - 查询编程库文档和代码示例"
    },
    "tavily": {
        "command": "npx.cmd",
        "args": [
            "-y",
            "mcp-remote",
            "https://mcp.tavily.com/mcp/?tavilyApiKey={api_key}"
        ],
        "env": {
            "TAVILY_API_KEY": {"required": True, "description": "Tavily API Key"}
        },
        "tools": ["mcp__tavily__tavily_search", "mcp__tavily__tavily_extract"],
        "description": "Tavily - 网络搜索与内容提取 (通过 mcp-remote)"
    },
    "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem"],
        "env": {},
        "tools": ["mcp__filesystem__read_file", "mcp__filesystem__write_file"],
        "description": "Filesystem - 文件系统访问（需要配置路径）"
    },
    "brave-search": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-brave-search"],
        "env": {
            "BRAVE_API_KEY": {"required": True, "description": "Brave Search API Key"}
        },
        "tools": ["mcp__brave_search__brave_web_search"],
        "description": "Brave Search - 隐私友好的网络搜索"
    },
    "github": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {
            "GITHUB_TOKEN": {"required": True, "description": "GitHub Personal Access Token"}
        },
        "tools": ["mcp__github__push_repository"],
        "description": "GitHub - GitHub 仓库操作"
    },
    "sqlite": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sqlite"],
        "env": {},
        "tools": ["mcp__sqlite__query"],
        "description": "SQLite - SQLite 数据库查询"
    },
    "memory": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-memory"],
        "env": {},
        "tools": ["mcp__memory__query", "mcp__memory__delete"],
        "description": "Memory - 键值存储"
    },
}

# =============================================================================
# 日志工具
# =============================================================================

class Colors:
    """终端颜色代码"""
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def log(level: str, message: str, emoji: str = ""):
    """统一日志输出"""
    timestamp = datetime.now().strftime("%H:%M:%S")

    color_map = {
        "OK": Colors.OKGREEN,
        "INFO": Colors.OKCYAN,
        "WARN": Colors.WARNING,
        "ERROR": Colors.FAIL,
    }

    color = color_map.get(level, "")
    reset = Colors.ENDC if color else ""

    try:
        print(f"{color}[{timestamp}] {emoji} [{level}]{reset} {message}")
    except Exception:
        print(f"[{timestamp}] [{level}] {message}")


def success(msg: str):
    log("OK", msg, "[OK]")


def info(msg: str):
    log("INFO", msg, "[i]")


def warn(msg: str):
    log("WARN", msg, "[!]")


def error(msg: str):
    log("ERROR", msg, "[X]")


def header(msg: str):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{msg.center(60)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")


# =============================================================================
# 备份管理器
# =============================================================================

class BackupManager:
    """配置文件备份与回滚"""

    def __init__(self):
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    def backup(self) -> Optional[Path]:
        """备份当前配置文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"backup_{timestamp}"

        try:
            backup_path.mkdir(parents=True, exist_ok=True)

            # 备份 .mcp.json
            if MCP_CONFIG_FILE.exists():
                shutil.copy2(MCP_CONFIG_FILE, backup_path / "mcp.json")

            # 备份 settings.local.json
            if SETTINGS_FILE.exists():
                shutil.copy2(SETTINGS_FILE, backup_path / "settings.json")

            success(f"配置已备份到: {backup_path.relative_to(BASE_DIR)}")
            return backup_path
        except Exception as e:
            error(f"备份失败: {e}")
            return None

    def rollback(self, backup_path: Path) -> bool:
        """从备份恢复配置"""
        try:
            if backup_path is None or not backup_path.exists():
                error("备份路径不存在")
                return False

            # 恢复 .mcp.json
            mcp_backup = backup_path / "mcp.json"
            if mcp_backup.exists():
                shutil.copy2(mcp_backup, MCP_CONFIG_FILE)

            # 恢复 settings.local.json
            settings_backup = backup_path / "settings.json"
            if settings_backup.exists():
                shutil.copy2(settings_backup, SETTINGS_FILE)

            success("配置已回滚")
            return True
        except Exception as e:
            error(f"回滚失败: {e}")
            return False


# =============================================================================
# MCP 配置处理器
# =============================================================================

class MCPConfigHandler:
    """MCP 配置文件处理器"""

    def __init__(self):
        self.backup_manager = BackupManager()

    def load_mcp_config(self) -> Dict:
        """加载 MCP 配置"""
        if not MCP_CONFIG_FILE.exists():
            return {"mcpServers": {}}
        with open(MCP_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_mcp_config(self, config: Dict) -> bool:
        """保存 MCP 配置"""
        try:
            MCP_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(MCP_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            error(f"保存 MCP 配置失败: {e}")
            return False

    def load_settings_config(self) -> Dict:
        """加载 settings 配置"""
        if not SETTINGS_FILE.exists():
            return {
                "permissions": {"allow": [], "deny": []},
                "enableAllProjectMcpServers": True,
                "enabledMcpjsonServers": []
            }
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_settings_config(self, config: Dict) -> bool:
        """保存 settings 配置"""
        try:
            SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            error(f"保存 settings 配置失败: {e}")
            return False

    def add_server(self, name: str, config: Dict, tools: List[str]) -> bool:
        """添加 MCP 服务器"""
        # 备份当前配置
        backup_path = self.backup_manager.backup()
        if not backup_path:
            return False

        try:
            # 更新 .mcp.json
            mcp_config = self.load_mcp_config()
            mcp_config["mcpServers"][name] = config
            if not self.save_mcp_config(mcp_config):
                self.backup_manager.rollback(backup_path)
                return False

            # 更新 settings.local.json
            settings = self.load_settings_config()

            # 添加到 enabledMcpjsonServers
            if "enabledMcpjsonServers" not in settings:
                settings["enabledMcpjsonServers"] = []
            if name not in settings["enabledMcpjsonServers"]:
                settings["enabledMcpjsonServers"].append(name)

            # 添加工具权限
            if "permissions" not in settings:
                settings["permissions"] = {"allow": [], "deny": []}
            if "allow" not in settings["permissions"]:
                settings["permissions"]["allow"] = []

            for tool in tools:
                if tool not in settings["permissions"]["allow"]:
                    settings["permissions"]["allow"].append(tool)

            if not self.save_settings_config(settings):
                self.backup_manager.rollback(backup_path)
                return False

            success(f"MCP 服务器 '{name}' 已添加")
            return True

        except Exception as e:
            error(f"添加服务器失败: {e}")
            self.backup_manager.rollback(backup_path)
            return False

    def remove_server(self, name: str) -> bool:
        """移除 MCP 服务器"""
        # 备份当前配置
        backup_path = self.backup_manager.backup()
        if not backup_path:
            return False

        try:
            # 从 .mcp.json 移除
            mcp_config = self.load_mcp_config()
            if name not in mcp_config.get("mcpServers", {}):
                warn(f"MCP 服务器 '{name}' 不存在")
                return False

            # 获取工具列表以便移除权限
            server_config = mcp_config["mcpServers"][name]
            del mcp_config["mcpServers"][name]

            if not self.save_mcp_config(mcp_config):
                self.backup_manager.rollback(backup_path)
                return False

            # 从 settings.local.json 移除
            settings = self.load_settings_config()

            # 从 enabledMcpjsonServers 移除
            if "enabledMcpjsonServers" in settings and name in settings["enabledMcpjsonServers"]:
                settings["enabledMcpjsonServers"].remove(name)

            if not self.save_settings_config(settings):
                self.backup_manager.rollback(backup_path)
                return False

            success(f"MCP 服务器 '{name}' 已移除")
            return True

        except Exception as e:
            error(f"移除服务器失败: {e}")
            self.backup_manager.rollback(backup_path)
            return False

    def list_servers(self) -> List[Dict]:
        """列出所有 MCP 服务器"""
        mcp_config = self.load_mcp_config()
        settings = self.load_settings_config()

        servers = []
        enabled = set(settings.get("enabledMcpjsonServers", []))

        for name, config in mcp_config.get("mcpServers", {}).items():
            servers.append({
                "name": name,
                "command": config.get("command", ""),
                "args": " ".join(config.get("args", [])),
                "enabled": name in enabled,
                "has_env": bool(config.get("env"))
            })

        return servers


# =============================================================================
# 环境变量处理器
# =============================================================================

class EnvHandler:
    """环境变量配置处理器"""

    @staticmethod
    def parse_env_args(env_args: List[str]) -> Dict[str, str]:
        """
        解析 --env 参数

        支持 KEY=VALUE 格式，VALUE 中可以包含 `=` 字符
        示例: --env "TOKEN=abc=def=xyz" → {"TOKEN": "abc=def=xyz"}
        """
        env_dict = {}
        for arg in env_args:
            if "=" in arg:
                # 只按第一个 = 分割，保留值中的 =
                first_eq_idx = arg.index("=")
                key = arg[:first_eq_idx]
                value = arg[first_eq_idx + 1:]
                if key:  # 确保键非空
                    env_dict[key] = value
            else:
                warn(f"忽略无效的环境变量参数: {arg} (格式应为 KEY=VALUE)")
        return env_dict

    @staticmethod
    def resolve_env_value(key: str, template_info: Dict, provided_env: Dict[str, str]) -> Optional[str]:
        """解析环境变量值"""
        # 1. 优先使用命令行提供的值
        if key in provided_env:
            return provided_env[key]

        # 2. 尝试从系统环境变量读取
        system_value = os.environ.get(key)
        if system_value:
            return system_value

        # 3. 需要交互式输入（由调用方处理）
        return None

    @staticmethod
    def get_required_keys(template: Dict) -> List[str]:
        """获取模板中需要的 API Keys"""
        required = []
        for key, info in template.get("env", {}).items():
            if info.get("required", False):
                required.append(key)
        return required


# =============================================================================
# MCP 管理器主类
# =============================================================================

class MCPManager:
    """MCP 服务器管理器"""

    def __init__(self):
        self.config_handler = MCPConfigHandler()
        self.env_handler = EnvHandler()

    def list_servers(self):
        """列出所有 MCP 服务器"""
        header("MCP 服务器列表")

        servers = self.config_handler.list_servers()

        if not servers:
            info("暂无已安装的 MCP 服务器")
            info("\n可用的预设模板:")
            for name, template in PRESET_TEMPLATES.items():
                print(f"  - {name}: {template.get('description', '无描述')}")
            return

        # 显示已安装的服务器
        for server in servers:
            status = f"{Colors.OKGREEN}[启用]{Colors.ENDC}" if server["enabled"] else f"{Colors.WARNING}[禁用]{Colors.ENDC}"
            env_indicator = f" {Colors.OKCYAN}(含环境变量){Colors.ENDC}" if server["has_env"] else ""

            print(f"\n{status} {Colors.BOLD}{server['name']}{Colors.ENDC}{env_indicator}")
            print(f"  命令: {server['command']} {server['args']}")

        print()
        info("可用的预设模板:")
        for name, template in PRESET_TEMPLATES.items():
            is_installed = any(s["name"] == name for s in servers)
            status = f"{Colors.OKGREEN}[已安装]{Colors.ENDC}" if is_installed else ""
            print(f"  - {name}: {template.get('description', '无描述')} {status}")

    def add_server(self, name: str, command: str, args: List[str], env: Dict[str, str],
                   tools: List[str], is_custom: bool = False):
        """添加 MCP 服务器"""
        info(f"添加 MCP 服务器: {name}")

        # 构建配置
        config = {
            "command": command,
            "args": args,
            "env": env,
            "type": "stdio"
        }

        # 添加服务器
        if self.config_handler.add_server(name, config, tools):
            info(f"\n服务器配置:")
            print(f"  名称: {name}")
            print(f"  命令: {command}")
            print(f"  参数: {' '.join(args)}")
            if env:
                print(f"  环境变量: {', '.join(env.keys())}")
            print(f"  工具: {', '.join(tools)}")

            if not is_custom:
                success(f"\n'{name}' 已成功添加！使用 'python bin/mcp_manager.py test {name}' 测试连接")

    def add_preset(self, name: str, env_args: List[str], interactive: bool = False):
        """添加预设模板服务器"""
        if name not in PRESET_TEMPLATES:
            error(f"未找到预设模板: {name}")
            info(f"可用的模板: {', '.join(PRESET_TEMPLATES.keys())}")
            return

        template = PRESET_TEMPLATES[name]
        provided_env = self.env_handler.parse_env_args(env_args)

        # 检查是否需要 API Key
        required_keys = self.env_handler.get_required_keys(template)
        final_env = {}
        api_key_value = None

        if required_keys:
            info(f"\n'{name}' 需要以下 API Key:")

            for key in required_keys:
                key_info = template["env"][key]
                description = key_info.get("description", key)

                # 尝试解析值
                value = self.env_handler.resolve_env_value(key, key_info, provided_env)

                if value:
                    api_key_value = value
                    success(f"  {key}: 已配置 ({'*' * 12})")
                elif interactive:
                    # 交互式输入
                    import getpass
                    prompt = f"  请输入 {key} ({description}): "
                    value = getpass.getpass(prompt)
                    if value:
                        api_key_value = value
                    else:
                        error(f"未提供 {key}，取消安装")
                        return
                else:
                    # 需要提供 key
                    error(f"\n缺少必需的 API Key: {key}")
                    info(f"使用 --env {key}=YOUR_KEY 或启用交互式输入 (-i)")
                    return

        # 处理 args 中的 {api_key} 占位符
        final_args = []
        for arg in template["args"]:
            if "{api_key}" in arg and api_key_value:
                final_args.append(arg.replace("{api_key}", api_key_value))
            else:
                final_args.append(arg)

        # 添加服务器
        self.add_server(
            name=name,
            command=template["command"],
            args=final_args,
            env=final_env,
            tools=template["tools"]
        )

    def remove_server(self, name: str):
        """移除 MCP 服务器"""
        info(f"移除 MCP 服务器: {name}")

        if self.config_handler.remove_server(name):
            success(f"'{name}' 已成功移除")

    def test_server(self, name: str):
        """
        测试 MCP 服务器连接

        注意: MCP 服务器是持续交互的协议（stdio），不会自动退出。
        此测试仅验证服务器能否成功启动。
        """
        info(f"测试 MCP 服务器: {name}")

        mcp_config = self.config_handler.load_mcp_config()
        servers = mcp_config.get("mcpServers", {})

        if name not in servers:
            error(f"MCP 服务器 '{name}' 不存在")
            return

        config = servers[name]
        command = config.get("command", "")
        args = config.get("args", [])
        env = config.get("env", {})

        # 构建环境变量
        test_env = os.environ.copy()
        test_env.update(env)

        info(f"\n执行命令: {command} {' '.join(args)}")
        info("提示: MCP 服务器将持续运行，测试将在 3 秒后自动终止")

        try:
            # 构建命令列表（安全方式，避免 shell=True）
            cmd_list = [command] + args

            # 启动进程但不等待（MCP 是持续交互协议）
            process = subprocess.Popen(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=test_env,
                shell=False  # 安全：禁用 shell 防止命令注入
            )

            # 等待 3 秒检测启动状态
            import time
            time.sleep(3)

            # 检查进程状态
            poll_result = process.poll()

            if poll_result is None:
                # 进程仍在运行 = 成功启动
                success(f"服务器 '{name}' 启动成功！进程 ID: {process.pid}")
                process.terminate()
                process.wait(timeout=2)
            elif poll_result == 0:
                success(f"服务器 '{name}' 启动后正常退出（返回码: 0）")
            else:
                # 进程异常退出
                warn(f"服务器 '{name}' 启动失败（返回码: {poll_result}）")
                stderr_output = process.stderr.read()
                if stderr_output:
                    print(f"\n错误输出:\n{stderr_output}")

        except FileNotFoundError:
            error(f"未找到命令: {command}")
            info("请确保命令路径正确或已安装相应工具")
        except Exception as e:
            error(f"测试失败: {e}")


# =============================================================================
# CLI 入口
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="MCP 服务器管理器 - 统一管理 Model Context Protocol 服务器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 列出所有 MCP 服务器
  python bin/mcp_manager.py list

  # 添加预设模板（无需 key）
  python bin/mcp_manager.py add context7

  # 添加预设模板（需要 key）- 命令行参数
  python bin/mcp_manager.py add tavily --env TAVILY_API_KEY=your_key

  # 添加预设模板（需要 key）- 交互式输入
  python bin/mcp_manager.py add tavily -i

  # 添加自定义服务器
  python bin/mcp_manager.py add custom --command npx --args "@org/server@latest" --env API_KEY=xxx

  # 移除服务器
  python bin/mcp_manager.py remove tavily

  # 测试连接
  python bin/mcp_manager.py test context7
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # list 命令
    subparsers.add_parser("list", help="列出所有 MCP 服务器及状态")

    # add 命令
    add_parser = subparsers.add_parser("add", help="添加新的 MCP 服务器")
    add_parser.add_argument("name", help="服务器名称（预设模板名或 'custom'）")
    add_parser.add_argument("--command", help="自定义服务器命令")
    add_parser.add_argument("--args", nargs="+", help="自定义服务器参数")
    add_parser.add_argument("--env", action="append", help="环境变量 (KEY=VALUE)")
    add_parser.add_argument("-i", "--interactive", action="store_true", help="交互式输入 API Key")

    # remove 命令
    remove_parser = subparsers.add_parser("remove", help="移除 MCP 服务器")
    remove_parser.add_argument("name", help="服务器名称")

    # test 命令
    test_parser = subparsers.add_parser("test", help="测试 MCP 服务器连接")
    test_parser.add_argument("name", help="服务器名称")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    manager = MCPManager()

    if args.command == "list":
        manager.list_servers()
    elif args.command == "add":
        if args.name == "custom":
            # 自定义服务器
            if not args.command or not args.args:
                error("自定义服务器需要 --command 和 --args 参数")
                return 1
            manager.add_server(
                name=f"custom_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                command=args.command,
                args=args.args,
                env=EnvHandler.parse_env_args(args.env or []),
                tools=[],
                is_custom=True
            )
        else:
            # 预设模板
            manager.add_preset(args.name, args.env or [], args.interactive)
    elif args.command == "remove":
        manager.remove_server(args.name)
    elif args.command == "test":
        manager.test_server(args.name)

    return 0


if __name__ == "__main__":
    sys.exit(main())

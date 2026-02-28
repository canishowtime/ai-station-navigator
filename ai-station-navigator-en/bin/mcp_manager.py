#!/usr/bin/env python3
"""
mcp_manager.py - MCP Manager (MCP Server Manager)
--------------------------------------------------
Unified management of Model Context Protocol (MCP) server lifecycle

Responsibilities:
1. Server Management - Add, remove, list MCP servers
2. Permission Configuration - Auto-manage MCP tool permission configuration
3. Connection Test - Verify MCP server connection status
4. Backup & Rollback - Auto backup before operations, auto rollback on failure

Architecture:
    Kernel (AI) -> MCP Manager -> Config Handler -> Backup System

Usage:
    python bin/mcp_manager.py list
    python bin/mcp_manager.py add <name> [options]
    python bin/mcp_manager.py remove <name>
    python bin/mcp_manager.py test <name>

v2.1 - Feature Complete:
    - Support MCP server installation and configuration
    - Support MCP server connection test and health check
    - Support enable/disable MCP servers (via add/remove)
    - Support MCP server uninstallation
    - List all available/installed MCP servers
    - Support preset template system (context7, tavily, etc.)
    - Support multiple API Key configuration methods (--env/interactive/environment variables)
    - Auto backup and rollback mechanism
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
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project lib directory to sys.path (pre-built dependencies for portable package)
_lib_dir = Path(__file__).parent.parent / "lib"
if _lib_dir.exists():
    sys.path.insert(0, str(_lib_dir))

# =============================================================================
# Configuration Constants
# =============================================================================

BASE_DIR = Path(__file__).parent.parent
MCP_CONFIG_FILE = BASE_DIR / ".mcp.json"
SETTINGS_FILE = BASE_DIR / ".claude" / "settings.local.json"
BACKUP_DIR = BASE_DIR / "mybox" / "backups" / "mcp"

# Platform-specific commands (P0 - cross-platform compatibility)
NPX_COMMAND = "npx.cmd" if sys.platform == 'win32' else "npx"

# =============================================================================
# Preset Templates Registry
# =============================================================================

PRESET_TEMPLATES = {
    "context7": {
        "command": "npx",
        "args": ["-y", "@upstash/context7-mcp@latest"],
        "env": {},
        "tools": ["mcp__context7__resolve-library-id", "mcp__context7__query-docs"],
        "description": "Context7 - Query programming library documentation and code examples"
    },
    "tavily": {
        "command": "npx",
        "args": [
            "-y",
            "mcp-remote",
            "https://mcp.tavily.com/mcp/?tavilyApiKey={api_key}"
        ],
        "env": {
            "TAVILY_API_KEY": {"required": True, "description": "Tavily API Key"}
        },
        "tools": ["mcp__tavily__tavily_search", "mcp__tavily__tavily_extract"],
        "description": "Tavily - Web search and content extraction (via mcp-remote)"
    },
    "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem"],
        "env": {},
        "tools": ["mcp__filesystem__read_file", "mcp__filesystem__write_file"],
        "description": "Filesystem - Filesystem access (requires path configuration)"
    },
    "brave-search": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-brave-search"],
        "env": {
            "BRAVE_API_KEY": {"required": True, "description": "Brave Search API Key"}
        },
        "tools": ["mcp__brave_search__brave_web_search"],
        "description": "Brave Search - Privacy-friendly web search"
    },
    "github": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {
            "GITHUB_TOKEN": {"required": True, "description": "GitHub Personal Access Token"}
        },
        "tools": ["mcp__github__push_repository"],
        "description": "GitHub - GitHub repository operations"
    },
    "sqlite": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sqlite"],
        "env": {},
        "tools": ["mcp__sqlite__query"],
        "description": "SQLite - SQLite database query"
    },
    "memory": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-memory"],
        "env": {},
        "tools": ["mcp__memory__query", "mcp__memory__delete"],
        "description": "Memory - Key-value storage"
    },
}

# =============================================================================
# Logging Utilities
# =============================================================================

class Colors:
    """Terminal color codes"""
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
    """Unified log output"""
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
# Backup Manager
# =============================================================================

class BackupManager:
    """Configuration file backup and rollback"""

    def __init__(self):
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    def backup(self) -> Optional[Path]:
        """Backup current configuration files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"backup_{timestamp}"

        try:
            backup_path.mkdir(parents=True, exist_ok=True)

            # Backup .mcp.json
            if MCP_CONFIG_FILE.exists():
                shutil.copy2(MCP_CONFIG_FILE, backup_path / "mcp.json")

            # Backup settings.local.json
            if SETTINGS_FILE.exists():
                shutil.copy2(SETTINGS_FILE, backup_path / "settings.json")

            success(f"Configuration backed up to: {backup_path.relative_to(BASE_DIR)}")
            return backup_path
        except Exception as e:
            error(f"Backup failed: {e}")
            return None

    def rollback(self, backup_path: Path) -> bool:
        """Restore configuration from backup"""
        try:
            if backup_path is None or not backup_path.exists():
                error("Backup path does not exist")
                return False

            # Restore .mcp.json
            mcp_backup = backup_path / "mcp.json"
            if mcp_backup.exists():
                shutil.copy2(mcp_backup, MCP_CONFIG_FILE)

            # Restore settings.local.json
            settings_backup = backup_path / "settings.json"
            if settings_backup.exists():
                shutil.copy2(settings_backup, SETTINGS_FILE)

            success("Configuration rolled back")
            return True
        except Exception as e:
            error(f"Rollback failed: {e}")
            return False


# =============================================================================
# MCP Configuration Handler
# =============================================================================

class MCPConfigHandler:
    """MCP configuration file handler"""

    def __init__(self):
        self.backup_manager = BackupManager()

    def load_mcp_config(self) -> Dict:
        """Load MCP configuration"""
        if not MCP_CONFIG_FILE.exists():
            return {"mcpServers": {}}
        with open(MCP_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_mcp_config(self, config: Dict) -> bool:
        """Save MCP configuration"""
        try:
            MCP_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(MCP_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            error(f"Failed to save MCP configuration: {e}")
            return False

    def load_settings_config(self) -> Dict:
        """Load settings configuration"""
        if not SETTINGS_FILE.exists():
            return {
                "permissions": {"allow": [], "deny": []},
                "enableAllProjectMcpServers": True,
                "enabledMcpjsonServers": []
            }
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_settings_config(self, config: Dict) -> bool:
        """Save settings configuration"""
        try:
            SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            error(f"Failed to save settings configuration: {e}")
            return False

    def add_server(self, name: str, config: Dict, tools: List[str]) -> bool:
        """Add MCP server"""
        # Backup current configuration
        backup_path = self.backup_manager.backup()
        if not backup_path:
            return False

        try:
            # Update .mcp.json
            mcp_config = self.load_mcp_config()
            mcp_config["mcpServers"][name] = config
            if not self.save_mcp_config(mcp_config):
                self.backup_manager.rollback(backup_path)
                return False

            # Update settings.local.json
            settings = self.load_settings_config()

            # Add to enabledMcpjsonServers
            if "enabledMcpjsonServers" not in settings:
                settings["enabledMcpjsonServers"] = []
            if name not in settings["enabledMcpjsonServers"]:
                settings["enabledMcpjsonServers"].append(name)

            # Add tool permissions
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

            success(f"MCP server '{name}' added")
            return True

        except Exception as e:
            error(f"Failed to add server: {e}")
            self.backup_manager.rollback(backup_path)
            return False

    def remove_server(self, name: str) -> bool:
        """Remove MCP server"""
        # Backup current configuration
        backup_path = self.backup_manager.backup()
        if not backup_path:
            return False

        try:
            # Remove from .mcp.json
            mcp_config = self.load_mcp_config()
            if name not in mcp_config.get("mcpServers", {}):
                warn(f"MCP server '{name}' does not exist")
                return False

            # Get tool list for permission removal
            server_config = mcp_config["mcpServers"][name]
            del mcp_config["mcpServers"][name]

            if not self.save_mcp_config(mcp_config):
                self.backup_manager.rollback(backup_path)
                return False

            # Remove from settings.local.json
            settings = self.load_settings_config()

            # Remove from enabledMcpjsonServers
            if "enabledMcpjsonServers" in settings and name in settings["enabledMcpjsonServers"]:
                settings["enabledMcpjsonServers"].remove(name)

            if not self.save_settings_config(settings):
                self.backup_manager.rollback(backup_path)
                return False

            success(f"MCP server '{name}' removed")
            return True

        except Exception as e:
            error(f"Failed to remove server: {e}")
            self.backup_manager.rollback(backup_path)
            return False

    def list_servers(self) -> List[Dict]:
        """List all MCP servers"""
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
# Environment Variable Handler
# =============================================================================

class EnvHandler:
    """Environment variable configuration handler"""

    @staticmethod
    def parse_env_args(env_args: List[str]) -> Dict[str, str]:
        """
        Parse --env parameters

        Supports KEY=VALUE format, VALUE can contain `=` characters
        Example: --env "TOKEN=abc=def=xyz" -> {"TOKEN": "abc=def=xyz"}
        """
        env_dict = {}
        for arg in env_args:
            if "=" in arg:
                # Only split on first =, preserve = in value
                first_eq_idx = arg.index("=")
                key = arg[:first_eq_idx]
                value = arg[first_eq_idx + 1:]
                if key:  # Ensure key is not empty
                    env_dict[key] = value
            else:
                warn(f"Ignoring invalid environment variable parameter: {arg} (format should be KEY=VALUE)")
        return env_dict

    @staticmethod
    def resolve_env_value(key: str, template_info: Dict, provided_env: Dict[str, str]) -> Optional[str]:
        """Resolve environment variable value"""
        # 1. Prioritize command-line provided values
        if key in provided_env:
            return provided_env[key]

        # 2. Try reading from system environment variables
        system_value = os.environ.get(key)
        if system_value:
            return system_value

        # 3. Need interactive input (handled by caller)
        return None

    @staticmethod
    def get_required_keys(template: Dict) -> List[str]:
        """Get required API Keys from template"""
        required = []
        for key, info in template.get("env", {}).items():
            if info.get("required", False):
                required.append(key)
        return required


# =============================================================================
# MCP Manager Main Class
# =============================================================================

class MCPManager:
    """MCP server manager"""

    def __init__(self):
        self.config_handler = MCPConfigHandler()
        self.env_handler = EnvHandler()

    def list_servers(self):
        """List all MCP servers"""
        header("MCP Server List")

        servers = self.config_handler.list_servers()

        if not servers:
            info("No installed MCP servers")
            info("\nAvailable preset templates:")
            for name, template in PRESET_TEMPLATES.items():
                print(f"  - {name}: {template.get('description', 'No description')}")
            return

        # Display installed servers
        for server in servers:
            status = f"{Colors.OKGREEN}[Enabled]{Colors.ENDC}" if server["enabled"] else f"{Colors.WARNING}[Disabled]{Colors.ENDC}"
            env_indicator = f" {Colors.OKCYAN}(with env vars){Colors.ENDC}" if server["has_env"] else ""

            print(f"\n{status} {Colors.BOLD}{server['name']}{Colors.ENDC}{env_indicator}")
            print(f"  Command: {server['command']} {server['args']}")

        print()
        info("Available preset templates:")
        for name, template in PRESET_TEMPLATES.items():
            is_installed = any(s["name"] == name for s in servers)
            status = f"{Colors.OKGREEN}[Installed]{Colors.ENDC}" if is_installed else ""
            print(f"  - {name}: {template.get('description', 'No description')} {status}")

    def add_server(self, name: str, command: str, args: List[str], env: Dict[str, str],
                   tools: List[str], is_custom: bool = False):
        """Add MCP server"""
        info(f"Adding MCP server: {name}")

        # Build configuration
        config = {
            "command": command,
            "args": args,
            "env": env,
            "type": "stdio"
        }

        # Add server
        if self.config_handler.add_server(name, config, tools):
            info(f"\nServer configuration:")
            print(f"  Name: {name}")
            print(f"  Command: {command}")
            print(f"  Args: {' '.join(args)}")
            if env:
                print(f"  Environment variables: {', '.join(env.keys())}")
            print(f"  Tools: {', '.join(tools)}")

            if not is_custom:
                success(f"\n'{name}' successfully added! Use 'python bin/mcp_manager.py test {name}' to test connection")

    def add_preset(self, name: str, env_args: List[str], interactive: bool = False):
        """Add preset template server"""
        if name not in PRESET_TEMPLATES:
            error(f"Preset template not found: {name}")
            info(f"Available templates: {', '.join(PRESET_TEMPLATES.keys())}")
            return

        template = PRESET_TEMPLATES[name]
        provided_env = self.env_handler.parse_env_args(env_args)

        # Check if API Key is required
        required_keys = self.env_handler.get_required_keys(template)
        final_env = {}
        api_key_value = None

        if required_keys:
            info(f"\n'{name}' requires the following API Keys:")

            for key in required_keys:
                key_info = template["env"][key]
                description = key_info.get("description", key)

                # Try to resolve value
                value = self.env_handler.resolve_env_value(key, key_info, provided_env)

                if value:
                    api_key_value = value
                    success(f"  {key}: Configured ({'*' * 12})")
                elif interactive:
                    # Interactive input
                    import getpass
                    prompt = f"  Please enter {key} ({description}): "
                    value = getpass.getpass(prompt)
                    if value:
                        api_key_value = value
                    else:
                        error(f"{key} not provided, installation cancelled")
                        return
                else:
                    # Need to provide key
                    error(f"\nMissing required API Key: {key}")
                    info(f"Use --env {key}=YOUR_KEY or enable interactive input (-i)")
                    return

        # Handle {api_key} placeholder in args
        final_args = []
        for arg in template["args"]:
            if "{api_key}" in arg and api_key_value:
                final_args.append(arg.replace("{api_key}", api_key_value))
            else:
                final_args.append(arg)

        # Add server (platform-adapt npx command)
        command = template["command"]
        if command == "npx":
            command = NPX_COMMAND

        self.add_server(
            name=name,
            command=command,
            args=final_args,
            env=final_env,
            tools=template["tools"]
        )

    def remove_server(self, name: str):
        """Remove MCP server"""
        info(f"Removing MCP server: {name}")

        if self.config_handler.remove_server(name):
            success(f"'{name}' successfully removed")

    def test_server(self, name: str):
        """
        Test MCP server connection

        Note: MCP servers are continuous interaction protocols (stdio), won't exit automatically.
        This test only verifies if the server can start successfully.
        """
        info(f"Testing MCP server: {name}")

        mcp_config = self.config_handler.load_mcp_config()
        servers = mcp_config.get("mcpServers", {})

        if name not in servers:
            error(f"MCP server '{name}' does not exist")
            return

        config = servers[name]
        command = config.get("command", "")
        args = config.get("args", [])
        env = config.get("env", {})

        # Build environment variables
        test_env = os.environ.copy()
        test_env.update(env)

        info(f"\nExecuting command: {command} {' '.join(args)}")
        info("Note: MCP server will keep running, test will auto-terminate in 3 seconds")

        try:
            # Build command list (safe way, avoid shell=True)
            cmd_list = [command] + args

            # Start process but don't wait (MCP is continuous protocol)
            process = subprocess.Popen(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=test_env,
                shell=False  # Safe: disable shell to prevent command injection
            )

            # Wait 3 seconds to check startup status
            import time
            time.sleep(3)

            # Check process status
            poll_result = process.poll()

            if poll_result is None:
                # Process still running = successful startup
                success(f"Server '{name}' started successfully! Process ID: {process.pid}")
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    # terminate() timeout, force kill
                    process.kill()
                    process.wait()
            elif poll_result == 0:
                success(f"Server '{name}' exited normally after startup (return code: 0)")
            else:
                # Process exited abnormally
                warn(f"Server '{name}' failed to start (return code: {poll_result})")
                stderr_output = process.stderr.read()
                if stderr_output:
                    print(f"\nError output:\n{stderr_output}")

        except FileNotFoundError:
            error(f"Command not found: {command}")
            info("Please ensure command path is correct or corresponding tool is installed")
        except Exception as e:
            error(f"Test failed: {e}")


# =============================================================================
# CLI Entry
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="MCP Server Manager - Unified management of Model Context Protocol servers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all MCP servers
  python bin/mcp_manager.py list

  # Add preset template (no key required)
  python bin/mcp_manager.py add context7

  # Add preset template (key required) - command line parameter
  python bin/mcp_manager.py add tavily --env TAVILY_API_KEY=your_key

  # Add preset template (key required) - interactive input
  python bin/mcp_manager.py add tavily -i

  # Add custom server
  python bin/mcp_manager.py add custom --command npx --args "@org/server@latest" --env API_KEY=xxx

  # Remove server
  python bin/mcp_manager.py remove tavily

  # Test connection
  python bin/mcp_manager.py test context7
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # list command
    subparsers.add_parser("list", help="List all MCP servers and status")

    # add command
    add_parser = subparsers.add_parser("add", help="Add new MCP server")
    add_parser.add_argument("name", help="Server name (preset template name or 'custom')")
    add_parser.add_argument("--command", help="Custom server command")
    add_parser.add_argument("--args", nargs="+", help="Custom server arguments")
    add_parser.add_argument("--env", action="append", help="Environment variables (KEY=VALUE)")
    add_parser.add_argument("-i", "--interactive", action="store_true", help="Interactive API Key input")

    # remove command
    remove_parser = subparsers.add_parser("remove", help="Remove MCP server")
    remove_parser.add_argument("name", help="Server name")

    # test command
    test_parser = subparsers.add_parser("test", help="Test MCP server connection")
    test_parser.add_argument("name", help="Server name")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    manager = MCPManager()

    if args.command == "list":
        manager.list_servers()
    elif args.command == "add":
        if args.name == "custom":
            # Custom server
            if not args.command or not args.args:
                error("Custom server requires --command and --args parameters")
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
            # Preset template
            manager.add_preset(args.name, args.env or [], args.interactive)
    elif args.command == "remove":
        manager.remove_server(args.name)
    elif args.command == "test":
        manager.test_server(args.name)

    return 0


if __name__ == "__main__":
    sys.exit(main())

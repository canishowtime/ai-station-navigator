#!/usr/bin/env python3
"""
hooks_manager.py - 系统事件钩子管理器
---------------------------------------
"在关键时刻自动触发维护操作" —— Hooks Manager 实现系统事件的自动化响应。

职责：
1. 日志轮转 - on_session_start 时自动轮转日志
2. 工作区清理 - on_delivery 时自动清理 workspace
3. 磁盘检查 - 定期检查磁盘空间并发出警告
4. 自动维护 - 在满足条件时自动触发维护操作

Architecture:
    Kernel 启动 → Hooks Manager → 自动执行预定义操作

v2.0 - 简化版
    - 移除 agent_protocol 依赖
    - 简化为基础 Hook 管理系统
    - 保留核心功能
"""

import json
import subprocess
import sys
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Optional

# 添加项目 lib 目录到 sys.path（绿色包预置依赖）
_lib_dir = Path(__file__).parent.parent / "lib"
if _lib_dir.exists():
    sys.path.insert(0, str(_lib_dir))

# 添加 bin 目录到 sys.path（用于导入 security_scanner）
_bin_dir = Path(__file__).parent
if _bin_dir.exists() and str(_bin_dir) not in sys.path:
    sys.path.insert(0, str(_bin_dir))

# =============================================================================
# 日志工具
# =============================================================================

def log(level: str, message: str, emoji: str = ""):
    """统一日志输出"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    try:
        print(f"[{timestamp}] {emoji} [{level}] {message}")
    except UnicodeEncodeError:
        emoji_safe = emoji.encode("gbk", errors="ignore").decode("gbk")
        print(f"[{timestamp}] {emoji_safe} [{level}] {message}")


def info(msg: str):
    log("INFO", msg, "[i]")


def warn(msg: str):
    log("WARN", msg, "[!]")


def error(msg: str):
    log("ERROR", msg, "[X]")


def success(msg: str):
    log("OK", msg, "[OK]")


# =============================================================================
# 配置常量
# =============================================================================

BASE_DIR = Path(__file__).parent.parent
SANDBOX_DIR = BASE_DIR / "mybox"
WORKSPACE_DIR = SANDBOX_DIR / "workspace"
LOGS_DIR = SANDBOX_DIR / "logs"
DELIVERY_ROOT = BASE_DIR / "delivery"

# Hook 配置文件
HOOKS_CONFIG_FILE = BASE_DIR / ".claude" / "config" / "hooks.json"
HOOKS_STATE_FILE = BASE_DIR / ".claude" / "state" / "hooks_state.json"


# =============================================================================
# 枚举类型
# =============================================================================

class HookType(Enum):
    """Hook 类型"""
    ON_SESSION_START = "on_session_start"   # 会话开始时触发
    ON_SESSION_END = "on_session_end"       # 会话结束时触发
    ON_DELIVERY = "on_delivery"             # 交付完成后触发
    ON_DISK_WARNING = "on_disk_warning"     # 磁盘空间警告时触发
    ON_ERROR = "on_error"                  # 发生错误时触发
    MANUAL = "manual"                      # 手动触发


class HookStatus(Enum):
    """Hook 执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


# =============================================================================
# Hook 定义
# =============================================================================

class Hook:
    """Hook 定义

    Attributes:
        name: Hook 名称
        hook_type: Hook 类型
        description: 描述
        condition: 触发条件函数 (可选)
        action: 执行动作函数
        enabled: 是否启用
        last_run: 最后执行时间
        run_count: 执行次数
    """

    def __init__(
        self,
        name: str,
        hook_type: HookType,
        description: str,
        action: Callable[[], Dict[str, Any]],
        condition: Callable[[], bool] = None,
        enabled: bool = True
    ):
        self.name = name
        self.hook_type = hook_type
        self.description = description
        self.action = action
        self.condition = condition
        self.enabled = enabled
        self.last_run: Optional[str] = None
        self.run_count = 0

    def should_run(self) -> bool:
        """检查是否应该运行"""
        if not self.enabled:
            return False
        if self.condition is None:
            return True
        return self.condition()

    def execute(self) -> Dict[str, Any]:
        """执行 Hook，返回结果字典"""
        if not self.should_run():
            result = {
                "status": "skipped",
                "message": "Hook 已跳过（条件不满足或未启用）",
                "skipped": True
            }
        else:
            try:
                result = self.action()
                # 确保返回结果包含 status 字段
                if "status" not in result:
                    result["status"] = "success"

                # 更新执行记录
                self.last_run = datetime.now().isoformat()
                self.run_count += 1
            except Exception as e:
                result = {
                    "status": "failed",
                    "message": f"Hook 执行失败: {str(e)}"
                }

        return result

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "type": self.hook_type.value,
            "description": self.description,
            "enabled": self.enabled,
            "last_run": self.last_run,
            "run_count": self.run_count
        }


# =============================================================================
# Hooks Manager
# =============================================================================

class HooksManager:
    """Hooks Manager - 系统事件钩子管理器

    v2.0 - 简化版（移除 agent_protocol 依赖）

    支持的操作:
        - execute: 执行指定类型的所有 Hooks
        - trigger: 触发指定 Hook
        - list: 列出所有 Hooks
        - enable: 启用 Hook
        - disable: 禁用 Hook
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.hooks: Dict[str, Hook] = {}
        self._register_default_hooks()
        self._load_state()

    # ======================================================================
    # Hook 注册
    # ======================================================================

    def _register_default_hooks(self):
        """注册默认 Hooks

        注意：注册时不保存状态，避免覆盖已有状态文件。
        状态将在 _load_state() 后通过 _save_state() 同步。
        """

        # Hook 1: 会话开始前清理nul文件
        self.register_hook(
            Hook(
                name="cleanup_nul_files",
                hook_type=HookType.ON_SESSION_START,
                description="会话开始前清理根目录的nul文件",
                action=self._action_cleanup_nul_files
            ),
            save_state=False
        )

    def register_hook(self, hook: Hook, save_state: bool = True):
        """注册 Hook

        Args:
            hook: Hook 对象
            save_state: 是否保存状态到文件（默认 True）
        """
        self.hooks[hook.name] = hook
        if save_state:
            self._save_state()

    # ======================================================================
    # Hook 操作
    # ======================================================================

    def execute_hooks(self, hook_type: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
        """执行指定类型的所有 Hooks

        Returns:
            包含执行结果的字典
        """
        executed = []
        results = {}
        failures = []

        for name, hook in self.hooks.items():
            if hook_type is None or hook.hook_type.value == hook_type:
                if force or hook.should_run():
                    if self.verbose:
                        info(f"执行 Hook: {name}")
                    result = hook.execute()
                    results[name] = result

                    if result.get("status") in ["success", "partial"]:
                        executed.append(name)
                    else:
                        failures.append(name)

        # 保存状态
        self._save_state()

        return {
            "success": True,
            "executed_hooks": executed,
            "failed_hooks": failures,
            "results": results
        }

    def trigger_hook(self, hook_name: Optional[str], force: bool = False) -> Dict[str, Any]:
        """触发指定 Hook

        Returns:
            包含执行结果的字典
        """
        if hook_name is None:
            return {
                "success": False,
                "error": "未指定 hook_name"
            }

        if hook_name not in self.hooks:
            return {
                "success": False,
                "error": f"Hook 不存在: {hook_name}"
            }

        hook = self.hooks[hook_name]
        result = hook.execute()
        self._save_state()

        return {
            "success": result.get("status") in ["success", "partial"],
            "result": result
        }

    def list_hooks(self) -> Dict[str, Any]:
        """列出所有 Hooks"""
        hooks_list = []
        for name, hook in self.hooks.items():
            hook_info = hook.to_dict()
            hook_info["should_run"] = hook.should_run()
            hooks_list.append(hook_info)

        return {
            "success": True,
            "hooks": hooks_list
        }

    def enable_hook(self, hook_name: Optional[str]) -> Dict[str, Any]:
        """启用 Hook"""
        if hook_name is None:
            return {"success": False, "error": "未指定 hook_name"}

        if hook_name not in self.hooks:
            return {"success": False, "error": f"Hook 不存在: {hook_name}"}

        self.hooks[hook_name].enabled = True
        self._save_state()
        return {"success": True, "message": f"Hook {hook_name} 已启用"}

    def disable_hook(self, hook_name: Optional[str]) -> Dict[str, Any]:
        """禁用 Hook"""
        if hook_name is None:
            return {"success": False, "error": "未指定 hook_name"}

        if hook_name not in self.hooks:
            return {"success": False, "error": f"Hook 不存在: {hook_name}"}

        self.hooks[hook_name].enabled = False
        self._save_state()
        return {"success": True, "message": f"Hook {hook_name} 已禁用"}

    # ======================================================================
    # Hook 动作实现
    # ======================================================================

    def _action_cleanup_nul_files(self) -> Dict[str, Any]:
        """清理根目录的nul文件（已禁用 - 仅记录状态）

        说明：由于Windows对nul文件名的特殊处理，自动清理存在兼容性问题。
             此hook保留为占位符，不执行任何删除操作。
        """
        if self.verbose:
            print(f"  [i] cleanup_nul_files hook已禁用，不执行删除操作")

        return {
            "success": True,
            "message": "hook已禁用",
            "deleted_files": [],
            "skipped_files": []
        }

        message = f"清理了 {len(deleted)} 个nul文件"
        if skipped:
            message += f" (跳过 {len(skipped)} 个大文件)"

        return {
            "success": True,
            "message": message,
            "deleted_files": deleted,
            "skipped_files": skipped
        }


    # ======================================================================
    # 状态持久化
    # ======================================================================

    def _load_state(self):
        """加载 Hook 状态"""
        if not HOOKS_STATE_FILE.exists():
            return

        try:
            state = json.loads(HOOKS_STATE_FILE.read_text(encoding="utf-8"))
            for name, hook_state in state.get("hooks", {}).items():
                if name in self.hooks:
                    self.hooks[name].last_run = hook_state.get("last_run")
                    self.hooks[name].run_count = hook_state.get("run_count", 0)
                    self.hooks[name].enabled = hook_state.get("enabled", True)
        except Exception as e:
            if self.verbose:
                print(f"加载 Hook 状态失败: {e}")

    def _save_state(self):
        """保存 Hook 状态"""
        try:
            HOOKS_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

            state = {
                "last_updated": datetime.now().isoformat(),
                "hooks": {
                    name: {
                        "last_run": hook.last_run,
                        "run_count": hook.run_count,
                        "enabled": hook.enabled
                    }
                    for name, hook in self.hooks.items()
                }
            }

            HOOKS_STATE_FILE.write_text(
                json.dumps(state, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            if self.verbose:
                print(f"保存 Hook 状态失败: {e}")


# =============================================================================
# 全局 Hook 管理器实例
# =============================================================================

_hooks_manager: Optional[HooksManager] = None


def get_hooks_manager(verbose: bool = False) -> HooksManager:
    """获取全局 Hooks Manager 实例"""
    global _hooks_manager
    if _hooks_manager is None:
        _hooks_manager = HooksManager(verbose=verbose)
    return _hooks_manager


# =============================================================================
# 便捷函数
# =============================================================================

def trigger_session_start_hooks(verbose: bool = False) -> Dict[str, Any]:
    """触发会话开始时的 Hooks"""
    manager = get_hooks_manager(verbose)
    return manager.execute_hooks(HookType.ON_SESSION_START.value)


def trigger_delivery_hooks(verbose: bool = False) -> Dict[str, Any]:
    """触发交付完成时的 Hooks"""
    manager = get_hooks_manager(verbose)
    return manager.execute_hooks(HookType.ON_DELIVERY.value)


def trigger_hook_by_name(hook_name: str, force: bool = False, verbose: bool = False) -> Dict[str, Any]:
    """按名称触发 Hook"""
    manager = get_hooks_manager(verbose)
    return manager.trigger_hook(hook_name, force)


# =============================================================================
# CLI 入口
# =============================================================================

def main():
    """CLI 入口"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Hooks Manager - 系统事件钩子管理器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 触发会话开始的 Hooks
  python bin/hooks_manager.py execute --hook-type on_session_start

  # 触发所有 Hooks（强制执行）
  python bin/hooks_manager.py execute --force

  # 触发指定 Hook
  python bin/hooks_manager.py trigger --hook-name log_rotate

  # 列出所有 Hooks
  python bin/hooks_manager.py list

  # 启用/禁用 Hook
  python bin/hooks_manager.py enable --hook-name log_rotate
  python bin/hooks_manager.py disable --hook-name log_rotate
        """
    )

    subparsers = parser.add_subparsers(dest="action", help="可用命令")

    # execute
    execute_parser = subparsers.add_parser("execute", help="执行指定类型的所有 Hooks")
    execute_parser.add_argument("--hook-type", help="Hook 类型")
    execute_parser.add_argument("--force", action="store_true", help="强制执行（忽略条件）")

    # trigger
    trigger_parser = subparsers.add_parser("trigger", help="触发指定 Hook")
    trigger_parser.add_argument("--hook-name", required=True, help="Hook 名称")
    trigger_parser.add_argument("--force", action="store_true", help="强制执行")

    # list
    subparsers.add_parser("list", help="列出所有 Hooks")

    # enable
    enable_parser = subparsers.add_parser("enable", help="启用 Hook")
    enable_parser.add_argument("--hook-name", required=True, help="Hook 名称")

    # disable
    disable_parser = subparsers.add_parser("disable", help="禁用 Hook")
    disable_parser.add_argument("--hook-name", required=True, help="Hook 名称")

    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")

    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        return 1

    # 创建 Hooks Manager
    manager = HooksManager(verbose=args.verbose)

    # 执行命令
    if args.action == "execute":
        result = manager.execute_hooks(getattr(args, "hook_type", None), getattr(args, "force", False))
    elif args.action == "trigger":
        result = manager.trigger_hook(args.hook_name, getattr(args, "force", False))
    elif args.action == "list":
        result = manager.list_hooks()
    elif args.action == "enable":
        result = manager.enable_hook(args.hook_name)
    elif args.action == "disable":
        result = manager.disable_hook(args.hook_name)
    else:
        print(f"未知操作: {args.action}")
        return 1

    # 输出结果
    print("\n" + "="*60)
    if result.get("success"):
        print(f"[OK] {result.get('message', '操作完成')}")
        if "hooks" in result:
            print(f"\n  Hooks ({len(result['hooks'])} 个):")
            for hook in result["hooks"]:
                status = "[启用]" if hook["enabled"] else "[禁用]"
                should = "[将执行]" if hook["should_run"] else "[跳过]"
                print(f"    {status} {should} {hook['name']} ({hook['type']})")
                print(f"        {hook['description']}")
                print(f"        执行次数: {hook['run_count']}, 最后执行: {hook['last_run'] or '从未'}")
        if "executed_hooks" in result:
            print(f"\n  已执行: {', '.join(result['executed_hooks'])}")
        if result.get("failed_hooks"):
            print(f"\n  失败: {', '.join(result['failed_hooks'])}")
    else:
        print(f"[X] {result.get('error', '操作失败')}")
    print("="*60 + "\n")

    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())

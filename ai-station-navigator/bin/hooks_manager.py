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
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# 添加项目 lib 目录到 sys.path（绿色包预置依赖）
_lib_dir = Path(__file__).parent.parent / "lib"
if _lib_dir.exists():
    sys.path.insert(0, str(_lib_dir))

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
    ON_SKILL_INSTALL = "on_skill_install"   # 技能安装后触发
    ON_SKILL_UNINSTALL = "on_skill_uninstall"  # 技能卸载后触发
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

        # Hook 1: 日志轮转
        self.register_hook(
            Hook(
                name="log_rotate",
                hook_type=HookType.ON_SESSION_START,
                description="轮转日志文件（保留最近 7 天）",
                action=self._action_log_rotate,
                condition=lambda: self._should_rotate_logs()
            ),
            save_state=False
        )

        # Hook 2: 工作区清理
        self.register_hook(
            Hook(
                name="cleanup_workspace",
                hook_type=HookType.ON_DELIVERY,
                description="清理 workspace/current/ 目录",
                action=self._action_cleanup_workspace
            ),
            save_state=False
        )

        # Hook 3: 磁盘检查
        self.register_hook(
            Hook(
                name="check_disk_space",
                hook_type=HookType.ON_SESSION_START,
                description="检查磁盘空间，发出警告",
                action=self._action_check_disk_space
            ),
            save_state=False
        )

        # Hook 4: 清理过期下载
        self.register_hook(
            Hook(
                name="cleanup_old_downloads",
                hook_type=HookType.ON_SESSION_START,
                description="清理 7 天前的下载文件",
                action=self._action_cleanup_old_downloads,
                condition=lambda: self._should_cleanup_downloads()
            ),
            save_state=False
        )

        # Hook 5: 交付后创建快照
        self.register_hook(
            Hook(
                name="create_delivery_snapshot",
                hook_type=HookType.ON_DELIVERY,
                description="为最新交付创建快照",
                action=self._action_create_delivery_snapshot
            ),
            save_state=False
        )

        # Hook 6: 会话开始时获取技能数据
        self.register_hook(
            Hook(
                name="refresh_skills_on_start",
                hook_type=HookType.ON_SESSION_START,
                description="会话开始时自动刷新技能数据",
                action=self._action_refresh_skills
            ),
            save_state=False
        )

        # Note: 技能安装/卸载的数据库同步已移至 skill_manager.py
        # 移除了 sync_skill_install_status 和 sync_skill_uninstall_status Hooks

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

    def _action_log_rotate(self) -> Dict[str, Any]:
        """日志轮转动作"""
        if not LOGS_DIR.exists():
            return {"success": True, "message": "日志目录不存在，跳过轮转"}

        rotated = []
        now = datetime.now()
        cutoff_time = now - timedelta(days=7)

        for log_file in LOGS_DIR.glob("*.log"):
            if log_file.stat().st_mtime < cutoff_time.timestamp():
                # 归档旧日志
                archive_name = f"{log_file.stem}.{log_file.stat().st_mtime}.old"
                archive_path = LOGS_DIR / archive_name
                log_file.rename(archive_path)
                rotated.append(log_file.name)

        # 删除 30 天前的归档
        for archive in LOGS_DIR.glob("*.old"):
            if archive.stat().st_mtime < (now - timedelta(days=30)).timestamp():
                archive.unlink()
                rotated.append(f"删除归档: {archive.name}")

        return {
            "success": True,
            "message": f"轮转了 {len(rotated)} 个日志文件",
            "rotated_files": rotated
        }

    def _action_cleanup_workspace(self) -> Dict[str, Any]:
        """清理工作区动作"""
        current_dir = WORKSPACE_DIR / "current"

        if not current_dir.exists():
            return {"success": True, "message": "工作区不存在，无需清理"}

        deleted = []
        total_size = 0

        for item in current_dir.glob("*"):
            size = item.stat().st_size if item.is_file() else 0
            try:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
                deleted.append(item.name)
                total_size += size
            except Exception as e:
                if self.verbose:
                    print(f"  [!] 删除失败: {item.name} - {e}")

        return {
            "success": True,
            "message": f"清理了 {len(deleted)} 个项目，释放 {self._format_size(total_size)}",
            "deleted_items": deleted,
            "space_freed": self._format_size(total_size)
        }

    def _action_check_disk_space(self) -> Dict[str, Any]:
        """检查磁盘空间动作"""
        usage = self._get_disk_usage()

        # 检查是否超过阈值
        warnings = []
        for name, info in usage.items():
            size_gb = info["size_bytes"] / (1024 ** 3)
            if size_gb > 1.0:  # 超过 1GB
                warnings.append(f"{name}: {self._format_size(info['size_bytes'])}")

        if warnings:
            return {
                "success": True,
                "status": "partial",
                "message": f"发现 {len(warnings)} 个大目录",
                "warnings": warnings,
                "usage": usage
            }
        else:
            return {
                "success": True,
                "message": "磁盘空间正常",
                "usage": usage
            }

    def _action_cleanup_old_downloads(self) -> Dict[str, Any]:
        """清理过期下载动作"""
        downloads_dir = SANDBOX_DIR / "downloads"

        if not downloads_dir.exists():
            return {"success": True, "message": "下载目录不存在"}

        deleted = []
        cutoff_time = datetime.now() - timedelta(days=7)

        for item in downloads_dir.glob("*"):
            if item.stat().st_mtime < cutoff_time.timestamp():
                try:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                    deleted.append(item.name)
                except Exception as e:
                    if self.verbose:
                        print(f"  [!] 删除失败: {item.name} - {e}")

        return {
            "success": True,
            "message": f"清理了 {len(deleted)} 个过期下载",
            "deleted_items": deleted
        }

    def _action_create_delivery_snapshot(self) -> Dict[str, Any]:
        """创建交付快照动作"""
        if not DELIVERY_ROOT.exists():
            return {"success": True, "message": "交付目录不存在"}

        latest_link = DELIVERY_ROOT / "latest"
        if not latest_link.exists():
            return {"success": True, "message": "没有 latest 快捷方式"}

        # 获取 latest 指向的目录
        try:
            target = latest_link.resolve()
            snapshot_name = f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            snapshot_path = DELIVERY_ROOT / snapshot_name

            # 复制到快照
            shutil.copytree(target, snapshot_path)

            return {
                "success": True,
                "message": f"创建快照: {snapshot_name}",
                "snapshot_path": str(snapshot_path)
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"创建快照失败: {str(e)}"
            }

    def _action_sync_skill_install_status(self) -> Dict[str, Any]:
        """[DEPRECATED] 技能安装后同步数据库状态

        注意：此 Hook 已废弃，数据库同步已移至 skill_manager.py 直接处理。
        保留此方法仅为兼容性，不应再被调用。
        """
        warn("sync_skill_install_status Hook 已废弃，请使用 skill_manager.py 直接同步")
        return {
            "success": False,
            "message": "此 Hook 已废弃，数据库同步已移至 skill_manager.py"
        }

    def _action_sync_skill_uninstall_status(self) -> Dict[str, Any]:
        """[DEPRECATED] 技能卸载后同步数据库状态

        注意：此 Hook 已废弃，数据库同步已移至 skill_manager.py 直接处理。
        保留此方法仅为兼容性，不应再被调用。
        """
        warn("sync_skill_uninstall_status Hook 已废弃，请使用 skill_manager.py 直接同步")
        return {
            "success": False,
            "message": "此 Hook 已废弃，数据库同步已移至 skill_manager.py"
        }

    # ======================================================================
    # 条件检查
    # ======================================================================

    def _should_rotate_logs(self) -> bool:
        """检查是否需要轮转日志"""
        if not LOGS_DIR.exists():
            return False

        # 检查是否有超过 7 天的日志
        cutoff_time = datetime.now() - timedelta(days=7)
        for log_file in LOGS_DIR.glob("*.log"):
            if log_file.stat().st_mtime < cutoff_time.timestamp():
                return True
        return False

    def _should_cleanup_downloads(self) -> bool:
        """检查是否需要清理下载"""
        downloads_dir = SANDBOX_DIR / "downloads"
        if not downloads_dir.exists():
            return False

        # 检查是否有超过 7 天的下载
        cutoff_time = datetime.now() - timedelta(days=7)
        for item in downloads_dir.glob("*"):
            if item.stat().st_mtime < cutoff_time.timestamp():
                return True
        return False

    # ======================================================================
    # 工具方法
    # ======================================================================

    def _get_disk_usage(self) -> Dict[str, Any]:
        """获取磁盘使用情况"""
        usage = {}

        for name, path in [
            ("sandbox", SANDBOX_DIR),
            ("workspace", WORKSPACE_DIR),
            ("downloads", SANDBOX_DIR / "downloads"),
            ("logs", LOGS_DIR),
            ("delivery", DELIVERY_ROOT)
        ]:
            if path.exists():
                size = 0
                try:
                    for f in path.rglob("*"):
                        try:
                            if f.is_file() and not f.is_symlink():
                                size += f.stat().st_size
                        except (FileNotFoundError, PermissionError):
                            continue
                except Exception:
                    pass

                usage[name] = {
                    "size_bytes": size,
                    "size": self._format_size(size)
                }

        return usage

    def _format_size(self, size_bytes: int) -> str:
        """格式化字节大小"""
        size = size_bytes
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

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

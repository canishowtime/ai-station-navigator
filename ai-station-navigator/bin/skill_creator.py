#!/usr/bin/env python3
"""
skill_creator.py - Creator Agent (创建者)
-----------------------------------------
"从零开始创造工具的能力" —— Creator Agent 负责帮助用户创建自定义技能。

职责：
1. 技能初始化 - 生成标准技能模板（SKILL.md + scripts/references/assets）
2. 技能验证 - 检查技能结构合规性
3. 技能打包 - 打包为 .skill 分发包

Architecture:
    Kernel (AI) → Creator Agent → skill-creator scripts → File System

Source: Based on Anthropic's skill-creator (Apache 2.0)
https://github.com/anthropics/skills/tree/main/skills/skill-creator

v1.0 - 已适配 Agent Protocol:
    - 继承 BaseAgent
    - 返回标准 AgentResult
    - 支持输入验证
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# 导入 Agent Protocol
_bin_dir = Path(__file__).parent
if str(_bin_dir) not in sys.path:
    sys.path.insert(0, str(_bin_dir))

# 添加项目 lib 目录到 sys.path（绿色包预置依赖）
_lib_dir = Path(__file__).parent.parent / "lib"
if _lib_dir.exists():
    sys.path.insert(0, str(_lib_dir))

from agent_protocol import (
    BaseAgent,
    AgentResult,
    AgentStatus,
    AgentErrorType,
    ValidationException,
    register_agent,
    AgentRegistry,
)


# =============================================================================
# 配置常量
# =============================================================================

BASE_DIR = Path(__file__).parent.parent
SKILL_CREATOR_LIB = BASE_DIR / "mybox" / "lib" / "skill-creator" / "scripts"
CUSTOM_SKILLS_DIR = BASE_DIR / "skills" / "custom"

# 默认输出目录
DEFAULT_OUTPUT_DIR = CUSTOM_SKILLS_DIR


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


def success(msg: str):
    log("OK", msg, "[OK]")


def info(msg: str):
    log("INFO", msg, "[i]")


def warn(msg: str):
    log("WARN", msg, "[!]")


def error(msg: str):
    log("ERROR", msg, "[X]")


# =============================================================================
# Creator Agent
# =============================================================================

@register_agent("creator")
class CreatorAgent(BaseAgent):
    """创建者 - 自定义技能创建

    v1.0 - 已适配 Agent Protocol

    输入格式:
        {
            "action": "init|validate|package",
            "skill_name": "my-skill",        # init 时必需
            "skill_path": "./skills/custom/my-skill",  # 可选，默认自动计算
            "output_dir": "./dist"           # package 时可选
        }

    返回格式:
        AgentResult(
            status=AgentStatus.SUCCESS,
            data={
                "skill_path": "/path/to/skill",
                "skill_file": "/path/to/skill.skill"  # package 时
            }
        )
    """

    def __init__(self, work_dir: Path = None, verbose: bool = False):
        super().__init__(work_dir, verbose)
        self._created_skill_path = None  # 用于回滚

    # ======================================================================
    # BaseAgent 抽象方法实现
    # ======================================================================

    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """验证输入参数"""
        if not isinstance(input_data, dict):
            raise ValidationException("输入必须是字典类型")

        action = input_data.get("action")
        if not action:
            raise ValidationException("缺少必需参数: action")

        if action not in ("init", "validate", "package"):
            raise ValidationException(
                f"无效的 action: {action}\\n"
                f"支持的 action: init, validate, package"
            )

        if action == "init":
            if "skill_name" not in input_data:
                raise ValidationException("init 操作需要 skill_name 参数")
            skill_name = input_data["skill_name"]
            if not isinstance(skill_name, str) or not skill_name.strip():
                raise ValidationException("skill_name 必须是非空字符串")

        return True

    def execute(self, input_data: Dict[str, Any]) -> AgentResult:
        """执行技能创建操作"""
        action = input_data.get("action")

        if action == "init":
            return self._init_skill(input_data)
        elif action == "validate":
            return self._validate_skill(input_data)
        elif action == "package":
            return self._package_skill(input_data)
        else:
            return AgentResult.failure(
                self.agent_name,
                f"未知的 action: {action}",
                error_type=AgentErrorType.VALIDATION_ERROR
            )

    def rollback(self, input_data: Dict[str, Any]) -> AgentResult:
        """回滚 - 删除已创建的技能目录"""
        if not self._created_skill_path:
            return AgentResult.success(
                self.agent_name,
                "无需回滚（未创建技能）"
            )

        skill_path = Path(self._created_skill_path)
        info(f"回滚: 删除技能目录 {skill_path}")

        try:
            if skill_path.exists():
                import shutil
                shutil.rmtree(skill_path)
                return AgentResult.success(
                    self.agent_name,
                    f"回滚成功: 已删除 {skill_path.name}"
                )
            else:
                return AgentResult.success(
                    self.agent_name,
                    "技能目录不存在，无需回滚"
                )
        except Exception as e:
            return AgentResult.failure(
                self.agent_name,
                f"回滚失败: {str(e)}"
            )

    def cleanup(self):
        """清理资源"""
        pass

    # ======================================================================
    # 私有方法 - 操作实现
    # ======================================================================

    def _init_skill(self, input_data: Dict[str, Any]) -> AgentResult:
        """初始化新技能"""
        skill_name = input_data["skill_name"]
        output_dir = input_data.get("output_dir", str(DEFAULT_OUTPUT_DIR))

        info(f"创建技能: {skill_name}")

        # 调用 init_skill.py
        init_script = SKILL_CREATOR_LIB / "init_skill.py"
        if not init_script.exists():
            return AgentResult.failure(
                self.agent_name,
                f"init_skill.py 不存在: {init_script}",
                error_type=AgentErrorType.EXECUTION_ERROR
            )

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(init_script),
                    skill_name,
                    "--path",
                    output_dir
                ],
                capture_output=True,
                text=True,
                check=False,
                cwd=BASE_DIR
            )

            # 打印输出
            if result.stdout:
                print(result.stdout)

            if result.returncode != 0:
                return AgentResult.failure(
                    self.agent_name,
                    "技能初始化失败",
                    error=result.stderr or result.stdout
                )

            # 计算技能路径
            skill_path = Path(output_dir) / skill_name
            self._created_skill_path = str(skill_path)

            return AgentResult.success(
                self.agent_name,
                f"技能初始化成功: {skill_name}",
                data={
                    "skill_name": skill_name,
                    "skill_path": str(skill_path),
                    "next_steps": [
                        f"编辑 {skill_path / 'SKILL.md'} 完成技能定义",
                        "根据需要添加 scripts/references/assets",
                        f"运行验证: python bin/skill_creator.py validate {skill_path}"
                    ]
                }
            )

        except Exception as e:
            return AgentResult.failure(
                self.agent_name,
                f"执行异常: {str(e)}",
                error_type=AgentErrorType.EXECUTION_ERROR
            )

    def _validate_skill(self, input_data: Dict[str, Any]) -> AgentResult:
        """验证技能"""
        skill_path_str = input_data.get("skill_path")

        if not skill_path_str:
            return AgentResult.failure(
                self.agent_name,
                "缺少 skill_path 参数",
                error_type=AgentErrorType.VALIDATION_ERROR
            )

        skill_path = Path(skill_path_str)
        if not skill_path.exists():
            return AgentResult.failure(
                self.agent_name,
                f"技能路径不存在: {skill_path}",
                error_type=AgentErrorType.VALIDATION_ERROR
            )

        info(f"验证技能: {skill_path}")

        # 调用 quick_validate.py
        validate_script = SKILL_CREATOR_LIB / "quick_validate.py"
        if not validate_script.exists():
            return AgentResult.failure(
                self.agent_name,
                f"quick_validate.py 不存在: {validate_script}",
                error_type=AgentErrorType.EXECUTION_ERROR
            )

        try:
            result = subprocess.run(
                [sys.executable, str(validate_script), str(skill_path)],
                capture_output=True,
                text=True,
                check=False,
                cwd=BASE_DIR
            )

            # 打印输出
            if result.stdout:
                print(result.stdout)

            if result.returncode != 0:
                return AgentResult.failure(
                    self.agent_name,
                    "技能验证失败",
                    error=result.stderr or result.stdout
                )

            return AgentResult.success(
                self.agent_name,
                f"技能验证通过: {skill_path.name}",
                data={"skill_path": str(skill_path)}
            )

        except Exception as e:
            return AgentResult.failure(
                self.agent_name,
                f"执行异常: {str(e)}",
                error_type=AgentErrorType.EXECUTION_ERROR
            )

    def _package_skill(self, input_data: Dict[str, Any]) -> AgentResult:
        """打包技能"""
        skill_path_str = input_data.get("skill_path")
        output_dir = input_data.get("output_dir")

        if not skill_path_str:
            return AgentResult.failure(
                self.agent_name,
                "缺少 skill_path 参数",
                error_type=AgentErrorType.VALIDATION_ERROR
            )

        skill_path = Path(skill_path_str)
        if not skill_path.exists():
            return AgentResult.failure(
                self.agent_name,
                f"技能路径不存在: {skill_path}",
                error_type=AgentErrorType.VALIDATION_ERROR
            )

        info(f"打包技能: {skill_path.name}")

        # 调用 package_skill.py
        package_script = SKILL_CREATOR_LIB / "package_skill.py"
        if not package_script.exists():
            return AgentResult.failure(
                self.agent_name,
                f"package_skill.py 不存在: {package_script}",
                error_type=AgentErrorType.EXECUTION_ERROR
            )

        try:
            cmd = [sys.executable, str(package_script), str(skill_path)]
            if output_dir:
                cmd.append(output_dir)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                cwd=BASE_DIR
            )

            # 打印输出
            if result.stdout:
                print(result.stdout)

            if result.returncode != 0:
                return AgentResult.failure(
                    self.agent_name,
                    "技能打包失败",
                    error=result.stderr or result.stdout
                )

            # 计算输出文件路径
            skill_name = skill_path.name
            out_dir = Path(output_dir) if output_dir else Path.cwd()
            skill_file = out_dir / f"{skill_name}.skill"

            return AgentResult.success(
                self.agent_name,
                f"技能打包成功: {skill_file.name}",
                data={
                    "skill_path": str(skill_path),
                    "skill_file": str(skill_file)
                }
            )

        except Exception as e:
            return AgentResult.failure(
                self.agent_name,
                f"执行异常: {str(e)}",
                error_type=AgentErrorType.EXECUTION_ERROR
            )


# =============================================================================
# CLI 入口
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="创建者 (Creator Agent) - 自定义技能创建工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 初始化新技能
  python bin/skill_creator.py init my-new-skill

  # 验证技能
  python bin/skill_creator.py validate skills/custom/my-skill

  # 打包技能
  python bin/skill_creator.py package skills/custom/my-skill

  # 打包到指定目录
  python bin/skill_creator.py package skills/custom/my-skill --output-dir ./dist

使用 Agent Protocol:
  from agent_protocol import AgentRegistry
  agent = AgentRegistry.create("creator")
  result = agent.run({"action": "init", "skill_name": "my-skill"})
        """
    )

    parser.add_argument("action", choices=["init", "validate", "package"],
                       help="操作类型: init(创建) | validate(验证) | package(打包)")
    parser.add_argument("target", nargs="?", help="技能名称或路径")
    parser.add_argument("--output-dir", "-o", help="输出目录（用于 init 和 package）")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")

    args = parser.parse_args()

    # 使用 Agent Protocol
    agent = CreatorAgent(verbose=args.verbose)

    # 构建输入数据
    input_data = {"action": args.action}

    if args.action == "init":
        if not args.target:
            parser.error("init 操作需要指定技能名称")
        input_data["skill_name"] = args.target
        if args.output_dir:
            input_data["output_dir"] = args.output_dir

    elif args.action == "validate":
        if not args.target:
            parser.error("validate 操作需要指定技能路径")
        input_data["skill_path"] = args.target

    elif args.action == "package":
        if not args.target:
            parser.error("package 操作需要指定技能路径")
        input_data["skill_path"] = args.target
        if args.output_dir:
            input_data["output_dir"] = args.output_dir

    # 执行 Agent
    result = agent.run(input_data)

    # 输出结果
    print("\n" + "="*60)
    if result.is_success():
        success("任务完成")
        print(f"  状态: {result.status.value}")
        print(f"  消息: {result.message}")

        if result.data:
            print(f"\n  详细信息:")
            for key, value in result.data.items():
                if key == "next_steps":
                    print(f"\n  后续步骤:")
                    for step in value:
                        print(f"    - {step}")
                else:
                    print(f"    {key}: {value}")

        if result.next_action:
            print(f"\n  建议下一步: {result.next_action}")

    else:
        error("任务失败")
        print(f"  状态: {result.status.value}")
        print(f"  原因: {result.message}")
        if result.error:
            print(f"  错误: {result.error}")
    print("="*60 + "\n")

    return 0 if result.is_success() else 1


if __name__ == "__main__":
    sys.exit(main())

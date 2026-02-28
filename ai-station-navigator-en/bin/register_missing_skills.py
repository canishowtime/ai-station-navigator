#!/usr/bin/env python3
"""
register_missing_skills.py - Missing Skills Registration Script
----------------------------------------------------------------
功能：扫描技能目录，注册未在数据库中的技能

1. 扫描技能目录 (.claude/skills/) - 找出所有包含 SKILL.md 的目录
2. 对比数据库 (.claude/skills/skills.db) - 找出未注册技能
3. 对比映射表 (docs/skills-mapping.md) - 找出未映射技能
4. 批量注册 - 调用 skill_manager 的 _sync_skill_to_db 方法
5. 更新映射表 - 调用 update_skills_mapping.py

Usage:
    python bin/register_missing_skills.py [--dry-run]

Options:
    --dry-run    预览模式，不执行实际注册
"""

import argparse
import sys
import os

# Windows UTF-8 兼容 (P0 - 所有脚本必须包含)
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


from pathlib import Path
from typing import Dict, List, Set, Optional

# 路径配置
bin_dir = Path(__file__).parent
project_root = bin_dir.parent

# 添加 bin 目录到 sys.path (用于导入 skill_manager)
sys.path.insert(0, str(bin_dir))

# TinyDB 导入
try:
    from tinydb import TinyDB, Query
    from tinydb.middlewares import CachingMiddleware
    from tinydb.storages import JSONStorage
except ImportError:
    print("错误: TinyDB 未安装，请运行: python -m pip install tinydb")
    sys.exit(1)

# 导入 skill_manager 中的类
try:
    from skill_manager import (
        SkillInstaller,
        db_connection,
        CLAUDE_SKILLS_DIR,
        DEFAULT_SKILL_CATEGORY,
        DEFAULT_SKILL_TAGS,
        warn,
        info,
        success
    )
except ImportError as e:
    print(f"错误: 无法导入 skill_manager: {e}")
    sys.exit(1)


# 常量定义
SKILLS_DB = CLAUDE_SKILLS_DIR / "skills.db"
SKILLS_DIR = CLAUDE_SKILLS_DIR
MAPPING_FILE = project_root / "docs" / "skills-mapping.md"


class SkillsRegistry:
    """技能注册器 - 扫描并注册缺失的技能"""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.missing_in_db: List[str] = []
        self.registered_count = 0
        self.failed_count = 0

    def scan_skill_directories(self) -> Dict[str, Path]:
        """扫描技能目录，返回技能名到路径的映射"""
        skills = {}
        if not SKILLS_DIR.exists():
            print(f"错误: 技能目录不存在: {SKILLS_DIR}")
            return skills

        for skill_dir in SKILLS_DIR.iterdir():
            # 跳过数据库文件
            if skill_dir.name == "skills.db" or not skill_dir.is_dir():
                continue

            # 检查是否包含 SKILL.md
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                skills[skill_dir.name] = skill_dir

        return skills

    def get_registered_skills(self) -> Set[str]:
        """从数据库获取已注册的技能列表"""
        registered = set()
        if not SKILLS_DB.exists():
            return registered

        try:
            storage = CachingMiddleware(JSONStorage)
            db = TinyDB(SKILLS_DB, storage=storage)
            Skill = Query()

            all_skills = db.all()
            for skill in all_skills:
                folder_name = skill.get("folder_name", "")
                if folder_name:
                    registered.add(folder_name)
        except Exception as e:
            print(f"警告: 读取数据库失败: {e}")

        return registered

    def compare_and_identify_missing(self, filesystem_skills: Dict[str, Path]) -> None:
        """对比找出缺失的技能（仅检查数据库，用 folder_name 匹配）"""
        registered = self.get_registered_skills()
        # 找出未在数据库中的技能（按 folder_name 匹配）
        self.missing_in_db = [name for name in filesystem_skills.keys() if name not in registered]

    def register_skills(self, skills_to_register: List[str]) -> None:
        """批量注册技能到数据库"""
        if not skills_to_register:
            return

        if self.dry_run:
            print(f"\n[预览] 将注册 {len(skills_to_register)} 个技能:")
            for skill in skills_to_register:
                print(f"  - {skill}")
            return

        # 使用单个数据库连接进行批量操作
        with db_connection() as (db, Skill):
            if db is None:
                print("错误: 无法连接数据库")
                return

            for skill_name in skills_to_register:
                try:
                    result = SkillInstaller._sync_skill_to_db(skill_name, db, Skill)
                    if result:
                        self.registered_count += 1
                        print(f"  ✓ {skill_name}")
                    else:
                        self.failed_count += 1
                        print(f"  ✗ {skill_name} (失败)")
                except Exception as e:
                    self.failed_count += 1
                    print(f"  ✗ {skill_name} (异常: {e})")

    def update_mapping(self) -> bool:
        """更新映射表"""
        if self.dry_run:
            print("\n[预览] 将更新映射表 (docs/skills-mapping.md)")
            return True

        try:
            # 导入并执行 update_skills_mapping
            import update_skills_mapping
            update_skills_mapping.main()
            return True
        except Exception as e:
            print(f"错误: 更新映射表失败: {e}")
            return False

    def generate_report(self) -> str:
        """生成处理结果报告"""
        lines = [
            "=" * 60,
            "技能注册报告",
            "=" * 60,
            "",
            f"扫描目录: {SKILLS_DIR}",
            f"数据库:   {SKILLS_DB}",
            f"映射表:   {MAPPING_FILE}",
            "",
            f"未在数据库中: {len(self.missing_in_db)} 个",
            ""
        ]

        if self.missing_in_db:
            lines.append("未注册技能列表:")
            for skill in sorted(self.missing_in_db):
                lines.append(f"  - {skill}")
            lines.append("")

        if not self.dry_run:
            lines.extend([
                "处理结果:",
                f"  注册成功: {self.registered_count}",
                f"  注册失败: {self.failed_count}",
                ""
            ])

        lines.extend([
            "=" * 60,
            ""
        ])

        return "\n".join(lines)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="扫描并注册缺失的技能",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python bin/register_missing_skills.py          # 扫描并注册
    python bin/register_missing_skills.py --dry-run # 预览模式
        """
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式，不执行实际注册"
    )

    args = parser.parse_args()

    # 打印标题
    print("=" * 60)
    if args.dry_run:
        print("技能注册扫描 [预览模式]")
    else:
        print("技能注册扫描")
    print("=" * 60)
    print()

    # 创建注册器
    registry = SkillsRegistry(dry_run=args.dry_run)

    # 步骤 1: 扫描技能目录
    print("步骤 1: 扫描技能目录...")
    filesystem_skills = registry.scan_skill_directories()
    print(f"  发现 {len(filesystem_skills)} 个技能目录")
    print()

    # 步骤 2: 对比数据库
    print("步骤 2: 对比数据库...")
    registry.compare_and_identify_missing(filesystem_skills)
    print(f"  未在数据库中: {len(registry.missing_in_db)} 个")
    print()

    # 步骤 3: 注册缺失的技能
    if registry.missing_in_db:
        print("步骤 3: 注册缺失的技能...")
        registry.register_skills(registry.missing_in_db)
        print()

    # 步骤 4: 重建映射表（无论是否有新技能）
    print("步骤 4: 重建映射表...")
    if registry.update_mapping():
        print("  [OK] 映射表已更新")
    else:
        print("  [ERROR] 映射表更新失败")
    print()

    # 打印报告
    print(registry.generate_report())

    # 返回状态码
    if registry.failed_count > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()

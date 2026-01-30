#!/usr/bin/env python3
"""
skill_matcher.py - 技能匹配引擎 (TinyDB 版)
--------------------------------
根据用户任务描述自动匹配相关技能。

统一数据源: .claude/skills/skills.db (TinyDB)

Usage:
    from skill_matcher import SkillMatcher, SkillCandidate

    matcher = SkillMatcher()
    candidates = matcher.match("转换 PDF 为 Markdown")
    for candidate in candidates:
        print(f"{candidate.name}: {candidate.confidence:.2f}")

Architecture:
    InteractiveSelector → SkillMatcher → skills.db (TinyDB)
                       → UserPreferenceTracker (JSON)
"""

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime

# TinyDB 导入
try:
    from tinydb import TinyDB, Query
    from tinydb.storages import JSONStorage
    HAS_TINYDB = True
except ImportError:
    HAS_TINYDB = False
    TinyDB = None
    Query = None

# 添加项目 lib 目录到 sys.path（绿色包预置依赖）
_lib_dir = Path(__file__).parent.parent / "lib"
if _lib_dir.exists():
    sys.path.insert(0, str(_lib_dir))

# =============================================================================
# 配置常量
# =============================================================================

BASE_DIR = Path(__file__).parent.parent
SKILLS_DIR = BASE_DIR / ".claude" / "skills"
DB_FILE = SKILLS_DIR / "skills.db"
USER_CHOICES_FILE = BASE_DIR / ".claude" / "state" / "user_choices.json"

# 已安装技能目录（用于同步）
INSTALLED_SKILLS_DIR = BASE_DIR / ".claude" / "skills"


# =============================================================================
# 数据类
# =============================================================================

@dataclass
class SkillCandidate:
    """技能候选结果"""
    name: str  # 技能显示名（从 SKILL.md 的 name 字段读取）
    folder_name: str = ""  # 文件夹名（实际存储路径，可能包含 author-repo 前缀）
    confidence: float = 0.0
    reason: str = ""
    installed: bool = False
    capabilities: Dict = None
    entry_point: str = ""
    category: str = ""
    source: str = "db"  # db (统一来自 TinyDB)
    install_cmd: str = ""
    parent: str = ""
    repo: str = ""

    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = {}

    def __str__(self) -> str:
        status = "[已安装]" if self.installed else "[推荐]"
        parent_info = f" ({self.parent})" if self.parent else ""
        return f"{status} {self.name}{parent_info} (置信度: {self.confidence:.2f}) - {self.reason}"


@dataclass
class UserChoice:
    """用户偏好记录"""
    task_pattern: str
    skill: str
    auto_confirm_count: int = 0
    last_confirmed: str = ""
    never_ask: bool = False

    def to_dict(self) -> dict:
        return {
            "task_pattern": self.task_pattern,
            "skill": self.skill,
            "auto_confirm_count": self.auto_confirm_count,
            "last_confirmed": self.last_confirmed,
            "never_ask": self.never_ask
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'UserChoice':
        return cls(**data)


# =============================================================================
# 技能匹配引擎
# =============================================================================

class SkillMatcher:
    """技能匹配引擎 - 基于 TinyDB"""

    def __init__(
        self,
        db_path: Path = DB_FILE,
        user_choices_path: Path = USER_CHOICES_FILE
    ):
        if not HAS_TINYDB:
            raise ImportError(
                "TinyDB 未安装，请运行: pip install tinydb\n"
                "或运行: python bin/skills_db_init.py"
            )

        self.db_path = db_path
        self.user_choices_path = user_choices_path
        self._db = None
        self._Skill = None
        self._user_choices = None
        self._pref_manager = None

    # -------------------------------------------------------------------------
    # 数据加载
    # -------------------------------------------------------------------------

    @property
    def db(self) -> TinyDB:
        """延迟加载数据库"""
        if self._db is None:
            if not self.db_path.exists():
                raise FileNotFoundError(
                    f"数据库不存在: {self.db_path}\n"
                    f"请先运行: python bin/skills_db_init.py"
                )
            self._db = TinyDB(self.db_path, storage=JSONStorage)
            self._Skill = Query()
        return self._db

    @property
    def Skill(self) -> Query:
        """获取 Query 对象"""
        if self._Skill is None:
            _ = self.db  # 触发加载
        return self._Skill

    @property
    def user_choices(self) -> dict:
        """延迟加载用户偏好"""
        if self._user_choices is None:
            self._user_choices = self._load_user_choices()
        return self._user_choices

    def reload(self):
        """重新加载数据"""
        self._db = None
        self._Skill = None
        self._user_choices = None

    def _load_user_choices(self) -> dict:
        """加载用户偏好"""
        if not self.user_choices_path.exists():
            return {"version": "1.0", "choices": []}

        try:
            with open(self.user_choices_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {"version": "1.0", "choices": []}

    def _save_user_choices(self):
        """保存用户偏好"""
        self.user_choices_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.user_choices_path, 'w', encoding='utf-8') as f:
            json.dump(self.user_choices, f, ensure_ascii=False, indent=2)

    # -------------------------------------------------------------------------
    # 核心匹配方法
    # -------------------------------------------------------------------------

    def match(
        self,
        task: str,
        threshold: float = 0.2,
        top_k: int = 5,
        installed_first: bool = True
    ) -> List[SkillCandidate]:
        """
        匹配技能（混合展示：已安装 + 推荐）

        Args:
            task: 用户任务描述
            threshold: 匹配阈值 (0-1)
            top_k: 返回最多多少个候选
            installed_first: 是否优先展示已安装技能

        Returns:
            按置信度排序的候选技能列表
        """
        all_skills = self.db.all()
        task_lower = task.lower()

        candidates = []

        for skill in all_skills:
            score = self._calculate_score(task_lower, skill)

            if score >= threshold:
                candidates.append(SkillCandidate(
                    name=skill.get("name", ""),
                    folder_name=skill.get("folder_name", skill.get("name", "")),  # 优先用 folder_name
                    confidence=score,
                    reason=self._generate_reason(skill),
                    installed=skill.get("installed", False),
                    capabilities=self._get_capabilities(skill),
                    entry_point=skill.get("installed_path", "") or "SKILL.md",
                    category=skill.get("category", "unknown"),
                    source="db",
                    install_cmd=skill.get("install", ""),
                    parent=skill.get("parent", ""),
                    repo=skill.get("repo", "")
                ))

        # 排序：已安装优先 + 置信度
        if installed_first:
            candidates.sort(
                key=lambda x: (
                    0 if x.installed else 1,  # 已安装排前面
                    -x.confidence              # 置信度降序
                )
            )
        else:
            candidates.sort(key=lambda x: -x.confidence)

        return candidates[:top_k]

    def _calculate_score(self, task: str, skill: Dict) -> float:
        """
        计算匹配分数 (加权)

        权重分配:
        - 名称匹配: 0.30
        - 标签匹配: 0.25
        - 搜索索引: 0.30
        - 分类匹配: 0.15
        - 中文关键词匹配: 0.40 (新增)
        - 用户偏好加成: +0.0 ~ +0.3
        """
        score = 0.0

        # 1. 名称匹配 (0.30)
        name = skill.get("name", "").lower()
        if task in name:
            if task == name:
                score += 0.30
            else:
                score += 0.20

        # 2. 标签匹配 (0.25)
        tags = skill.get("tags", [])
        for tag in tags:
            if task in tag.lower():
                score += 0.25
                break

        # 3. 搜索索引匹配 (0.30)
        search_index = skill.get("search_index", "").lower()
        if task in search_index:
            # 计算出现次数
            count = search_index.count(task)
            score += min(0.30, count * 0.10)

        # 4. 分类匹配 (0.15)
        category = skill.get("category", "").lower()
        if task in category:
            score += 0.15

        # 5. 中文关键词匹配 (0.40) - @Runner 专用
        keywords_cn = skill.get("keywords_cn", [])
        for kw in keywords_cn:
            if task in kw or kw in task:
                score += 0.40
                break

        # 6. 父包匹配 (加成)
        parent = skill.get("parent", "").lower()
        if task in parent:
            score += 0.10

        # 7. 用户偏好加成
        try:
            if self._pref_manager is None:
                try:
                    import importlib
                    pref_module = importlib.import_module('runner_preferences')
                    self._pref_manager = pref_module.PreferenceManager()
                except ImportError:
                    self._pref_manager = None

            if self._pref_manager:
                boost = self._pref_manager.get_confidence_boost(task, skill.get("name", ""))
                score += boost
        except Exception:
            pass

        return round(min(score, 1.0), 3)

    def _get_capabilities(self, skill: Dict) -> Dict:
        """从 TinyDB 数据构造 capabilities"""
        return {
            "input": ["text", "task"],
            "output": ["result"],
            "tags": skill.get("tags", [skill.get("category", "skill")]),
            "semantic": [skill.get("search_index", "")[:100]],
            "category": skill.get("category", "unknown")
        }

    def _generate_reason(self, skill: Dict) -> str:
        """生成推荐理由"""
        parts = []

        category = skill.get("category", "")
        if category:
            parts.append(f"[{category}]")

        tags = skill.get("tags", [])[:3]
        if tags:
            parts.append(", ".join(tags))

        parent = skill.get("parent", "")
        if parent:
            parts.append(f"包: {parent}")

        return " | ".join(parts) if parts else "技能"

    # -------------------------------------------------------------------------
    # 查询方法
    # -------------------------------------------------------------------------

    def get_installed_skills(self) -> List[Dict]:
        """获取所有已安装技能"""
        return self.db.search(self.Skill.installed == True)

    def get_curated_skills(self) -> List[Dict]:
        """获取所有推荐技能（未安装）"""
        return self.db.search(self.Skill.installed == False)

    def get_skills_by_category(self, category: str) -> List[Dict]:
        """按分类获取技能"""
        return self.db.search(self.Skill.category == category)

    def get_skills_by_parent(self, parent: str) -> List[Dict]:
        """获取父包下的所有子技能"""
        return self.db.search(self.Skill.parent == parent)

    def search_by_tag(self, tag: str) -> List[Dict]:
        """按标签搜索技能"""
        # TinyDB 的 any 查询
        return self.db.search(self.Skill.tags.any(tag))

    # -------------------------------------------------------------------------
    # locate() 方法 - 优先级查找
    # -------------------------------------------------------------------------

    def locate(self, query: str) -> Dict[str, Any]:
        """
        按优先级查找技能

        优先级: 已安装 → 推荐

        Args:
            query: 用户需求描述

        Returns:
            {
                "source": "installed/curated/none",
                "skill": {...},
                "action": "run/install",
                "message": "...",
                "priority": 1-3
            }
        """
        query_lower = query.lower()

        # 1. 检查已安装技能
        installed = self.get_installed_skills()
        for skill in installed:
            name = skill.get("name", "").lower()
            parent = skill.get("parent", "").lower()
            search_index = skill.get("search_index", "").lower()

            if (query_lower in name or
                query_lower in parent or
                query_lower in search_index):
                return {
                    "source": "installed",
                    "skill": skill,
                    "action": "run",
                    "message": f"[已安装] {skill['name']}",
                    "priority": 1
                }

        # 2. 检查推荐技能
        curated = self.get_curated_skills()
        for skill in curated:
            name = skill.get("name", "").lower()
            parent = skill.get("parent", "").lower()
            search_index = skill.get("search_index", "").lower()

            if (query_lower in name or
                query_lower in parent or
                query_lower in search_index):
                return {
                    "source": "curated",
                    "skill": skill,
                    "action": "install",
                    "message": f"[推荐] {skill['name']}",
                    "priority": 2
                }

        # 3. 无匹配
        return {
            "source": "none",
            "skill": None,
            "action": "search",
            "message": "[未匹配] 建议使用 GitHub 搜索或 MCP 服务",
            "priority": 3
        }

    # -------------------------------------------------------------------------
    # 统计方法
    # -------------------------------------------------------------------------

    def get_stats(self) -> Dict:
        """获取数据库统计信息"""
        all_skills = self.db.all()
        installed = self.get_installed_skills()

        # 按分类统计
        categories = {}
        for skill in all_skills:
            cat = skill.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1

        # 按父包统计
        parents = {}
        for skill in all_skills:
            parent = skill.get("parent", "")
            if parent:
                parents[parent] = parents.get(parent, 0) + 1

        return {
            "total": len(all_skills),
            "installed": len(installed),
            "curated": len(all_skills) - len(installed),
            "categories": categories,
            "parents": parents,
            "db_size": self.db_path.stat().st_size if self.db_path.exists() else 0
        }

    # -------------------------------------------------------------------------
    # 同步方法
    # -------------------------------------------------------------------------

    def sync_installed_skills(self) -> int:
        """
        同步 .claude/skills/ 中的已安装技能到 TinyDB

        Returns:
            更新的技能数量
        """
        if not INSTALLED_SKILLS_DIR.exists():
            return 0

        updated_count = 0

        for skill_dir in INSTALLED_SKILLS_DIR.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_name = skill_dir.name
            skill_md = skill_dir / "SKILL.md"

            if not skill_md.exists():
                continue

            # 解析 SKILL.md
            try:
                frontmatter = self._parse_skill_frontmatter(skill_md)
            except Exception:
                continue

            # 构造搜索索引
            search_parts = [
                skill_name,
                frontmatter.get("category", "utilities"),
                " ".join(frontmatter.get("tags", [])),
                frontmatter.get("description", "")
            ]
            search_index = " ".join(filter(None, search_parts))

            # 准备数据
            skill_data = {
                "id": skill_name.lower().replace("_", "-"),
                "name": skill_name,
                "category": frontmatter.get("category", "utilities"),
                "description": frontmatter.get("description", ""),
                "tags": frontmatter.get("tags", ["skill"]),
                "keywords_cn": frontmatter.get("keywords_cn", []),  # 提取中文关键词
                "installed": True,
                "installed_path": f".claude/skills/{skill_name}",
                "search_index": search_index.lower(),
                "parent": "",
                "repo": "",
                "install": "",
                "last_updated": datetime.now().strftime("%Y-%m-%d")
            }

            # 检查是否存在
            existing = self.db.get(self.Skill.id == skill_data["id"])

            if existing:
                # 更新
                self.db.update(skill_data, doc_ids=[existing.doc_id])
                updated_count += 1
            else:
                # 插入
                self.db.insert(skill_data)
                updated_count += 1

        return updated_count

    def _parse_skill_frontmatter(self, skill_md: Path) -> Dict:
        """解析 SKILL.md 的 YAML frontmatter"""
        content = skill_md.read_text(encoding='utf-8')

        # 解析 YAML frontmatter
        if content.startswith('---'):
            end = content.find('---', 3)
            if end > 0:
                frontmatter_str = content[3:end].strip()
                # 尝试导入 yaml
                try:
                    import yaml
                    return yaml.safe_load(frontmatter_str) or {}
                except ImportError:
                    pass

                # 手动解析
                result = {}
                for line in frontmatter_str.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        result[key.strip()] = value.strip().strip('"').strip("'")
                return result

        return {}

    # -------------------------------------------------------------------------
    # 用户偏好管理
    # -------------------------------------------------------------------------

    def record_choice(self, task: str, skill: str, accepted: bool = True):
        """记录用户选择"""
        if not accepted:
            return

        task_pattern = self._generate_task_pattern(task)
        choices = self.user_choices.get("choices", [])

        existing = None
        for i, choice in enumerate(choices):
            if choice["task_pattern"] == task_pattern and choice["skill"] == skill:
                existing = i
                break

        if existing is not None:
            choices[existing]["auto_confirm_count"] += 1
            choices[existing]["last_confirmed"] = datetime.now().isoformat()
            if choices[existing]["auto_confirm_count"] >= 5:
                choices[existing]["never_ask"] = True
        else:
            choices.append(UserChoice(
                task_pattern=task_pattern,
                skill=skill,
                auto_confirm_count=1,
                last_confirmed=datetime.now().isoformat(),
                never_ask=False
            ).to_dict())

        self.user_choices["choices"] = choices
        self._save_user_choices()

    def get_auto_confirm_status(self, task: str, skill: str) -> bool:
        """检查是否可以自动确认"""
        task_pattern = self._generate_task_pattern(task)

        for choice in self.user_choices.get("choices", []):
            if (choice["task_pattern"] == task_pattern and
                choice["skill"] == skill and
                choice.get("never_ask", False)):
                return True

        return False

    def reset_preference(self, task: str, skill: str = None):
        """重置偏好"""
        task_pattern = self._generate_task_pattern(task)
        choices = self.user_choices.get("choices", [])

        if skill:
            choices = [
                c for c in choices
                if not (c["task_pattern"] == task_pattern and c["skill"] == skill)
            ]
        else:
            choices = [
                c for c in choices
                if c["task_pattern"] != task_pattern
            ]

        self.user_choices["choices"] = choices
        self._save_user_choices()

    def _generate_task_pattern(self, task: str) -> str:
        """生成任务模式（用于匹配）"""
        return task.lower().strip()


# =============================================================================
# CLI 入口
# =============================================================================

def main():
    """CLI 测试入口"""
    import argparse

    parser = argparse.ArgumentParser(
        description="技能匹配引擎 - TinyDB 版",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 搜索技能
  python bin/skill_matcher.py "调试"

  # 显示统计信息
  python bin/skill_matcher.py --stats

  # 同步已安装技能
  python bin/skill_matcher.py --sync

  # locate 模式
  python bin/skill_matcher.py --locate "pdf"
        """
    )

    parser.add_argument("task", nargs="?", help="搜索查询")
    parser.add_argument("--threshold", "-t", type=float, default=0.2,
                       help="匹配阈值 (默认: 0.2)")
    parser.add_argument("--top", "-k", type=int, default=5,
                       help="返回候选数量 (默认: 5)")
    parser.add_argument("--stats", action="store_true",
                       help="显示统计信息")
    parser.add_argument("--sync", action="store_true",
                       help="同步已安装技能到数据库")
    parser.add_argument("--list-installed", action="store_true",
                       help="列出已安装技能")
    parser.add_argument("--locate", "-l", action="store_true",
                       help="使用优先级查找模式")
    parser.add_argument("--category", "-c",
                       help="按分类筛选")
    parser.add_argument("--parent", "-p",
                       help="按父包筛选")

    args = parser.parse_args()

    try:
        matcher = SkillMatcher()

        if args.stats:
            stats = matcher.get_stats()
            print(f"\n📊 技能数据库统计:\n")
            print(f"   总技能数: {stats['total']}")
            print(f"   已安装: {stats['installed']}")
            print(f"   推荐: {stats['curated']}")
            print(f"   数据库大小: {stats['db_size']} bytes\n")

            print(f"   按分类:")
            for cat, count in sorted(stats['categories'].items()):
                print(f"     {cat}: {count}")

            print(f"\n   按父包:")
            for parent, count in sorted(stats['parents'].items()):
                print(f"     {parent}: {count}")

        elif args.sync:
            print("同步已安装技能...")
            count = matcher.sync_installed_skills()
            print(f"✓ 同步了 {count} 个已安装技能")

        elif args.list_installed:
            installed = matcher.get_installed_skills()
            print(f"\n✅ 已安装技能 ({len(installed)} 个):\n")
            for skill in installed:
                parent = skill.get('parent', '')
                parent_info = f" ({parent})" if parent else ""
                print(f"   {skill.get('name')}{parent_info}")

        elif args.category:
            skills = matcher.get_skills_by_category(args.category)
            print(f"\n📁 {args.category} 分类 ({len(skills)} 个):\n")
            for skill in skills:
                status = "[已安装]" if skill.get('installed') else "[推荐]"
                print(f"   {status} {skill.get('name')}")

        elif args.parent:
            skills = matcher.get_skills_by_parent(args.parent)
            print(f"\n📦 {args.parent} 子技能 ({len(skills)} 个):\n")
            for skill in skills:
                status = "[已安装]" if skill.get('installed') else "[推荐]"
                print(f"   {status} {skill.get('name')}")

        elif args.locate and args.task:
            result = matcher.locate(args.task)
            print(f"\n[*] 查找结果: '{args.task}'\n")
            print(f"  {result['message']}")

            skill = result.get("skill")
            if skill and result["source"] != "installed":
                if "repo" in skill:
                    print(f"  仓库: {skill['repo']}")
                if "stars" in skill:
                    print(f"  Stars: {skill['stars']}")
                if "tags" in skill:
                    print(f"  标签: {', '.join(skill['tags'])}")
                if "install" in skill:
                    print(f"  安装: {skill['install']}")
            print()

            return 0 if result["source"] != "none" else 1

        elif args.task:
            candidates = matcher.match(
                args.task,
                threshold=args.threshold,
                top_k=args.top
            )

            print(f"\n🔍 搜索: '{args.task}'\n")

            if not candidates:
                print("  未找到匹配的技能")
                print("  提示: 尝试降低阈值 (-t 0.1)")
                return 1

            for i, candidate in enumerate(candidates, 1):
                print(f"  [{i}] {candidate}")
                if candidate.install_cmd and not candidate.installed:
                    print(f"      安装: {candidate.install_cmd}")
            print()

            return 0

        else:
            parser.print_help()
            return 1

    except FileNotFoundError as e:
        print(f"\n❌ {e}")
        print(f"\n💡 提示: 请先初始化数据库")
        print(f"   python bin/skills_db_init.py")
        return 1
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

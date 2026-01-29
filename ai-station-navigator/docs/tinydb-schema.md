# TinyDB 技能数据库字段说明

**版本**: v1.1
**更新日期**: 2026-01-26

**文件位置**: `.claude/skills/skills.db`

**⚠️ 数据库类型**: TinyDB（轻量级 JSON 文档数据库）
**❌ 禁止使用**: `sqlite3` 命令（这是 TinyDB，不是 SQLite！）

---

## 快速查询指南

### Python 查询（推荐）

```python
from tinydb import TinyDB, Query

# 打开数据库
db = TinyDB('.claude/skills/skills.db', encoding='utf-8')

# 查询所有技能
all_skills = db.all()
print(f"总计: {len(all_skills)} 个技能")

# 查询已安装技能
Skill = Query()
installed = db.search(Skill.installed == True)
print(f"已安装: {len(installed)} 个")

# 按名称查询
skill = db.search(Skill.name == 'brainstorming')

# 按分类查询
utilities = db.search(Skill.category == 'utilities')
```

### 命令行快速查看

```bash
# 查看数据库类型
file .claude/skills/skills.db
# 输出: JSON text data

# 查看前几条记录（JSON 格式）
head -100 .claude/skills/skills.db

# 统计记录数
python -c "from tinydb import TinyDB; db=TinyDB('.claude/skills/skills.db',encoding='utf-8'); print(len(db))"
```

---

## 字段结构

### 基础字段

| 字段 | 类型 | 必填 | 说明 |
|:---|:---:|:---:|:---|
| `id` | string | ✅ | 唯一标识符，格式：小写，连字符分隔 |
| `name` | string | ✅ | 技能名称 |
| `description` | string | ✅ | 技能描述 |
| `category` | string | ✅ | 分类（utilities/agent/debugging/testing等） |
| `tags` | array | ✅ | 标签列表 |
| `keywords_cn` | array | ⚪️ | 中文关键词列表（用于 @Runner 匹配） |

### 父子关系字段

| 字段 | 类型 | 必填 | 说明 |
|:---|:---|:---:|:---|
| `package_type` | string | ✅ | **包类型**：`standalone` / `parent` / `child` |
| `parent` | string | ✅ | 父包仓库地址（仅 `package_type=child` 时有值，与 `parent_repo` 保持一致） |
| `parent_repo` | string | ✅ | 父包仓库地址 |
| `child_count` | int | ✅ | 子技能数量（仅 `package_type=parent` 时 > 0） |

### 仓库字段

| 字段 | 类型 | 必填 | 说明 |
|:---|:---|:---:|:---|
| `repo` | string | ✅ | 技能仓库地址 (user/repo) |
| `stars` | string | ⚪️ | GitHub Stars 数量 |
| `install` | string | ✅ | 安装命令 |

### 安装状态字段

| 字段 | 类型 | 必填 | 说明 |
|:---|:---|:---:|:---|
| `installed` | boolean | ✅ | 是否已安装 |
| `installed_path` | string | ✅ | 安装路径（如 `.claude/skills/skill-name`） |
| `last_updated` | string | ✅ | 最后更新日期 (YYYY-MM-DD) |
| `synced_at` | string | ⚪️ | 同步时间戳 |

### 搜索字段

| 字段 | 类型 | 必填 | 说明 |
|:---|:---|:---:|:---|
| `search_index` | string | ✅ | 搜索索引（name + category + tags + description） |
| `source_file` | string | ✅ | 数据来源（github/manual/auto_created/auto_created_fallback） |

---

## package_type 值域

### `standalone` - 单项目技能

独立的单个技能项目，不包含子技能。

**示例**：
```json
{
  "id": "skillforge",
  "name": "SkillForge",
  "package_type": "standalone",
  "parent": "",
  "child_count": 0
}
```

### `parent` - 父包

包含多个子技能的项目集合。

**示例**：
```json
{
  "id": "superpowers",
  "name": "Superpowers",
  "package_type": "parent",
  "parent": "",
  "child_count": 12
}
```

**特征**：
- `parent` 为空
- `child_count` > 0
- 子技能的 `parent` 指向此项目名

### `child` - 子技能

属于某个父包的技能。

**示例**：
```json
{
  "id": "brainstorming",
  "name": "brainstorming",
  "package_type": "child",
  "parent": "Superpowers",
  "child_count": 0
}
```

**特征**：
- `parent` 有值（父包名称）
- `child_count` 为 0

---

## 判断逻辑

```
扫描仓库
    |
    ├─ 包含多个 SKILL.md？
    │
    ├─ 是 → package_type = "parent"
    │       child_count = SKILL.md 数量
    │
    └─ 否 → 是子技能？
            │
            ├─ 是 → package_type = "child"
            │        parent = 父包名
            │
            └─ 否 → package_type = "standalone"
```

---

## 数据示例

### Superpowers (父包)

```json
{
  "id": "superpowers",
  "name": "Superpowers",
  "package_type": "parent",
  "parent": "",
  "parent_repo": "obra/superpowers",
  "repo": "obra/superpowers",
  "child_count": 12
}
```

### brainstorming (子技能)

```json
{
  "id": "brainstorming",
  "name": "brainstorming",
  "package_type": "child",
  "parent": "obra/superpowers",
  "parent_repo": "obra/superpowers",
  "repo": "obra/superpowers",
  "child_count": 0,
  "installed": true,
  "installed_path": ".claude/skills/brainstorming",
  "keywords_cn": ["设计", "设计方案", "探索", "头脑风暴", "细化", "功能设计", "架构设计"]
}
```

### SkillForge (单项目)

```json
{
  "id": "skillforge",
  "name": "SkillForge",
  "package_type": "standalone",
  "parent": "",
  "parent_repo": "tripleyak/SkillForge",
  "repo": "tripleyak/SkillForge",
  "child_count": 0,
  "installed": false
}
```

---

## source_file 值域

### `github` - GitHub 扫描

从 GitHub 仓库获取的记录（已弃用 scanner，改用 skill_manager.py info）。

**特征**：
- 包含完整的 `repo`、`stars` 信息
- `category`、`tags` 从 SKILL.md frontmatter 提取
- `description` 完整

### `manual` - 手动创建

手动添加到 Markdown 索引的记录。

### `auto_created` - 自动创建（混合模式）

安装技能时发现数据库无记录，自动从本地 SKILL.md 创建。

**特征**：
- `category`、`tags`、`description` 从 SKILL.md frontmatter 提取
- `repo` 为空（待后续扫描补充）
- `stars` 为空（待后续扫描补充）

**示例**：
```json
{
  "id": "my-skill",
  "name": "my-skill",
  "category": "utilities",
  "tags": ["skill", "dev"],
  "description": "从 SKILL.md 提取的完整描述",
  "repo": "",
  "stars": "",
  "source_file": "auto_created"
}
```

### `auto_created_fallback` - 自动创建回退

SKILL.md 不存在或解析失败时的回退记录。

**特征**：
- 最小化信息
- `category` 默认为 "utilities"
- `description` 为技能名

**示例**：
```json
{
  "id": "my-skill",
  "name": "my-skill",
  "category": "utilities",
  "tags": ["skill"],
  "description": "my-skill 技能",
  "repo": "",
  "stars": "",
  "source_file": "auto_created_fallback"
}
```

---

## keywords_cn 字段说明

**用途**: @Runner 智能技能路由系统的中文关键词匹配。

**值域**: 字符串数组，如 `["设计", "调试", "测试"]`

**定义方式**: 在 SKILL.md 的 YAML frontmatter 中添加：

```markdown
---
name: brainstorming
description: "You MUST use this before any creative work"
category: utilities
tags: [skill, design]
keywords_cn: ["设计", "设计方案", "探索", "头脑风暴"]
---
```

**自动提取**:
- 安装技能时，系统自动从 SKILL.md 提取 `keywords_cn` 字段
- 同步已安装技能时 (`python bin/skills_db_sync.py --installed`)，也会更新此字段

**匹配逻辑**: 当用户输入 `@技能 <中文描述>` 时，系统提取中文关键词并匹配此字段。

**示例**:
| 技能 | keywords_cn | 用户输入 | 匹配 |
|:---|:---|:---|:---:|
| `brainstorming` | `["设计", "设计方案"]` | "@技能 **设计**一个登录页" | ✅ |
| `systematic-debugging` | `["调试", "bug"]` | "@技能 **调试**登录失败" | ✅ |

**来源**:
- 从 `.claude/runner-keywords.json` 迁移至 TinyDB（2026-01-26）
- 支持 SKILL.md frontmatter 定义（2026-01-26）

# Skill Manager 使用指南

## 概述

`skill_manager.py` 是技能的生命周期管理工具，负责技能的安装、卸载、搜索和验证。

**版本**: v1.0
**文件位置**: `bin/skill_manager.py`

## 核心功能

| 功能 | 说明 |
|:---|:---|
| **格式检测** | 检测输入技能的格式类型（GitHub/本地/.skill包） |
| **标准化转换** | 将非标准格式转换为官方 SKILL.md 格式 |
| **结构验证** | 验证转换后的技能结构完整性 |
| **自动安装** | 复制到 `.claude/skills/` 并同步数据库 |
| **智能搜索** | 基于关键词、描述、标签搜索已安装技能 |

## 架构

```
Kernel (AI) → Skill Manager → Format Detector → Normalizer → Installer
```

## 支持的格式

| 格式类型 | 识别标记 | 状态 |
|:---|:---|:---|
| **Claude Code Official** | `SKILL.md` | 官方格式，直接处理 |
| **Claude Plugin** | `.claude-plugin`, `plugin.json` | 内置转换 |
| **Agent Skills** | `skills/`, `SKILL.md` | 内置转换 |
| **Cursor Rules** | `.cursor`, `rules/` | 内置转换 |
| **Plugin Marketplace** | `plugins/`, `MARKETPLACE.md` | 内置转换 |

查看所有支持的格式：
```bash
python bin/skill_manager.py formats
```

## 命令参考

### 1. install - 安装技能

#### 从本地目录安装

```bash
python bin/skill_manager.py install /path/to/skill
```

#### 从 .skill 包安装

```bash
python bin/skill_manager.py install package.skill
```

#### 安装指定子技能（多技能仓库）

```bash
python bin/skill_manager.py install /path/to/repo --skill my-skill
```

#### 批量安装（所有技能）

```bash
python bin/skill_manager.py install /path/to/repo --batch
```

#### 强制覆盖已存在的技能

```bash
python bin/skill_manager.py install /path/to/skill --force
```

**参数说明**:
| 参数 | 说明 |
|:---|:---|
| `source` | 安装源（本地目录或 .skill 包） |
| `--batch, -b` | 批量安装所有技能 |
| `--skill, -s` | 指定子技能名称 |
| `--force, -f` | 强制安装，跳过非技能仓库检测 |
| `--refresh-cache` | 强制刷新仓库缓存 |

> **注意**: GitHub 源需要先使用 `clone_manager` 处理

### 2. list - 列出已安装技能

```bash
python bin/skill_manager.py list
```

**启用颜色输出**:
```bash
python bin/skill_manager.py list --color
```

### 3. search - 搜索技能

#### 单关键词搜索

```bash
python bin/skill_manager.py search prompt
```

#### 多关键词搜索

```bash
python bin/skill_manager.py search prompt optimize --score
```

**参数说明**:
| 参数 | 说明 |
|:---|:---|
| `keywords` | 搜索关键词（支持多个，AND 逻辑） |
| `--limit, -l` | 返回结果数量（默认 10） |
| `--score, -s` | 显示匹配分数和匹配原因 |

### 4. uninstall - 卸载技能

#### 卸载单个技能

```bash
python bin/skill_manager.py uninstall my-skill
```

#### 批量卸载

```bash
python bin/skill_manager.py uninstall skill1 skill2 skill3
```

#### 强制删除（不询问）

```bash
python bin/skill_manager.py uninstall my-skill --force
```

### 5. validate - 验证技能结构

```bash
python bin/skill_manager.py validate .claude/skills/my-skill
```

### 6. record - 记录技能使用

```bash
python bin/skill_manager.py record my-skill
```

> 用于搜索排序时增加使用频率加权

## 搜索评分机制

| 匹配类型 | 分数 | 说明 |
|:---|:---:|:---|
| **名称完全匹配** | 100 | 技能名与关键词完全一致 |
| **名称前缀匹配** | 90 | 技能名以关键词开头 |
| **名称包含** | 80 | 技能名包含关键词 |
| **中文关键词** | 40 | 匹配 `keywords_cn` 字段 |
| **描述包含** | 50 | 描述中包含关键词 |
| **标签匹配** | 30 | `tags` 字段匹配 |
| **类别匹配** | 20 | `category` 字段匹配 |
| **多关键词协同** | +20 | 两个以上关键词同时匹配 |
| **使用频率** | +3/次 | 最多 +15 分 |

## 技能结构

### SKILL.md 格式

```markdown
---
name: my-skill
description: "技能描述"
category: utilities
tags: ["tool", "automation"]
keywords_cn: ["关键词1", "关键词2"]
---

# 技能标题

## 功能说明

描述技能的功能...

## 使用方法

说明如何使用...
```

### 必需字段

| 字段 | 说明 | 限制 |
|:---|:---|:---|
| `name` | 技能名称 | 小写字母、数字、连字符，最多 128 字符 |
| `description` | 技能描述 | 最多 1024 字符，不能包含 HTML 标签 |

### 可选字段

| 字段 | 说明 |
|:---|:---|
| `category` | 技能分类 |
| `tags` | 标签列表 |
| `keywords_cn` | 中文关键词列表 |

## 数据库同步

技能安装/卸载时会自动同步到 `.claude/skills/skills.db`：

```json
{
  "_default": {
    "skill-id": {
      "id": "skill-id",
      "name": "skill-name",
      "folder_name": "skill_folder",
      "description": "技能描述",
      "category": "utilities",
      "tags": ["tool"],
      "keywords_cn": [],
      "installed": true,
      "installed_path": ".claude/skills/skill_folder"
    }
  }
}
```

## GitHub 源处理流程

GitHub 源需要使用 `clone_manager` 预处理：

```bash
# 步骤 1: 克隆仓库
python bin/clone_manager.py clone https://github.com/user/repo

# 步骤 2: 安全扫描（可选）
python bin/security_scanner.py scan-all

# 步骤 3: 安装技能
python bin/skill_manager.py install <缓存路径>
```

## 技能验证规则

### 项目类型检测

系统会自动检测是否为技能仓库，拒绝安装工具项目：

**技能仓库特征**:
- 根目录有 `SKILL.md`
- `skills/` 目录包含多个技能
- `.claude/skills/` 结构

**工具项目特征**:
- `setup.py`, `Cargo.toml`, `go.mod`
- 包含 `src/`, `lib/`, `api/` 等工具组件目录
- README 包含 "skill generator", "cli tool" 等关键词

### 子目录验证

自动跳过非技能目录：
- 工具组件目录（`src/`, `lib/`, `tests/` 等）
- Python 包目录（有 `__init__.py` 但无 `SKILL.md`）
- 不符合命名规范的目录

## 故障排除

### 常见问题

| 问题 | 解决方案 |
|:---|:---|
| `拒绝安装：这不是技能项目` | 确认目标确实是技能仓库，使用 `--force` 跳过检测 |
| `技能名称不符合规范` | 技能名必须是 kebab-case（小写字母+连字符） |
| `数据库同步失败` | 检查 `.claude/skills/skills.db` 文件权限 |
| `未找到子技能` | 使用 `list` 查看可用技能，确认名称正确 |

### 调试技巧

查看详细处理过程：
```bash
python bin/skill_manager.py install <source> --force
```

验证技能结构：
```bash
python bin/skill_manager.py validate .claude/skills/my-skill
```

## 工作流程示例

### 完整安装流程

```bash
# 1. GitHub 源预处理
python bin/clone_manager.py clone https://github.com/user/skills-repo

# 2. 扫描安全（可选）
python bin/security_scanner.py scan-all

# 3. 列出可用技能
python bin/skill_manager.py list

# 4. 搜索特定技能
python bin/skill_manager.py search prompt --score

# 5. 安装技能
python bin/skill_manager.py install mybox/cache/repos/user-skills/skill-name

# 6. 验证安装
python bin/skill_manager.py validate .claude/skills/skill-name
```

### 批量卸载流程

```bash
# 批量卸载多个技能
python bin/skill_manager.py uninstall skill1 skill2 skill3 --force
```

## 相关文档

- `docs/skill-install-quickstart.md` - 技能安装快速入门
- `docs/skills-mapping.md` - 子技能映射表
- `CLAUDE.md` §3.1 - 技能生命周期协议

# Skill Manager 使用指南

**版本**: v2.0
**最后更新**: 2026-01-31
**维护者**: AIOS 项目组

---

## 概述

**Skill Manager** 是技能管理工具，用于安装、搜索、卸载技能，支持多种输入源和格式自动转换。

**核心功能**：
- ✅ 自动检测输入源类型（GitHub / 本地 / .skill 包）
- ✅ 智能识别技能格式（Official / Claude Plugin / Agent Skills / Cursor Rules）
- ✅ 自动修复常见格式问题（frontmatter、命名规范）
- ✅ 批量安装支持
- ✅ 子技能单独安装
- ✅ 技能搜索（关键词匹配 + 使用频率加权）

---

## 快速开始

### 基本用法

```bash
# 安装 GitHub 仓库中的技能
python bin/skill_manager.py install https://github.com/user/repo

# 安装本地目录
python bin/skill_manager.py install path/to/skill

# 搜索技能
python bin/skill_manager.py search prompt

# 列出已安装技能
python bin/skill_manager.py list
```

---

## 命令详解

### install - 安装技能

#### 语法

```bash
python bin/skill_manager.py install <source> [选项]
```

#### 输入源支持

| 输入类型 | 示例 | 说明 |
|:---|:---|:---|
| **GitHub URL** | `https://github.com/user/repo` | 自动克隆并安装 |
| **GitHub 简写** | `user/repo` | 自动补全为完整 URL |
| **本地目录** | `path/to/skill` | 直接安装 |
| **.skill 包** | `path/to/skill.skill` | 解压后安装 |

#### 选项

| 选项 | 简写 | 说明 |
|:---|:---|:---|
| `--batch` | `-b` | 批量安装仓库中所有技能 |
| `--skill` | `-s` | 指定要安装的子技能名称 |
| `--force` | `-f` | 强制覆盖已存在的技能 |
| `--refresh-cache` | | 强制刷新仓库缓存（重新克隆） |

#### 示例

```bash
# 安装单技能仓库（自动安装）
python bin/skill_manager.py install https://github.com/user/single-skill

# 安装多技能仓库（自动批量安装所有子技能）
python bin/skill_manager.py install https://github.com/obra/superpowers
# → 找到 17 个技能，自动批量安装

# 只安装指定的子技能
python bin/skill_manager.py install obra/superpowers --skill brainstorming

# 强制覆盖已安装的技能
python bin/skill_manager.py install https://github.com/user/repo --force
```

#### 智能适配行为

| 检测结果 | 自动行为 |
|:---|:---|
| **1 个技能** | 自动安装该技能 |
| **多个子技能** | 自动批量安装所有 |
| **用户指定 `--skill`** | 只安装指定的子技能 |

---

### search - 搜索技能

#### 语法

```bash
python bin/skill_manager.py search <keywords> [选项]
```

#### 参数

| 参数 | 说明 |
|:---|:---|
| `keywords` | 搜索关键词（支持多个，AND 逻辑） |

#### 选项

| 选项 | 简写 | 说明 |
|:---|:---|:---|
| `--limit` | `-l` | 返回结果数量（默认 10） |
| `--score` | `-s` | 显示匹配分数 |

#### 搜索匹配优先级

| 匹配类型 | 分数 | 说明 |
|:---|:---:|:---|
| 名称完全匹配 | 100 | 精确匹配技能名 |
| 名称前缀匹配 | 90 | 技能名以关键词开头 |
| 名称包含 | 80 | 技能名包含关键词 |
| 描述包含 | 50 | 描述中包含关键词 |
| 标签匹配 | 30 | tags 字段匹配 |
| 使用频率加权 | +15 | 基于历史使用频率 |

#### 示例

```bash
# 单关键词搜索
python bin/skill_manager.py search prompt

# 多关键词搜索
python bin/skill_manager.py search prompt optimize --limit 5

# 显示匹配分数
python bin/skill_manager.py search git --score
```

---

### list - 列出已安装技能

```bash
# 列出所有已安装技能
python bin/skill_manager.py list

# 启用颜色输出
python bin/skill_manager.py list --color
```

---

### uninstall - 卸载技能

#### 语法

```bash
python bin/skill_manager.py uninstall <name> [选项]
```

#### 示例

```bash
# 卸载单个技能
python bin/skill_manager.py uninstall my-skill

# 批量卸载
python bin/skill_manager.py uninstall skill1 skill2 skill3

# 强制卸载（不询问确认）
python bin/skill_manager.py uninstall my-skill --force
```

---

### validate - 验证技能结构

```bash
# 验证指定技能目录
python bin/skill_manager.py validate .claude/skills/my-skill
```

**验证项目**：
- ✅ SKILL.md 文件存在
- ✅ YAML frontmatter 格式正确
- ✅ name 字段符合规范（hyphen-case）
- ✅ description 字段存在

---

### formats - 列出支持的技能格式

```bash
# 列出所有支持的格式
python bin/skill_manager.py formats
```

---

### cache - 管理仓库缓存

```bash
# 列出缓存
python bin/skill_manager.py cache list

# 清理所有缓存
python bin/skill_manager.py cache clear

# 清理超过 24 小时的缓存
python bin/skill_manager.py cache clear --older-than 24

# 更新指定仓库缓存
python bin/skill_manager.py cache update https://github.com/user/repo
```

---

### record - 记录技能使用

```bash
# 记录技能使用（内部使用，通常无需手动执行）
python bin/skill_manager.py record <skill-name>
```

---

## 支持的技能格式

| 格式 | 标记文件 | 处理方式 |
|:---|:---|:---|
| **Official** | `SKILL.md` | 直接安装 |
| **Claude Plugin** | `.claude-plugin`, `plugin.json` | 提取 metadata + 安装 |
| **Agent Skills** | `skills/`, `SKILL.md` | 保留结构 + 安装 |
| **Cursor Rules** | `.cursor`, `rules/` | 合并 .md 文件 + 安装 |
| **Generic** | 任意 | 从 README.md 生成 SKILL.md |

---

## 使用场景

### 场景 1：安装单个技能

```bash
python bin/skill_manager.py install \
  https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering
```

### 场景 2：批量安装技能包

```bash
python bin/skill_manager.py install \
  https://github.com/obra/superpowers
```

### 场景 3：安装指定子技能

```bash
python bin/skill_manager.py install \
  https://github.com/obra/superpowers --skill brainstorming
```

---

## 故障排查

### 问题：克隆失败

```bash
# 方案 1：使用代理
git config --global http.proxy http://127.0.0.1:7890

# 方案 2：手动克隆后安装本地目录
git clone https://github.com/user/repo mybox/temp/repo
python bin/skill_manager.py install mybox/temp/repo
```

### 问题：技能已存在

```bash
# 使用 --force 覆盖
python bin/skill_manager.py install <source> --force
```

---

## 相关文档

- [技能安装指南](./skills-installation.md)
- [推荐技能清单](./skills.md)
- [Vector Registry](./commands.md)

---

**更新记录**:

| 日期 | 版本 | 变更 |
|:---|:---|:---|
| 2026-01-31 | v2.0 | 移除 convert 命令，简化为 install 为主入口 |
| 2026-01-28 | v1.3 | 补充 search/uninstall/formats/record 命令 |

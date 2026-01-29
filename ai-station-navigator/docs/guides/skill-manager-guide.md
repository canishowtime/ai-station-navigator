# Skill Manager 使用指南

**版本**: v1.3
**最后更新**: 2026-01-28
**维护者**: AIOS 项目组

---

## 概述

**Skill Converter** 是一个自动化工具，用于将第三方技能转换为官方格式并安装到 `.claude/skills/` 目录，使其成为原生技能，可直接使用 `/Skill` 命令调用。

**核心功能**：
- ✅ 自动检测输入源类型（GitHub / 本地 / .skill 包）
- ✅ 智能识别技能格式（Official / Claude Plugin / Agent Skills / Cursor Rules）
- ✅ 自动修复常见格式问题（frontmatter、命名规范）
- ✅ 批量转换支持
- ✅ **子技能单独安装**（新增）
- ✅ 一键安装验证

---

## 快速开始

### 基本用法

```bash
# 转换并安装 GitHub 仓库中的技能
python bin/skill_manager.py convert https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering

# 转换本地目录
python bin/skill_manager.py convert path/to/skill

# 转换 .skill 包
python bin/skill_manager.py convert path/to/skill.skill
```

---

## 命令详解

### convert - 转换并安装

#### 语法

```bash
python bin/skill_manager.py convert <input> [选项]
```

#### 输入源支持

| 输入类型 | 示例 | 说明 |
|:---|:---|:---|
| **GitHub URL** | `https://github.com/user/repo` | 自动克隆并提取技能 |
| **本地目录** | `path/to/skill` | 直接转换目录 |
| **.skill 包** | `path/to/skill.skill` | 解压后转换 |

#### 选项

| 选项 | 简写 | 说明 |
|:---|:---|:---|
| `--output` | `-o` | 指定转换输出目录（默认: `mybox/temp/converted_skills`）|
| `--batch` | `-b` | 批量处理仓库中所有技能 |
| `--skill` | `-s` | 指定要处理的子技能名称（用于多技能仓库） |
| `--force` | `-f` | 强制覆盖已存在的技能 |
| `--no-install` | | 仅转换，不安装到 `.claude/skills/` |
| `--keep-temp` | | 保留临时文件（用于调试） |

#### 示例

```bash
# 安装单个技能仓库（自动安装）
python bin/skill_manager.py install https://github.com/user/single-skill

# 安装多技能仓库（自动批量安装所有子技能）
python bin/skill_manager.py install https://github.com/obra/superpowers
# → 找到 17 个技能，自动批量安装

# 只安装指定的子技能（覆盖自动判断）
python bin/skill_manager.py install obra/superpowers --skill brainstorming

# 批量安装（显式指定，与默认行为相同）
python bin/skill_manager.py install obra/superpowers --batch

# 强制覆盖已安装的技能
python bin/skill_manager.py install https://github.com/user/repo --force
```

#### 智能适配行为

系统会自动检测仓库结构并选择最佳处理方式：

| 检测结果 | 自动行为 | 手动覆盖 |
|:---|:---|:---|
| **1 个技能** | 自动安装该技能 | 无需覆盖 |
| **多个子技能** | 自动批量安装所有 | 使用 `--skill <name>` 只安装特定子技能 |
| **用户指定 `--skill`** | 只安装指定的子技能 | - |
| **用户指定 `--batch`** | 批量安装（与默认相同） | - |

#### 更多示例

```bash
# 仅转换不安裝（输出到指定目录）
python bin/skill_manager.py convert https://github.com/user/repo \
  --no-install --output mybox/custom_skills

# 保留临时文件用于调试
python bin/skill_manager.py convert https://github.com/user/repo --keep-temp
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
- ✅ description 字段存在且符合规范

---

### list - 列出已安装技能

```bash
# 列出所有已安装技能
python bin/skill_manager.py list
```

**输出示例**：
```
============================================================
                    已安装技能列表
============================================================

共 16 个技能:

  ✓ brainstorming
     You MUST use this before any creative work...

  ✓ systematic-debugging
     Use when encountering any bug, test failure...

  ! test-skill (无 SKILL.md)
```

---

### install - 安装技能

#### 语法

```bash
python bin/skill_manager.py install <source> [选项]
```

#### 输入源支持

| 输入类型 | 示例 | 说明 |
|:---|:---|:---|
| **GitHub URL** | `https://github.com/user/repo` | 自动克隆并安装 |
| **GitHub 简写** | `user/repo` | 自动克隆并安装 |
| **本地目录** | `path/to/skill` | 直接安装 |

#### 选项

| 选项 | 简写 | 说明 |
|:---|:---|:---|
| `--batch` | `-b` | 批量安装仓库中所有技能 |
| `--skill` | `-s` | 指定要安装的子技能名称（用于多技能仓库） |
| `--force` | `-f` | 强制覆盖已存在的技能 |

#### 示例

```bash
# 安装单技能仓库（自动安装）
python bin/skill_manager.py install https://github.com/user/single-skill

# 安装多技能仓库（自动批量安装所有子技能）
python bin/skill_manager.py install https://github.com/obra/superpowers
# → 找到 17 个技能，自动批量安装

# 只安装指定的子技能（覆盖自动判断）
python bin/skill_manager.py install obra/superpowers --skill brainstorming

# 强制覆盖已安装的技能
python bin/skill_manager.py install https://github.com/user/repo --force
```

#### 智能适配行为

系统会自动检测仓库结构并选择最佳处理方式：

| 检测结果 | 自动行为 | 手动覆盖 |
|:---|:---|:---|
| **1 个技能** | 自动安装该技能 | 无需覆盖 |
| **多个子技能** | 自动批量安装所有 | 使用 `--skill <name>` 只安装特定子技能 |

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
| 类别匹配 | 20 | category 字段匹配 |
| 多关键词协同 | +20 | 匹配多个关键词时的加成 |
| 使用频率加权 | +15 | 基于历史使用频率的加成 |

#### 示例

```bash
# 单关键词搜索
python bin/skill_manager.py search prompt

# 多关键词搜索（AND 逻辑）
python bin/skill_manager.py search prompt optimize --limit 5

# 显示匹配分数
python bin/skill_manager.py search git --score
```

---

### info - 分析远程技能仓库

#### 语法

```bash
python bin/skill_manager.py info <source>
```

#### 参数

| 参数 | 说明 |
|:---|:---|
| `source` | 仓库名或 URL |

#### 输入源支持

| 输入类型 | 示例 | 说明 |
|:---|:---|:---|
| **GitHub 简写** | `anthropics/skills` | user/repo 格式 |
| **GitHub URL** | `https://github.com/user/repo` | 完整 URL |

#### 功能说明

**快速扫描**远程 GitHub 仓库，获取技能信息，**无需克隆**：
- 📊 分析仓库结构
- 📋 列出所有技能及描述
- 🔗 生成建议安装链接（可直接复制到浏览器）

#### 输出示例

```
============================================================
                        技能仓库分析
============================================================

找到 17 个技能:

  1. mcp-builder
     分类: utilities
     描述: Guide for creating high-quality MCP servers...
     建议安装链接: https://github.com/anthropics/skills/tree/main/skills/mcp-builder

  2. doc-coauthoring
     分类: utilities
     描述: Guide users through structured documentation workflow
     建议安装链接: https://github.com/anthropics/skills/tree/main/skills/doc-coauthoring

============================================================
提示: 复制链接到浏览器查看，或使用命令安装
============================================================
```

#### 示例

```bash
# 快速查看仓库包含哪些技能
python bin/skill_manager.py info anthropics/skills

# 使用完整 URL
python bin/skill_manager.py info https://github.com/anthropics/skills
```

---

### uninstall - 卸载技能

#### 语法

```bash
python bin/skill_manager.py uninstall <name> [选项]
```

#### 参数

| 参数 | 说明 |
|:---|:---|
| `name` | 技能名称 |

#### 选项

| 选项 | 简写 | 说明 |
|:---|:---|:---|
| `--force` | `-f` | 强制删除，不询问确认 |

#### 示例

```bash
# 卸载技能
python bin/skill_manager.py uninstall my-skill

# 强制卸载
python bin/skill_manager.py uninstall my-skill --force
```

---

### formats - 列出支持的技能格式

#### 语法

```bash
python bin/skill_manager.py formats
```

#### 输出示例

```
============================================================
                    支持的技能格式
============================================================

共 4 种格式:

  official
     名称: Claude Code Official
     识别标记: SKILL.md
     状态: 内置处理

  claude-plugin
     名称: Claude Plugin
     识别标记: .claude-plugin, plugin.json, marketplace.json
     状态: 内置处理

  agent-skills
     名称: Anthropic Agent Skills
     识别标记: skills/, SKILL.md
     状态: 内置处理

  cursor-rules
     名称: Cursor Rules
     识别标记: .cursor, rules/
     状态: 内置处理

提示: 遇到不支持的格式？
查看贡献指南: docs/skill-formats-contribution-guide.md
```

---

### record - 记录技能使用

#### 语法

```bash
python bin/skill_manager.py record <name>
```

#### 参数

| 参数 | 说明 |
|:---|:---|
| `name` | 技能名称 |

#### 说明

用于记录技能使用频率，影响 `search` 命令的搜索排序。此命令通常由 `skills` 子智能体内部调用，无需手动执行。

---

## 支持的技能格式

### 1. Official Format (官方格式)

```
skill-name/
└── SKILL.md          # 标准 YAML frontmatter
```

**特征**：已有完整的 YAML frontmatter（name + description）

**处理方式**：直接复制，验证并修复格式问题

---

### 2. Claude Plugin Format

```
repo/
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
└── skills/
    └── skill-name/
        └── SKILL.md
```

**特征**：包含 `.claude-plugin` 目录和配置文件

**处理方式**：提取 SKILL.md，保留资源文件，生成标准 frontmatter

---

### 3. Agent Skills Format

```
skills/
└── skill-name/
    ├── SKILL.md
    ├── scripts/
    ├── references/
    └── examples/
```

**特征**：Anthropic Agent Skills 标准结构

**处理方式**：保留完整目录结构，验证格式

---

### 4. Cursor Rules Format

```
repo/
└── .cursor/
    └── rules/
        ├── rule1.md
        └── rule2.md
```

**特征**：Cursor 编辑器的 rules 目录

**处理方式**：合并所有 .md 文件，生成统一的 SKILL.md

---

### 5. Generic Format (通用格式)

```
skill-directory/
├── README.md         # 或其他 .md 文件
├── scripts/
└── resources/
```

**特征**：无法识别为上述任何格式

**处理方式**：从 README.md 或首个 .md 文件生成 SKILL.md

---

## 自动修复功能

Skill Converter 会自动修复以下常见问题：

### 问题 1：缺少 YAML frontmatter

```markdown
# 原始文件
# My Skill

This is my skill...
```

```markdown
# 修复后
---
name: my-skill
description: "从 My Skill 自动转换的技能，请手动完善描述"
---

# My Skill

This is my skill...
```

### 问题 2：技能名称不符合规范

```
原始: My_Skill-Name
修复: my-skill-name
```

### 问题 3：缺少描述

```
原始: description: ""
修复: description: "从 my-skill 自动转换的技能，请手动完善描述"
```

### 问题 4：name 与文件夹名不一致

```
检测到不一致并发出警告，但保留原值
```

---

## 工作流程

```
输入源
   │
   ├─→ GitHub URL ──→ 克隆仓库 ──┐
   │                              │
   ├─→ 本地目录 ──────────────────┤
   │                              │
   └─→ .skill 包 ──→ 解压 ────────┘
                │
                ▼
        格式检测
                │
                ▼
        技能提取 (批量)
                │
                ▼
        标准化转换
        ├─ 修复 frontmatter
        ├─ 规范化命名
        └─ 生成标准结构
                │
                ▼
        结构验证
                │
        ┌───────┴───────┐
        ▼               ▼
    安装到         输出到
  .claude/skills/   指定目录
        │
        ▼
    完成报告
```

---

## 使用场景

### 场景 1：转换单个技能

```bash
# 从 GitHub 转换单个技能
python bin/skill_manager.py convert \
  https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering
```

**输出**：
```
[10:30:15] [i] [INFO] 检测输入源: https://github.com/...
[10:30:15] [i] [INFO] 输入类型: github
[10:30:20] [OK] [OK] 克隆成功: mybox/temp/...
[10:30:21] [i] [INFO] 找到 1 个技能
[10:30:21] [i] [INFO] 检测到格式: agent-skills
[10:30:22] [OK] [OK] 转换完成: context-fundamentals
[10:30:23] [OK] [OK] 安装成功: context-fundamentals
[10:30:23] [i] [INFO] 清理临时文件
```

---

### 场景 2：批量转换技能包

```bash
# 转换 Context Engineering 全部 13 个技能
python bin/skill_manager.py convert \
  https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering \
  --batch
```

**输出报告**：
```
============================================================
                    转换完成
============================================================
输入源: https://github.com/.../Agent-Skills-for-Context-Engineering
处理技能数: 13
转换成功: 13
安装成功: 13

成功安装 (13):
  ✓ context-fundamentals
  ✓ context-degradation
  ✓ context-compression
  ✓ context-optimization
  ✓ multi-agent-patterns
  ✓ memory-systems
  ✓ tool-design
  ✓ filesystem-context
  ✓ hosted-agents
  ✓ evaluation
  ✓ advanced-evaluation
  ✓ project-development
  ✓ bdi-mental-states
```

---

### 场景 3：仅转换不安裝

```bash
# 转换到自定义目录，手动检查后再安装
python bin/skill_manager.py convert \
  https://github.com/user/repo \
  --no-install --output mybox/my_skills

# 检查转换结果
ls mybox/my_skills/

# 确认无误后手动复制
cp -r mybox/my_skills/skill-name .claude/skills/
```

---

### 场景 4：调试转换过程

```bash
# 保留临时文件，查看每一步的结果
python bin/skill_manager.py convert \
  https://github.com/user/repo \
  --keep-temp

# 检查转换中间结果
ls mybox/temp/converter_20260125_103015/
```

---

## 验证安装

转换完成后，验证技能是否可用：

```bash
# 1. 列出已安装技能
python bin/skill_manager.py list

# 2. 验证特定技能
python bin/skill_manager.py validate .claude/skills/context-fundamentals

# 3. 测试调用
/Skill context-fundamentals
```

---

## 故障排查

### 问题：克隆失败

```
[X] [ERROR] 克隆失败: fatal: unable to access...
```

**解决方案**：
```bash
# 方案 1：禁用 SSL 验证（临时）
git config --global http.sslVerify false

# 方案 2：使用代理
git config --global http.proxy http://127.0.0.1:7890

# 方案 3：手动克隆后转换本地目录
git clone https://github.com/user/repo mybox/temp/repo
python bin/skill_manager.py convert mybox/temp/repo --batch
```

---

### 问题：技能已存在

```
[-] [WARN] 跳过 (1):
  - context-fundamentals: 技能已存在: context-fundamentals（使用 --force 覆盖）
```

**解决方案**：
```bash
# 使用 --force 覆盖已存在的技能
python bin/skill_manager.py convert <input> --force
```

---

### 问题：验证失败

```
[X] [ERROR] 验证失败: 缺少必需字段: name
```

**解决方案**：
1. 检查 SKILL.md 是否有 YAML frontmatter
2. 确保 `---` 包裹 frontmatter
3. 检查 `name:` 和 `description:` 字段存在

---

### 问题：找不到技能目录

```
[X] [ERROR] 未找到技能目录
```

**解决方案**：
```bash
# 使用 --batch 查找所有技能
python bin/skill_manager.py convert <repo> --batch

# 或指定具体的技能子目录
python bin/skill_manager.py convert <repo>/skills/specific-skill
```

---

## 高级用法

### 自定义转换规则

如果需要自定义转换逻辑，可以编辑 `bin/skill_manager.py`：

```python
# 在 SkillNormalizer 类中添加自定义方法
@staticmethod
def convert_custom_format(source: Path, target: Path):
    """自定义格式转换"""
    # 你的转换逻辑
    pass
```

### 集成到工作流

```bash
# 一键转换并验证
python bin/skill_manager.py convert <input> --batch && \
python bin/skill_manager.py list
```

---

## 相关文档

- [技能安装指南](./skills-installation.md) - 手动安装技能的详细规则
- [推荐技能清单](./skills.md) - 经过验证的推荐技能列表
- [Vector Registry (算子注册表)](./commands.md) - 完整的工具命令参考

---

## 内部架构

### 核心设计理念

```
技能转换器 = 格式检测 + 标准化转换 + 自动安装
```

**目标**：将任意来源、任意格式的技能统一转换为官方 SKILL.md 格式，并安装到 `.claude/skills/` 运行时。

### 五大核心组件

| 组件 | 类名 | 职责 |
|:---|:---|:---|
| **格式检测器** | `FormatDetector` | 检测输入源类型和技能格式 |
| **标准化器** | `SkillNormalizer` | 转换为官方 SKILL.md 格式，验证 frontmatter |
| **安装器** | `SkillInstaller` | 安装到 `.claude/skills/`，结构验证 |
| **GitHub处理器** | `GitHubHandler` | 克隆仓库，提取技能目录 |
| **Skill Pack处理器** | `SkillPackHandler` | 解压 .skill 打包文件 |

### 数据流动

```
输入源 (GitHub/本地/.skill包)
         │
         ▼
┌─────────────────────────────────────┐
│  FormatDetector (格式检测)           │
│  - detect_input_type()               │
│  - detect_skill_format()             │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  SkillNormalizer (标准化转换)        │
│  - convert_to_official_format()      │
│  - fix_frontmatter()                 │
│  - normalize_skill_name()            │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  SkillInstaller (安装验证)           │
│  - install()                         │
│  - _validate_skill_structure()       │
│  - batch_install()                   │
└─────────────────────────────────────┘
         │
         ▼
.claude/skills/<skill-name>/ (运行时)
```

### 格式注册表 (Format Registry)

支持的格式在 `SUPPORTED_FORMATS` 字典中注册：

```python
SUPPORTED_FORMATS = {
    "official": {
        "name": "Claude Code Official",
        "markers": ["SKILL.md"],
        "handler": None,  # 官方格式直接处理
    },
    "claude-plugin": {
        "name": "Claude Plugin",
        "markers": [".claude-plugin", "plugin.json"],
        "handler": None,  # 内置处理
    },
    "agent-skills": {
        "name": "Anthropic Agent Skills",
        "markers": ["skills/", "SKILL.md"],
        "handler": None,
    },
    "cursor-rules": {
        "name": "Cursor Rules",
        "markers": [".cursor", "rules/"],
        "handler": None,
    },
}
```

**扩展新格式**：在此字典中添加新格式的标记文件和处理器类。

### 验证规则

| 字段 | 规则 |
|:---|:---|
| **name** | hyphen-case，小写字母+数字+连字符，不以连字符开头/结尾，最多64字符 |
| **description** | 非空，不超过1024字符，不含尖括号 `<>` |
| **SKILL.md** | 必需文件，包含 YAML frontmatter |

### 临时文件管理

```
mybox/temp/
├── converter_<timestamp>/     # 转换器临时文件
│   ├── repo/                  # GitHub 克隆目录
│   └── extracted/             # .skill 包解压目录
└── installer_<timestamp>/     # 安装器临时文件
    ├── repo/
    ├── processed/             # 转换后的技能
    └── extracted/
```

**自动清理**：默认在完成后删除，使用 `--keep-temp` 保留用于调试。

---

## 技术细节

### 格式检测逻辑

```
1. 检查 SKILL.md + YAML frontmatter → Official
2. 检查 .claude-plugin/ → Claude Plugin
3. 检查 skills/ + SKILL.md → Agent Skills
4. 检查 .cursor/rules/ → Cursor Rules
5. 检查 *.md 文件 → Generic (Unknown)
```

### 命名规范化规则

```python
# 原始名称 → 规范化名称
"My_Skill-Name" → "my-skill-name"
"123Skill" → "skill-123"
"Skill!!Test" → "skill-test"
```

### Frontmatter 修复优先级

1. 如果缺少 `name`：使用文件夹名（规范化后）
2. 如果缺少 `description`：从内容提取或使用默认值
3. 如果 `name` 不符合规范：自动规范化
4. 如果 `description` 过长或含非法字符：截断或替换

---

**更新记录**:

| 日期 | 版本 | 变更 |
|:---|:---|:---|
| 2026-01-28 | v1.4 | 新增 info 命令文档 |
| 2026-01-28 | v1.3 | 补充 search/uninstall/formats/record 命令；修复格式错乱；更新标题为 Skill Manager |
| 2026-01-26 | v1.2 | 新增"内部架构"章节，补充五大核心组件、数据流动、格式注册表等技术细节 |
| 2026-01-25 | v1.1 | 新增 install 命令文档 |
| 2026-01-24 | v1.0 | 初始版本，完整的技能转换工具使用指南 |

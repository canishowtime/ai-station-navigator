# Skill Creator 使用指南

**版本**: v1.0
**最后更新**: 2026-01-26
**维护者**: AIOS 项目组

---

## 概述

**Skill Creator** 是自定义技能创建工具（Creator Agent），负责从零开始创建、验证和打包技能。

**核心功能**：
- ✅ **初始化** - 生成标准技能模板（SKILL.md + scripts/references/assets）
- ✅ **验证** - 检查技能结构合规性
- ✅ **打包** - 打包为 .skill 分发包

**与 Converter 的区别**：

| 特性 | Creator (创建者) | Converter (转换器) |
|:---|:---|:---|
| **用途** | 从零创建新技能 | 转换已有技能格式 |
| **输入** | 技能名称 | GitHub/本地/.skill包 |
| **输出** | 技能模板目录 | .claude/skills/ |
| **典型场景** | 开发自定义技能 | 安装第三方技能 |

---

## 快速开始

### 创建第一个技能

```bash
# 1. 初始化技能模板
python bin/skill_creator.py init my-first-skill

# 2. 编辑技能定义
# 编辑 skills/custom/my-first-skill/SKILL.md

# 3. 验证结构
python bin/skill_creator.py validate skills/custom/my-first-skill

# 4. 打包分享
python bin/skill_creator.py package skills/custom/my-first-skill
```

---

## 命令详解

### init - 初始化新技能

#### 语法

```bash
python bin/skill_creator.py init <skill-name> [--output-dir <path>]
```

#### 参数

| 参数 | 说明 |
|:---|:---|
| `skill-name` | 技能名称（必需，使用 hyphen-case） |
| `--output-dir`, `-o` | 输出目录（可选，默认: `skills/custom/`） |

#### 命名规范

```
✅ 正确示例:
  - my-skill
  - code-reviewer
  - test-helper
  - api-client

❌ 错误示例:
  - MySkill      (首字母大写)
  - my_skill     (使用下划线)
  - my-skill-    (以连字符结尾)
  - -my-skill    (以连字符开头)
  - 123skill     (以数字开头)
```

#### 生成的目录结构

```
my-skill/
├── SKILL.md          # 技能定义（必需）
├── scripts/          # 可执行脚本（可选）
├── references/       # 参考资料（可选）
├── templates/        # 模板文件（可选）
└── examples.md       # 使用示例（可选）
```

#### 示例

```bash
# 使用默认目录创建
python bin/skill_creator.py init code-reviewer

# 创建到指定目录
python bin/skill_creator.py init api-client --output-dir ./my-skills

# 验证创建结果
ls skills/custom/code-reviewer/
```

---

### validate - 验证技能结构

#### 语法

```bash
python bin/skill_creator.py validate <skill-path>
```

#### 验证项目

| 检查项 | 说明 |
|:---|:---|
| **SKILL.md 存在** | 技能目录必须包含 SKILL.md |
| **YAML frontmatter** | 必须包含 `---` 包裹的 YAML 头部 |
| **name 字段** | 必需，符合 hyphen-case 规范 |
| **description 字段** | 必需，非空字符串 |
| **目录结构** | 可选目录（scripts/references 等）正确创建 |

#### 验证输出示例

```
✓ 技能验证通过
  技能名称: code-reviewer
  技能路径: skills/custom/code-reviewer

  详细信息:
    name: code-reviewer
    description: "Code review assistant for pull requests"
```

#### 示例

```bash
# 验证技能
python bin/skill_creator.py validate skills/custom/code-reviewer

# 验证通过后，可以安装到运行时
python bin/skill_manager.py install skills/custom/code-reviewer
```

---

### package - 打包技能

#### 语法

```bash
python bin/skill_creator.py package <skill-path> [--output-dir <path>]
```

#### 参数

| 参数 | 说明 |
|:---|:---|
| `skill-path` | 技能目录路径（必需） |
| `--output-dir`, `-o` | 输出目录（可选，默认: 当前目录） |

#### 输出

打包后生成 `<skill-name>.skill` 文件（ZIP 格式），可用于：
- 分享给他人
- 备份技能
- 通过 converter 安装

#### 示例

```bash
# 打包到当前目录
python bin/skill_creator.py package skills/custom/code-reviewer
# 生成: code-reviewer.skill

# 打包到指定目录
python bin/skill_creator.py package skills/custom/code-reviewer --output-dir ./dist
# 生成: dist/code-reviewer.skill
```

---

## 完整工作流

### 场景 1：创建并安装技能

```bash
# 1. 初始化
python bin/skill_creator.py init docker-helper

# 2. 编辑 SKILL.md
vim skills/custom/docker-helper/SKILL.md

# 3. 添加脚本（可选）
vim skills/custom/docker-helper/scripts/build.sh

# 4. 验证
python bin/skill_creator.py validate skills/custom/docker-helper

# 5. 安装到运行时
python bin/skill_manager.py install skills/custom/docker-helper

# 6. 测试调用
/Skill docker-helper
```

### 场景 2：创建可分享的技能包

```bash
# 1. 创建技能
python bin/skill_creator.py init python-formatter

# 2. 完善内容
# - 编辑 SKILL.md
# - 添加 scripts/ 格式化脚本
# - 添加 references/ 文档链接
# - 编写 examples.md

# 3. 验证
python bin/skill_creator.py validate skills/custom/python-formatter

# 4. 打包
python bin/skill_creator.py package skills/custom/python-formatter --output-dir ./dist

# 5. 分享（上传到 GitHub、发送给他人等）
# dist/python-formatter.skill
```

### 场景 3：使用 Agent Protocol 调用

```python
from agent_protocol import AgentRegistry

# 创建 Creator Agent
agent = AgentRegistry.create("creator")

# 初始化技能
result = agent.run({
    "action": "init",
    "skill_name": "my-skill"
})

if result.is_success():
    print(f"创建成功: {result.data['skill_path']}")

    # 验证技能
    result = agent.run({
        "action": "validate",
        "skill_path": result.data['skill_path']
    })
```

---

## SKILL.md 模板

### 标准模板结构

```markdown
---
name: my-skill
description: "简短描述技能的功能（最多 1024 字符）"
---

# My Skill

## Overview

详细说明技能的用途、适用场景...

## When to Use

- 场景 1
- 场景 2

## Usage

```
用户使用此技能的具体步骤...
```

## Examples

### Example 1: 标题

```
输入/输出示例...
```

## Resources

- [相关文档](链接)
- [API 参考](链接)
```

### YAML Frontmatter 规范

| 字段 | 必需 | 规范 |
|:---|:---:|:---|
| **name** | ✅ | hyphen-case，小写字母+数字+连字符，最多 64 字符 |
| **description** | ✅ | 非空，不超过 1024 字符，不含尖括号 `<>` |

### 示例

```yaml
---
name: code-reviewer
description: "Automated code review assistant for pull requests, checking code quality, security issues, and best practices."
---
```

---

## 目录结构详解

### 完整结构

```
skill-name/
├── SKILL.md              # 必需：技能定义
├── scripts/              # 可选：可执行脚本
│   ├── script.py         #   Python 脚本
│   ├── script.sh         #   Shell 脚本
│   └── ...
├── references/           # 可选：参考资料
│   ├── doc.md            #   文档
│   ├── api-spec.md       #   API 规范
│   └── ...
├── templates/            # 可选：模板文件
│   ├── template.txt      #   文本模板
│   └── ...
└── examples.md           # 可选：使用示例
```

### scripts/ 目录

用于存放与技能相关的可执行脚本：

```bash
scripts/
├── validate.py           # 验证脚本
├── format.sh             # 格式化脚本
└── helper.py             # 辅助函数
```

**注意**：脚本独立运行，不依赖技能系统。

### references/ 目录

存放技能相关的参考文档：

```bash
references/
├── api-reference.md      # API 文档
├── best-practices.md     # 最佳实践
└── troubleshooting.md    # 故障排查
```

### templates/ 目录

存放可复用的模板文件：

```bash
templates/
├── commit-message.txt    # 提交消息模板
├── pr-template.md        # PR 模板
└── config.yaml           # 配置模板
```

---

## 内部架构

### Creator Agent 结构

```
CreatorAgent (继承 BaseAgent)
    │
    ├─→ validate_input()      # 输入验证
    ├─→ execute()             # 执行操作
    │   ├─→ _init_skill()     #   初始化技能
    │   ├─→ _validate_skill() #   验证技能
    │   └─→ _package_skill()  #   打包技能
    ├─→ rollback()            # 回滚（删除已创建的目录）
    └─→ cleanup()             # 清理资源
```

### 底层脚本调用

Creator Agent 封装了 `lib/skill-creator/scripts/` 中的底层脚本：

```
CreatorAgent
    │
    ├─→ init_skill.py       # 生成技能模板
    ├─→ quick_validate.py   # 快速验证
    └─→ package_skill.py    # 打包技能
```

### Agent Protocol 集成

```python
@register_agent("creator")
class CreatorAgent(BaseAgent):
    """已适配 Agent Protocol 的创建者"""

    def validate_input(self, input_data):
        """验证输入参数"""

    def execute(self, input_data):
        """执行操作，返回 AgentResult"""

    def rollback(self, input_data):
        """失败时回滚（删除已创建的目录）"""
```

### 输入/输出格式

**输入格式**：
```python
{
    "action": "init|validate|package",
    "skill_name": "my-skill",        # init 时必需
    "skill_path": "./skills/custom/my-skill",
    "output_dir": "./dist"
}
```

**输出格式**：
```python
AgentResult(
    status=AgentStatus.SUCCESS,
    message="技能初始化成功: my-skill",
    data={
        "skill_name": "my-skill",
        "skill_path": "/path/to/skill",
        "next_steps": [...]
    }
)
```

---

## 故障排查

### 问题：技能名称不符合规范

```
[X] [ERROR] 技能名称无效: 技能名称必须是小写字母、数字和连字符...
```

**解决方案**：
```bash
# 使用正确的命名
python bin/skill_creator.py init my-skill         # ✅
python bin/skill_creator.py init MySkill         # ❌
python bin/skill_creator.py init my_skill        # ❌
```

### 问题：验证失败

```
[X] [ERROR] 验证失败: SKILL.md 不存在
```

**解决方案**：
```bash
# 1. 检查目录结构
ls skills/custom/my-skill/

# 2. 确保 SKILL.md 存在
ls skills/custom/my-skill/SKILL.md

# 3. 检查 YAML frontmatter 格式
head -10 skills/custom/my-skill/SKILL.md
```

### 问题：打包失败

```
[X] [ERROR] 技能打包失败
```

**解决方案**：
```bash
# 1. 先验证技能
python bin/skill_creator.py validate skills/custom/my-skill

# 2. 确保目录路径正确
pwd
ls skills/custom/my-skill

# 3. 检查输出目录权限
mkdir -p ./dist
```

### 问题：回滚后目录未删除

```bash
# 手动清理
rm -rf skills/custom/my-skill
```

---

## 最佳实践

### 1. 技能命名

```
✅ 推荐:
  - code-reviewer       (清晰的动词-名词组合)
  - docker-helper       (描述性强)
  - python-formatter    (指定语言/工具)

❌ 避免:
  - helper              (过于泛泛)
  - my-skill-v2         (版本号应放在描述中)
  - skill1              (无意义的名称)
```

### 2. 描述编写

```yaml
---
name: code-reviewer
description: "Automated code review assistant for Python projects, checking PEP 8 compliance, security issues, and documentation coverage"
---
```

**要素**：
- 说明功能
- 指定目标（Python 项目）
- 列出检查项

### 3. 文档组织

```markdown
## Overview          # 简要说明
## When to Use       # 适用场景
## Usage             # 使用方法
## Examples          # 具体示例
## Resources         # 相关链接
```

### 4. 脚本管理

```bash
scripts/
├── validate.py       # 主入口
├── utils.py          # 辅助函数
└── README.md         # 脚本说明
```

**原则**：
- 脚本独立可运行
- 添加文档说明
- 处理错误情况

---

## 与其他工具的配合

### 技能创建流程

```
1. skill_creator.py init    → 创建模板
2. 编辑 SKILL.md             → 定义技能
3. skill_creator.py validate → 验证结构
4. skill_manager.py install → 安装到运行时
5. /Skill <name>             → 测试调用
```

### 技能分享流程

```
1. skill_creator.py package  → 打包为 .skill
2. 上传到 GitHub              → 发布
3. 其他人使用 converter 安装 → 安装
```

### 与 Agent Protocol 集成

```python
from agent_protocol import AgentRegistry

# 创建技能
creator = AgentRegistry.create("creator")
result = creator.run({"action": "init", "skill_name": "my-skill"})

# 安装技能
builder = AgentRegistry.create("builder")
result = builder.run({"url": "path/to/my-skill"})
```

---

## 相关文档

- [Skill Converter 使用指南](./skill-manager-guide.md) - 技能转换与安装
- [技能安装指南](./skills-installation.md) - 手动安装技能的规则
- [Vector Registry](./commands.md) - 完整的工具命令参考
- [Agent Protocol](./agent-protocol.md) - Agent 系统架构

---

**更新记录**:

| 日期 | 版本 | 变更 |
|:---|:---|:---|
| 2026-01-26 | v1.0 | 初始版本，完整的技能创建工具使用指南 |

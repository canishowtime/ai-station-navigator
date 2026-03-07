# 工作流设计规范

**版本**: v1.2.0 (精简版)
**更新**: 2026-02-20
**来源**: AI Station Navigator 自研设计

---

## 快速开始

```bash
# 1. 复制模版
cp .template.md 新工作流.md

# 2. 编辑必填字段
name: 工作流名称
version: 1.0.0
description: 功能描述
depends_on:
  - skill-name

# 3. 编写工作流指令
```

---

## 完整配置说明

### 必填字段

| 字段 | 说明 | 示例 |
|------|------|------|
| `name` | 工作流名称 | `深度分析` |
| `version` | 版本号 | `1.0.0` |
| `description` | 功能描述 | `法务级事实核查...` |
| `depends_on` | 依赖技能 | `['truth-miner']` |

### 推荐字段

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `tags` | 分类标签 | `[]` |
| `sandbox` | 安全配置 | 见下方 |
| `output.location` | 输出位置 | `inline` |

---

## 安全配置

### 基础安全（推荐）

```yaml
sandbox:
  file_access:
    read: [mybox/**, docs/**, .claude/**]
    write: [mybox/workspace/**, mybox/temp/**]
    forbidden: [*.exe, *.dll, system32/**]
  network: false
```

### 高级安全（敏感工作流）

```yaml
sandbox:
  file_access:
    read: [docs/**, .claude/**]
    write: [mybox/temp/**]
    forbidden: [**]
  network: false
```

---

## 输出配置

```yaml
output:
  location: inline        # inline | file | both
  format: markdown        # markdown | json | text
  file_path: mybox/workspace/{name}/{date}.md
```

**路径变量**：
- `{name}` - 工作流名称
- `{date}` - 当前日期 (YYYY-MM-DD)
- `{timestamp}` - 时间戳

---

## 工作流文档结构

### 必需章节

| 章节 | 说明 |
|------|------|
| 功能/工作流链路/使用方式 | 开头三要素 |
| 使用场景 | 适用范围 |
| 工作流详解 | 分阶段说明 |
| 输出位置 | 文件组织 |
| 注意事项 | 执行约束 |

### 推荐结构

```markdown
# 标题
**功能**：xxx
**工作流链路**：`技能1 → 技能2 → 输出`

## 使用场景
- 场景1

## 工作流详解
### 阶段 1
**功能**：xxx
**执行**：@技能名
**输入/输出**：xxx
**示例**：xxx

### 阶段 N
...

## 输出位置
...

## 注意事项
...
```

---

## 验证工作流

```bash
# 验证配置
python bin/workflow_validator.py validate mazilin_workflows/工作流.md

# 检查依赖
python bin/workflow_validator.py check-deps mazilin_workflows/工作流.md

# 安全扫描
python bin/workflow_validator.py scan mazilin_workflows/
```

---

## 最佳实践

1. **工作流链路可视化** - `技能1 → 技能2 → 输出`
2. **使用场景列举** - 明确适用范围
3. **分阶段详解** - 每个阶段功能、输入、输出、示例
4. **输出格式规范** - 定义摘要结构
5. **注意事项明确** - 串行执行、路径引用、失败停止

---

## 目录结构

```
mazilin_workflows/
├── .template.md              # 精简模版 (v1.2.0)
├── README.md                  # 本说明文档
├── shared/                    # 共享组件
├── 深度分析.md               # 示例
└── 代码审查.md
```

---

## 设计理念

### MD DSL
用 Markdown 作为领域特定语言描述工作流

### Frontmatter 分离
- 配置层（YAML）- 需验证
- 指令层（Markdown）- 热更新

### 安全机制
- 沙盒隔离
- 编译验证
- 权限最小化

---

## 相关文档

- [SKILL.md 规范](../.claude/skills/)
- [Kernel 逻辑](../CLAUDE.md)

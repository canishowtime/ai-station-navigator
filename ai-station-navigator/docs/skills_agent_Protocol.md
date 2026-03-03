# Skills Agent 调度协议 v3.0

> **定位**: Kernel ↔ Skills Agent 的通信契约
> **原则**: 结构化派发 + 统一返回 + 明确错误处理

---

## 1. 调用规范 (Dispatch Protocol)

### 1.1 执行模式说明 [P0]
**同步执行架构**：Skills Agent 采用同步执行模式，任务结果直接在 `Task` 返回值中获取。

```yaml
# ✅ 正确：直接处理 Task 返回值
result = Task("skills_agent", "执行技能", "执行 @@markdown-converter README.md")
# → 结果已在 result 中，无需后续检索

# ❌ 错误：尝试用 TaskOutput 检索
TaskOutput(task_id=xxx)  # → 同步任务无 task_id，会报错
```

### 1.2 Task 工具签名
```
Task(
  "skills_agent",
  "<3-5词任务摘要>",
  "使用 Skill 工具调用 @@<技能名> [参数]"
)
```

**核心约束**: 智能体通过 Skill 工具触发用户需求的技能

### 1.2 Prompt 构建规则
```yaml
# 标准格式
执行 @@<技能名> [参数...]

# 示例
执行 @@markdown-converter README.md
执行 @@image-resizer photo.jpg --width 800
执行 @@code-analyzer src/ --language python
```

### 1.3 派发前检查 [MUST]
- [ ] 技能已安装（未安装则引导安装）
- [ ] 必要参数已提供（缺失则询问用户）
- [ ] 非多步任务（多步任务由 Kernel 设计工作流）

### 1.4 参数完整性强制检查 [P0-FORCE]

**执行前必须检查技能的 `required_params` 配置，缺失参数则禁止执行。**

#### 检查流程

```
1. 读取 SKILL.md frontmatter 中的 required_params
    ↓
2. 解析用户输入，提取已提供参数
    ↓
3. 对比 required_params 列表，识别缺失参数
    ↓
4. 缺失参数 → 先询问用户，禁止跳过
    ↓
5. 验证通过 → 继续执行技能
```

#### required_params 结构

```yaml
required_params:
  - name: github_url
    prompt: 目标项目的 GitHub URL
    validation: url_format
    required: true
  - name: requirements
    prompt: |
      ## 需求收集模板
      1. ...
    validation: not_empty
    required: true
```

#### 验证规则

| validation | 含义 | 检查方式 |
|:-----------|:-----|:---------|
| `url_format` | URL 格式 | 以 http:// 或 https:// 开头 |
| `not_empty` | 非空 | 内容长度 > 0 |
| `email` | 邮箱格式 | 包含 @ 符号 |
| `file_exists` | 文件存在 | 路径指向有效文件 |

#### 中断行为

当检测到 `required: true` 的参数缺失时：

```yaml
# 返回 pending 状态
⏸️ skills_agent 等待参数: 需要 <param_name>
  state: pending
  data: {
    required: ["github_url", "requirements"],
    missing: ["requirements"],
    prompt: "<SKILL.md 中定义的 prompt 内容>"
  }
  meta: {agent: skills_agent, time: 0.1, ts: "2025-02-19T10:00:00Z"}
```

#### 执行保障

- **禁止跳过**: `interrupt_on_missing: true` 时必须中断询问
- **禁止猜测**: 不得自动填充或假定用户意图
- **完整传递**: 将 SKILL.md 中定义的 `prompt` 完整展示给用户

---

## 2. 返回规范 (Return Protocol)

### 2.1 标准格式
```
<status> skills_agent <summary>
  state: <code> | data: {...} | meta: {...}
```

### 2.2 状态码定义
| 状态 | 图标 | 含义 | 使用场景 |
|:---|:---|:---|:---|
| `success` | ✅ | 完全成功 | 技能执行完成 |
| `pending` | ⏸️ | 等待参数 | 需要用户提供更多信息 |
| `error` | ❌ | 执行失败 | 可恢复或不可恢复的错误 |
| `timeout` | ⏱️ | 超时 | 执行超过90秒 |

### 2.3 内容透传规则 [P0]
Skills Agent 返回包含以下字段时，Kernel **必须**主动输出：

| 字段类型 | 触发字段 | 直接输出 | 文件输出 |
|:---|:---|:---:|:---:|
| 文本 | `content`/`text`/`article` | ≤2000字 | >2000字 → mybox/ |
| 代码 | `code`/`script` | ≤100行 | >100行 → mybox/ |
| 分析结果 | `analysis`/`report` | ✅ 总是输出 | - |

### 2.4 标准返回示例

```yaml
# 成功
✅ skills_agent 执行成功: Markdown转换 → mybox/workspace/result.html
  state: success
  data: {skill: "markdown-converter", output_path: "mybox/workspace/result.html", output_size: "12.5KB"}
  meta: {agent: skills_agent, time: 1.8, ts: "2025-01-29T10:30:00Z"}

# 等待参数
⏸️ skills_agent 等待参数: 需要 input_file
  state: pending
  data: {required: ["input_file"], optional: ["format", "quality"]}
  meta: {agent: skills_agent, time: 0.1, ts: "2025-01-29T10:30:00Z"}

# 错误
❌ skills_agent ParamMissing: 参数不足: 需要 input_file
  state: error
  data: {type: "ParamMissing", msg: "Required parameter 'input_file' not provided", recoverable: true}
  meta: {agent: skills_agent, time: 0.2, ts: "2025-01-29T10:30:00Z"}

# 超时
⏱️ skills_agent Timeout: 执行超时 (>90秒)
  state: timeout
  data: {skill: "large-processor", elapsed: 90, limit: 90}
  meta: {agent: skills_agent, time: 90, ts: "2025-01-29T10:30:00Z"}
```

---

## 3. 错误类型映射

| 错误类型 | 摘要格式 | recoverable | 处理建议 |
|:---|:---|:---:|:---|
| `SkillNotFound` | 未安装技能: `<name>` | true | 引导用户安装 |
| `MetadataMissing` | SKILL.md 损坏或缺失 | false | 重新安装技能 |
| `ParamMissing` | 参数不足: 需要 `<param>` | true | 询问用户提供 |
| `RuntimeFailed` | 执行失败: `<stderr片段>` | null | 视具体错误判断 |
| `Timeout` | 执行超时 (>90秒) | true | 建议拆分任务 |

---

## 4. 技能类型定义

| 类型 | 检测方式 | 行为 | 返回格式 |
|:---|:---|:---|:---|
| **Type A** | SKILL.md 有 `command` | 执行 Shell/Python 命令 | 标准返回 |
| **Type B** | SKILL.md 无 `command` | 返回提示词内容供 Kernel 使用 | Prompt返回 |

### Type B (提示词技能) 返回格式
```yaml
✅ skills_agent 提示词加载: marketing-ideas
  state: success
  data: {
    skill: "marketing-ideas",
    type: "prompt",
    name: "Marketing Ideas Generator",
    description: "提供营销策略建议",
    content: "<SKILL.md完整内容>",
    executable: false
  }
  meta: {agent: skills_agent, time: 0.1, ts: "2025-01-30T10:00:00Z"}
```



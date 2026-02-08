# Skills Agent 调度协议 v3.0

> **定位**: Kernel ↔ Skills Agent 的通信契约
> **原则**: 结构化派发 + 统一返回 + 明确错误处理

---

## 1. 调用规范 (Dispatch Protocol)

### 1.1 Task 工具签名
```
Task(
  "skills",                    // 固定子智能体类型
  "<3-5词任务摘要>",            // description: 任务简述
  "执行 @<技能名> [参数]",       // prompt: 自然语言指令
  { model?: "sonnet" | "opus" | "haiku" }  // 可选模型
)
```

### 1.2 Prompt 构建规则
```yaml
# 标准格式
执行 @<技能名> [参数...]

# 示例
执行 @markdown-converter README.md
执行 @image-resizer photo.jpg --width 800
执行 @code-analyzer src/ --language python
```

### 1.3 派发前检查 [MUST]
- [ ] 技能已安装（未安装则引导安装）
- [ ] 必要参数已提供（缺失则询问用户）
- [ ] 非多步任务（多步任务由 Kernel 设计工作流）

---

## 2. 返回规范 (Return Protocol)

### 2.1 标准格式
```
<status> skills <summary>
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
✅ skills 执行成功: Markdown转换 → mybox/workspace/result.html
  state: success
  data: {skill: "markdown-converter", output_path: "mybox/workspace/result.html", output_size: "12.5KB"}
  meta: {agent: skills, time: 1.8, ts: "2025-01-29T10:30:00Z"}

# 等待参数
⏸️ skills 等待参数: 需要 input_file
  state: pending
  data: {required: ["input_file"], optional: ["format", "quality"]}
  meta: {agent: skills, time: 0.1, ts: "2025-01-29T10:30:00Z"}

# 错误
❌ skills ParamMissing: 参数不足: 需要 input_file
  state: error
  data: {type: "ParamMissing", msg: "Required parameter 'input_file' not provided", recoverable: true}
  meta: {agent: skills, time: 0.2, ts: "2025-01-29T10:30:00Z"}

# 超时
⏱️ skills Timeout: 执行超时 (>90秒)
  state: timeout
  data: {skill: "large-processor", elapsed: 90, limit: 90}
  meta: {agent: skills, time: 90, ts: "2025-01-29T10:30:00Z"}
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
✅ skills 提示词加载: marketing-ideas
  state: success
  data: {
    skill: "marketing-ideas",
    type: "prompt",
    name: "Marketing Ideas Generator",
    description: "提供营销策略建议",
    content: "<SKILL.md完整内容>",
    executable: false
  }
  meta: {agent: skills, time: 0.1, ts: "2025-01-30T10:00:00Z"}
```

---

## 5. 与其他 Agent 对比

| Agent | 配置文件 | 职责 | 专属特性 |
|:---|:---|:---|:---|
| **worker** | `.claude/agents/worker_agent.md` | 执行 `bin/` 脚本 | 幂等性 (5s缓存) |
| **skills** | `.claude/agents/skills_agent.md` | 执行已安装技能 | 超时 (90s限制) |

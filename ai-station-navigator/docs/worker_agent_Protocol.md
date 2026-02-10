# Worker Agent 调度协议 v3.0

> **定位**: Kernel ↔ Worker Agent 的通信契约
> **原则**: 幂等调用 + 统一返回 + 防重复执行

---

## 1. 调用规范 (Dispatch Protocol)

### 1.1 执行模式说明 [P0]
**同步执行架构**：Worker Agent 采用同步执行模式，任务结果直接在 `Task` 返回值中获取。

```yaml
# ✅ 正确：直接处理 Task 返回值
result = Task("worker_agent", "列出技能", "执行 python bin/skill_manager.py list")
# → 结果已在 result 中，无需后续检索

# ❌ 错误：尝试用 TaskOutput 检索
TaskOutput(task_id=xxx)  # → 同步任务无 task_id，会报错
```

### 1.2 Task 工具签名
```
Task(
  "worker_agent",              // 固定子智能体类型
  "<3-5词任务摘要>",            // description: 任务简述
  "执行 python bin/<脚本> [参数]", // prompt: 完整执行指令
  {
    idempotency_key?: string   // 幂等键: 相同键5s内仅执行一次
  }
)
```

### 1.3 幂等性保证 [P0-LOCK]
```yaml
# 防重复执行规则
缓存时间: 5秒
去重键: idempotency_key (字符串)
行为: 相同键5s内直接返回缓存结果

# 推荐的 key 命名
- "skill-list"         # 列出技能
- "skill-search:<kw>"  # 搜索技能
- "scan-skills"        # 扫描技能
```

### 1.3 Prompt 构建规则
```yaml
# 标准格式
执行 python bin/<脚本名> [参数...]

# 示例
执行 python bin/skill_manager.py list
执行 python bin/skill_manager.py search markdown
执行 python bin/skill_scanner.py scan
```

### 1.4 派发前检查 [MUST]
- [ ] 脚本文件存在于 `bin/` 目录
- [ ] 操作参数完整（缺失则询问用户）
- [ ] 非代码创建任务（禁止创建 Python 脚本）
- [ ] Git Bash 规范检查（禁用 `> nul`，使用 `> /dev/null`）

---

## 2. 返回规范 (Return Protocol)

### 2.1 标准格式
```
<status> worker_agent <summary>
  state: <code> | data: {...} | meta: {...}
```

### 2.2 状态码定义
| 状态 | 图标 | 含义 | 使用场景 |
|:---|:---|:---|:---|
| `success` | ✅ | 完全成功 | 脚本执行完成 |
| `success` | ⏭️ | 缓存命中 | 5s内重复调用（幂等） |
| `partial` | ⚠️ | 部分成功 | 部分任务完成 |
| `error` | ❌ | 执行失败 | 可恢复或不可恢复的错误 |

### 2.3 标准返回示例

```yaml
# 成功
✅ worker_agent 扫描完成: 新增 2 个, 更新 3 个
  state: success
  data: {added: ["skill_a","skill_b"], updated: ["skill_c","skill_d","skill_e"], total: 5}
  meta: {agent: worker_agent, time: 0.5, ts: "2025-01-29T10:30:00Z"}

# 缓存命中（幂等）
⏭️ worker_agent 缓存命中: 使用最近结果 (<5s)
  state: success
  data: {cached: true, original_result: {total: 5, skills: [...]}}
  meta: {agent: worker_agent, time: 0.01, ts: "2025-01-29T10:30:05Z"}

# 部分成功
⚠️ worker_agent 部分完成: 3/5 个脚本执行成功
  state: partial
  data: {succeeded: ["a.py","b.py","c.py"], failed: ["d.py","e.py"]}
  meta: {agent: worker_agent, time: 1.2, ts: "2025-01-29T10:30:00Z"}

# 错误
❌ worker_agent RuntimeError: 脚本执行失败
  state: error
  data: {type: "FileNotFoundError", msg: "bin/script.py not found"}
  meta: {agent: worker_agent, time: 0.1, ts: "2025-01-29T10:30:00Z"}
```

---

## 3. 错误类型映射

| 错误类型 | 摘要格式 | recoverable | 处理建议 |
|:---|:---|:---:|:---|
| `ScriptNotFound` | 脚本不存在: `<script>` | false | 检查脚本路径 |
| `InvalidArgs` | 参数错误: `<reason>` | true | 显示脚本Help |
| `RuntimeError` | 执行失败: `<stderr片段>` | null | 视具体错误判断 |
| `PermissionDenied` | 权限不足 | false | 检查文件权限 |

---

## 4. 特殊返回字段

### 4.1 LangGraph Interrupt 补漏机制 [FALLBACK]

**触发条件**：Worker 返回 `state: interrupted` 时

**主会话处理流程**：
```yaml
1. 检测 "[INTERRUPT]" 标记
2. 读取 langgraph_interrupt.json
3. LLM 分析 → {"skill": "keep/uninstall"}
4. 执行恢复命令
```

**Worker 返回格式**（未处理）：
```yaml
⏸️ worker_agent 工作流已暂停: <N> 个技能需 LLM 分析
  state: interrupted
  data: {interrupted_skills: [...], resume_command: "..."}
```

**注**：Worker 应优先自主处理（见 `.claude/agents/worker_agent.md`），主会话仅作补漏。

### 4.2 analysis_prompt 字段
当输出包含 `【LLM 二次分析任务】` 时：
```yaml
data:
  analysis_prompt: "<需要LLM二次分析的内容>"
```

### 4.3 与其他 Agent 对比

| Agent | 职责 | 专属特性 |
|:---|:---|:---|
| **worker_agent** | 执行 `bin/` 脚本 | 幂等性 + Interrupt 自主处理 |
| **skills** | 执行已安装技能 | 超时限制 |

# Worker Agent Dispatch Protocol v3.0

> **Positioning**: Kernel ↔ Worker Agent Communication Contract
> **Principle**: Idempotent Call + Unified Return + Prevent Duplicate Execution

---

## 1. Dispatch Protocol

### 1.1 Execution Mode Description [P0]
**Synchronous Execution Architecture**: Worker Agent uses synchronous execution mode, task results obtained directly in `Task` return value.

```yaml
# ✅ Correct: Process Task return value directly
result = Task("worker_agent", "List skills", "Execute python bin/skill_manager.py list")
# → Result already in result, no subsequent retrieval needed

# ❌ Wrong: Attempt to retrieve with TaskOutput
TaskOutput(task_id=xxx)  # → Sync task has no task_id, will error
```

### 1.2 Task Tool Signature
```
Task(
  "worker_agent",              // Fixed sub-agent type
  "<3-5 word task summary>",   // description: task brief
  "Execute python bin/<script> [params]", // prompt: Complete execution instruction
  {
    idempotency_key?: string   // Idempotency key: same key executes only once within 5s
  }
)
```

### 1.3 Idempotency Guarantee [P0-LOCK]
```yaml
# Duplicate Execution Prevention Rules
Cache Duration: 5 seconds
Deduplication Key: idempotency_key (string)
Behavior: Same key returns cached result within 5s

# Recommended key naming
- "skill-list"         # List skills
- "skill-search:<kw>"  # Search skills
- "scan-skills"        # Scan skills
```

### 1.3 Prompt Construction Rules
```yaml
# Standard Format
Execute python bin/<script_name> [params...]

# Examples
Execute python bin/skill_manager.py list
Execute python bin/skill_manager.py search markdown
Execute python bin/skill_scanner.py scan
```

### 1.4 Pre-dispatch Check [MUST]
- [ ] Script file exists in `bin/` directory
- [ ] Operation parameters complete (if missing, ask user)
- [ ] Not code creation task (creating Python scripts prohibited)
- [ ] Git Bash spec check (disable `> nul`, use `> /dev/null`)

---

## 2. Return Protocol

### 2.1 Standard Format
```
<status> worker_agent <summary>
  state: <code> | data: {...} | meta: {...}
```

### 2.2 Status Code Definition
| Status | Icon | Meaning | Usage Scenario |
|:---|:---|:---|:---|
| `success` | ✅ | Complete success | Script execution completed |
| `success` | ⏭️ | Cache hit | Duplicate call within 5s (idempotent) |
| `partial` | ⚠️ | Partial success | Some tasks completed |
| `error` | ❌ | Execution failed | Recoverable or unrecoverable error |

### 2.3 Standard Return Examples

```yaml
# Success
✅ worker_agent scan completed: 2 added, 3 updated
  state: success
  data: {added: ["skill_a","skill_b"], updated: ["skill_c","skill_d","skill_e"], total: 5}
  meta: {agent: worker_agent, time: 0.5, ts: "2025-01-29T10:30:00Z"}

# Cache hit (idempotent)
⏭️ worker_agent cache hit: using recent result (<5s)
  state: success
  data: {cached: true, original_result: {total: 5, skills: [...]}}
  meta: {agent: worker_agent, time: 0.01, ts: "2025-01-29T10:30:05Z"}

# Partial success
⚠️ worker_agent partial completion: 3/5 scripts executed successfully
  state: partial
  data: {succeeded: ["a.py","b.py","c.py"], failed: ["d.py","e.py"]}
  meta: {agent: worker_agent, time: 1.2, ts: "2025-01-29T10:30:00Z"}

# Error
❌ worker_agent RuntimeError: Script execution failed
  state: error
  data: {type: "FileNotFoundError", msg: "bin/script.py not found"}
  meta: {agent: worker_agent, time: 0.1, ts: "2025-01-29T10:30:00Z"}
```

---

## 3. Error Type Mapping

| Error Type | Summary Format | recoverable | Handling Suggestion |
|:---|:---|:---:|:---|
| `ScriptNotFound` | Script not found: `<script>` | false | Check script path |
| `InvalidArgs` | Invalid args: `<reason>` | true | Show script Help |
| `RuntimeError` | Execution failed: `<stderr snippet>` | null | Judge by specific error |
| `PermissionDenied` | Permission denied | false | Check file permissions |

---

## 4. Special Return Fields

### 4.1 LangGraph Interrupt Fallback Mechanism [FALLBACK]

**Trigger Condition**: When Worker returns `state: interrupted`

**Main Session Handling Flow**:
```yaml
1. Detect "[INTERRUPT]" marker
2. Read langgraph_interrupt.json
3. LLM analysis → {"skill": "keep/uninstall"}
4. Execute recovery command
```

**Worker Return Format** (unhandled):
```yaml
⏸️ worker_agent workflow paused: <N> skills need LLM analysis
  state: interrupted
  data: {interrupted_skills: [...], resume_command: "..."}
```

**Note**: Worker should prioritize autonomous handling (see `.claude/agents/worker_agent.md`), main session only serves as fallback.

### 4.2 analysis_prompt Field
When output contains `【LLM Secondary Analysis Task】`:
```yaml
data:
  analysis_prompt: "<Content requiring LLM secondary analysis>"
```

### 4.3 Comparison with Other Agents

| Agent | Responsibility | Exclusive Feature |
|:---|:---|:---|
| **worker_agent** | Execute `bin/` scripts | Idempotency + Interrupt autonomous handling |
| **skills** | Execute installed skills | Timeout limit |

---

## 5. Python Encoding Compatibility [P0]

**Root Cause**: Windows Python defaults to GBK encoding, cannot output emoji, causing script crashes.

**Mandatory Requirement**: All Python scripts must add UTF-8 encoding setting at the beginning:

```python
import sys
import os

# Windows UTF-8 Compatibility (P0 - All scripts must include)
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
```

**Prohibit emoji**: Emoji is prohibited in output information, use ASCII instead:
- `✅` → `[OK]` / `success:`
- `❌` → `[ERROR]` / `failed:`
- `⚠️` → `[WARN]` / `warning:`

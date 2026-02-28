# Skills Agent Dispatch Protocol v3.0

> **Positioning**: Kernel ↔ Skills Agent Communication Contract
> **Principle**: Structured Dispatch + Unified Return + Clear Error Handling

---

## 1. Dispatch Protocol

### 1.1 Execution Mode Description [P0]
**Synchronous Execution Architecture**: Skills Agent uses synchronous execution mode, task results obtained directly in `Task` return value.

```yaml
# ✅ Correct: Process Task return value directly
result = Task("skills_agent", "Execute skill", "Execute @markdown-converter README.md")
# → Result already in result, no subsequent retrieval needed

# ❌ Wrong: Attempt to retrieve with TaskOutput
TaskOutput(task_id=xxx)  # → Sync task has no task_id, will error
```

### 1.2 Task Tool Signature
```
Task(
  "skills_agent",              // Fixed sub-agent type
  "<3-5 word task summary>",   // description: task brief
  "Execute @<skill_name> [params]", // prompt: natural language instruction
  { model?: "sonnet" | "opus" | "haiku" }  // Optional model
)
```

### 1.2 Prompt Construction Rules
```yaml
# Standard Format
Execute @<skill_name> [params...]

# Examples
Execute @markdown-converter README.md
Execute @image-resizer photo.jpg --width 800
Execute @code-analyzer src/ --language python
```

### 1.3 Pre-dispatch Check [MUST]
- [ ] Skill installed (if not installed, guide installation)
- [ ] Required parameters provided (if missing, ask user)
- [ ] Not multi-step task (multi-step tasks designed as workflow by Kernel)

### 1.4 Parameter Completeness Mandatory Check [P0-FORCE]

**Must check skill's `required_params` config before execution, prohibited from executing if parameters missing.**

#### Check Flow

```
1. Read required_params from SKILL.md frontmatter
    ↓
2. Parse user input, extract provided parameters
    ↓
3. Compare required_params list, identify missing parameters
    ↓
4. Missing parameters → Ask user first, prohibited to skip
    ↓
5. Validation passed → Continue skill execution
```

#### required_params Structure

```yaml
required_params:
  - name: github_url
    prompt: Target project GitHub URL
    validation: url_format
    required: true
  - name: requirements
    prompt: |
      ## Requirements Collection Template
      1. ...
    validation: not_empty
    required: true
```

#### Validation Rules

| validation | Meaning | Check Method |
|:-----------|:--------|:-------------|
| `url_format` | URL format | Starts with http:// or https:// |
| `not_empty` | Non-empty | Content length > 0 |
| `email` | Email format | Contains @ symbol |
| `file_exists` | File exists | Path points to valid file |

#### Interrupt Behavior

When `required: true` parameter is detected as missing:

```yaml
# Return pending status
⏸️ skills_agent waiting for params: need <param_name>
  state: pending
  data: {
    required: ["github_url", "requirements"],
    missing: ["requirements"],
    prompt: "<prompt content defined in SKILL.md>"
  }
  meta: {agent: skills_agent, time: 0.1, ts: "2025-02-19T10:00:00Z"}
```

#### Execution Guarantee

- **Prohibit Skip**: Must interrupt and ask when `interrupt_on_missing: true`
- **Prohibit Guessing**: Must not auto-fill or assume user intent
- **Complete Passthrough**: Show the `prompt` defined in SKILL.md completely to user

---

## 2. Return Protocol

### 2.1 Standard Format
```
<status> skills_agent <summary>
  state: <code> | data: {...} | meta: {...}
```

### 2.2 Status Code Definition
| Status | Icon | Meaning | Usage Scenario |
|:---|:---|:---|:---|
| `success` | ✅ | Complete success | Skill execution completed |
| `pending` | ⏸️ | Waiting for params | Need more info from user |
| `error` | ❌ | Execution failed | Recoverable or unrecoverable error |
| `timeout` | ⏱️ | Timeout | Execution exceeded 90 seconds |

### 2.3 Content Passthrough Rules [P0]
When Skills Agent returns containing the following fields, Kernel **must** actively output:

| Field Type | Trigger Fields | Direct Output | File Output |
|:---|:---|:---:|:---:|
| Text | `content`/`text`/`article` | ≤2000 chars | >2000 chars → mybox/ |
| Code | `code`/`script` | ≤100 lines | >100 lines → mybox/ |
| Analysis Result | `analysis`/`report` | ✅ Always output | - |

### 2.4 Standard Return Examples

```yaml
# Success
✅ skills_agent execution succeeded: Markdown conversion → mybox/workspace/result.html
  state: success
  data: {skill: "markdown-converter", output_path: "mybox/workspace/result.html", output_size: "12.5KB"}
  meta: {agent: skills_agent, time: 1.8, ts: "2025-01-29T10:30:00Z"}

# Waiting for params
⏸️ skills_agent waiting for params: need input_file
  state: pending
  data: {required: ["input_file"], optional: ["format", "quality"]}
  meta: {agent: skills_agent, time: 0.1, ts: "2025-01-29T10:30:00Z"}

# Error
❌ skills_agent ParamMissing: Insufficient params: need input_file
  state: error
  data: {type: "ParamMissing", msg: "Required parameter 'input_file' not provided", recoverable: true}
  meta: {agent: skills_agent, time: 0.2, ts: "2025-01-29T10:30:00Z"}

# Timeout
⏱️ skills_agent Timeout: Execution timeout (>90 seconds)
  state: timeout
  data: {skill: "large-processor", elapsed: 90, limit: 90}
  meta: {agent: skills_agent, time: 90, ts: "2025-01-29T10:30:00Z"}
```

---

## 3. Error Type Mapping

| Error Type | Summary Format | recoverable | Handling Suggestion |
|:---|:---|:---:|:---|
| `SkillNotFound` | Skill not installed: `<name>` | true | Guide user to install |
| `MetadataMissing` | SKILL.md corrupted or missing | false | Reinstall skill |
| `ParamMissing` | Insufficient params: need `<param>` | true | Ask user to provide |
| `RuntimeFailed` | Execution failed: `<stderr snippet>` | null | Judge by specific error |
| `Timeout` | Execution timeout (>90 seconds) | true | Suggest splitting task |

---

## 4. Skill Type Definition

| Type | Detection Method | Behavior | Return Format |
|:---|:---|:---|:---|
| **Type A** | SKILL.md has `command` | Execute Shell/Python command | Standard return |
| **Type B** | SKILL.md has no `command` | Return prompt content for Kernel use | Prompt return |

### Type B (Prompt Skill) Return Format
```yaml
✅ skills_agent prompt loaded: marketing-ideas
  state: success
  data: {
    skill: "marketing-ideas",
    type: "prompt",
    name: "Marketing Ideas Generator",
    description: "Provide marketing strategy suggestions",
    content: "<SKILL.md full content>",
    executable: false
  }
  meta: {agent: skills_agent, time: 0.1, ts: "2025-01-30T10:00:00Z"}
```

---

## 5. Comparison with Other Agents

| Agent | Config File | Responsibility | Exclusive Feature |
|:---|:---|:---|:---|
| **worker_agent** | `.claude/agents/worker_agent.md` | Execute `bin/` scripts | Idempotency (5s cache) |
| **skills_agent** | `.claude/agents/skills_agent.md` | Execute installed skills | Timeout (90s limit) |

---

## 6. Python Encoding Compatibility [P0]

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

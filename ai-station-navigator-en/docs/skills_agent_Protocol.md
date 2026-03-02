# Skills Agent Dispatch Protocol v3.0

> **Positioning**: Kernel ↔ Skills Agent Communication Contract
> **Principle**: Structured Dispatch + Unified Return + Explicit Error Handling

---

## 1. Dispatch Protocol

### 1.1 Execution Mode Description [P0]
**Synchronous Execution Architecture**: Skills Agent uses synchronous execution mode, task results obtained directly in `Task` return value.

```yaml
# Correct: Process Task return value directly
result = Task("skills_agent", "Execute skill", "Execute @markdown-converter README.md")
# Result already in result, no subsequent retrieval needed

# Wrong: Attempt to retrieve with TaskOutput
TaskOutput(task_id=xxx)  # Sync task has no task_id, will error
```

### 1.2 Task Tool Signature
```
Task(
  "skills_agent",
  "<3-5 word task summary>",
  "Execute @<skill_name> [params]"
)
```

**Core Constraint**: Agent triggers user-required skills through Skill tool

### 1.3 Prompt Construction Rules
```yaml
# Standard format
Execute @<skill_name> [params...]

# Examples
Execute @markdown-converter README.md
Execute @image-resizer photo.jpg --width 800
Execute @code-analyzer src/ --language python
```

### 1.4 Pre-dispatch Check [MUST]
- [ ] Skill installed (guide user to install if not)
- [ ] Required parameters provided (ask user if missing)
- [ ] Not multi-step task (multi-step tasks designed by Kernel as workflow)

### 1.5 Parameter Completeness Mandatory Check [P0-FORCE]

**Must check skill's `required_params` configuration before execution, prohibit execution if parameters missing.**

#### Check Process

```
1. Read required_params from SKILL.md frontmatter
    ↓
2. Parse user input, extract provided parameters
    ↓
3. Compare with required_params list, identify missing parameters
    ↓
4. Missing parameters → Ask user first, prohibit skipping
    ↓
5. Validation passed → Continue skill execution
```

#### required_params Structure

```yaml
required_params:
  - name: github_url
    prompt: Target project's GitHub URL
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
|:-----------|:-----|:---------|
| `url_format` | URL format | Starts with http:// or https:// |
| `not_empty` | Non-empty | Content length > 0 |
| `email` | Email format | Contains @ symbol |
| `file_exists` | File exists | Path points to valid file |

#### Interrupt Behavior

When detecting parameters with `required: true` missing:

```yaml
# Return pending status
pause-icon skills_agent waiting for parameters: Needs <param_name>
  state: pending
  data: {
    required: ["github_url", "requirements"],
    missing: ["requirements"],
    prompt: "<prompt content defined in SKILL.md>"
  }
  meta: {agent: skills_agent, time: 0.1, ts: "2025-02-19T10:00:00Z"}
```

#### Execution Guarantee

- **Prohibit skipping**: When `interrupt_on_missing: true`, must interrupt and ask
- **Prohibit guessing**: Must not auto-fill or assume user intent
- **Complete delivery**: Fully display `prompt` defined in SKILL.md to user

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
| `success` | check-icon | Complete success | Skill execution completed |
| `pending` | pause-icon | Waiting for parameters | Need user to provide more information |
| `error` | x-icon | Execution failed | Recoverable or unrecoverable error |
| `timeout` | clock-icon | Timeout | Execution exceeded 90 seconds |

### 2.3 Content Pass-through Rule [P0]
When Skills Agent returns containing following fields, Kernel **MUST** actively output:

| Field Type | Trigger Fields | Direct Output | File Output |
|:---|:---|:---:|:---:|
| Text | `content`/`text`/`article` | ≤2000 chars | >2000 chars → mybox/ |
| Code | `code`/`script` | ≤100 lines | >100 lines → mybox/ |
| Analysis result | `analysis`/`report` | Always output | - |

### 2.4 Standard Return Examples

```yaml
# Success
check-icon skills_agent execution succeeded: Markdown conversion → mybox/workspace/result.html
  state: success
  data: {skill: "markdown-converter", output_path: "mybox/workspace/result.html", output_size: "12.5KB"}
  meta: {agent: skills_agent, time: 1.8, ts: "2025-01-29T10:30:00Z"}

# Waiting for parameters
pause-icon skills_agent waiting for parameters: Needs input_file
  state: pending
  data: {required: ["input_file"], optional: ["format", "quality"]}
  meta: {agent: skills_agent, time: 0.1, ts: "2025-01-29T10:30:00Z"}

# Error
x-icon skills_agent ParamMissing: Insufficient parameters: Needs input_file
  state: error
  data: {type: "ParamMissing", msg: "Required parameter 'input_file' not provided", recoverable: true}
  meta: {agent: skills_agent, time: 0.2, ts: "2025-01-29T10:30:00Z"}

# Timeout
clock-icon skills_agent Timeout: Execution timeout (>90 seconds)
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
| `ParamMissing` | Insufficient parameters: Needs `<param>` | true | Ask user to provide |
| `RuntimeFailed` | Execution failed: `<stderr fragment>` | null | Judge by specific error |
| `Timeout` | Execution timeout (>90 seconds) | true | Suggest splitting task |

---

## 4. Skill Type Definition

| Type | Detection Method | Behavior | Return Format |
|:---|:---|:---|:---|
| **Type A** | SKILL.md has `command` | Execute Shell/Python command | Standard return |
| **Type B** | SKILL.md has no `command` | Return prompt content for Kernel use | Prompt return |

### Type B (Prompt Skill) Return Format
```yaml
check-icon skills_agent prompt loaded: marketing-ideas
  state: success
  data: {
    skill: "marketing-ideas",
    type: "prompt",
    name: "Marketing Ideas Generator",
    description: "Provides marketing strategy suggestions",
    content: "<Complete SKILL.md content>",
    executable: false
  }
  meta: {agent: skills_agent, time: 0.1, ts: "2025-01-30T10:00:00Z"}
```

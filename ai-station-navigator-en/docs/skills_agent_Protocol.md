# Skills Agent Dispatch Protocol v3.0

> **Purpose**: Communication contract between Kernel and Skills Agent
> **Principles**: Structured dispatch + Unified return + Explicit error handling

---

## 1. Dispatch Protocol

### 1.1 Execution Mode Specification [P0]
**Synchronous Execution Architecture**: Skills Agent uses synchronous execution mode, task results are obtained directly from `Task` return values.

```yaml
# ✅ Correct: Process Task return value directly
result = Task("skills_agent", "Execute skill", "Execute @@markdown-converter README.md")
# → Result already in result, no need for subsequent retrieval

# ❌ Wrong: Try to retrieve with TaskOutput
TaskOutput(task_id=xxx)  # → Synchronous task has no task_id, will error
```

### 1.2 Task Tool Signature
```
Task(
  "skills_agent",
  "<3-5 word task summary>",
  "Use Skill tool to invoke @@<skill_name> [parameters]"
)
```

**Core Constraint**: Agent triggers user-required skills through Skill tool

### 1.2 Prompt Construction Rules
```yaml
# Standard format
Execute @@<skill_name> [parameters...]

# Examples
Execute @@markdown-converter README.md
Execute @@image-resizer photo.jpg --width 800
Execute @@code-analyzer src/ --language python
```

### 1.3 Pre-Dispatch Checks [MUST]
- [ ] Skill installed (guide installation if not)
- [ ] Required parameters provided (ask user if missing)
- [ ] Not a multi-step task (Kernel designs workflows for multi-step tasks)

### 1.4 Mandatory Parameter Completeness Check [P0-FORCE]

**Must check skill's `required_params` configuration before execution, prohibit execution if parameters are missing.**

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
|:-----------|:-------|:-------------|
| `url_format` | URL format | Starts with http:// or https:// |
| `not_empty` | Non-empty | Content length > 0 |
| `email` | Email format | Contains @ symbol |
| `file_exists` | File exists | Path points to valid file |

#### Interrupt Behavior

When detecting missing parameters with `required: true`:

```yaml
# Return pending status
⏸️ skills_agent waiting for parameter: Need <param_name>
  state: pending
  data: {
    required: ["github_url", "requirements"],
    missing: ["requirements"],
    prompt: "<prompt content defined in SKILL.md>"
  }
  meta: {agent: skills_agent, time: 0.1, ts: "2025-02-19T10:00:00Z"}
```

#### Execution Guarantees

- **Prohibit skip**: Must interrupt to ask when `interrupt_on_missing: true`
- **Prohibit guess**: Do not auto-fill or assume user intent
- **Complete pass**: Display the `prompt` defined in SKILL.md completely to user

---

## 2. Return Protocol

### 2.1 Standard Format
```
<status> skills_agent <summary>
  state: <code> | data: {...} | meta: {...}
```

### 2.2 Status Code Definitions
| Status | Icon | Meaning | Usage Scenario |
|:---|:---|:---|:---|
| `success` | ✅ | Complete success | Skill execution completed |
| `pending` | ⏸️ | Waiting for parameters | Need more user input |
| `error` | ❌ | Execution failed | Recoverable or unrecoverable error |
| `timeout` | ⏱️ | Timeout | Execution exceeded 90 seconds |

### 2.3 Content Pass-Through Rules [P0]
When Skills Agent returns containing the following fields, Kernel **MUST** actively output:

| Field Type | Trigger Field | Direct Output | File Output |
|:---|:---|:---:|:---:|
| Text | `content`/`text`/`article` | ≤2000 words | >2000 words → mybox/ |
| Code | `code`/`script` | ≤100 lines | >100 lines → mybox/ |
| Analysis Result | `analysis`/`report` | ✅ Always output | - |

### 2.4 Standard Return Examples

```yaml
# Success
✅ skills_agent execution successful: Markdown conversion → mybox/workspace/result.html
  state: success
  data: {skill: "markdown-converter", output_path: "mybox/workspace/result.html", output_size: "12.5KB"}
  meta: {agent: skills_agent, time: 1.8, ts: "2025-01-29T10:30:00Z"}

# Waiting for parameters
⏸️ skills_agent waiting for parameter: Need input_file
  state: pending
  data: {required: ["input_file"], optional: ["format", "quality"]}
  meta: {agent: skills_agent, time: 0.1, ts: "2025-01-29T10:30:00Z"}

# Error
❌ skills_agent ParamMissing: Insufficient parameters: Need input_file
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
| `ParamMissing` | Insufficient parameters: Need `<param>` | true | Ask user to provide |
| `RuntimeFailed` | Execution failed: `<stderr fragment>` | null | Judge based on specific error |
| `Timeout` | Execution timeout (>90 seconds) | true | Suggest splitting task |

---

## 4. Skill Type Definitions

| Type | Detection Method | Behavior | Return Format |
|:---|:---|:---|:---|
| **Type A** | SKILL.md has `command` | Execute Shell/Python command | Standard return |
| Type B | SKILL.md has no `command` | Return prompt content for Kernel use | Prompt return |

### Type B (Prompt Skill) Return Format
```yaml
✅ skills_agent prompt loaded: marketing-ideas
  state: success
  data: {
    skill: "marketing-ideas",
    type: "prompt",
    name: "Marketing Ideas Generator",
    description: "Provide marketing strategy suggestions",
    content: "<Complete SKILL.md content>",
    executable: false
  }
  meta: {agent: skills_agent, time: 0.1, ts: "2025-01-30T10:00:00Z"}
```



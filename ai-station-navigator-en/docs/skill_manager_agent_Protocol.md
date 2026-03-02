# Skill Manager Agent Dispatch Protocol v2.0

> **Positioning**: Kernel ↔ Skill Manager Agent Communication Contract
> **Principle**: Define interfaces only, do not describe implementation

---

## 1. How to Call

### Task Signature
```
Task(
  "skill_manager_agent",
  "<3-5 word task summary>",
  "<Natural language instruction with necessary parameters>"
)
```

### Call Examples
```yaml
# Install skill - Pass original URL
Task("skill_manager_agent", "Install skill", "Install from https://github.com/user/repo")

# Install specific sub-skill - Use full subpath URL (script auto-parses)
Task("skill_manager_agent", "Install skill", "Install from https://github.com/user/repo/tree/main/skills/skill-a")

# Delete skill - By name
Task("skill_manager_agent", "Delete skill", "Delete skills skill-a skill-b")

# Delete skill - By repo URL
Task("skill_manager_agent", "Delete skill", "Delete https://github.com/user/repo")

# Resume installation (after pending)
Task("skill_manager_agent", "Continue installation", "resume: keep skill-b, uninstall skill-c")
```

---

## 2. What Returns

### Status Code Definition
| Status | Meaning | data Fields |
|:---|:---|:---|
| `success` | Complete | `installed[]`, `uninstalled[]`, `skipped[]` |
| `pending` | Waiting review | `threatened_skills[]`, `safe_skills[]`, `cached_paths{}` |
| `partial` | Partial success | `installed[]`, `failed[]`, `errors{}` |
| `error` | Failed | `type`, `reason`, `recoverable` |

### Return Examples

**Install Success**:
```yaml
check-icon skill_manager_agent installation complete: 2/3 succeeded
  state: success
  data: {
    installed: ["skill-a", "skill-b"],
    skipped: ["skill-c"],
    failed: []
  }
```

**Waiting Review**:
```yaml
pause-icon skill_manager_agent waiting review: 1 skill needs decision
  state: pending
  data: {
    threatened_skills: [
      {
        name: "skill-b",
        severity: "MEDIUM",
        threats: [
          {
            rule: "user_input_network_request",
            file: "lib/api.py",
            line: 42,
            code: ">>> def send_data(data):\n...    requests.post(f'https://api.com/{data}', ...)",
            description: "User input directly used in URL"
          }
        ],
        threats_count: 3
      }
    ],
    safe_skills: ["skill-a"],
    cached_paths: {
      "skill-a": "mybox/cache/.../skill-a",
      "skill-b": "mybox/cache/.../skill-b"
    },
    meta_json: "mybox/cache/.../.meta.json"  # User original requirement record
  }
```

**Delete Success**:
```yaml
check-icon skill_manager_agent deletion complete: 2 skills
  state: success
  data: {
    uninstalled: ["skill-a", "skill-b"],
    db_synced: true
  }
```

**Error**:
```yaml
x-icon skill_manager_agent CloneFailed: Repository not found
  state: error
  data: {
    type: "CloneFailed",
    url: "https://github.com/user/repo",
    reason: "Repository not found",
    recoverable: false
  }
```

---

## 3. How to Handle

### 3.1 Error Handling

| Error Type | recoverable | Handling Suggestion |
|:---|---:|:---|
| `CloneFailed` | false | Prompt check URL and permissions |
| `ScanFailed` | true | Skip scan, continue installation |
| `ModuleNotFound` | true | Guide install dependencies (pip install) |
| `InvalidSkill` | false | Skip this skill |
| `InstallFailed` | null | Judge by specific error |

### 3.2 Pending Recovery Flow

```
┌─────────────────────────────────────────┐
│  First Call                              │
├─────────────────────────────────────────┤
│  Kernel → Agent: Install skill           │
│  Agent → Kernel: pending + threat details │
│    + cached_paths (for recovery)         │
└─────────────────────────────────────────┘
              ↓ User Decision
┌─────────────────────────────────────────┐
│  Second Call (Recovery)                  │
├─────────────────────────────────────────┤
│  Kernel → Agent: resume task             │
│    - mode: "resume"                      │
│    - decisions: {skill: "keep/uninstall"}│
│    - safe_skills: [...]                 │
│    - cached_paths: {...}                │
│    - skip_scan: true                    │
│  Agent: Skip clone/scan, install directly│
│  Agent → Kernel: success result          │
└─────────────────────────────────────────┘
```

### 3.3 Threat Level Handling

| Level | Handling |
|:---|:---|
| `SAFE` | Install directly |
| `LOW` | Install directly |
| `MEDIUM` | **Must review** |
| `HIGH` | **Must review** |
| `CRITICAL` | **Strongly recommend uninstall** |

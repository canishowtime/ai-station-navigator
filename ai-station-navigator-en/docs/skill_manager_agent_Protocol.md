# Skill Manager Agent Dispatch Protocol v2.0

> **Positioning**: Communication contract between Kernel ↔ Skill Manager Agent
> **Principle**: Define interfaces only, not implementation

---

## 1. How to Dispatch

### Task Signature
```
Task(
  "skill_manager_agent",
  "<3-5 word task summary>",
  "<natural language instruction>",
  {
    url?: string,           # GitHub URL (when installing)
    skill_name?: string,    # Sub-skill name (optional)
    force?: boolean,        # Force override (optional)
    skill_names?: string[], # Skill list (when uninstalling)
  }
)
```

### Dispatch Examples
```yaml
# Install skill
Task("skill_manager_agent", "Install skill", "Install skill from https://github.com/user/repo")

# Install specified sub-skill
Task("skill_manager_agent", "Install skill", "Install skill-a from repo", {
  url: "https://github.com/user/repo",
  skill_name: "skill-a"
})

# Delete skill
Task("skill_manager_agent", "Delete skill", "Delete skills skill-a skill-b")

# Resume installation (after pending)
Task("skill_manager_agent", "Continue installation", "Continue based on decision", {
  mode: "resume",
  decisions: {"skill-b": "keep", "skill-c": "uninstall"},
  safe_skills: ["skill-a"],
  skip_scan: true,
  cached_paths: {"skill-a": "path", "skill-b": "path"}
})
```

---

## 2. What Returns

### Status Code Definitions
| Status | Meaning | data Field |
|:---|:---|:---|
| `success` | Completed | `installed[]`, `uninstalled[]`, `skipped[]` |
| `pending` | Awaiting review | `threatened_skills[]`, `safe_skills[]`, `cached_paths{}` |
| `partial` | Partially successful | `installed[]`, `failed[]`, `errors{}` |
| `error` | Failed | `type`, `reason`, `recoverable` |

### Return Examples

**Installation Success**:
```yaml
✅ skill_manager_agent installation complete: 2/3 successful
  state: success
  data: {
    installed: ["skill-a", "skill-b"],
    skipped: ["skill-c"],
    failed: []
  }
```

**Awaiting Review**:
```yaml
⏸️ skill_manager_agent awaiting review: 1 skill requires decision
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
    }
  }
```

**Deletion Success**:
```yaml
✅ skill_manager_agent deletion complete: 2 skills
  state: success
  data: {
    uninstalled: ["skill-a", "skill-b"],
    db_synced: true
  }
```

**Error**:
```yaml
❌ skill_manager_agent CloneFailed: Repository not found
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

| Error Type | recoverable | Handling Recommendation |
|:---|---:|:---|
| `CloneFailed` | false | Prompt to check URL and permissions |
| `ScanFailed` | true | Skip scan and continue installation |
| `ModuleNotFound` | true | Guide to install dependencies (pip install) |
| `InvalidSkill` | false | Skip this skill |
| `InstallFailed` | null | Judge based on specific error |

### 3.2 Pending Recovery Flow

```
┌─────────────────────────────────────────┐
│  First call                              │
├─────────────────────────────────────────┤
│  Kernel → Agent: Install skill          │
│  Agent → Kernel: pending + threat details│
│    + cached_paths (for recovery)        │
└─────────────────────────────────────────┘
              ↓ User decision
┌─────────────────────────────────────────┐
│  Second call (recovery)                 │
├─────────────────────────────────────────┤
│  Kernel → Agent: resume task            │
│    - mode: "resume"                     │
│    - decisions: {skill: "keep/uninstall"}│
│    - safe_skills: [...]                │
│    - cached_paths: {...}               │
│    - skip_scan: true                   │
│  Agent: Skip clone/scan, install directly│
│  Agent → Kernel: success result         │
└─────────────────────────────────────────┘
```

### 3.3 Threat Level Handling

| Level | Handling |
|:---|:---|
| `SAFE` | Install directly |
| `LOW` | Install directly |
| `MEDIUM` | **Review required** |
| `HIGH` | **Review required** |
| `CRITICAL` | **Strongly recommend uninstall** |

---

## Version History

| Version | Changes |
|------|----------|
| v2.0 | Streamlined to core three elements, removed implementation details |
| v1.2 | Included complete functional specification (migrated to Agent config) |

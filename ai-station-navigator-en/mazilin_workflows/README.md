# Workflow Design Specification

**Version**: v1.2.0 (Simplified)
**Updated**: 2026-02-20

---

## Quick Start

```bash
# 1. Copy template
cp .template.md new-workflow.md

# 2. Edit required fields
name: workflow-name
version: 1.0.0
description: function description
depends_on:
  - skill-name

# 3. Write workflow instructions
```

---

## Complete Configuration Guide

### Required Fields

| Field | Description | Example |
|-------|-------------|---------|
| `name` | Workflow name | `Deep Analysis` |
| `version` | Version number | `1.0.0` |
| `description` | Function description | `Legal-grade fact verification...` |
| `depends_on` | Dependent skills | `['truth-miner']` |

### Recommended Fields

| Field | Description | Default |
|-------|-------------|---------|
| `tags` | Category tags | `[]` |
| `sandbox` | Security configuration | See below |
| `output.location` | Output location | `inline` |

---

## Security Configuration

### Basic Security (Recommended)

```yaml
sandbox:
  file_access:
    read: [mybox/**, docs/**, .claude/**]
    write: [mybox/workspace/**, mybox/temp/**]
    forbidden: [*.exe, *.dll, system32/**]
  network: false
```

### Advanced Security (Sensitive Workflows)

```yaml
sandbox:
  file_access:
    read: [docs/**, .claude/**]
    write: [mybox/temp/**]
    forbidden: [**]
  network: false
```

---

## Output Configuration

```yaml
output:
  location: inline        # inline | file | both
  format: markdown        # markdown | json | text
  file_path: mybox/workspace/{name}/{date}.md
```

**Path Variables**:
- `{name}` - Workflow name
- `{date}` - Current date (YYYY-MM-DD)
- `{timestamp}` - Timestamp

---

## Workflow Document Structure

### Required Sections

| Section | Description |
|---------|-------------|
| Function/Workflow Chain/Usage | Three opening elements |
| Use Cases | Application scope |
| Workflow Details | Phase-by-phase description |
| Output Location | File organization |
| Notes | Execution constraints |

### Recommended Structure

```markdown
# Title
**Function**: xxx
**Workflow Chain**: `skill1 → skill2 → output`

## Use Cases
- Case 1

## Workflow Details
### Phase 1
**Function**: xxx
**Execution**: @skill-name
**Input/Output**: xxx
**Example**: xxx

### Phase N
...

## Output Location
...

## Notes
...
```

---

## Validate Workflow

```bash
# Validate configuration
python bin/workflow_validator.py validate mazilin_workflows/workflow.md

# Check dependencies
python bin/workflow_validator.py check-deps mazilin_workflows/workflow.md

# Security scan
python bin/workflow_validator.py scan mazilin_workflows/
```

---

## Best Practices

1. **Visualize workflow chain** - `skill1 → skill2 → output`
2. **List use cases** - Define application scope clearly
3. **Detail each phase** - Function, input, output, example for each
4. **Standardize output format** - Define summary structure
5. **Clarify constraints** - Sequential execution, path references, stop on error

---

## Directory Structure

```
mazilin_workflows/
├── .template.md              # Simplified template (v1.2.0)
├── README.md                  # This documentation
├── shared/                    # Shared components
├── deep-analysis.md          # Example
└── code-review.md
```

---

## Design Philosophy

### MD DSL
Use Markdown as Domain Specific Language to describe workflows

### Frontmatter Separation
- Configuration layer (YAML) - Requires validation
- Instruction layer (Markdown) - Hot reload

### Security Mechanisms
- Sandbox isolation
- Compile validation
- Minimal permissions

---

## Related Documentation

- [SKILL.md specification](../.claude/skills/)
- [Kernel logic](../CLAUDE.md)

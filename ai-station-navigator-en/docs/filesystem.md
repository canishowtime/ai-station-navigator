# Filesystem Architecture

**Context**: Level 2 Architecture
**Parent**: `CLAUDE.md`
**Rule**: All I/O operations must strictly follow these permission bits (Permission Bits).

## 0. Project Root Detection

### Marker Files
Project root directory should contain the following files:
- `CLAUDE.md` (required)
- `docs/` (required)
- `bin/` (required)
- `.claude/` (required)

### Detection Commands
```bash
# Check if current directory is project root
test -f CLAUDE.md && echo "ROOT" || echo "NOT_ROOT"

# Search upward for project root
# Start from current directory, search upward for directory containing CLAUDE.md
```

### Directory Structure Description
```
<any-parent-directory>/              ← Launch location
└── myagent/ai-station-navigator/    ← Project root (CLAUDE.md here)
    ├── CLAUDE.md
    ├── docs/
    ├── bin/
    ├── .claude/
    └── mybox/
```

---

## 1. Topology & Permissions

```text
project-root/
├── bin/                     🔒 [RO]  Core Logic (modifications/writing prohibited)
├── .claude/                 🟡 [Sys] System Config (manager operations only)
│   ├── agents/              📋 Agent Definitions
│   ├── memory/              💾 User Preferences
│   ├── skills/              ⚙️  Active Skills
│   └── state/               🔄 Runtime State
├── mybox/                   ⚡ [RW]  Sandbox (only free R/W area)
│   ├── workspace/           ↻  [Work] Workspace (task files)
│   ├── temp/                ✕  [Tmp] Temporary cache (auto cleanup)
│   ├── cache/               💾 Persistent cache
│   │   └── repos/           📦 Git repository cache
│   └── logs/                📝 Runtime logs
├── docs/                    📖 [RO]  Documentation
│   ├── commands.md          📋 Command registry
│   ├── filesystem.md        📁 Filesystem specification
│   ├── skills-quickstart.md ⚡ Skills quickstart
│   ├── skills-mapping.md    🗺️ Sub-skill mapping table
│   ├── subagent-Protocol.md 📡 Sub-agent communication protocol
│   ├── guides/              📚 Operation guides
│   │   ├── README.md                        Overview index
│   │   ├── skill-install-workflow-guide.md  Skill installation workflow
│   │   ├── clone-manager-guide.md           Repository clone management
│   │   ├── security-scanner-guide.md        Security scanner
│   │   ├── skill-manager-guide.md           Skill management
│   │   ├── mcp-manager-guide.md             MCP management
│   │   ├── file-editor-guide.md             File editor
│   │   ├── gh-fetch-guide.md                GitHub resource fetching
│   │   └── hooks-manager-guide.md           Hooks management
├── tests/                   🧪 [RO]  Test Suite
├── mazilin_workflows/       🔄 [RW]  Official workflow storage
│   ├── README.md            📋 Workflow overview
│   └── *.md                 📄 Individual workflow documents
├── CLAUDE.md                📜 Core Protocol
└── README.md                📄 Project Info
```

## 1.1 mybox Path Specification

**Directory Purpose Definition**:

| Path | Purpose | Volatility | Cleanup Timing |
|:---|:---|:---|:---|
| `workspace/` | Work files (organized by task name) | Medium | After task completion |
| `temp/` | Temporary files (downloads/intermediate) | High | Auto/periodic cleanup |
| `cache/repos/` | Git repository cache | Low | Manual cleanup |
| `logs/` | Runtime logs | Low | Auto rotation |

**Path Selection Rules**:
```
Write requirement → File type?
    ├─ Temporary/download → mybox/temp/
    ├─ Persistent cache → mybox/cache/
    ├─ Work files → mybox/workspace/<task-name>/
    ├─ Workflow docs → mazilin_workflows/<workflow-name>.md
    └─ Logs → mybox/logs/
```

## 2. Data Pipelines

### A. Skill Deployment Pipeline
`External Source` -> `mybox/temp/` (Download) -> **Validate** -> `.claude/skills/` (Deploy)

### B. Task Execution Pipeline
1. **Ingest**: External files -> `mybox/temp/`
2. **Process**: Work files -> `mybox/workspace/<task>/`
3. **GC**: Task end -> Clean up `mybox/temp/` and `mybox/workspace/<task>/`

## 3. Core Constraints

1.  **Default Sandboxing**:
    - If user does not specify path, write operations **must** point to `mybox/workspace/`.
    - Prohibit creating files in `project-root/` root directory.

2.  **Volatility**:
    - `mybox/` is considered **volatile storage** (can be cleaned up at any time).
    - Configuration requiring persistence should be stored in `.claude/`.

3.  **Task Isolation**:
    - Each task uses independent subdirectory: `mybox/workspace/<task-name>/`

## 4. Cleanup Mechanism

| Trigger Condition | Cleanup Content |
|:---|:---|
| Session start | log_rotate (rotate logs) |
| Session start | cleanup_temp (clean temporary files) |
| Task completion | cleanup_workspace (clean task directory) |

### Manual Operations
```bash
# Trigger all Hooks
python bin/hooks_manager.py execute --force

# Clean specific directories
rm -rf mybox/temp/*
rm -rf mybox/workspace/<task-name>/
```

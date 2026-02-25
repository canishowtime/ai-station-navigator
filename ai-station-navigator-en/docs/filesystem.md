# Filesystem Architecture

**Context**: Level 2 Architecture
**Parent**: `CLAUDE.md`
**Rule**: All I/O operations strictly follow the permission bits below.

## 1. Topology & Permissions

```text
project-root/
├── bin/                     🔒 [RO]  Core Logic (modification/write prohibited)
├── .claude/                 🟡 [Sys] System Config (manager operations only)
│   ├── agents/              📋 Agent Definitions
│   ├── memory/              💾 User Preferences
│   ├── skills/              ⚙️  Active Skills
│   └── state/               🔄 Runtime State
├── mybox/                   ⚡ [RW]  Sandbox (only free R/W zone)
│   ├── workspace/           ↻  [Work] Workspace (task files)
│   ├── temp/                ✕  [Tmp] Temp cache (auto cleanup)
│   ├── cache/               💾 Persistent cache
│   │   └── repos/           📦 Git repo cache
│   └── logs/                📝 Runtime logs
├── docs/                    📖 [RO]  Documentation
│   ├── commands.md          📋 Command Registry
│   ├── filesystem.md        📁 Filesystem Specification
│   ├── skills-quickstart.md ⚡ Skill Quick Start
│   ├── skills-mapping.md    🗺️ Sub-skill Mapping Table
│   ├── subagent-Protocol.md 📡 Sub-agent Communication Protocol
│   ├── guides/              📚 Operation Guides
│   │   ├── README.md                        Overview Index
│   │   ├── skill-install-workflow-guide.md  Skill Install Workflow
│   │   ├── clone-manager-guide.md           Repo Clone Management
│   │   ├── security-scanner-guide.md        Security Scanner
│   │   ├── skill-manager-guide.md           Skill Management
│   │   ├── mcp-manager-guide.md             MCP Management
│   │   ├── file-editor-guide.md             File Editor
│   │   ├── gh-fetch-guide.md                GitHub Resource Fetch
│   │   └── hooks-manager-guide.md           Hooks Management
├── tests/                   🧪 [RO]  Test Suite
├── mazilin_workflows/       🔄 [RW]  Official Workflow App Storage
│   ├── README.md            📋 Workflow Overview
│   └── *.md                 📄 Individual Workflow Docs
├── CLAUDE.md                📜 Core Protocol
└── README.md                📄 Project Info
```

## 1.1 mybox Path Specification

**Directory Purpose Definition**:

| Path | Purpose | Volatility | Cleanup Timing |
|:---|:---|:---|:---|
| `workspace/` | Working files (organized by task name) | Medium | After task completion |
| `temp/` | Temp files (downloads/intermediate artifacts) | High | Auto/periodic cleanup |
| `cache/repos/` | Git repository cache | Low | Manual cleanup |
| `logs/` | Runtime logs | Low | Auto rotation |

**Path Selection Rules**:
```
Write Request → File Type?
    ├─ Temp/Download → mybox/temp/
    ├─ Persistent Cache → mybox/cache/
    ├─ Working Files → mybox/workspace/<task-name>/
    ├─ Workflow Docs → mazilin_workflows/<workflow-name>.md
    └─ Logs → mybox/logs/
```

## 2. Data Pipelines

### A. Skill Deploy Pipeline (Install Pipeline)
`External Source` -> `mybox/temp/` (Download) -> **Validate** -> `.claude/skills/` (Deploy)

### B. Task Execution Pipeline (Task Pipeline)
1. **Ingest**: External files -> `mybox/temp/`
2. **Process**: Working files -> `mybox/workspace/<task>/`
3. **GC**: Task end -> cleanup `mybox/temp/` and `mybox/workspace/<task>/`

## 3. Core Constraints

1.  **Default Sandboxing**:
    - If user doesn't specify path, write operations **must** point to `mybox/workspace/`.
    - Creating files in `project-root/` root directory prohibited.

2.  **Volatility**:
    - `mybox/` treated as **volatile storage** (can be cleaned anytime).
    - Configs requiring persistence go into `.claude/`.

3.  **Task Isolation**:
    - Each task uses independent subdirectory: `mybox/workspace/<task-name>/`

## 4. Cleanup Mechanism

| Trigger | Cleanup Content |
|:---|:---|
| Session Start | log_rotate (rotate logs) |
| Session Start | cleanup_temp (cleanup temp files) |
| Task Complete | cleanup_workspace (cleanup task directory) |

### Manual Operations
```bash
# Trigger all Hooks
python bin/hooks_manager.py execute --force

# Cleanup specific directory
rm -rf mybox/temp/*
rm -rf mybox/workspace/<task-name>/
```

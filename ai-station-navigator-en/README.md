# AI Station Navigator

> Navigator Kernel - Claude Agent System Bus and Dispatcher Framework

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

---

## Introduction

AI Station Navigator is a **production-ready** modular Claude agent framework. It implements skill management, MCP resource integration, and system improvement management through sub-agent collaboration.

### Core Design Philosophy

> **Minimize State_Gap** - Efficiently transition from current state (S_Current) to target state (S_Target)

### Architecture Features

- **Three-Layer Architecture**: Kernel (System Bus) + Sub-agents (Specialized Execution) + Tools (Capability Extension)
- **No Side Effects Principle**: All write operations require explicit authorization
- **Minimal Output**: Data and state only, no fluff
- **Session Stickiness**: Subsequent operations of the same task auto-route to the same sub-agent

---

## Core Capabilities

### Complete Tool Matrix

| Tool | Function | Command |
|:---|:---|---|
| **skill_manager** | Skill install/uninstall/search/convert/validate | `python bin/skill_manager.py <cmd>` |
| **mcp_manager** | MCP server management | `python bin/mcp_manager.py <cmd>` |
| **improvement_manager** | System improvement management (dual-track) | `python bin/improvement_manager.py <cmd>` |
| **improvement_checklist** | Improvement completion checklist | `python bin/improvement_checklist.py <cmd>` |
| **hooks_manager** | System event hooks management | `python bin/hooks_manager.py <cmd>` |
| **gh_fetch** | GitHub content fetcher (acceleration supported) | `python bin/gh_fetch.py <cmd>` |

### Featured Functions

| Feature | Description |
|:---|:---|
| **Smart Matching** | Multi-dimensional weighted scoring algorithm, auto-match related skills |
| **Format Conversion** | Auto-detect and convert non-standard formats to official SKILL.md |
| **Dual-Track Improvement** | Quick Fix (lightweight) / Full Proposal (complete) mode |
| **Backup & Rollback** | Auto backup before MCP operations, auto rollback on failure |
| **Network Acceleration** | Support Git clone and GitHub Raw file acceleration |
| **Auto Hooks** | Session cleanup, log rotation, disk check automation |

---

## Directory Structure

```
project-root/
├── bin/                     🔒 Core Scripts (Read-only)
│   ├── skill_manager.py         Skill Manager
│   ├── mcp_manager.py           MCP Manager
│   ├── improvement_manager.py   Improvement Manager
│   ├── improvement_checklist.py Checklist
│   ├── hooks_manager.py         Hooks Manager
│   └── gh_fetch.py              GitHub Fetcher
│
├── .claude/                 🟡 System Config/State/Agent Definitions
│   ├── agents/                  Sub-agent Definitions
│   │   ├── worker_agent.md          Internal Script Executor
│   │   └── skills_agent.md          Skill Runtime
│   ├── skills/              🧪 Installed Skills
│   │   └── skills.db               TinyDB Unified Data Source
│   ├── memory/              💾 User Preferences & State
│   ├── state/               🔄 Runtime State
│   │   ├── hooks_state.json         Hooks State
│   │   └── user_choices.json        User Choice Records
│   └── extensions_config.json    Extension Config
│
├── mybox/                   ⚡ Sandbox Environment (Free R/W)
│   ├── workspace/           ↻ Processing Center
│   ├── temp/                ✕ Temp Cache
│   ├── output/              📤 Final Output
│   ├── lib/                 📚 User Library
│   └── skills/              Local Skill Testing
│
├── docs/                    📖 Complete Documentation System
│   ├── commands.md              Command Registry
│   ├── filesystem.md            Filesystem Specification
│   ├── skills-quickstart.md     Skill Quick Start
│   ├── skill-support.md         Skill Support List
│   ├── tinydb-schema.md         Database Schema
│   ├── guides/                  Operation Guides Index
│   │   ├── README.md                Overview Index
│   │   ├── skill-manager-guide.md   Skill Management Guide
│   │   ├── skill-creator-guide.md   Skill Creation Guide
│   │   ├── mcp-manager-guide.md     MCP Management Guide
│   │   └── hooks-guide.md           Hooks Guide
│
├── tests/                   🧪 Test Suite (In Development)
│
├── CLAUDE.md                📜 Core Protocol (Must Read)
├── config.json              ⚙️ Network & Proxy Config
└── requirements.txt         📦 Python Dependencies
```

---

## Quick Start

### 1. Environment Setup

```bash
# Install dependencies
pip install -r requirements.txt
```

### 2. Core Protocol Reading

**Must read `CLAUDE.md` first** - Contains system routing logic, execution flow, and specialized protocols.

### 3. Skill Management

```bash
# View installed skills
python bin/skill_manager.py list

# Install new skill (supports URL/Path/Name)
python bin/skill_manager.py install <source>

# Search skill (smart matching)
python bin/skill_manager.py search <keyword>
```

### 4. MCP Server Management

```bash
# List available presets
python bin/mcp_manager.py list

# Add server (auto-configure permissions)
python bin/mcp_manager.py add context7

# Test connection
python bin/mcp_manager.py test context7
```

### 5. System Improvement

```bash
# Create full proposal
python bin/improvement_manager.py create "Add feature X"

# Create quick fix
python bin/improvement_manager.py create "Fix bug Y" --quickfix

# Completion check
python bin/improvement_checklist.py check <id>
```

---

## Documentation Index

### Core Documents

| Document | Purpose |
|:---|:---|
| [`CLAUDE.md`](CLAUDE.md) | **Core Protocol** - System Bus Logic |
| [`docs/commands.md`](docs/commands.md) | Command Registry - All Available Commands |
| [`docs/filesystem.md`](docs/filesystem.md) | Filesystem Specification - Permissions & Data Flow |
| [`docs/guides/README.md`](docs/guides/README.md) | Guides Index - Detailed Operation Guides |

### Specialized Guides

| Document | Content |
|:---|:---|
| [`docs/skills-quickstart.md`](docs/skills-quickstart.md) | Skill Quick Start |
| [`docs/tinydb-schema.md`](docs/tinydb-schema.md) | Database Schema Details |

---

## System Architecture

### Sub-agent Responsibilities

```
┌─────────────────────────────────────────────────────────┐
│                    Kernel (System Bus)                   │
│  Perception & Intent Analysis → Routing Strategy →      │
│  Sub-agent Dispatch                                      │
└─────────────────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ↓               ↓               ↓
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   skills    │  │   worker    │  │     mcp     │
│  Sub-agent  │  │  Sub-agent  │  │  Sub-agent  │
│             │  │             │  │             │
│Skill Runtime│  │Script Exec  │  │MCP Operator │
│             │  │             │  │             │
│ - Parse Cmd │  │ - Exec bin/ │  │ - Query     │
│ - Inject    │  │ - Return    │  │ - Read      │
│ - Run Cmd   │  │   Results   │  │   Content   │
└─────────────┘  └─────────────┘  └─────────────┘
```

### Workflow

#### Skill Execution Flow
```
User Input Task
    ↓
[skill_manager search] → Smart match related skills
    ↓
Branch Decision:
├─ Installed → [skills sub-agent] → Direct execution
└─ Not Installed → [worker] → skill_manager install → [skills] execute
    ↓
Record Usage → skills.db
```

#### Improvement Proposal Flow
```
User proposes improvement
    ↓
Complexity Assessment:
├─ Simple → Quick Fix (3 steps, ~400 tokens)
└─ Complex → Full Proposal (6 steps, ~1500 tokens)
    ↓
[improvement_manager create]
    ↓
Execute Improvement → [improvement_checklist check]
    ↓
Complete → Update STATUS.md
```

---

## Configuration

### config.json

```json
{
  "git": {
    "proxies": [
      "https://gitclone.com/github.com/{repo}",
      "https://gh-proxy.com/github.com/{repo}"
    ]
  },
  "raw": {
    "proxies": [
      "https://ghfast.top/https://raw.githubusercontent.com/{path}"
    ]
  },
  "network": {
    "timeout": 120,
    "retry": 3
  }
}
```

### MCP Preset Templates

| Preset | Purpose | Documentation |
|:---|:---|:---|
| `context7` | Programming library doc query | [Context7](https://context7.com) |
| `tavily` | Web search & content extraction | [Tavily](https://tavily.com) |
| `filesystem` | Filesystem access | MCP Built-in |
| `github` | GitHub repository operations | MCP Built-in |
| `sqlite` | SQLite database | MCP Built-in |
| `memory` | Key-value storage | MCP Built-in |

---

## Smart Matching Engine

### Matching Algorithm

skill_manager uses multi-dimensional weighted scoring:

| Dimension | Weight | Description |
|:---|:---|:---|
| Name Match | 0.30 | Exact/fuzzy match skill name |
| Tag Match | 0.25 | Tag exact match |
| Search Index | 0.30 | Predefined keywords |
| Category Match | 0.15 | Skill category |
| Chinese Keywords | 0.40 | Chinese user optimization |
| User Preference | +0.3 | History usage bonus |

### Usage Examples

```bash
# Search skill (installed + recommended)
python bin/skill_manager.py search "image processing"

# List installed skills
python bin/skill_manager.py list
```

---

## Dual-Track Improvement Mode

### Quick Fix (Lightweight)

**Suitable For**: Bug fixes, documentation updates, minor script adjustments

- Token Consumption: ~400 (79% reduction)
- Steps: 3 steps
- Check: STATUS.md update only

### Full Proposal (Complete Process)

**Suitable For**: Architecture adjustments, new features, system upgrades

- Token Consumption: ~1500
- Steps: 6 steps
- Check: CLI registration + Guide docs + STATUS.md

---

## Automated Hooks

### Pre-registered Hooks

| Hook | Trigger | Function |
|:---|:---|:---|
| `log_rotate` | Session start | Rotate logs (keep 7 days) |
| `check_disk_space` | Session start | Disk space warning |
| `cleanup_workspace` | Delivery complete | Cleanup workspace |
| `cleanup_old_downloads` | Session start | Cleanup downloads older than 7 days |
| `create_delivery_snapshot` | Delivery complete | Create delivery snapshot |

### Management

```bash
# Manually trigger all Hooks
python bin/hooks_manager.py execute --force

# Enable/Disable Hook
python bin/hooks_manager.py enable --hook-name log_rotate
python bin/hooks_manager.py disable --hook-name log_rotate
```

---

## Skill Format Support

### Supported Formats

| Format | Auto Convert |
|:---|:---|
| Official SKILL.md | ✅ Native Support |
| Claude Code Skills | ✅ Auto Convert |
| Custom Format | ✅ Extensible |

### Skill Structure

```
skill-name/
├── SKILL.md              # Skill Definition (Required)
├── scripts/              # Execution Scripts
├── references/           # Reference Docs
└── assets/               # Asset Files
```

---

## Data Consistency Guarantee

### Axioms

1. **Filesystem = Source of Truth**: Actual skills are based on disk files
2. **Database = Cache**: Only for accelerating queries or storing metadata

### Sync Mechanism

- Auto sync skills.db on install/uninstall
- Auto record user preferences to user_choices.json

---

## Test Status

> **In Development** - `tests/` directory pending

### Planned Coverage

- [ ] Unit tests (each bin/ script)
- [ ] Integration tests (sub-agent collaboration)
- [ ] End-to-end tests (complete workflows)
- [ ] Regression tests (improvement proposal validation)

---

## Contributing

### Improvement Suggestions

Welcome to submit improvement suggestions via `improvement_manager`:

```bash
python bin/improvement_manager.py create "Your suggestion"
```

### Code Standards

- Follow PEP 8
- Add type annotations
- Write docstrings
- Update related guides

---

## License

MIT License

---

## Acknowledgments

This project is based on the following excellent projects:

- [Anthropic Claude Code](https://github.com/anthropics/claude-code) - skill-creator (Apache 2.0)
- [Model Context Protocol](https://modelcontextprotocol.io/) - MCP Specification
- [TinyDB](https://tinydb.readthedocs.io/) - Lightweight Database

---

**Last Updated**: 2026-01-28 | **Version**: v2.6

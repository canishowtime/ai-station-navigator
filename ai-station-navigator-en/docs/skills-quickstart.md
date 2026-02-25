# Skill System Quick Start

**Version**: v2.6 | **Updated**: 2026-02-04

---

## System Navigation

```
┌─────────────────────────────────────────────────────────┐
│                    AI Station Navigator                   │
│                    Skill System Navigation                │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  📥 [Skill Management]   → guides/skill-manager-guide.md │
│  🔌 [MCP Management]     → guides/mcp-manager-guide.md   │
│  📋 [Command Registry]   → commands.md                   │
│  📁 [Filesystem]         → filesystem.md                 │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Core Command Reference

### Skill Management

| Command | Description | Detailed Docs |
|:---|:---|:---|
| `python bin/skill_manager.py list` | List installed skills | [skill-manager-guide](./guides/skill-manager-guide.md) |
| `python bin/skill_manager.py search <keyword>` | Search skills | [skill-manager-guide](./guides/skill-manager-guide.md) |
| `python bin/skill_manager.py install <local_path>` | Install skill | [skill-manager-guide](./guides/skill-manager-guide.md) |
| `python bin/skill_manager.py uninstall <name>` | Uninstall skill | [skill-manager-guide](./guides/skill-manager-guide.md) |

### MCP Server Management

| Command | Description | Detailed Docs |
|:---|:---|:---|
| `python bin/mcp_manager.py list` | List MCP servers | [mcp-manager-guide](./guides/mcp-manager-guide.md) |
| `python bin/mcp_manager.py add <template_name>` | Add preset server | [mcp-manager-guide](./guides/mcp-manager-guide.md) |
| `python bin/mcp_manager.py remove <name>` | Remove server | [mcp-manager-guide](./guides/mcp-manager-guide.md) |
| `python bin/mcp_manager.py test <name>` | Test connection | [mcp-manager-guide](./guides/mcp-manager-guide.md) |

### GitHub Source Handling

| Command | Description |
|:---|:---|
| `python bin/clone_manager.py clone <URL>` | Clone GitHub repo to cache |

---

## Quick Workflows

### Install GitHub Skill

```bash
# Step 1: Clone repository
python bin/clone_manager.py clone https://github.com/user/repo

# Step 2: Install skill (from cache)
python bin/skill_manager.py install mybox/cache/repos/user-repo/skill-name
```

### Add MCP Server

```bash
# No API Key needed
python bin/mcp_manager.py add context7

# API Key required (interactive input)
python bin/mcp_manager.py add tavily -i

# API Key required (command line parameter)
python bin/mcp_manager.py add tavily --env TAVILY_API_KEY=xxx
```

---

## Supported Skill Formats

| Format | Description | Status |
|:---|:---|:---:|
| **Official** | Claude Code official format (SKILL.md) | ✅ |
| **Claude Plugin** | Claude plugin format | ✅ |
| **Agent Skills** | Anthropic Agent Skills | ✅ |
| **Cursor Rules** | Cursor rules file | ✅ |

View all formats: `python bin/skill_manager.py formats`

---

## MCP Preset Templates

| Template | Description | Key Required |
|:---|:---|:---:|
| `context7` | Programming library doc query | ❌ |
| `tavily` | Web search | ✅ |
| `filesystem` | Filesystem access | ❌ |
| `brave-search` | Privacy search | ✅ |
| `github` | GitHub operations | ✅ |
| `sqlite` | Database query | ❌ |
| `memory` | Key-value storage | ❌ |

---

## Verify Installation

### Skill Verification

```bash
# List installed skills
python bin/skill_manager.py list

# Validate specific skill
python bin/skill_manager.py validate .claude/skills/<name>

# Search skill
python bin/skill_manager.py search prompt --score
```

### MCP Verification

```bash
# List servers
python bin/mcp_manager.py list

# Test connection
python bin/mcp_manager.py test context7
```

---

## Common Issues

**Q: Skill not working?**
```bash
# Check if SKILL.md exists
cat .claude/skills/<name>/SKILL.md

# Check frontmatter format
head -10 .claude/skills/<name>/SKILL.md
```

**Q: How to install skill from GitHub?**
```bash
# GitHub source needs to be cloned first
python bin/clone_manager.py clone https://github.com/user/repo
# Then install from local cache
python bin/skill_manager.py install mybox/cache/repos/user-repo/skill-name
```

**Q: MCP server startup failed?**
```bash
# Check if command is available
where npx

# Test connection
python bin/mcp_manager.py test <server-name>
```

---

## Directory Structure

```
myagent/
├── .claude/
│   ├── skills/              # Installed skills
│   │   └── <skill-name>/
│   │       └── SKILL.md
│   └── settings.local.json  # MCP permission config
├── .mcp.json                 # MCP server config
├── bin/
│   ├── skill_manager.py     # Skill management
│   ├── mcp_manager.py       # MCP management
│   └── clone_manager.py     # Git clone
├── mybox/
│   ├── workspace/           # Working files
│   ├── cache/repos/         # Git cache
│   └── backups/mcp/         # MCP backups
└── docs/
    ├── guides/              # Detailed guides
    ├── commands.md          # Command registry
    └── filesystem.md        # Filesystem description
```

---

## Related Documentation

### Detailed Guides
- [Skill Manager Guide](./guides/skill-manager-guide.md) - Skill install, search, uninstall
- [MCP Manager Guide](./guides/mcp-manager-guide.md) - MCP server management

### Reference Documents
- [commands.md](./commands.md) - Complete command registry
- [filesystem.md](./filesystem.md) - Filesystem layout
- [CLAUDE.md](../CLAUDE.md) - Kernel logic core

# Vector Registry (Operator Registry)

**Context**: Level 2 Registry
**Parent**: `CLAUDE.md`
**Doc Base**: `docs/guides/` (If parameters are unclear, refer to corresponding guides)

## 1. Skill & Scan Domain
**Base**: `python bin/`

⚠️ **Prohibit direct Kernel calls** → Must dispatch via `worker_agent` (CLAUDE.md:232)

| Intent | Command Signature | Note |
|:---|:---|:---|
| **Install** | `#skill-install-agent <url> [--skill <name>] [--force]` | **Recommended**: Agent workflow (clone→scan→audit→install) |
| **Install** | `skill_install_workflow.py <url> [--skill <name>] [--force]` | (Legacy) LangGraph workflow, to be deprecated |
| **Install** | `skill_manager.py install <src>` | Quick install (local/package), no scan |
| **Uninstall** | `skill_manager.py uninstall <name> [...]` | **Sync DB Auto, batch support** |
| **List** | `skill_manager.py list` | List installed skills |
| **Search** | `skill_manager.py search <kw>` | See CLAUDE.md protocol |
| **Register Skills** | `register_missing_skills.py [--dry-run]` | Scan and register missing skills to database |
| **Verify Config** | `skill_manager.py verify-config [--fix]` | Verify configuration files |
| **Scan** | `security_scanner.py scan <target>` | Scan single skill |
| **Scan All** | `security_scanner.py scan-all` | Scan all installed skills |
| **Scan Config** | `security_scanner.py config` | View security scan configuration |

### 1.1 Repository Management (Repo)
**Base**: `python bin/clone_manager.py`

| Intent | Command Signature | Note |
|:---|:---|:---|
| **Clone** | `clone <url> [--ref <branch>] [--depth <n>]` | Clone GitHub repository |
| **List Cache** | `list-cache` | List repository cache |
| **Clear Cache** | `clear-cache [--older-than <days>] [--all]` | Clear repository cache |

## 2. MCP Server Resources
**Base**: `python bin/mcp_manager.py`

- **List**: `list`
- **Add**: `add <name> [--env K=V] [-i]`
- **Rm**: `remove <name>`
- **Test**: `test <name>`
- **Presets**: `context7`, `tavily`, `filesystem`, `github`, `sqlite`, `memory`

## 3. Automation Tasks (Hooks Manager)
**Base**: `python bin/hooks_manager.py`

- **Execute**: `execute [--hook-type <type>] [--force]`
- **Trigger**: `trigger --hook-name <name>`
- **List**: `list`
- **Enable**: `enable --hook-name <name>`
- **Disable**: `disable --hook-name <name>`

**Auto Hooks** (system auto-triggered):
- `log_rotate` (Session Start)
- `check_disk_space` (Session Start)
- `cleanup_workspace` (Delivery)
- `refresh_skills_on_start` (Session Start)
- `security_scan_on_install` (Post-Install) - Auto scan skill security
- `cleanup_old_downloads` (Session Start)
- `create_delivery_snapshot` (Delivery)

## 4. File Editing (File Editor)
**Base**: `python bin/file_editor.py`

- **Replace**: `replace <file> <old> <new>`
- **Regex**: `regex <file> <pattern> <replacement> [count=0]`
- **Append**: `append <file> <content>`
- **Prepend**: `prepend <file> <content>`
- **Insert After**: `insert-after <file> <marker> <content>`
- **Insert Before**: `insert-before <file> <marker> <content>`
- **Delete Between**: `delete-between <file> <start_marker> <end_marker>`
- **Update JSON**: `update-json <file> <field_path> <value>`

## 5. External Access Protocol (Ext. Access)

| Zone | Path | Permission | Role |
|:---|:---|:---|:---|
| **Core** | `bin/` | 🔒 **Read-Only** | Execute only, modifications prohibited |
| **Memory** | `.claude/` | 🟡 **Kernel R/W** | State persistence |
| **Work** | `mybox/` | ⚡ **Free R/W** | Only sandbox environment |
| **Output** | `delivery/` | 🟢 **Write-Once** | Final deliverables |

## 6. Version Information (Version)

### GitHub Protocol
⚠️ **STRICT RULE**: Prohibit direct `git clone` or `curl`. Must go through accelerator/resolver.

Repository operations use `clone_manager.py` (see Section 1.1).

**Last Updated**: 2026-02-27
**Ver**: v7.0 (Add: #skill-install-agent; Deprecate: skill_install_workflow.py)

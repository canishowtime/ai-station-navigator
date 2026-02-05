# Vector Registry (算子注册表)

**Context**: Level 2 Registry
**Parent**: `CLAUDE.md`
**Doc Base**: `docs/guides/` (若参数不清，查阅对应指南)

## 1. 技能域 (Skill & Scan)
**Base**: `python bin/`

⚠️ **禁止 Kernel 直接调用** → 必须通过 `worker_agent` 派发 (CLAUDE.md:232)

| Intent | Command Signature | Note |
|:---|:---|:---|
| **Install** | `skill_install_workflow.py <url> [--skill <name>] [--force]` | **推荐**: 完整工作流(clone→scan→LLM→install) |
| **Install** | `skill_manager.py install <src>` | 快速安装(本地/包)，无扫描 |
| **Uninstall** | `skill_manager.py uninstall <name> [...]` | **Sync DB Auto, 支持批量** |
| **List** | `skill_manager.py list` | 查看已装技能 |
| **Search** | `skill_manager.py search <kw>` | 见 CLAUDE.md 协议 |
| **Verify Config** | `skill_manager.py verify-config [--fix]` | 验证配置文件 |
| **Scan** | `security_scanner.py scan <target>` | 扫描单个技能 |
| **Scan All** | `security_scanner.py scan-all` | 扫描所有已安装技能 |
| **Scan Config** | `security_scanner.py config` | 查看安全扫描配置 |

### 1.1 仓库管理 (Repo)
**Base**: `python bin/clone_manager.py`

| Intent | Command Signature | Note |
|:---|:---|:---|
| **Clone** | `clone <url> [--ref <branch>] [--depth <n>]` | 克隆 GitHub 仓库 |
| **List Cache** | `list-cache` | 列出仓库缓存 |
| **Clear Cache** | `clear-cache [--older-than <days>] [--all]` | 清理仓库缓存 |

## 2. MCP 资源 (MCP Server)
**Base**: `python bin/mcp_manager.py`

- **List**: `list`
- **Add**: `add <name> [--env K=V] [-i]`
- **Rm**: `remove <name>`
- **Test**: `test <name>`
- **Presets**: `context7`, `tavily`, `filesystem`, `github`, `sqlite`, `memory`

## 4. 文件编辑 (File Editor)
**Base**: `python bin/hooks_manager.py`

- **Execute**: `execute [--hook-type <type>] [--force]`
- **Trigger**: `trigger --hook-name <name>`
- **List**: `list`
- **Enable**: `enable --hook-name <name>`
- **Disable**: `disable --hook-name <name>`

**Auto Hooks** (系统自动触发):
- `log_rotate` (Session Start)
- `check_disk_space` (Session Start)
- `cleanup_workspace` (Delivery)
- `refresh_skills_on_start` (Session Start)
- `security_scan_on_install` (Post-Install) - 自动扫描技能安全性
- `cleanup_old_downloads` (Session Start)
- `create_delivery_snapshot` (Delivery)

## 5. 文件系统权限 (FS Map)
**Base**: `python bin/file_editor.py`

- **Replace**: `replace <file> <old> <new>`
- **Regex**: `regex <file> <pattern> <replacement> [count=0]`
- **Append**: `append <file> <content>`
- **Prepend**: `prepend <file> <content>`
- **Insert After**: `insert-after <file> <marker> <content>`
- **Insert Before**: `insert-before <file> <marker> <content>`
- **Delete Between**: `delete-between <file> <start_marker> <end_marker>`
- **Update JSON**: `update-json <file> <field_path> <value>`

## 6. 外部访问协议 (Ext. Access)

| Zone | Path | Permission | Role |
|:---|:---|:---|:---|
| **Core** | `bin/` | 🔒 **Read-Only** | 仅执行，禁修改 |
| **Memory** | `.claude/` | 🟡 **Kernel R/W** | 状态持久化 |
| **Work** | `mybox/` | ⚡ **Free R/W** | 唯一的沙盒环境 |
| **Output** | `delivery/` | 🟢 **Write-Once** | 最终交付物 |

## 7. 版本信息 (Version)

### GitHub Protocol
⚠️ **STRICT RULE**: 禁止直接 `git clone` 或 `curl`。必须经过加速器/解析器。

| Action | Tool Command |
|:---|:---|
| **DB Import** | `python bin/skills_db_sync.py --import <json>` |
| **Get File** | `python bin/gh_fetch.py raw <user/repo/branch/path>` |

**Last Updated**: 2026-02-04
**Ver**: v6.0 (Remove: improvement_manager; Add: skill_install_workflow, clone_manager)
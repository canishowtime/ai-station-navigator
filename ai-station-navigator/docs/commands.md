# Vector Registry (算子注册表)

**Context**: Level 2 Registry
**Parent**: `CLAUDE.md`
**Doc Base**: `docs/guides/` (若参数不清，查阅对应指南)

## 1. 技能域 (Skill & Scan)
**Base**: `python bin/`

| Intent | Command Signature | Note |
|:---|:---|:---|
| **Install** | `skill_manager.py install <src>` | 支持 URL/Path/Name |
| **Uninstall** | `skill_manager.py uninstall <name>` | **Sync DB Auto** |
| **List** | `skill_manager.py list` | 查看已装技能 |
| **Search** | `skill_manager.py search <kw>` | 见 CLAUDE.md 协议 |
| **Info** | `skill_manager.py info <repo>` | 分析远程仓库（不克隆） |
| **Create** | `skill_creator.py init <name>` | 初始化模板 |
| **Validate** | `skill_creator.py validate <path>` | 格式校验 |

## 2. 系统改进 (Improvements)
**Base**: `python bin/improvement_manager.py`

| Intent | Sub-Command | Flags |
|:---|:---|:---|
| **New (Full)** | `create <title>` | `--priority high` |
| **New (Quick)** | `create <title>` | `--quickfix` |
| **List** | `list` | 查看积压事项 |
| **Update** | `update <id>` | 更新状态/内容 |
| **Done** | `complete <id>` | 标记完成 |
| **Check** | `python bin/improvement_checklist.py check <id>` | 验收检查单 |

## 3. MCP 资源 (MCP Server)
**Base**: `python bin/mcp_manager.py`

- **List**: `list`
- **Add**: `add <name> [--env K=V] [-i]`
- **Rm**: `remove <name>`
- **Test**: `test <name>`
- **Presets**: `context7`, `tavily`, `filesystem`, `github`, `sqlite`, `memory`

## 4. 自动挂钩 (Auto Hooks)
*系统自动触发，无需手动调用*

- `log_rotate` (Session Start)
- `check_disk_space` (Session Start)
- `cleanup_workspace` (Delivery)
- `sync_skill_status` (Post-Install/Uninstall)

## 5. 文件系统权限 (FS Map)

| Zone | Path | Permission | Role |
|:---|:---|:---|:---|
| **Core** | `bin/` | 🔒 **Read-Only** | 仅执行，禁修改 |
| **Memory** | `.claude/` | 🟡 **Kernel R/W** | 状态持久化 |
| **Work** | `mybox/` | ⚡ **Free R/W** | 唯一的沙盒环境 |
| **Output** | `delivery/` | 🟢 **Write-Once** | 最终交付物 |

## 6. 外部访问协议 (Ext. Access)

### GitHub Protocol
⚠️ **STRICT RULE**: 禁止直接 `git clone` 或 `curl`。必须经过加速器/解析器。

| Action | Tool Command |
|:---|:---|
| **DB Import** | `python bin/skills_db_sync.py --import <json>` |
| **Get File** | `python bin/gh_fetch.py raw <user/repo/branch/path>` |

**Last Updated**: 2026-01-28
**Ver**: v5.2 (Opt)
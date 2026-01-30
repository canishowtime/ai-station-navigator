# Filesystem Architecture (文件系统架构)

**Context**: Level 2 Architecture
**Parent**: `CLAUDE.md`
**Rule**: 所有 I/O 操作严格遵循以下权限位 (Permission Bits)。

## 1. 拓扑与权限 (Topology & Permissions)

```text
project-root/
├── bin/                     🔒 [RO]  Core Logic (严禁修改/写入)
├── .claude/                 🟡 [Sys] System Config (仅限 manager 操作)
│   ├── agents/              📋 Agent Definitions
│   ├── memory/              💾 User Preferences
│   ├── skills/              ⚙️  Active Skills
│   └── state/               🔄 Runtime State
├── mybox/                   ⚡ [RW]  Sandbox (唯一自由读写区)
│   ├── workspace/           ↻  [Work] 处理中心
│   ├── temp/                ✕  [Tmp] 临时缓存
│   ├── output/              📤 [Out] 最终产物
│   ├── lib/                 📚 用户库
│   └── skills/              🧪 本地技能测试
├── docs/                    📖 [RO]  Documentation
│   ├── commands.md          📋 命令注册表
│   ├── filesystem.md        📁 文件系统规范
│   ├── skills-quickstart.md ⚡ 技能快速入门
│   ├── skill-support.md     🛠️ 技能支持清单
│   ├── tinydb-schema.md     🗄️ 数据库模式
│   ├── guides/              📚 操作指南
│   │   ├── README.md                    总览索引
│   │   ├── skill-manager-guide.md       技能管理
│   │   └── mcp-manager-guide.md         MCP 管理
├── tests/                   🧪 [RO]  Test Suite
├── CLAUDE.md                📜 Core Protocol
└── README.md                📄 Project Info
```

## 2. 数据管道 (Data Pipelines)

### A. 技能部署流 (Install Pipeline)
`External Source` -> `mybox/temp/` (Download) -> **Validate** -> `.claude/skills/` (Deploy)

### B. 任务执行流 (Task Pipeline)
1. **Ingest**: 外部文件 -> `mybox/temp/`
2. **Process**: 读写交互 -> `mybox/workspace/`
3. **Commit**: 最终产物 -> `mybox/output/`
4. **GC**: 任务结束 -> 清理 `mybox/workspace/` 和 `mybox/temp/`

## 3. 核心约束 (Core Constraints)

1.  **沙盒默认 (Default Sandboxing)**:
    - 若用户未指定路径，写操作**必须**指向 `mybox/workspace/`。
    - 禁止在 `project-root/` 根目录创建文件。

2.  **易失性 (Volatility)**:
    - `mybox/` 视为**易失性存储** (可随时被清理)。
    - 需要持久化的配置存入 `.claude/`，产物存入 `mybox/output/`。

3.  **原子性 (Atomicity)**:
    - `mybox/output/` 写入完成后建议不再修改（需创建新版本）。

## 4. 清理机制 (Cleanup)

| 触发条件 | 清理内容 |
|:---|:---|
| 会话开始 | log_rotate (轮转日志) |
| 会话开始 | cleanup_old_downloads (清理旧下载) |
| 交付完成 | cleanup_workspace (清理工作区) |

### 手动操作
```bash
# 触发所有 Hooks
python bin/hooks_manager.py execute --force

# 启用/禁用 Hook
python bin/hooks_manager.py enable --hook-name log_rotate
python bin/hooks_manager.py disable --hook-name log_rotate
```

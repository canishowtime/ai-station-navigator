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
│   ├── workspace/           ↻  [Work] 工作区 (任务文件)
│   ├── temp/                ✕  [Tmp] 临时缓存 (自动清理)
│   ├── cache/               💾 持久化缓存
│   │   └── repos/           📦 Git 仓库缓存
│   └── logs/                📝 运行日志
├── docs/                    📖 [RO]  Documentation
│   ├── commands.md          📋 命令注册表
│   ├── filesystem.md        📁 文件系统规范
│   ├── skills-quickstart.md ⚡ 技能快速入门
│   ├── skills-mapping.md    🗺️ 子技能映射表
│   ├── subagent-Protocol.md 📡 子智能体通信协议
│   ├── guides/              📚 操作指南
│   │   ├── README.md                        总览索引
│   │   ├── skill-install-workflow-guide.md  技能安装工作流
│   │   ├── clone-manager-guide.md           仓库克隆管理
│   │   ├── security-scanner-guide.md        安全扫描器
│   │   ├── skill-manager-guide.md           技能管理
│   │   ├── mcp-manager-guide.md             MCP 管理
│   │   ├── file-editor-guide.md             文件编辑器
│   │   ├── gh-fetch-guide.md                GitHub 资源获取
│   │   └── hooks-manager-guide.md           钩子管理
├── tests/                   🧪 [RO]  Test Suite
├── mazilin_workflows/       🔄 [RW]  官方工作流应用存储
│   ├── README.md            📋 工作流总览
│   └── *.md                 📄 各工作流文档
├── CLAUDE.md                📜 Core Protocol
└── README.md                📄 Project Info
```

## 1.1 mybox 路径规范 (Path Specification)

**目录用途定义**:

| 路径 | 用途 | 易失性 | 清理时机 |
|:---|:---|:---|:---|
| `workspace/` | 工作文件 (按任务名组织) | 中 | 任务完成后 |
| `temp/` | 临时文件 (下载/中间产物) | 高 | 自动/定期清理 |
| `cache/repos/` | Git 仓库缓存 | 低 | 手动清理 |
| `logs/` | 运行日志 | 低 | 自动轮转 |

**路径选择规则**:
```
写入需求 → 文件类型？
    ├─ 临时/下载 → mybox/temp/
    ├─ 持久化缓存 → mybox/cache/
    ├─ 工作文件 → mybox/workspace/<task-name>/
    ├─ 工作流文档 → mazilin_workflows/<workflow-name>.md
    └─ 日志 → mybox/logs/
```

## 2. 数据管道 (Data Pipelines)

### A. 技能部署流 (Install Pipeline)
`External Source` -> `mybox/temp/` (Download) -> **Validate** -> `.claude/skills/` (Deploy)

### B. 任务执行流 (Task Pipeline)
1. **Ingest**: 外部文件 -> `mybox/temp/`
2. **Process**: 工作文件 -> `mybox/workspace/<task>/`
3. **GC**: 任务结束 -> 清理 `mybox/temp/` 和 `mybox/workspace/<task>/`

## 3. 核心约束 (Core Constraints)

1.  **沙盒默认 (Default Sandboxing)**:
    - 若用户未指定路径，写操作**必须**指向 `mybox/workspace/`。
    - 禁止在 `project-root/` 根目录创建文件。

2.  **易失性 (Volatility)**:
    - `mybox/` 视为**易失性存储** (可随时被清理)。
    - 需要持久化的配置存入 `.claude/`。

3.  **任务隔离 (Task Isolation)**:
    - 每个任务使用独立子目录：`mybox/workspace/<task-name>/`

## 4. 清理机制 (Cleanup)

| 触发条件 | 清理内容 |
|:---|:---|
| 会话开始 | log_rotate (轮转日志) |
| 会话开始 | cleanup_temp (清理临时文件) |
| 任务完成 | cleanup_workspace (清理任务目录) |

### 手动操作
```bash
# 触发所有 Hooks
python bin/hooks_manager.py execute --force

# 清理特定目录
rm -rf mybox/temp/*
rm -rf mybox/workspace/<task-name>/
```

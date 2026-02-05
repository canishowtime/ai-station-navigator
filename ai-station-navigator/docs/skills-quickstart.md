# 技能系统快速上手

**版本**: v2.6 | **更新**: 2026-02-04

---

## 系统导航

```
┌─────────────────────────────────────────────────────────┐
│                    AI Station Navigator                   │
│                       技能系统导航                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  📥 [技能管理]     → guides/skill-manager-guide.md      │
│  🔌 [MCP 管理]     → guides/mcp-manager-guide.md        │
│  📋 [命令注册表]   → commands.md                        │
│  📁 [文件系统]     → filesystem.md                      │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 核心命令速查

### 技能管理

| 命令 | 说明 | 详细文档 |
|:---|:---|:---|
| `python bin/skill_manager.py list` | 列出已安装技能 | [skill-manager-guide](./guides/skill-manager-guide.md) |
| `python bin/skill_manager.py search <关键词>` | 搜索技能 | [skill-manager-guide](./guides/skill-manager-guide.md) |
| `python bin/skill_manager.py install <本地路径>` | 安装技能 | [skill-manager-guide](./guides/skill-manager-guide.md) |
| `python bin/skill_manager.py uninstall <名称>` | 卸载技能 | [skill-manager-guide](./guides/skill-manager-guide.md) |

### MCP 服务器管理

| 命令 | 说明 | 详细文档 |
|:---|:---|:---|
| `python bin/mcp_manager.py list` | 列出 MCP 服务器 | [mcp-manager-guide](./guides/mcp-manager-guide.md) |
| `python bin/mcp_manager.py add <模板名>` | 添加预设服务器 | [mcp-manager-guide](./guides/mcp-manager-guide.md) |
| `python bin/mcp_manager.py remove <名称>` | 移除服务器 | [mcp-manager-guide](./guides/mcp-manager-guide.md) |
| `python bin/mcp_manager.py test <名称>` | 测试连接 | [mcp-manager-guide](./guides/mcp-manager-guide.md) |

### GitHub 源处理

| 命令 | 说明 |
|:---|:---|
| `python bin/clone_manager.py clone <URL>` | 克隆 GitHub 仓库到缓存 |

---

## 快速工作流

### 安装 GitHub 技能

```bash
# 步骤 1: 克隆仓库
python bin/clone_manager.py clone https://github.com/user/repo

# 步骤 2: 安装技能（从缓存）
python bin/skill_manager.py install mybox/cache/repos/user-repo/skill-name
```

### 添加 MCP 服务器

```bash
# 无需 API Key
python bin/mcp_manager.py add context7

# 需要 API Key（交互式输入）
python bin/mcp_manager.py add tavily -i

# 需要 API Key（命令行参数）
python bin/mcp_manager.py add tavily --env TAVILY_API_KEY=xxx
```

---

## 支持的技能格式

| 格式 | 说明 | 状态 |
|:---|:---|:---:|
| **Official** | Claude Code 官方格式 (SKILL.md) | ✅ |
| **Claude Plugin** | Claude 插件格式 | ✅ |
| **Agent Skills** | Anthropic Agent Skills | ✅ |
| **Cursor Rules** | Cursor 规则文件 | ✅ |

查看所有格式：`python bin/skill_manager.py formats`

---

## MCP 预设模板

| 模板 | 描述 | 需要 Key |
|:---|:---|:---:|
| `context7` | 编程库文档查询 | ❌ |
| `tavily` | 网络搜索 | ✅ |
| `filesystem` | 文件系统访问 | ❌ |
| `brave-search` | 隐私搜索 | ✅ |
| `github` | GitHub 操作 | ✅ |
| `sqlite` | 数据库查询 | ❌ |
| `memory` | 键值存储 | ❌ |

---

## 验证安装

### 技能验证

```bash
# 列出已安装技能
python bin/skill_manager.py list

# 验证特定技能
python bin/skill_manager.py validate .claude/skills/<name>

# 搜索技能
python bin/skill_manager.py search prompt --score
```

### MCP 验证

```bash
# 列出服务器
python bin/mcp_manager.py list

# 测试连接
python bin/mcp_manager.py test context7
```

---

## 常见问题

**Q: 技能不生效？**
```bash
# 检查 SKILL.md 是否存在
cat .claude/skills/<name>/SKILL.md

# 检查 frontmatter 格式
head -10 .claude/skills/<name>/SKILL.md
```

**Q: 如何从 GitHub 安装技能？**
```bash
# GitHub 源需要先克隆
python bin/clone_manager.py clone https://github.com/user/repo
# 然后从本地缓存安装
python bin/skill_manager.py install mybox/cache/repos/user-repo/skill-name
```

**Q: MCP 服务器启动失败？**
```bash
# 检查命令是否可用
where npx

# 测试连接
python bin/mcp_manager.py test <server-name>
```

---

## 目录结构

```
myagent/
├── .claude/
│   ├── skills/              # 已安装技能
│   │   └── <skill-name>/
│   │       └── SKILL.md
│   └── settings.local.json  # MCP 权限配置
├── .mcp.json                 # MCP 服务器配置
├── bin/
│   ├── skill_manager.py     # 技能管理
│   ├── mcp_manager.py       # MCP 管理
│   └── clone_manager.py     # Git 克隆
├── mybox/
│   ├── workspace/           # 工作文件
│   ├── cache/repos/         # Git 缓存
│   └── backups/mcp/         # MCP 备份
└── docs/
    ├── guides/              # 详细指南
    ├── commands.md          # 命令注册表
    └── filesystem.md        # 文件系统说明
```

---

## 相关文档

### 详细指南
- [Skill Manager 使用指南](./guides/skill-manager-guide.md) - 技能安装、搜索、卸载
- [MCP Manager 使用指南](./guides/mcp-manager-guide.md) - MCP 服务器管理

### 参考文档
- [commands.md](./commands.md) - 完整命令注册表
- [filesystem.md](./filesystem.md) - 文件系统布局
- [CLAUDE.md](../CLAUDE.md) - 内核逻辑核心

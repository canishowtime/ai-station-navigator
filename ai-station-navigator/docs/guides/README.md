# Guides Index (指南索引)

**Level 3 - 详细参考文档**

**上级索引**: `docs/commands.md` | `docs/filesystem.md`

---

## 目录结构

```
docs/guides/
├── 主题指南 (系统核心)
│   ├── skills-guide.md
│   ├── filesystem-guide.md
│   └── hooks-guide.md
│
├── 工具指南 (bin/ 脚本)
│   ├── mcp-manager-guide.md
│   ├── skill-manager-guide.md
│   ├── skill-creator-guide.md
│
└── 参考资料 (docs/ 根目录)
    ├── skills-migration.md
    ├── skills-quickstart.md
    ├── skills-installation.md
    ├── skill-formats-registry.md
    ├── skill-formats-contribution-guide.md
    └── tinydb-schema.md
```

---

## 主题指南

### [skills-guide.md](skills-guide.md)
技能管理完整指南

| 章节 | 内容 |
|:---|:---|
| §1 | 技能架构概述 |
| §2 | 安装命令详解 |
| §3 | 创建自定义技能 |
| §4 | 技能格式与转换 |
| §5 | GitHub 仓库扫描 |
| §6 | 故障排查 |

---

### [filesystem-guide.md](filesystem-guide.md)
文件系统详细指南

| 章节 | 内容 |
|:---|:---|
| §1 | 完整目录结构 |
| §2 | 技能运行时详解 |
| §3 | 源码库管理 |
| §4 | 工作空间流程 |
| §5 | 交付产物管理 |
| §6 | 临时文件清理 |

---

### [hooks-guide.md](hooks-guide.md)

### [hooks-guide.md](hooks-guide.md)
系统钩子详细指南

| 章节 | 内容 |
|:---|:---|
| §1 | 系统概述 |
| §2 | 可用 Hooks |
| §3 | Hooks 管理 |
| §4 | 自定义 Hooks |
| §5 | 状态持久化 |

---

## 工具指南

### [mcp-manager-guide.md](mcp-manager-guide.md)
MCP 管理器详细指南

| 章节 | 内容 |
|:---|:---|
| §1 | 概述与功能特性 |
| §2 | 命令详解（list/add/remove/test） |
| §3 | 预设模板 |
| §4 | 配置文件说明 |
| §5 | 备份与回滚 |
| §6 | 故障排查 |

---

### [skill-manager-guide.md](skill-manager-guide.md)
技能转换器详细指南

- 统一安装接口
- 格式转换逻辑
- 批量安装
- 故障处理

---

### [skill-creator-guide.md](skill-creator-guide.md)
技能创建器详细指南

- SKILL.md 格式规范
- 技能结构验证
- 模板系统
- 最佳实践

---

## 参考资料 (docs/ 根目录)

| 文档 | 说明 |
|:---|:---|
| [skills-quickstart.md](../skills-quickstart.md) | 技能快速入门 |
| [tinydb-schema.md](../tinydb-schema.md) | TinyDB 数据库模式 |

---

## 文档维护

| 文档 | 维护者 | 更新频率 |
|:---|:---|:---|
| 主题指南 | Core Team | 按需更新 |
| 工具指南 | Tool Owner | 随工具更新 |
| 参考资料 | Community | 贡献者维护 |

---

**更新日期**: 2026-01-26
**版本**: v1.2 (添加改进检查指南)

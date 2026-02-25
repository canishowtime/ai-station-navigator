# 操作指南 (Guides)

本目录包含 AI Station Navigator 各核心组件的详细使用指南。

---

## 指南索引

### 核心工具

| 指南 | 说明 |
|:---|:---|
| [Skill Install Workflow Guide](./skill-install-workflow-guide.md) | 技能安装工作流 |

### 仓库与克隆

| 指南 | 说明 |
|:---|:---|
| [Clone Manager Guide](./clone-manager-guide.md) | GitHub 仓库克隆管理器 |
| [GH Fetch Guide](./gh-fetch-guide.md) | GitHub 内容获取工具 |

### 安全与分析

| 指南 | 说明 |
|:---|:---|
| [Security Scanner Guide](./security-scanner-guide.md) | 技能安全扫描器 |

### 系统工具

| 指南 | 说明 |
|:---|:---|
| [File Editor Guide](./file-editor-guide.md) | 无预览文件编辑工具 |
| [Hooks Manager Guide](./hooks-manager-guide.md) | 系统事件钩子管理 |

---

## 快速查找

### 按功能分类

**技能相关**:
- 安装/卸载 → [Skill Manager Guide](./skill-manager-guide.md)
- 自动化安装 → [Skill Install Workflow Guide](./skill-install-workflow-guide.md)
- 安全扫描 → [Security Scanner Guide](./security-scanner-guide.md)

**仓库相关**:
- 克隆仓库 → [Clone Manager Guide](./clone-manager-guide.md)
- 获取文件 → [GH Fetch Guide](./gh-fetch-guide.md)

**系统管理**:
- MCP 管理 → [MCP Manager Guide](./mcp-manager-guide.md)
- 钩子管理 → [Hooks Manager Guide](./hooks-manager-guide.md)
- 文件编辑 → [File Editor Guide](./file-editor-guide.md)

---

## 命令速查

```bash
# 技能管理
python bin/skill_manager.py list                    # 列出技能
python bin/skill_manager.py install <url>           # 安装技能
python bin/skill_manager.py uninstall <name>        # 卸载技能

# 仓库操作
python bin/clone_manager.py clone <url>             # 克隆仓库
python bin/gh_fetch.py raw <user>/<repo>/...         # 获取文件

# 安全扫描
python bin/security_scanner.py scan <path>          # 扫描技能
python bin/security_scanner.py scan-all             # 扫描全部

# MCP 管理
python bin/mcp_manager.py list                      # 列出 MCP
python bin/mcp_manager.py add <name> <url>          # 添加 MCP

# 系统工具
python bin/hooks_manager.py execute --type <type>   # 执行钩子
python bin/file_editor.py replace <file> <old> <new> # 替换文本
```

---

## 贡献指南

如需添加新的指南文档：

1. 文件命名：`<tool-name>-guide.md`
2. 使用小写字母和连字符
3. 更新本 README.md 的索引
4. 遵循现有文档格式

# MCP Manager 使用指南

## 概述

`mcp_manager.py` 是 Model Context Protocol (MCP) 服务器的统一管理工具，负责服务器的安装、配置、测试和维护。

**版本**: v2.1
**文件位置**: `bin/mcp_manager.py`

## 核心功能

| 功能 | 说明 |
|:---|:---|
| **服务器管理** | 添加、移除、列出 MCP 服务器 |
| **权限配置** | 自动管理 MCP 工具的权限配置 |
| **连接测试** | 验证 MCP 服务器连接状态 |
| **备份回滚** | 操作前自动备份，失败自动回滚 |

## 架构

```
Kernel (AI) → MCP Manager → Config Handler → Backup System
```

## 预设模板

系统内置以下预设模板，可快速安装：

| 模板名 | 描述 | 需要 API Key |
|:---|:---|:---|
| `context7` | 查询编程库文档和代码示例 | 否 |
| `tavily` | 网络搜索与内容提取 | 是 |
| `filesystem` | 文件系统访问 | 否 |
| `brave-search` | 隐私友好的网络搜索 | 是 |
| `github` | GitHub 仓库操作 | 是 |
| `sqlite` | SQLite 数据库查询 | 否 |
| `memory` | 键值存储 | 否 |

## 命令参考

### 1. list - 列出所有服务器

```bash
python bin/mcp_manager.py list
```

**输出示例**:
- 已安装服务器的状态（启用/禁用）
- 服务器配置信息
- 可用预设模板列表

### 2. add - 添加服务器

#### 添加预设模板（无需 API Key）

```bash
python bin/mcp_manager.py add context7
```

#### 添加预设模板（命令行提供 API Key）

```bash
python bin/mcp_manager.py add tavily --env TAVILY_API_KEY=your_key
```

#### 添加预设模板（交互式输入）

```bash
python bin/mcp_manager.py add tavily -i
```

#### 添加自定义服务器

```bash
python bin/mcp_manager.py add custom --command npx --args "@org/server@latest" --env API_KEY=xxx
```

**参数说明**:
| 参数 | 说明 |
|:---|:---|
| `name` | 服务器名称（预设模板名或 'custom'） |
| `--command` | 自定义服务器命令 |
| `--args` | 自定义服务器参数（多个） |
| `--env` | 环境变量（KEY=VALUE 格式，可多次使用） |
| `-i, --interactive` | 交互式输入 API Key |

### 3. remove - 移除服务器

```bash
python bin/mcp_manager.py remove tavily
```

**操作说明**:
- 从 `.mcp.json` 移除服务器配置
- 从 `settings.local.json` 移除启用状态
- 操作前自动备份，失败自动回滚

### 4. test - 测试连接

```bash
python bin/mcp_manager.py test context7
```

**测试说明**:
- 验证服务器能否成功启动
- 持续 3 秒后自动终止
- 显示启动状态和进程信息

## 配置文件

### `.mcp.json`

MCP 服务器主配置文件，存储服务器定义：

```json
{
  "mcpServers": {
    "context7": {
      "command": "npx.cmd",
      "args": ["-y", "@upstash/context7-mcp@latest"],
      "env": {},
      "type": "stdio"
    }
  }
}
```

### `.claude/settings.local.json`

Claude 设置文件，包含权限配置：

```json
{
  "permissions": {
    "allow": ["mcp__context7__resolve-library-id"],
    "deny": []
  },
  "enabledMcpjsonServers": ["context7"]
}
```

## 备份机制

### 备份位置

```
mybox/backups/mcp/backup_YYYYMMDD_HHMMSS/
├── mcp.json         # .mcp.json 备份
└── settings.json    # settings.local.json 备份
```

### 自动回滚

任何配置修改操作失败时，系统会自动从最近的备份恢复配置。

## 环境变量处理

### 优先级顺序

1. **命令行 `--env` 参数** (最高优先级)
2. **系统环境变量**
3. **交互式输入** (启用 `-i` 时)

### 支持的格式

```bash
# 简单格式
--env API_KEY=abc123

# 值包含等号
--env TOKEN=abc=def=xyz
```

## 安全注意事项

1. **API Key 安全**:
   - 避免在命令行历史中明文传递 API Key
   - 推荐使用系统环境变量或交互式输入

2. **命令注入防护**:
   - 自定义服务器使用安全启动模式（`shell=False`）
   - 禁止直接执行 shell 命令

3. **备份管理**:
   - 定期清理旧备份
   - 备份文件包含敏感信息，注意保护

## 工作流程示例

### 完整安装流程

```bash
# 1. 列出可用模板
python bin/mcp_manager.py list

# 2. 添加服务器（无 Key）
python bin/mcp_manager.py add context7

# 3. 添加服务器（有 Key，交互式）
python bin/mcp_manager.py add tavily -i
# 输入提示: 请输入 TAVILY_API_KEY: ********

# 4. 测试连接
python bin/mcp_manager.py test tavily

# 5. 确认安装状态
python bin/mcp_manager.py list
```

### 卸载流程

```bash
# 1. 移除服务器
python bin/mcp_manager.py remove tavily

# 2. 验证移除结果
python bin/mcp_manager.py list
```

## 故障排除

### 常见问题

| 问题 | 解决方案 |
|:---|:---|
| `未找到命令: npx` | 安装 Node.js，确保 npx 在 PATH 中 |
| `缺少必需的 API Key` | 使用 `--env KEY=VALUE` 或 `-i` 参数 |
| `服务器启动失败` | 检查命令路径和网络连接 |
| `配置保存失败` | 检查文件权限，确保目录可写 |

### 调试模式

查看详细输出：
```bash
python bin/mcp_manager.py add <name> --env KEY=value -v
```

## 相关文档

- [MCP 官方规范](https://modelcontextprotocol.io/)
- `docs/filesystem.md` - 文件系统布局说明
- `docs/commands.md` - 命令注册表

# MCP Manager Guide (MCP 管理器指南)

**统一管理 Model Context Protocol 服务器**

---

## 1. 概述

### 1.1 工具定位

`mcp_manager.py` 是 MCP 服务器的统一管理工具，负责：

- **服务器安装** - 一键添加预设模板或自定义 MCP 服务器
- **权限配置** - 自动管理 MCP 工具的权限配置
- **连接测试** - 验证 MCP 服务器连接状态
- **备份回滚** - 操作前自动备份，失败自动回滚

### 1.2 在系统中的位置

```
.mcp.json (服务器配置)
    ↓ 管理
bin/mcp_manager.py (统一管理工具)
    ↓ 同步
.claude/settings.local.json (权限 + 启用状态)
```

### 1.3 v2.1 功能特性

- ✅ 预设模板系统（context7, tavily, filesystem 等）
- ✅ 自动权限配置
- ✅ API Key 多种配置方式（命令行/交互式/环境变量）
- ✅ 自动备份与回滚
- ✅ 连接测试功能

---

## 2. 命令详解

### 2.1 list - 列出所有 MCP 服务器

**语法**:
```bash
python bin/mcp_manager.py list
```

**输出示例**:
```
============================================================
                         MCP 服务器列表
============================================================

[启用] context7
  命令: npx.cmd -y @upstash/context7-mcp@latest

可用的预设模板:
  - context7: Context7 - 查询编程库文档和代码示例 [已安装]
  - tavily: Tavily - 网络搜索与内容提取
  - filesystem: Filesystem - 文件系统访问（需要配置路径）
  ...
```

---

### 2.2 add - 添加 MCP 服务器

**语法**:
```bash
python bin/mcp_manager.py add <name> [选项]
```

**选项**:
| 选项 | 说明 |
|:---|:---|
| `--command` | 自定义服务器命令（仅用于 custom） |
| `--args` | 自定义服务器参数列表 |
| `--env` | 环境变量 (KEY=VALUE) |
| `-i`, `--interactive` | 交互式输入 API Key |

---

#### 预设模板（无需 API Key）

```bash
python bin/mcp_manager.py add context7
```

---

#### 预设模板（需要 API Key）

**Tavily (mcp-remote 方式)**:
```bash
python bin/mcp_manager.py add tavily --env TAVILY_API_KEY=your_key_here
```
> 注意: Tavily 使用 `mcp-remote` 通过远程 URL 连接，API Key 会嵌入 URL 中

**其他服务器 - 方式 A: 命令行参数**
```bash
python bin/mcp_manager.py add brave-search --env BRAVE_API_KEY=your_key_here
```

**其他服务器 - 方式 B: 交互式输入（隐藏显示）**
```bash
python bin/mcp_manager.py add github -i
# → 请输入 GITHUB_TOKEN: ********
```

**其他服务器 - 方式 C: 系统环境变量**
```bash
# Windows
set BRAVE_API_KEY=your_key_here

# Linux/Mac
export BRAVE_API_KEY=your_key_here

# 添加时自动读取
python bin/mcp_manager.py add brave-search
```

---

#### 自定义服务器

```bash
python bin/mcp_manager.py add custom --command npx --args "@org/server@latest" --env API_KEY=xxx
```

---

### 2.3 remove - 移除 MCP 服务器

**语法**:
```bash
python bin/mcp_manager.py remove <name>
```

**示例**:
```bash
python bin/mcp_manager.py remove tavily
```

---

### 2.4 test - 测试 MCP 服务器连接

**语法**:
```bash
python bin/mcp_manager.py test <name>
```

**示例**:
```bash
python bin/mcp_manager.py test context7
```

**输出**:
```
[i] 测试 MCP 服务器: context7
[i]
执行命令: npx.cmd -y @upstash/context7-mcp@latest
[OK] 连接成功！
```

---

## 3. 预设模板

### 3.1 内置模板列表

| 模板名 | 描述 | 需要 API Key | 连接方式 |
|:---|:---|:---:|:---|
| **context7** | 查询编程库文档和代码示例 | ❌ | npm |
| **tavily** | 网络搜索与内容提取 | ✅ TAVILY_API_KEY | mcp-remote |
| **filesystem** | 文件系统访问 | ❌（需配置路径） | npm |
| **brave-search** | 隐私友好的网络搜索 | ✅ BRAVE_API_KEY | npm |
| **github** | GitHub 仓库操作 | ✅ GITHUB_TOKEN | npm |
| **sqlite** | SQLite 数据库查询 | ❌ | npm |
| **memory** | 键值存储 | ❌ | npm |

**Tavily 特殊说明**: 使用 `mcp-remote` 通过远程 URL 连接，API Key 嵌入在 URL 中，无需环境变量配置。

### 3.2 发现更多 MCP 服务器

**官方来源** (推荐):

| 来源 | URL | 说明 |
|:---|:---|:---|
| **MCP 官方文档** | https://modelcontextprotocol.io/servers | 官方维护的服务器列表 |
| **npm 搜索** | https://www.npmjs.com/search?q=mcp-server | 搜索 `mcp-server` 包 |
| **GitHub 组织** | https://github.com/modelcontextprotocol | 官方组织仓库 |

**按功能分类**:

| 功能 | 包名/URL | 连接方式 | 工具类型 |
|:---|:---|:---:|:---|
| **搜索** | `mcp-remote` + Tavily URL | mcp-remote | 网络搜索 |
| **搜索** | `@modelcontextprotocol/server-brave-search` | npm | Brave 搜索 |
| **文档** | `@upstash/context7-mcp@latest` | npm | 编程库文档 |
| **数据** | `@modelcontextprotocol/server-sqlite` | npm | SQLite 数据库 |
| **数据** | `@modelcontextprotocol/server-memory` | npm | 键值存储 |
| **文件** | `@modelcontextprotocol/server-filesystem` | npm | 文件系统 |
| **集成** | `@modelcontextprotocol/server-github` | npm | GitHub 操作 |

**连接方式说明**:
- **npm**: 通过 `npx` 安装并运行 npm 包
- **mcp-remote**: 通过 `npx -y mcp-remote` 连接远程 MCP 服务器 URL

**添加新服务器**:

```bash
# 方式 A: 使用内置预设
python bin/mcp_manager.py add context7

# 方式 B: 添加自定义 npm 包
python bin/mcp_manager.py add custom --command npx --args "@org/package@latest"
```

---

## 4. 配置文件说明

### 4.1 .mcp.json

定义 MCP 服务器及其命令/参数：

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

### 4.2 .claude/settings.local.json

控制启用状态和权限：

```json
{
  "permissions": {
    "allow": [
      "mcp__context7__resolve-library-id",
      "mcp__context7__query-docs"
    ]
  },
  "enabledMcpjsonServers": ["context7"]
}
```

---

## 5. 备份与回滚

每次操作前自动备份到 `mybox/backups/mcp/backup_<timestamp>/`：

```
mybox/backups/mcp/
└── backup_20260126_133145/
    ├── mcp.json          # .mcp.json 备份
    └── settings.json     # settings.local.json 备份
```

操作失败时自动回滚到上一个备份。

---

## 6. 错误代码对照表

| 错误信息 | 可能原因 | 解决方案 |
|:---|:---|:---|
| `MCP 服务器 'xxx' 不存在` | 服务器名称拼写错误或未安装 | 使用 `list` 命令查看已安装的服务器 |
| `未找到命令: npx` | Node.js 或 npx 未安装 | 安装 Node.js: https://nodejs.org/ |
| `缺少必需的 API Key: XXX` | 未配置所需的环境变量 | 使用 `--env KEY=VALUE` 或 `-i` 交互式输入 |
| `未提供 xxx，取消安装` | 交互式输入时未提供值 | 确保输入有效值或取消后重试 |
| `服务器 'xxx' 启动失败（返回码: N）` | 服务器配置错误或 API Key 无效 | 检查 API Key 有效性，查看错误输出 |
| `连接超时（服务器可能正在启动）` | 服务器启动缓慢 | 等待后重试，或检查网络连接 |
| `备份失败` | 磁盘空间不足或权限问题 | 检查磁盘空间和 `mybox/backups/mcp/` 权限 |

---

## 7. 故障排查

### 连接测试失败

**问题**: `test` 命令返回错误

**解决方案**:
1. 检查命令路径是否正确（Windows 需使用 `npx.cmd`）
2. 确认 Node.js 和 npx 已安装
3. 检查 API Key 是否正确配置

### 权限未生效

**问题**: 添加服务器后工具不可用

**解决方案**:
1. 检查 `.claude/settings.local.json` 中的 `permissions.allow`
2. 重启 Claude 使配置生效

### 环境变量问题

**问题**: API Key 配置后仍提示缺失

**解决方案**:
1. 使用 `-i` 交互式输入
2. 或使用 `--env KEY=VALUE` 命令行参数
3. 或在系统环境变量中设置

---

**更新日期**: 2026-01-26
**版本**: v2.1

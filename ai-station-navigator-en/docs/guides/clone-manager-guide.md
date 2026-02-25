# Clone Manager Guide

**GitHub 仓库克隆管理器**

负责从 GitHub 克隆技能仓库到本地暂存空间，支持加速器、缓存管理和远程仓库分析。

---

## 功能概览

| 功能 | 说明 |
|:---|:---|
| **仓库克隆** | 支持加速器，自动代理 |
| **远程分析** | 预检、缓存、技能提取 |
| **缓存管理** | 列出、清理仓库缓存 |

---

## 命令参考

### 1. 克隆仓库

```bash
python bin/clone_manager.py clone <url> [options]
```

**参数**:
- `<url>` - GitHub 仓库 URL（完整或简写）
- `--ref, -r <branch>` - 指定分支（默认: main）
- `--depth <n>` - 浅克隆深度
- `--no-cache` - 跳过缓存，强制重新克隆
- `--proxy` - 强制使用代理

**示例**:
```bash
# 完整 URL
python bin/clone_manager.py clone https://github.com/user/repo.git

# 简写格式
python bin/clone_manager.py clone user/repo

# 指定分支
python bin/clone_manager.py clone user/repo --ref develop

# 浅克隆（单分支）
python bin/clone_manager.py clone user/repo --depth 1
```

### 2. 列出缓存

```bash
python bin/clone_manager.py list-cache
```

显示所有已缓存的仓库。

### 3. 清理缓存

```bash
python bin/clone_manager.py clear-cache [options]
```

**参数**:
- `--older-than <days>` - 仅清理 N 天前的缓存
- `--all` - 清理所有缓存

**示例**:
```bash
# 清理 7 天前的缓存
python bin/clone_manager.py clear-cache --older-than 7

# 清理所有缓存
python bin/clone_manager.py clear-cache --all
```

---

## 工作流程

```
GitHub URL
    ↓
检查缓存
    ↓
┌─────────┴─────────┐
│                   │
缓存命中         克隆仓库
│                   │
└─────────┬─────────┘
          ↓
    提取技能目录
          ↓
    暂存到 mybox/cache/repos/
```

---

## 路径规范

| 类型 | 路径 |
|:---|:---|
| 缓存根目录 | `mybox/cache/repos/` |
| 仓库存储 | `mybox/cache/repos/<user>/<repo>/` |
| 临时文件 | `mybox/temp/` |

---

## 配置

克隆行为受 `config.json` 中的 `git` 配置影响：

```json
{
  "git": {
    "proxies": [
      "https://gh-proxy.com/github.com/{repo}",
      "https://gitclone.com/github.com/{repo}"
    ],
    "ssl_verify": false
  }
}
```

---

## 常见问题

**Q: 克隆速度慢？**
A: 检查 `config.json` 中的 `git.proxies` 配置，启用加速器。

**Q: 如何强制重新克隆？**
A: 使用 `--no-cache` 参数或先清理缓存。

**Q: 缓存占用空间过大？**
A: 定期运行 `clear-cache --older-than 30` 清理旧缓存。

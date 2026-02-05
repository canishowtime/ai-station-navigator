# GH Fetch Guide

**GitHub 内容获取工具**

自动使用配置的加速器获取 GitHub 内容，支持 raw 文件、仓库克隆和远程分支查询。

---

## 功能概览

| 功能 | 说明 |
|:---|:---|
| **Raw 文件** | 获取 GitHub raw 文件内容 |
| **仓库克隆** | 克隆仓库到本地 |
| **远程查询** | 列出远程仓库分支 |

---

## 命令参考

### 1. 获取 Raw 文件

```bash
python bin/gh_fetch.py raw <user>/<repo>/<branch>/<path>
```

**参数**:
- `<user>` - GitHub 用户名
- `<repo>` - 仓库名
- `<branch>` - 分支名
- `<path>` - 文件路径

**示例**:
```bash
# 获取 README
python bin/gh_fetch.py raw user/repo/main/README.md

# 获取技能定义
python bin/gh_fetch.py raw mrgoonie/claudekit-skills/main/.claude/skills/mermaidjs-v11/skill.md

# 获取嵌套文件
python bin/gh_fetch.py raw user/repo/develop/docs/config.json
```

### 2. 克隆仓库

```bash
python bin/gh_fetch.py clone <url> [dest]
```

**参数**:
- `<url>` - GitHub 仓库 URL
- `[dest]` - 目标目录（可选）

**示例**:
```bash
# 克隆到当前目录
python bin/gh_fetch.py clone https://github.com/user/repo.git

# 克隆到指定目录
python bin/gh_fetch.py clone https://github.com/user/repo.git my-repo
```

### 3. 查询远程分支

```bash
python bin/gh_fetch.py ls-remote <url>
```

**示例**:
```bash
python bin/gh_fetch.py ls-remote https://github.com/user/repo.git
```

---

## 加速器配置

工具自动读取 `config.json` 中的 `raw.proxies` 配置：

```json
{
  "raw": {
    "proxies": [
      "https://ghfast.top/https://raw.githubusercontent.com/{path}"
    ]
  }
}
```

**加速优先级**:
1. 依次尝试 `proxies` 列表中的镜像
2. 全部失败后回退到官方源

---

## 使用场景

### 场景 1: 快速查看文件

```bash
# 不克隆整个仓库，直接查看文件
python bin/gh_fetch.py raw user/repo/main/package.json | jq .
```

### 场景 2: 批量获取技能定义

```bash
# 获取多个技能的 SKILL.md
for skill in markdown-converter pdf-extractor; do
  python bin/gh_fetch.py raw user/skills-repo/main/skills/$skill/skill.md
done
```

### 场景 3: 仓库预检

```bash
# 先查看分支，再决定克隆
python bin/gh_fetch.py ls-remote https://github.com/user/repo.git
```

---

## 与 Clone Manager 的区别

| 特性 | gh_fetch | clone_manager |
|:---|:---|:---|
| **用途** | 快速获取内容 | 完整克隆+分析 |
| **加速器** | raw.proxies | git.proxies |
| **缓存** | 无 | 支持 |
| **技能提取** | 不支持 | 支持 |

**选择建议**:
- 只需查看文件 → 使用 `gh_fetch raw`
- 需要完整仓库 → 使用 `clone_manager clone`
- 需要技能提取 → 使用 `clone_manager clone`

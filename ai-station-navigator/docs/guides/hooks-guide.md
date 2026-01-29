# Hooks System Guide (系统钩子详细指南)

**Level 3 - 详细参考文档**

**上级索引**: `docs/commands.md`

---

## 目录
1. [系统概述](#1-系统概述)
2. [可用 Hooks](#2-可用-hooks)
3. [Hooks 管理](#3-hooks-管理)
4. [自定义 Hooks](#4-自定义-hooks)
5. [状态持久化](#5-状态持久化)

---

## 1. 系统概述

### 什么是 Hooks

Hooks 是在特定事件触发时自动执行的脚本，用于自动化维护任务。

### 触发时机

```
会话开始 → [log_rotate, check_disk_space, cleanup_old_downloads]
交付完成 → [cleanup_workspace]
```

### 存储位置

```
.claude/
├── agents/
│   └── hooks/           # Hooks 定义
└── state/
    └── hooks.json       # Hooks 状态
```

---

## 2. 可用 Hooks

### log_rotate (日志轮转)

| 属性 | 值 |
|:---|:---|
| **触发时机** | 会话开始 |
| **功能** | 轮转日志文件，防止单个文件过大 |
| **配置** | 最大文件大小，保留数量 |

### cleanup_workspace (清理工作区)

| 属性 | 值 |
|:---|:---|
| **触发时机** | 交付完成 |
| **功能** | 清理 mybox/workspace/ |
| **配置** | 是否保留特定文件 |

### check_disk_space (磁盘检查)

| 属性 | 值 |
|:---|:---|
| **触发时机** | 会话开始 |
| **功能** | 检查磁盘空间，低于阈值告警 |
| **配置** | 告警阈值 (默认 10GB) |

### cleanup_old_downloads (清理旧下载)

| 属性 | 值 |
|:---|:---|
| **触发时机** | 会话开始 |
| **功能** | 清理 mybox/downloads/ 中 7 天前的文件 |
| **配置** | 保留天数 |

---

## 3. Hooks 管理

### 列出所有 Hooks

```bash
python bin/hooks_manager.py list
```

### 触发 Hooks

```bash
# 强制执行所有 Hooks
python bin/hooks_manager.py execute --force

# 执行特定 Hook
python bin/hooks_manager.py execute --hook-name log_rotate
```

### 启用/禁用 Hook

```bash
# 启用 Hook
python bin/hooks_manager.py enable --hook-name log_rotate

# 禁用 Hook
python bin/hooks_manager.py disable --hook-name log_rotate
```

### 查看 Hook 状态

```bash
python bin/hooks_manager.py status --hook-name log_rotate
```

---

## 4. 自定义 Hooks

### Hook 结构

```python
# .claude/agents/hooks/my_hook.py
from datetime import datetime

def execute(context):
    """
    context: {
        "event": "session_start" | "delivery_complete",
        "timestamp": datetime,
        "workspace": str
    }
    """
    # 实现逻辑
    print(f"Hook executed at {context['timestamp']}")
    return {"success": True}
```

### 注册 Hook

```bash
python bin/hooks_manager.py register --path .claude/agents/hooks/my_hook.py
```

### Hook 配置

```json
{
  "name": "my_hook",
  "enabled": true,
  "trigger": "session_start",
  "config": {
    "threshold": 100
  }
}
```

---

## 5. 状态持久化

### 状态文件

```
.claude/state/hooks.json
```

### 状态结构

```json
{
  "log_rotate": {
    "enabled": true,
    "last_run": "2026-01-26T10:00:00",
    "runs_count": 42
  },
  "cleanup_workspace": {
    "enabled": true,
    "last_run": "2026-01-26T09:30:00",
    "runs_count": 15
  }
}
```

### 读取状态

```python
import json

with open(".claude/state/hooks.json") as f:
    state = json.load(f)
    last_run = state["log_rotate"]["last_run"]
```

---

**更新日期**: 2026-01-26
**版本**: v1.0

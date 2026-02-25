# Hooks Manager Guide

**系统事件钩子管理器**

管理系统事件钩子，支持会话开始/结束、交付完成等时机的自动任务执行。

---

## 功能概览

| 功能 | 说明 |
|:---|:---|
| **钩子执行** | 触发指定类型的所有钩子 |
| **状态管理** | 启用/禁用钩子 |
| **列表查看** | 查看所有钩子状态 |

---

## 内置钩子

| 钩子名称 | 类型 | 说明 |
|:---|:---|:---|
| `log_rotate` | ON_SESSION_START | 日志轮转 |
| `cleanup_temp` | ON_SESSION_START | 清理临时文件 |
| `cleanup_workspace` | ON_DELIVERY | 清理工作区 |

---

## 命令参考

### 1. 执行钩子

```bash
python bin/hooks_manager.py execute --type <type> [--force]
```

**参数**:
- `--type <type>` - 钩子类型 (session_start|session_end|delivery)
- `--force` - 强制执行（忽略禁用状态）

**示例**:
```bash
# 执行所有会话开始钩子
python bin/hooks_manager.py execute --type session_start

# 强制执行所有钩子
python bin/hooks_manager.py execute --type session_start --force
```

### 2. 触发指定钩子

```bash
python bin/hooks_manager.py trigger <hook_name>
```

**示例**:
```bash
python bin/hooks_manager.py trigger log_rotate
python bin/hooks_manager.py trigger cleanup_temp
```

### 3. 列出钩子

```bash
python bin/hooks_manager.py list
```

显示所有钩子的名称、类型和状态。

### 4. 启用/禁用钩子

```bash
python bin/hooks_manager.py enable <hook_name>
python bin/hooks_manager.py disable <hook_name>
```

**示例**:
```bash
# 禁用自动清理
python bin/hooks_manager.py disable cleanup_temp

# 重新启用
python bin/hooks_manager.py enable cleanup_temp
```

---

## 钩子类型

| 类型 | 触发时机 |
|:---|:---|
| `ON_SESSION_START` | 会话开始时 |
| `ON_SESSION_END` | 会话结束时 |
| `ON_DELIVERY` | 任务交付完成时 |

---

## 状态存储

钩子状态存储在 `.claude/state/hooks.json`：

```json
{
  "hooks": [
    {
      "name": "log_rotate",
      "type": "ON_SESSION_START",
      "enabled": true,
      "last_run": "2025-02-04T10:00:00"
    }
  ]
}
```

---

## 自定义钩子

要添加自定义钩子，编辑 `bin/hooks_manager.py`：

```python
# 在 _register_hooks 方法中添加
self.register_hook(
    Hook(
        name="my_custom_hook",
        hook_type=HookType.ON_SESSION_START,
        description="我的自定义钩子",
        action=self._action_my_custom
    ),
    save_state=False
)

# 实现钩子动作
def _action_my_custom(self) -> HookResult:
    # 钩子逻辑
    return HookResult.success("my_custom_hook", "执行成功")
```

---

## 使用场景

### 场景 1: 会话开始自动清理

```bash
# 启用会话开始时的临时文件清理
python bin/hooks_manager.py enable cleanup_temp

# 下次会话开始时自动执行
```

### 场景 2: 任务完成后清理工作区

```bash
# 启用交付时的工作区清理
python bin/hooks_manager.py enable cleanup_workspace

# 任务交付后自动清理 mybox/workspace/
```

### 场景 3: 手动触发清理

```bash
# 不等待会话开始，立即执行清理
python bin/hooks_manager.py trigger cleanup_temp
```

---

## 故障排查

**Q: 钩子没有自动执行？**
A: 检查钩子是否启用：`python bin/hooks_manager.py list`

**Q: 如何强制执行所有钩子？**
A: 使用 `--force` 参数：`python bin/hooks_manager.py execute --type session_start --force`

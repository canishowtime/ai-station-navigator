# Skill Manager Agent 调度协议 v2.0

> **定位**: Kernel ↔ Skill Manager Agent 的通信契约
> **原则**: 仅定义接口，不描述实现

---

## 1. 怎么调

### Task 签名
```
Task(
  "skill_manager_agent",
  "<3-5词任务摘要>",
  "<自然语言指令，包含必要参数>"
)
```

### 调用示例
```yaml
# 安装技能 - 传递原始 URL
Task("skill_manager_agent", "安装技能", "从 https://github.com/user/repo 安装技能")

# 安装指定子技能 - 使用完整子路径 URL（脚本自动解析）
Task("skill_manager_agent", "安装技能", "从 https://github.com/user/repo/tree/main/skills/skill-a 安装")

# 删除技能 - 按名称
Task("skill_manager_agent", "删除技能", "删除技能 skill-a skill-b")

# 删除技能 - 按仓库 URL
Task("skill_manager_agent", "删除技能", "删除 https://github.com/user/repo")

# 恢复安装 (pending 后)
Task("skill_manager_agent", "继续安装", "resume: keep skill-b, uninstall skill-c")
```

---

## 2. 返回什么

### 状态码定义
| 状态 | 含义 | data 字段 |
|:---|:---|:---|
| `success` | 完成 | `installed[]`, `uninstalled[]`, `skipped[]` |
| `pending` | 等待审核 | `threatened_skills[]`, `safe_skills[]`, `cached_paths{}` |
| `partial` | 部分成功 | `installed[]`, `failed[]`, `errors{}` |
| `error` | 失败 | `type`, `reason`, `recoverable` |

### 返回示例

**安装成功**:
```yaml
✅ skill_manager_agent 安装完成: 2/3 成功
  state: success
  data: {
    installed: ["skill-a", "skill-b"],
    skipped: ["skill-c"],
    failed: []
  }
```

**等待审核**:
```yaml
⏸️ skill_manager_agent 等待审核: 1 个技能需决策
  state: pending
  data: {
    threatened_skills: [
      {
        name: "skill-b",
        severity: "MEDIUM",
        threats: [
          {
            rule: "user_input_network_request",
            file: "lib/api.py",
            line: 42,
            code: ">>> def send_data(data):\n...    requests.post(f'https://api.com/{data}', ...)",
            description: "用户输入直接用于URL"
          }
        ],
        threats_count: 3
      }
    ],
    safe_skills: ["skill-a"],
    cached_paths: {
      "skill-a": "mybox/cache/.../skill-a",
      "skill-b": "mybox/cache/.../skill-b"
    },
    meta_json: "mybox/cache/.../.meta.json"  # 用户原始需求记录
  }
```

**删除成功**:
```yaml
✅ skill_manager_agent 删除完成: 2 个技能
  state: success
  data: {
    uninstalled: ["skill-a", "skill-b"],
    db_synced: true
  }
```

**错误**:
```yaml
❌ skill_manager_agent CloneFailed: 仓库不存在
  state: error
  data: {
    type: "CloneFailed",
    url: "https://github.com/user/repo",
    reason: "Repository not found",
    recoverable: false
  }
```

---

## 3. 怎么处理

### 3.1 错误处理

| 错误类型 | recoverable | 处理建议 |
|:---|---:|:---|
| `CloneFailed` | false | 提示检查 URL 和权限 |
| `ScanFailed` | true | 跳过扫描继续安装 |
| `ModuleNotFound` | true | 引导安装依赖 (pip install) |
| `InvalidSkill` | false | 跳过该技能 |
| `InstallFailed` | null | 视具体错误判断 |

### 3.2 pending 恢复流程

```
┌─────────────────────────────────────────┐
│  第一次调用                              │
├─────────────────────────────────────────┤
│  Kernel → Agent: 安装技能               │
│  Agent → Kernel: pending + 威胁详情      │
│    + cached_paths (用于恢复)            │
└─────────────────────────────────────────┘
              ↓ 用户决策
┌─────────────────────────────────────────┐
│  第二次调用 (恢复)                       │
├─────────────────────────────────────────┤
│  Kernel → Agent: resume 任务            │
│    - mode: "resume"                     │
│    - decisions: {技能: "keep/uninstall"}│
│    - safe_skills: [...]                │
│    - cached_paths: {...}               │
│    - skip_scan: true                   │
│  Agent: 跳过克隆/扫描，直接安装          │
│  Agent → Kernel: success 结果           │
└─────────────────────────────────────────┘
```

### 3.3 威胁级别处理

| 级别 | 处理方式 |
|:---|:---|
| `SAFE` | 直接安装 |
| `LOW` | 直接安装 |
| `MEDIUM` | **必须审核** |
| `HIGH` | **必须审核** |
| `CRITICAL` | **强烈建议卸载** |


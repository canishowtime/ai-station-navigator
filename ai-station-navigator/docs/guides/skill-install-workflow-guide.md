# Skill Install Workflow Guide

**技能安装工作流**

基于 LangGraph 的自动化安装流程，串联克隆、扫描、分析、安装等步骤。

---

## 功能概览

| 功能 | 说明 |
|:---|:---|
| **自动化流程** | 克隆 → 扫描 → 分析 → 安装 |
| **状态持久化** | SQLite checkpoint，支持中断恢复 |
| **LLM 分析** | 威胁技能可进行二次分析 |
| **误报处理** | 支持人工干预确认 |

---

## 工作流程

```
┌─────────────────────────────────────────────────────────┐
│                    安装工作流                            │
└─────────────────────────────────────────────────────────┘
                          │
                          ↓
              ┌───────────────────────┐
              │  1. 克隆仓库节点        │
              │  (clone_repo_node)    │
              └───────────┬───────────┘
                          │
                          ↓
              ┌───────────────────────┐
              │  2. 安全扫描节点        │
              │ (security_scan_node)  │
              └───────────┬───────────┘
                          │
                          ↓
              ┌───────────────────────┐
              │  3. 威胁级别检查        │
              │(check_threat_level)   │
              └───────────┬───────────┘
                          │
            ┌─────────────┴─────────────┐
            │                           │
         无威胁                     有威胁
            │                           │
            ↓                           ↓
   ┌───────────────┐         ┌──────────────────┐
   │ 5. 安装技能    │         │ 4. LLM 分析节点   │
   │(install_node) │         │  (可选中断)       │
   └───────────────┘         └────────┬─────────┘
                                      │
                             ┌────────┴────────┐
                             │                 │
                          确认安全           放弃
                             │                 │
                             ↓                 ↓
                    ┌───────────────┐   ┌──────┐
                    │ 5. 安装技能    │   │ END  │
                    └───────────────┘   └──────┘
```

---

## 命令参考

### 运行安装工作流

```bash
python bin/skill_install_workflow.py run <url> [options]
```

**参数**:
- `<url>` - GitHub 仓库 URL
- `--skill <name>` - 指定子技能名
- `--force` - 强制覆盖已安装技能
- `--checkpoint <path>` - 从指定 checkpoint 恢复

**示例**:
```bash
# 基本安装
python bin/skill_install_workflow.py run https://github.com/user/repo.git

# 安装子技能
python bin/skill_install_workflow.py run https://github.com/user/skills.git --skill pdf-converter

# 强制覆盖
python bin/skill_install_workflow.py run user/repo --force

# 从中断恢复
python bin/skill_install_workflow.py run user/repo --checkpoint mybox/temp/langgraph/checkpoints
```

---

## 工作流状态

### 状态字段

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| `github_url` | str | GitHub 仓库 URL |
| `skill_name` | str | 子技能名（可选） |
| `force_install` | bool | 是否强制覆盖 |
| `cloned_repo_path` | str | 克隆的仓库路径 |
| `extracted_skills` | list | 提取的技能目录列表 |
| `scan_results` | dict | 扫描结果 |
| `threatened_skills` | list | 威胁技能列表 |
| `llm_analysis` | dict | LLM 分析结果 |
| `install_decision` | str | 安装决策 |

---

## 中断与恢复

### 中断点

工作流在以下节点会中断（需人工确认）：

1. **威胁检测**: 发现 HIGH/CRITICAL 级别威胁
2. **LLM 分析请求**: 需要用户确认是否进行二次分析

### 恢复执行

```bash
# 查看checkpoint目录
ls mybox/temp/langgraph/checkpoints/

# 从checkpoint恢复
python bin/skill_install_workflow.py run <original-url> --checkpoint mybox/temp/langgraph/checkpoints
```

---

## 使用场景

### 场景 1: 标准安装流程

```bash
# 自动完成：克隆 → 扫描 → 安装
python bin/skill_install_workflow.py run https://github.com/user/skills.git
```

### 场景 2: 子技能安装

```bash
# 只安装仓库中的指定技能
python bin/skill_install_workflow.py run https://github.com/user/skills.git --skill markdown-converter
```

### 场景 3: 威胁处理

```bash
# 发现威胁时自动中断
# 人工审查后决定是否继续
python bin/skill_install_workflow.py run user/suspicious-skills
```

---

## Checkpoint 存储

**路径**: `mybox/temp/langgraph/checkpoints/`

**结构**:
```
mybox/temp/langgraph/checkpoints/
└── <workflow_id>/
    └── <checkpoint_id>.data
```

---

## 依赖要求

```bash
# 安装 LangGraph 相关依赖
pip install langgraph>=0.2.0
pip install typing-extensions>=4.9.0
```

---

## 与 Skill Manager 的区别

| 特性 | skill_install_workflow | skill_manager |
|:---|:---|:---|
| **流程** | 多步骤自动化 | 单步命令 |
| **安全检查** | 内置扫描+分析 | 需手动扫描 |
| **中断恢复** | 支持 checkpoint | 不支持 |
| **LLM 分析** | 支持 | 不支持 |
| **适用场景** | 复杂安装、需要审查 | 快速安装 |

**选择建议**:
- 信任的来源 → 使用 `skill_manager install`
- 不确定安全性 → 使用 `skill_install_workflow run`

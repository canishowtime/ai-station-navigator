# AI Station Navigator 🧭
> **基于 Claude Code 的智能体系统总线与调度器 (Kernel Logic Core)**

<br>

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Engine: Claude Code](https://img.shields.io/badge/Engine-Claude--Code-blue)](https://anthropic.com)
[![Python: 3.8+](https://img.shields.io/badge/Python-3.8+-green)](https://python.org)

<br>

**AI Station Navigator** 是一款基于 Claude Code 引擎构建的模块化 AI 工作站。它模仿计算机组成原理，将繁杂的 AI 任务精准路由至隔离的子智能体（Sub-Agents）执行。项目集成了沙盒化执行环境与“应用商店式”技能管理，配合全绿色的免安装运行环境，旨在为用户提供一个“解压即用”、性能恒定、无限扩展的个人 AI 智慧中枢。

**✅ 模块化架构 | ✅ 沙盒隔离 | ✅ 零预装 | ✅ 应用商店式技能管理**

---

## 🎯 核心设计理念：AI工作站 架构

项目参考计算机组成原理，将 AI 能力转化为稳定、可扩展的系统服务：

### 🏗️ 架构类比

| 物理组件 | 软件映射 | 角色功能描述 |
| --- | --- | --- |
| **中央处理器 (CPU)** | **Claude Code + CLAUDE.md + LLM** | **核心逻辑层**：负责能力驱动、意图识别、指令调度、任务拆解与上下文管理。 |
| **系统进程/线程** | **Sub-Agents (worker/skills)** | **任务执行层**：子智能体隔离运行，**减少对主智能体上下文污染**。 |
| **系统驱动 (Drivers)** | **MCP + Hooks** | **扩展与自动化**：MCP 提供外部资源交互驱动；Hooks 驱动系统自动化管理（日志/空间/状态）。 |
| **应用程序 (Apps)** | **Skills (GitHub 技能仓)** | **功能插件层**：通过 GitHub 链接实现“应用商店式”的一键安装与调用。 |
| **集成环境 (Runtime)** | **Portable Environment** | **底层支撑**：预集成绿色版 Python, Node.js, Git强力底层工具，确保环境高度统一，增强潜在扩展能力。 |

---

## ✨ 核心特性

* 🧠 **内核调度系统 (Kernel)**
* 意图识别：用CLAUDE.md作为指令集，自动判断任务类型并路由至对应处理器。
* 会话隔离：子智能体独立运行，保护主对话 Context 不被冗余数据淹没。


* 🔧 **应用商店式技能管理 (Skills)**
* **零预装设计**：项目本身不内置功能，用户按需从 GitHub 安装技能。
* **一键安装**：支持通过 GitHub 仓库链接直接下载、校验并注册技能。
* **多格式兼容**：支持 SKILL.md、Claude Plugin、Cursor Rules 等。


* 🔌 **系统扩展与驱动 (MCP & Hooks)**
* **MCP 资源驱动**：通过 Model Context Protocol 接入实时搜索、数据库、本地文件等。


* 🛡️ **沙盒化执行环境**
* 严格权限控制：设定内核只读范围，子智能体写入范围，用户自行判断和控制权限。
* 安全隔离：防止 AI 生成的实验性内容造成高风险危害。

---

## 📂 目录结构

```text
ai-station-navigator/
├── .claude/                    # 系统配置区 (注册表)
│   ├── agents/                 # 子智能体定义 (进程)
│   ├── skills/                 # 已安装的应用（应用中心） 
│   └── state/                  # 运行时状态
├── bin/                        # 系统核心脚本 (内核组件)
│   ├── skill_manager.py        # 技能管理器 (应用商店入口)
│   ├── mcp_manager.py          # MCP 驱动管理器
│   └── hooks_manager.py        # 自动化钩子管理器
├── docs/                       # 系统文档 (操作说明)
├── mybox/                      # 沙盒工作区 (个人空间)
│   ├── workspace/              # 任务处理中心
│   └── output/                 # 最终产物导出
├── CLAUDE.md                   # Kernel 逻辑核心 (System CPU)
├── .mcp.json                   # MCP 服务器配置 (驱动配置，可用系统命令自动化配置)
└── requirements.txt            # Python 依赖

```

---

## 🚀 快速开始

### 1. 一键启动

下载**整合包**后，即可实现零配置运行：

1. **启动**：双击根目录下的 `启动 ai-station-navigator.bat`。
2. **就绪**：按照屏幕提示安装缺失组件并输入自行准备的 `LLM-API-KEY`，即可进入启动状态。

### 2. 智能化管理 (对话即指令)

直接在对话框输入以下指令，即可通过 **Sub-Agent** (子进程) 实现技能管理与运行，有效减少对主智能体的上下文污染：
（系统内已配置github网络加速器，解决git源码获取的网络问题，直接黏贴原始地址或路径即可，可以是主项目，也可以是某个子技能）

* **查看能力**：`你现在有哪些技能？`
* **安装应用**：`安装技能：https://github.com/xxx/repo   （自动执行安装，如果主项目是技能包，建议地址路径正确指示到你需要单个技能，否则会安装整个技能包）
* **分析应用**：分析技能：https://github.com/xxx/repo   （自动执行分析，并反馈分析结果和安装建议）
* **使用应用**： `@技能  需求内容`  （自动分析需求匹配已安装技能，确认后可立即执行并返回执行结果）
* **卸载应用**：`卸载技能：https://github.com/xxx/repo  或  xxx/repo
这里收藏了一些可用于测试的github项目：[查看技能分类](skills-by-category.md)

---

## ⚖️ 免责声明

1. **后果自负**：AI 生成的代码具有随机性。在授权 AI 执行重要命令前，请务必审计。
2. **数据安全**：本工具直接连接 AI 官方服务器，不记录、不转发您的任何隐私数据。
3. **责任界定**：因使用本工具导致的任何数据丢失，作者不承担责任。

---

## 🤝 贡献与支持

* **作者**: 麻子林 (Mazilin)
* **项目主页**: [canishowtime/ai-station-navigator](https://github.com/canishowtime/ai-station-navigator)
* **反馈渠道**: [GitHub Issues](https://github.com/canishowtime/ai-station-navigator/issues) | [Discussions](https://github.com/canishowtime/ai-station-navigator/discussions)

---
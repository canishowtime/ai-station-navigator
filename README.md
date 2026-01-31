# AI Station Navigator 🧭
> **基于 Claude Code 的智能体系统总线与调度器 (Kernel Logic Core)**

<br>

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows&logoColor=white)](https://microsoft.com)
[![Release](https://img.shields.io/github/v/release/YOUR_USERNAME/YOUR_REPO_NAME?label=Release&color=blue)](https://github.com/canishowtime/ai-station-navigator/releases)

[![Python](https://img.shields.io/badge/Python-3.8%2B_(Portable)-3776AB?logo=python&logoColor=white)](https://python.org)
[![Node.js](https://img.shields.io/badge/Node.js-Bundled-339933?logo=nodedotjs&logoColor=white)](https://nodejs.org)
[![Git](https://img.shields.io/badge/Git-Embedded-F05032?logo=git&logoColor=white)](https://git-scm.com)

[![Powered By](https://img.shields.io/badge/Powered%20By-Windows%20Terminal-4D4D4D?logo=windows-terminal&logoColor=white)](https://github.com/microsoft/terminal)
[![Claude Code](https://img.shields.io/badge/Integration-Claude%20Code-D97757?logo=anthropic&logoColor=white)](https://anthropic.com)

</div>

<br>

**AI Station Navigator** 是一款基于 Claude Code 引擎构建的模块化 AI 工作站。它模仿计算机组成原理，将繁杂的 AI 任务路由至子智能体（Sub-Agents）内并匹配相应的skills执行。项目集成了“应用商店式”技能管理与沙盒化执行环境，配合全绿色的免安装运行环境，旨在为用户提供一个解压即用、性能稳定、无限扩展的个人 AI 智慧中枢。

** ✅ 智能体上下文优化 | ✅ 应用商店式技能管理 | ✅ 良好的UI | ✅ 沙盒隔离 | ✅ 绿色零预装 | ✅ 模块化架构**

---

## 🎯 核心设计理念：AI工作站 架构

项目参考计算机组成原理，将 AI 能力转化为稳定、可扩展的系统服务：

### 🏗️ 架构类比

| 物理组件 | 软件映射 | 角色功能描述 |
| --- | --- | --- |
| **中央处理器 (CPU)** | **LLM** | **算力能源**：负责能力驱动。 |
| **系统内核 (Kernel )** | **Claude Code + CLAUDE.md** | **核心逻辑层**：负责意图识别、指令调度、任务拆解与上下文管理。 |
| **系统进程（Processes）** | **Sub-Agents (worker/skills)** | **任务执行层**：子智能体隔离运行单个应用或脚本，**减少对主智能体上下文污染**。 |
| **应用程序 (Apps)** | **Skills (GitHub 技能仓)** | **功能插件层**：通过 GitHub 链接实现“应用商店式”的一键安装与调用。 |
| **系统驱动 (Drivers)** | **MCP + Hooks** | **扩展与自动化**：MCP 提供外部系统扩展；Hooks 驱动系统自动化管理（日志/空间/状态）。 |
| **显示器 (Monitor)** | **Windows Terminal** | **信息输出**：提供运行状态展示，信息输出。 |
| **集成环境 (Runtime)** | **Portable Environment** | **底层支撑**：集成绿色版 Python, Node.js, Git强力底层工具，确保环境高度统一，增强潜在扩展能力。 |

---

## ✨ 核心特性

* 🧠 **核心特性**
* **一键启动环境**：双击启动脚本即可启动“claude code”。
* **一键安装应用**：支持通过 GitHub 仓库链接直接安装技能（skills）,支持多种skills项目类型。
* **会话隔离**：通过任务分流，子智能体独立运行脚本或skills，保护主对话 Context 不被冗余数据淹没。
* **沉浸式交互终端**：基于现代终端的可视化界面，兼顾专业感与易用性，默认浅色主题。
* **搭建基础工作流**：通过任务拆解实现将多个技能组合成串行的工作流执行。
* **扩展与自动化**：mcp对接外部系统，如AI搜索引擎等；hooks提供自动化支持。
* **环境沙箱**：工具整体运行在沙箱内，不会影响系统全局设置，智能体内部也配置了专用空间。

---

## 📂 目录结构

```text
ai-station-navigator/
├── .claude/                    # 系统配置区 (注册表)
│   ├── agents/                 # 子智能体定义 (进程)
│   ├── skills/                 # 已安装的应用（应用中心） 
├── bin/                        # 系统核心脚本 (内核组件)
│   ├── skill_manager.py        # 技能管理器 (应用商店入口)
│   ├── mcp_manager.py          # MCP 驱动管理器
│   └── hooks_manager.py        # 自动化钩子管理器
├── docs/                       # 系统文档 (操作说明)
├── mybox/                      # 沙盒工作区 (个人空间)
│   ├── workspace/              # 任务处理中心
│   └── output/                 # 最终产物导出
├── CLAUDE.md                   # Kernel 逻辑核心 (System CPU)
└── requirements.txt            # Python 依赖

```

---

## 🚀 快速开始

### 1. 一键启动

下载**[整合包](https://github.com/canishowtime/ai-station-navigator/releases) **后，即可实现零配置运行：

1. **启动**：双击根目录下的 `启动 ai-station-navigator.bat`。
2. **就绪**：按照屏幕提示安装缺失组件并输入自行准备的 `LLM-API-KEY`，即可进入启动状态。

### 2. 智能化管理 (对话即指令)

直接在对话框输入以下指令，即可通过 **Sub-Agent** (子进程) 实现技能管理与运行，有效减少对主智能体的上下文污染：
（系统内已配置github网络加速器，解决git源码获取的网络问题，直接黏贴原始地址或路径即可，可以是主项目，也可以是某个子技能）

* **查看能力**：`你现在有哪些技能？`
* **安装应用**：`安装技能：https://github.com/xxx/repo   （自动执行安装，如果主项目是技能包，建议地址路径正确指示到你需要单个技能，否则会安装整个技能包）
* **使用应用**： `@技能  需求内容`  （自动分析需求匹配已安装技能，确认后可立即执行并返回执行结果）
* **卸载应用**：`卸载技能：https://github.com/xxx/repo  或  xxx/repo`
* **尝试创建skills工作流**：`参考 docs\skills-mapping.md 设计一个包含x步的工作流，以流程xx,xx,xx,xx...为准，可以用在xxxx场景`
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
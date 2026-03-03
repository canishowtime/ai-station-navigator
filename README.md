[English](#en)  |  [中文](#cn)
<span id="en"></span>
# AI Station Navigator     
> **Agent System Bus and Scheduler based on Claude Code (Kernel Logic Core)**

<br>

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS-0078D6?logo=windows&logoColor=white)](https://microsoft.com)
[![Release](https://img.shields.io/github/v/release/canishowtime/ai-station-navigator?label=Release&color=blue)](https://github.com/canishowtime/ai-station-navigator/releases)

[![Python](https://img.shields.io/badge/Python-3.8%2B_(Portable)-3776AB?logo=python&logoColor=white)](https://python.org)
[![Node.js](https://img.shields.io/badge/Node.js-Bundled-339933?logo=nodedotjs&logoColor=white)](https://nodejs.org)
[![Git](https://img.shields.io/badge/Git-Embedded-F05032?logo=git&logoColor=white)](https://git-scm.com)

[![Powered By](https://img.shields.io/badge/Powered%20By-Windows%20Terminal-4D4D4D?logo=windows-terminal&logoColor=white)](https://github.com/microsoft/terminal)
[![Claude Code](https://img.shields.io/badge/Integration-Claude%20Code-D97757?logo=anthropic&logoColor=white)](https://anthropic.com)

</div>

<br>

**AI Station Navigator** is a modular AI workstation built on the Claude Code engine. Mimicking the principles of computer organization, it routes complex AI tasks to **Sub-Agents** and matches them with corresponding skills for execution. The project integrates an "App Store-style" skill management system and a sandboxed execution environment. Paired with a fully portable, installation-free runtime, it aims to provide users with an unzip-and-play, stable, and infinitely scalable personal AI intelligence hub.

** ✅ Agent Context Optimization | ✅ App Store-style Skill Management | ✅ Excellent UI | ✅ Sandbox Isolation | ✅ Skills Security Scanning | ✅ Modular Architecture**

---

## 🎯 Core Design Philosophy: AI Workstation Architecture

The project references computer organization principles to transform AI capabilities into stable, scalable system services:

### 🏗️ Architecture Analogy

| Computer | AI Station | Role & Function Description |
| --- | --- | --- |
| **CPU** | **LLM** | **Computing Power**: Responsible for driving capabilities. |
| **System Kernel** | **Claude Code + CLAUDE.md** | **Core Logic Layer**: Responsible for intent recognition, instruction scheduling, task decomposition, and context management. |
| **System Processes** | **Sub-Agents (worker/skills)** | **Execution Layer**: Sub-agents isolate the running of single applications or scripts, **reducing context pollution for the main agent**. |
| **Applications (Apps)** | **Skills (GitHub Repos)** | **Function Plugin Layer**: Implements "App Store-style" one-click installation and invocation via GitHub links. |
| **System Drivers** | **MCP + Hooks** | **Extension & Automation**: MCP provides external system extensions; Hooks drive system automation (logs/space/status). |
| **Monitor** | **Windows Terminal / macOS Terminal** | **Information Output**: Provides status display and information output. |
| **Runtime Environment** | **Portable Environment** | **Underlying Support**: Integrated portable versions of Python, Node.js, and Git. Ensures a highly unified environment and enhances potential scalability. |

---

## ✨ Core Features

* 🧠 **Key Highlights**
* **Convenient Environment Startup**: Simply double-click the script to start the environment; ready to use after a quick configuration.
* **One-Click App Installation**: Supports installing skills directly via GitHub repository links, supporting various skill project types.
* **Session Isolation**: Through task routing, Sub-Agents run scripts or skills independently, protecting the main dialogue Context from being overwhelmed by redundant data.
* **Immersive Interactive Terminal**: Visual interface based on modern terminals, balancing professionalism with ease of use (default light theme).
* **Build Basic Workflows**: Achieve serial execution of multiple skills combined into a workflow through task decomposition.
* **Extension & Automation**: MCP connects to external systems (e.g., AI search engines); Hooks provide automation support.
* **Environment Sandbox**: The tool runs entirely within a sandbox, ensuring it does not affect global system settings. Dedicated spaces are also configured within the agents.
* **Skills Security Detection**: Integrates the [Cisco Skill Scanner](https://github.com/cisco-ai-defense/skill-scanner) developed by Cisco AI Defense. It automatically detects potential security risks after installing skills.

---

<div align="center">
  <img src="demo.gif" width="800" alt="演示动图" />
</div>

---

## 📂 Directory Structure

```text
ai-station-navigator/
├── .claude/                    # System Configuration (Registry)
│   ├── agents/                 # Sub-Agent Definitions (Processes)
│   ├── skills/                 # Installed Apps (App Center) 
├── bin/                        # System Core Scripts (Kernel Components)
│   ├── skill_manager.py        # Skill Manager (App Store Entry)
│   ├── mcp_manager.py          # MCP Driver Manager
│   └── hooks_manager.py        # Automation Hooks Manager
├── docs/                       # System Documentation (Manuals)
├── mybox/                      # Sandbox Workspace (Personal Space)
│   ├── workspace/              # Task Processing Center
│   └── output/                 # Final Output Export
├── CLAUDE.md                   # Kernel Logic Core (System CPU)
└── requirements.txt            # Python Dependencies

```

---

## 🚀 Quick Start

### 1. One-Click Launch

Download the **[All-in-One Package](https://github.com/canishowtime/ai-station-navigator/releases)** to achieve zero-configuration operation:

#### Windows Users
1. **Launch**: Double-click `Start.bat` in the root directory.
2. **Ready**: Follow the on-screen prompts to install missing components and input your self-prepared `LLM-API-KEY` to enter the startup state.

#### macOS Users

**Installation Steps:**

1. After extracting the downloaded zip file (double-click to extract), open the built-in "Terminal" application and navigate to the extracted directory:
   ```bash
   cd ~/Downloads/AI-Station-navigator
   ```

2. Run the installation script:
   ```bash
   bash unpack.sh
   ```

**Launching the Application:**

After installation, for first-time use, **right-click 'start.command' and select 'Open'**; subsequent runs can be done by double-clicking 'start.command'.

**Notes:**

- A new terminal window will open with a custom theme applied on first launch
- If prompted about security during launch, right-click 'start.command' and select 'Open'
- If the system prompts you to install Git during first run, please follow the system instructions to complete the installation (typically requires installing Xcode Command Line Tools)
- **Do not run this project in directories with Chinese characters or spaces in the path**

### 2. Intelligent Management (Chat as Command)

Enter the following instructions directly into the chat box to manage and run skills via **Sub-Agents** (Sub-processes), effectively reducing context pollution for the main agent:
(The system has a built-in GitHub network accelerator to solve network issues with Git source retrieval. You can paste the original address or path directly. It can be a main project or a specific sub-skill).

* **Check Capabilities**: `What skills do you have now?`
* **Install App**: `Install skill: https://github.com/xxx/repo` (Automatically performs installation. If the main project is a skill package, it is recommended to point the address path correctly to the specific skill you need; otherwise, the entire skill package will be installed).
* **Use App**: `@Skill [Requirement Content]` (Automatically analyzes the requirement, matches installed skills, and executes immediately upon confirmation, returning the result).
* **Uninstall App**: `Uninstall skill: https://github.com/xxx/repo` or `xxx/repo`.
* **Try Creating a Skills Workflow**: `Refer to docs\skills-mapping.md to design a workflow containing X steps, based on the flow xx,xx,xx,xx..., to be used in the xxxx scenario.`

Here are some GitHub projects collected for testing: [View Skills Categories](skills-by-category.md)

---

## ⚖️ Disclaimer

1. **At Your Own Risk**: AI-generated code or executed commands possess randomness. Please be sure to audit before authorizing the AI to delete or modify files.
2. **Liability**: The author assumes no responsibility for any data loss or system damage caused by the use of this tool.

---

## 🤝 Contribution & Support

* **Author**: Mazilin
* **Project Homepage**: [canishowtime/ai-station-navigator](https://github.com/canishowtime/ai-station-navigator)
* **Feedback Channels**: [GitHub Issues](https://github.com/canishowtime/ai-station-navigator/issues) | [Discussions](https://github.com/canishowtime/ai-station-navigator/discussions)

---

<span id="cn"></span>
# AI 工作站 领航员
> **基于 Claude Code 的智能体系统总线与调度器 (Kernel Logic Core)**

<br>

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS-0078D6?logo=windows&logoColor=white)](https://microsoft.com)
[![Release](https://img.shields.io/github/v/release/canishowtime/ai-station-navigator?label=Release&color=blue)](https://github.com/canishowtime/ai-station-navigator/releases)

[![Python](https://img.shields.io/badge/Python-3.8%2B_(Portable)-3776AB?logo=python&logoColor=white)](https://python.org)
[![Node.js](https://img.shields.io/badge/Node.js-Bundled-339933?logo=nodedotjs&logoColor=white)](https://nodejs.org)
[![Git](https://img.shields.io/badge/Git-Embedded-F05032?logo=git&logoColor=white)](https://git-scm.com)

[![Powered By](https://img.shields.io/badge/Powered%20By-Windows%20Terminal-4D4D4D?logo=windows-terminal&logoColor=white)](https://github.com/microsoft/terminal)
[![Claude Code](https://img.shields.io/badge/Integration-Claude%20Code-D97757?logo=anthropic&logoColor=white)](https://anthropic.com)

</div>

<br>

**AI Station Navigator** 是一款基于 Claude Code 引擎构建的模块化 AI 工作站。它模仿计算机组成原理，将繁杂的 AI 任务路由至子智能体（Sub-Agents）内并匹配相应的skills执行。项目集成了“应用商店式”技能管理与沙盒化执行环境，配合全绿色的免安装运行环境，旨在为用户提供一个解压即用、性能稳定、无限扩展的个人 AI 智慧中枢。

** ✅ 智能体上下文优化 | ✅ 应用商店式技能管理 | ✅ 良好的UI | ✅ 沙盒隔离 | ✅ Skills安全扫描 | ✅ 模块化架构**

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
* **便捷启动环境**：双击启动脚本即可启动环境，快捷配置即可使用。
* **一键安装应用**：支持通过 GitHub 仓库链接直接安装技能（skills）,支持多种skills项目类型。
* **会话隔离**：通过任务分流，子智能体独立运行脚本或skills，保护主对话 Context 不被冗余数据淹没。
* **沉浸式交互终端**：基于现代终端的可视化界面，兼顾专业感与易用性，默认浅色主题。
* **搭建基础工作流**：通过任务拆解实现将多个技能组合成串行的工作流执行。
* **扩展与自动化**：mcp对接外部系统，如AI搜索引擎等；hooks提供自动化支持。
* **环境沙箱**：工具整体运行在沙箱内，不会影响系统全局设置，智能体内部也配置了专用空间。
* **Skills安全检测**：集成思科（Cisco）开发的 AI 技能安全扫描工具[Cisco Skill Scanner](https://github.com/cisco-ai-defense/skill-scanner)，安装skills后自动检测潜在安全风险。

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

#### Windows 用户
1. **启动**：双击根目录下的 `启动.bat`。
2. **就绪**：按照屏幕提示安装缺失组件并输入自行准备的 `LLM-API-KEY`，即可进入启动状态。

#### macOS 用户

**安装步骤：**

1. 解压下载的 zip 文件（双击即可解压）后，打开系统自带"终端"应用，进入解压后的目录：
   ```bash
   cd ~/Downloads/AI-Station-navigator
   ```

2. 执行安装脚本：
   ```bash
   bash unpack.sh
   ```

**启动应用：**

安装完成后，首次使用需 **右键'启动.command'——> 选'打开'**；下次运行时可通过双击'启动.command'。

**注意事项：**

- 首次启动时会打开新终端窗口并应用自定义主题
- 如果启动时提示无法确认安全性，请右键点击'启动.command'选择'打开'
- 首次运行时如果系统提示需要安装 Git，请按照系统提示完成安装（通常需要安装 Xcode 命令行工具）
- **不要在中文路径和带有空格的路径运行此项目**

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

1. **后果自负**：AI 生成的代码或执行的命令具有随机性。在授权 AI 执行删除、修改文件前，请务必审计。
2. **责任界定**：因使用本工具导致的任何数据丢失或系统损坏，作者不承担任何责任。

---

## 🤝 贡献与支持

* **作者**: 麻子林 (Mazilin)
* **项目主页**: [canishowtime/ai-station-navigator](https://github.com/canishowtime/ai-station-navigator)
* **反馈渠道**: [GitHub Issues](https://github.com/canishowtime/ai-station-navigator/issues) | [Discussions](https://github.com/canishowtime/ai-station-navigator/discussions)

---
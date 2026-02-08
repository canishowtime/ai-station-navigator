# Claude Skills 功能分类汇总

> **⚠️ 免责声明**：以下链接仅供 Skills 安装测试，具体用途、安全性和限制请务必查阅对应仓库说明。本文档仅作功能汇总，版权归属原项目作者。

<div align="center">

| 📅 分析日期 | 📦 仓库总数 | 🧩 技能总数 |
| :---: | :---: | :---: |
| 2026-02-07 | 15 | 135 |

</div>

## 📖 目录索引

| 章节 | 🏷️ 分类 | 📊 技能数 |
| :---: | :--- | ---: |
| [01](#一开发工作流-development-workflow) | 🛠️ 开发工作流 | 14 |
| [02](#二文本处理与写作-text--writing) | ✍️ 文本处理与写作 | 32 |
| [03](#三创业与商业-startup--business) | 💼 创业与商业 | 26 |
| [04](#四笔记与知识管理-note-taking--knowledge) | 📓 笔记与知识管理 | 6 |
| [05](#五prompt工程与技能管理-skill-management) | 🤖 Prompt工程与管理 | 4 |
| [06](#六专业领域-professional-domains) | ⚖️ 专业领域 | 30 |
| [07](#七综合工具集-comprehensive-toolkits) | 🧰 综合工具集 | 14 |

---

## 一、开发工作流 (Development Workflow)

### 📦 [obra/superpowers](https://github.com/obra/superpowers)
**简介**：全流程开发工作流增强工具，覆盖从创意到部署的完整周期。

#### 核心能力矩阵

| 阶段 | 技能名称 | 功能描述 |
| :--- | :--- | :--- |
| **🎯 规划与执行** | `brainstorming` | 创意工作前置，创建功能特性清单 |
| | `writing-plans` | 编写多步骤任务实现计划 |
| | `executing-plans` | 执行书面实现计划 |
| | `subagent-driven-development` | 使用独立子任务执行实现计划 |
| **🔧 开发方法论** | `test-driven-development` | 测试驱动开发（功能/修复） |
| | `systematic-debugging` | 系统性调试（bug/测试失败） |
| | `using-git-worktrees` | 使用 Git 工作树隔离特性开发 |
| **🤝 协作与审查** | `requesting-code-review` | 请求代码审查 |
| | `receiving-code-review` | 接收代码审查反馈处理 |
| **✅ 完成与验证** | `finishing-a-development-branch` | 完成开发分支（测试通过后） |
| | `verification-before-completion` | 完成前验证机制 |
| **🛠️ 元能力** | `writing-skills` | 创建/编辑技能 |
| | `dispatching-parallel-agents` | 并行处理 2+ 个独立任务 |
| | `using-superpowers` | 会话起始，建立技能使用规则 |

---

## 二、文本处理与写作 (Text & Writing)

### 📦 [op7418/Humanizer-zh](https://github.com/op7418/Humanizer-zh)
| 技能 | 功能 |
| :--- | :--- |
| `humanizer-zh` | **去 AI 味**：去除 AI 生成痕迹的中文文本优化工具 |

### 📦 [ginobefun/deep-reading-analyst-skill](https://github.com/ginobefun/deep-reading-analyst-skill)
| 技能 | 功能 |
| :--- | :--- |
| `deep-reading-analyst` | **深度阅读**：文章/论文/书籍的深度分析框架 |

### 📦 [anthropics/skills](https://github.com/anthropics/skills) (官方)
| 类别 | 技能 | 功能 |
| :--- | :--- | :--- |
| **🎨 设计与视觉** | `canvas-design` | 创建视觉艺术 (PNG/PDF) |
| | `algorithmic-art` | p5.js 算法艺术创作 |
| | `frontend-design` | 前端界面创建 |
| | `tailwindcss` | Tailwind CSS 样式框架 |
| | `slack-gif-creator` | Slack 动画 GIF 制作 |
| **📄 文档处理** | `docx` / `xlsx` | Word / Excel 处理 |
| | `pdf` | PDF 操作工具包 |
| | `pptx` | PowerPoint 演示文稿 |
| | `doc-coauthoring` | 文档协作工作流 |
| **🏗️ 构建与开发** | `mcp-builder` | MCP 服务器构建指南 |
| | `web-artifacts-builder` | 复杂 Web 产物构建 |
| | `web-app-testing` | Web 应用测试 |

### 📦 [JimLiu/baoyu-skills](https://github.com/JimLiu/baoyu-skills)
**简介**：Baoyu 分享的 Claude Code 技能集合，专注于内容生成、发布与 AI 图像处理。

#### 🎨 内容生成技能 (6个)
| 技能 | 命令 | 功能描述 |
| :--- | :--- | :--- |
| **小红书信息图** | `/baoyu-xhs-images` | Style × Layout 二维系统 (9风格×6布局) |
| **专业信息图** | `/baoyu-infographic` | 20种布局 × 17种视觉风格 |
| **文章封面** | `/baoyu-cover-image` | 5维系统 (Type×Palette×Rendering×Text×Mood) |
| **幻灯片** | `/baoyu-slide-deck` | 16种预设风格，自动生成 PPTX/PDF |
| **知识漫画** | `/baoyu-comic` | 5种艺术风格 × 7种基调 |
| **文章插图** | `/baoyu-article-illustrator` | 6种类型 × 8种风格 |

#### 📢 内容发布技能 (2个)
| 技能 | 命令 | 功能描述 |
| :--- | :--- | :--- |
| **发布到X** | `/baoyu-post-to-x` | 推文和 X Articles (长文章) |
| **发布到微信** | `/baoyu-post-to-wechat` | 图文/文章两种模式 |

#### 🤖 AI生成技能 (2个)
| 技能 | 命令 | 功能描述 |
| :--- | :--- | :--- |
| **图像生成** | `/baoyu-image-gen` | OpenAI/Google API 图像生成 |
| **Gemini Web** | `/baoyu-danger-gemini-web` | 文本和图像生成 ( unofficial API) |

#### 🛠️ 实用工具 (3个)
| 技能 | 命令 | 功能描述 |
| :--- | :--- | :--- |
| **URL转Markdown** | `/baoyu-url-to-markdown` | Chrome CDP 网页捕获 |
| **X转Markdown** | `/baoyu-danger-x-to-markdown` | 推文/文章转 MD |
| **图像压缩** | `/baoyu-compress-image` | 保持质量压缩 |

---

## 三、创业与商业 (Startup & Business)

### 📦 [Agent-3-7/agent37-skills-collection](https://github.com/Agent-3-7/agent37-skills-collection)
| 技能 | 功能 |
| :--- | :--- |
| `yc-advisor` | **YC 创业顾问**：基于 443 个精选资源（Paul Graham论文/访谈）提供创业决策支持 |

### 📦 [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills)
| 技能 | 功能 |
| :--- | :--- |
| `ab-test-setup` | **A/B测试设置**：配置和执行A/B测试实验 |
| `analytics-tracking` | **分析追踪**：设置和分析营销数据追踪 |
| `competitor-alternatives` | **竞品分析**：识别竞品并提供替代方案分析 |
| `content-strategy` | **内容策略**：制定和优化内容营销策略 |
| `copy-editing` | **文案编辑**：优化和编辑营销文案 |
| `copywriting` | **文案写作**：创作有效的营销文案 |
| `email-sequence` | **邮件序列**：设计和执行邮件营销序列 |
| `form-cro` | **表单优化**：优化表单转化率 |
| `free-tool-strategy` | **免费工具策略**：制定免费工具营销策略 |
| `launch-strategy` | **发布策略**：产品发布和营销活动策划 |
| `marketing-ideas` | **营销创意**：生成营销活动和推广创意 |
| `marketing-psychology` | **营销心理学**：应用心理学原理提升营销效果 |
| `onboarding-cro` | **引导优化**：优化新用户引导流程转化率 |
| `page-cro` | **页面优化**：优化单页转化率 |
| `paid-ads` | **付费广告**：管理和优化付费广告活动 |
| `paypal-upgrade-cro` | **PayPal 升级优化**：优化 PayPal 升级转化率 |
| `popup-cro` | **弹窗优化**：优化弹窗转化率 |
| `pricing-strategy` | **定价策略**：制定和优化产品定价策略 |
| `product-marketing-context` | **产品营销**：提供产品营销背景和策略 |
| `programmatic-seo` | **程序化SEO**：规模化SEO内容生成 |
| `referral-program` | **推荐计划**：设计和优化推荐奖励计划 |
| `schema-markup` | **Schema标记**：实现结构化数据标记 |
| `seo-audit` | **SEO审计**：执行全面的SEO审计 |
| `signup-flow-cro` | **注册流程优化**：优化注册转化率 |
| `social-content` | **社交内容**：创建社交媒体内容 |

---

## 四、笔记与知识管理 (Note-taking & Knowledge)

### 📦 [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills)
| 技能 | 功能 |
| :--- | :--- |
| `json-canvas` | JSON Canvas 文件创建/编辑 (节点/边) |
| `obsidian-bases` | Obsidian Bases 数据库操作 (视图/过滤器) |
| `obsidian-markdown` | Obsidian 风格 Markdown (双链/嵌入) |

### 📦 [axtonliu/axton-obsidian-visual-skills](https://github.com/axtonliu/axton-obsidian-visual-skills)
| 技能 | 功能 |
| :--- | :--- |
| `excalidraw-diagram` | Excalidraw 图表生成 (流程图/思维导图) |
| `mermaid-visualizer` | Mermaid 专业图表可视化 |
| `obsidian-canvas-creator` | Obsidian Canvas 创建 (自由布局) |

---

## 五、Prompt工程与技能管理 (Skill Management)

### 📦 [chujianyun/skills](https://github.com/chujianyun/skills)
*   `prompt-optimizer`: Prompt 优化专家（内置 57 种框架）
*   `sync-skills`: 技能同步工具

### 📦 [tripleyak/SkillForge](https://github.com/tripleyak/SkillForge)
*   `skillforge`: 智能技能路由（分析输入自动匹配技能）

### 📦 [OthmanAdi/planning-with-files](https://github.com/OthmanAdi/planning-with-files)
*   `planning-with-files`: 类 Manus 的基于文件的复杂任务规划系统

---

## 六、专业领域 (Professional Domains)

### 📦 [muratcankoylan/Agent-Skills-for-Context-Engineering](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering)
**上下文工程与 Agent 设计**：
| 技能 | 功能 |
|:---|:---|
| `context-engineering-collection` | 上下文工程集合包（含10个子技能：context-compression, context-optimization, context-degradation-diagnosis, multiagent-patterns, tool-design, filesystem-context-unload, agent-evaluation, reasoning-trace-optimization, bdi-modeling, memory-system） |

### 📦 [trailofbits/skills](https://github.com/trailofbits/skills)
**Trail of Bits 安全研究技能集**：安全研究、漏洞检测、审计工作流工具

#### 🔐 智能合约安全
| 技能 | 功能 |
| :--- | :--- |
| `building-secure-contracts` | 智能合约安全工具包，支持 6 条区块链的漏洞扫描器 |
| `entry-point-analyzer` | 识别智能合约中状态变更的入口点，用于安全审计 |

#### 🛡️ 代码审计
| 技能 | 功能 |
| :--- | :--- |
| `audit-context-building` | 通过超细粒度代码分析构建深度架构上下文 |
| `burpsuite-project-parser` | 从 Burp Suite 项目文件中搜索和提取数据 |
| `differential-review` | 基于历史分析的安全差异化代码审查 |
| `semgrep-rule-creator` | 创建和优化 Semgrep 规则用于自定义漏洞检测 |
| `semgrep-rule-variant-creator` | 将现有 Semgrep 规则移植到新目标语言 |
| `sharp-edges` | 识别易错 API、危险配置和隐患设计 |
| `static-analysis` | 静态分析工具包 (CodeQL, Semgrep, SARIF 解析) |
| `testing-handbook-generator` | 测试手册技能：Fuzzers、静态分析、Sanitizers、覆盖率 |
| `variant-analysis` | 基于模式分析在代码库中发现类似漏洞 |
| `codeql` | CodeQL 静态分析工具 |
| `sarif-parsing` | SARIF 结果解析 |
| `semgrep` | Semgrep 静态分析 |
| `insecure-defaults` | 识别不安全的默认配置 |
| `modern-python` | 现代 Python 安全最佳实践 |
| `guidelines-advisor` | 安全指南顾问 |
| `secure-workflow-guide` | 安全工作流指南 |

#### 🔍 智能合约漏洞扫描器
| 技能 | 功能 |
|:---|:---|
| `algorand-vulnerability-scanner` | Algorand 区块链漏洞扫描 |
| `cairo-vulnerability-scanner` | Cairo 智能合约漏洞扫描 |
| `cosmos-vulnerability-scanner` | Cosmos 区块链漏洞扫描 |
| `solana-vulnerability-scanner` | Solana 区块链漏洞扫描 |
| `substrate-vulnerability-scanner` | Substrate 链漏洞扫描 |
| `ton-vulnerability-scanner` | TON 区块链漏洞扫描 |
| `audit-prep-assistant` | 审计准备助手 |
| `code-maturity-assessor` | 代码成熟度评估 |
| `token-integration-analyzer` | 代币集成分析 |

#### 🧪 模糊测试工具
| 技能 | 功能 |
|:---|:---|
| `aflpp` | AFL++ 模糊测试 |
| `atheris` | Atheris 模糊测试 |
| `cargo-fuzz` | Rust Cargo 模糊测试 |
| `libafl` | LibAFL 模糊测试框架 |
| `libfuzzer` | LibFuzzer 模糊测试 |
| `ossfuzz` | OSS-Fuzz 集成 |
| `ruzzy` | Ruzzy 模糊测试 |
| `address-sanitizer` | AddressSanitizer 内存错误检测 |
| `constant-time-testing` | 常量时间测试 |
| `coverage-analysis` | 覆盖率分析 |
| `fuzzing-dictionary` | 模糊测试字典 |
| `fuzzing-obstacles` | 模糊测试障碍 |
| `harness-writing` | 测试工具编写 |
| `wycheproof` | Wycheproof 密码测试向量 |
| `yara-rule-authoring` | YARA 规则编写 |

#### ✅ 验证
| 技能 | 功能 |
| :--- | :--- |
| `constant-time-analysis` | 检测加密代码中编译器引入的时序侧信道 |
| `property-based-testing` | 多语言和智能合约的基于属性测试指导 |
| `spec-to-code-compliance` | 区块链审计的规范到代码合规性检查器 |

#### 📋 审计生命周期
| 技能 | 功能 |
| :--- | :--- |
| `fix-review` | 验证修复提交是否解决了审计发现且未引入新漏洞 |

#### 🔧 逆向工程
| 技能 | 功能 |
| :--- | :--- |
| `dwarf-expert` | 交互和理解 DWARF 调试格式 |

#### 📱 移动安全
| 技能 | 功能 |
| :--- | :--- |
| `firebase-apk-scanner` | 扫描 Android APK 的 Firebase 安全配置错误 |

#### 💻 开发
| 技能 | 功能 |
| :--- | :--- |
| `ask-questions-if-underspecified` | 实现前澄清需求 |

#### 👥 团队管理
| 技能 | 功能 |
| :--- | :--- |
| `interpreting-culture-index` | 解释个人和团队的 Culture Index 调查结果 |

#### 🛠️ 工具
| 技能 | 功能 |
| :--- | :--- |
| `claude-in-chrome-troubleshooting` | 诊断和修复 Claude in Chrome MCP 扩展连接问题 |

---

## 七、综合工具集 (Comprehensive Toolkits)

### 📦 [ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills)

| 分类 | 技能 | 功能 |
| :--- | :--- | :--- |
| **📄 文档处理** | `docx`/`pdf`/`pptx`/`xlsx` | Office 全家桶处理套件 |
| **🛠️ 开发工具** | `artifacts-builder` | 创建多组件工件 |
| | `mcp-builder` | MCP 协议构建指南 |
| | `skill-creator` | 技能开发工具链 |
| | `langsmith-fetch` | LangChain/LangGraph 调试 |
| | `template-skill` | 模板技能 |
| **⚡ 生产力** | `connect` | 连接外部应用 (Gmail/Slack/GitHub) |
| | `connect-apps` | 连接外部应用 (Gmail/Slack/GitHub) |
| | `file-organizer` | 智能文件/发票整理 |
| | `meeting-insights-analyzer` | 会议洞察分析 |
| | `web-app-testing` | Web 应用测试 |
| | `invoice-organizer` | 发票整理 |
| | `domain-name-brainstormer` | 域名名生成 |
| | `raffle-winner-picker` | 抽奖工具 |
| | `youtube-downloader` | YouTube 下载 |
| **✍️ 内容创作** | `targeted-resume-generator` | 定制简历生成 |
| | `content-research-writer` | 内容研究与写作 |
| | `twitter-algorithm-optimizer` | Twitter 算法优化 |
| | `competitive-ads-extractor` | 竞品广告分析 |
| | `slack-gif-creator` | Slack 动画 GIF 制作 |
| | `changelog-generator` | 变更日志自动生成 |
| **📊 分析工具** | `developer-growth-analysis` | 开发者成长分析 |
| | `lead-research-assistant` | 潜在客户研究 |
| **🎨 设计增强** | `brand-guidelines` | Anthropic 品牌样式应用 |
| | `theme-factory` | 主题样式工厂 |
| | `image-enhancer` | 图像增强 |
| **📢 内部沟通** | `internal-comms` | 内部通信模板 |
| | `skill-share` | Slack 技能分享 |
| | `whatsapp-integration` | WhatsApp 集成 |

---

> 📝 **备注**：本文档更新于 2026-02-07，已同步 GitHub 仓库最新技能列表，修正名称不一致、补充缺失技能。
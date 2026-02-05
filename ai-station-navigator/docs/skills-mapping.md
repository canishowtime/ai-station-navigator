# 子技能映射表 (Sub-skills Mapping)

> **🔗 派生关系**: 本文档从 `skills-by-category.md` **自动派生 (Derived Source)**，是子技能路由查询的索引表。
>
> **⚡ 用途**: 当用户请求安装子技能时，Kernel 查找此表自动定位所属主仓库，并添加 `--skill` 参数
>
> **📅 最后同步**: 2026-02-03 (移除 K-Dense-AI, claudekit-skills, claude-skills)

---

## 一、开发工作流 (obra/superpowers)

| 子技能名称 | 说明 |
|:---|:---|
| `brainstorming` | 创意工作前置，创建功能特性清单 |
| `writing-plans` | 编写多步骤任务实现计划 |
| `executing-plans` | 执行书面实现计划 |
| `subagent-driven-development` | 使用独立子任务执行实现计划 |
| `test-driven-development` | 测试驱动开发（功能/修复） |
| `systematic-debugging` | 系统性调试（bug/测试失败） |
| `using-git-worktrees` | 使用 Git 工作树隔离特性开发 |
| `requesting-code-review` | 请求代码审查 |
| `receiving-code-review` | 接收代码审查反馈处理 |
| `finishing-a-development-branch` | 完成开发分支（测试通过后） |
| `verification-before-completion` | 完成前验证机制 |
| `writing-skills` | 创建/编辑技能 |
| `dispatching-parallel-agents` | 并行处理 2+ 个独立任务 |
| `using-superpowers` | 会话起始，建立技能使用规则 |

---


## 三、文本处理与写作

### op7418/Humanizer-zh
| 子技能名称 | 说明 |
|:---|:---|
| `humanizer-zh` | 去 AI 味：去除 AI 生成痕迹的中文文本优化工具 |

### ginobefun/deep-reading-analyst-skill
| 子技能名称 | 说明 |
|:---|:---|
| `deep-reading-analyst` | 深度阅读：文章/论文/书籍的深度分析框架 |

### anthropics/skills (官方)
| 子技能名称 | 说明 |
|:---|:---|
| `canvas-design` | 创建视觉艺术 (PNG/PDF) |
| `algorithmic-art` | p5.js 算法艺术创作 |
| `frontend-design` | 前端界面创建 |
| `slack-gif-creator` | Slack 动画 GIF 制作 |
| `docx` | Word 文档处理 |
| `xlsx` | Excel 表格处理 |
| `pdf` | PDF 操作工具包 |
| `pptx` | PowerPoint 演示文稿 |
| `doc-coauthoring` | 文档协作工作流 |
| `mcp-builder` | MCP 服务器构建指南 |
| `web-artifacts-builder` | 复杂 Web 产物构建 |
| `webapp-testing` | Web 应用测试 |

### JimLiu/baoyu-skills

#### 🎨 内容生成技能
| 子技能名称 | 说明 |
|:---|:---|
| `baoyu-xhs-images` | 小红书信息图生成器 (9风格×6布局) |
| `baoyu-infographic` | 专业信息图 (20布局×17风格) |
| `baoyu-cover-image` | 文章封面图 (5维系统) |
| `baoyu-slide-deck` | 专业幻灯片生成 (16种预设) |
| `baoyu-comic` | 知识漫画创作器 (5风格×7基调) |
| `baoyu-article-illustrator` | 智能文章插图 (6类型×8风格) |

#### 📢 内容发布技能
| 子技能名称 | 说明 |
|:---|:---|
| `baoyu-post-to-x` | 发布到 X/Twitter (推文/长文章) |
| `baoyu-post-to-wechat` | 发布到微信公众号 (图文/文章) |

#### 🤖 AI生成技能
| 子技能名称 | 说明 |
|:---|:---|
| `baoyu-image-gen` | OpenAI/Google API 图像生成 |
| `baoyu-danger-gemini-web` | Gemini Web 文本/图像生成 |

#### 🛠️ 实用工具
| 子技能名称 | 说明 |
|:---|:---|
| `baoyu-url-to-markdown` | URL 转 Markdown (Chrome CDP) |
| `baoyu-danger-x-to-markdown` | X 推文/文章转 Markdown |
| `baoyu-compress-image` | 图像压缩工具 |

---

## 四、创业与商业

### Agent-3-7/agent37-skills-collection
| 子技能名称 | 说明 |
|:---|:---|
| `yc-advisor` | YC 创业顾问：基于 443 个精选资源提供创业决策支持 |

### coreyhaines31/marketingskills
| 子技能名称 | 说明 |
|:---|:---|
| `signup-flow-cro` | 注册流程转化率优化 |
| `page-cro` | 页面转化率优化 |
| `form-cro` | 表单转化率优化 |
| `popup-cro` | 弹窗转化率优化 |
| `paywall-upgrade-cro` | 付费墙升级转化率优化 |
| `onboarding-cro` | 入驻流程转化率优化 |
| `copywriting` | 文案写作 |
| `copy-editing` | 文案编辑 |
| `content-strategy` | 内容策略 |
| `social-content` | 社交内容 |
| `email-sequence` | 邮件序列 |
| `launch-strategy` | 发布策略 |
| `referral-program` | 推荐计划 |
| `pricing-strategy` | 定价策略 |
| `free-tool-strategy` | 免费工具策略 |
| `seo-audit` | SEO 审计 |
| `programmatic-seo` | 程序化 SEO |
| `schema-markup` | Schema 标记 |
| `paid-ads` | 付费广告 |
| `ab-test-setup` | A/B 测试设置 |
| `analytics-tracking` | 分析追踪 |
| `marketing-psychology` | 营销心理学 |
| `marketing-ideas` | 营销创意 |
| `competitor-alternatives` | 竞品对比 |
| `product-marketing-context` | 产品营销上下文 |

---

## 五、笔记与知识管理

### kepano/obsidian-skills
| 子技能名称 | 说明 |
|:---|:---|
| `json-canvas` | JSON Canvas 文件创建/编辑 (节点/边) |
| `obsidian-bases` | Obsidian Bases 数据库操作 (视图/过滤器) |
| `obsidian-markdown` | Obsidian 风格 Markdown (双链/嵌入) |

### axtonliu/axton-obsidian-visual-skills
| 子技能名称 | 说明 |
|:---|:---|
| `excalidraw-diagram` | Excalidraw 图表生成 (流程图/思维导图) |
| `mermaid-visualizer` | Mermaid 专业图表可视化 |
| `obsidian-canvas-creator` | Obsidian Canvas 创建 (自由布局) |

---

## 六、Prompt工程与技能管理

### chujianyun/skills
| 子技能名称 | 说明 |
|:---|:---|
| `prompt-optimizer` | Prompt 优化专家（内置 57 种框架） |
| `sync-skills` | 技能同步工具 |

### tripleyak/SkillForge
| 子技能名称 | 说明 |
|:---|:---|
| `skillforge` | 智能技能路由（分析输入自动匹配技能） |

### OthmanAdi/planning-with-files
| 子技能名称 | 说明 |
|:---|:---|
| `planning-with-files` | 类 Manus 的基于文件的复杂任务规划系统 |

---

## 七、专业领域

### muratcankoylan/Agent-Skills-for-Context-Engineering
上下文工程与 Agent 设计

| 子技能名称 | 说明 |
|:---|:---|
| `context-compression` | 上下文压缩 |
| `context-optimization` | 上下文优化 |
| `context-degradation-diagnosis` | 降级诊断 |
| `multiagent-patterns` | 多智能体模式 |
| `tool-design` | 工具设计 |
| `filesystem-context-unload` | 文件系统上下文卸载 |
| `agent-evaluation` | Agent 评估 |
| `reasoning-trace-optimization` | 推理追踪优化 (Reasoning Trace) |
| `bdi-modeling` | BDI 精神状态建模 |
| `memory-system` | 记忆系统实现 |

---

## 八、综合工具集

### ComposioHQ/awesome-claude-skills
| 子技能名称 | 说明 |
|:---|:---|
| `docx` | Word 处理 |
| `pdf` | PDF 处理 |
| `ppt` | PowerPoint 处理 |
| `xlsx` | Excel 处理 |
| `artifacts-builder` | 创建多组件工件 |
| `mcp-builder` | MCP 协议构建指南 |
| `skill-creator` | 技能开发工具链 |
| `langsmith-fetch` | LangChain/LangGraph 调试 |
| `connect-apps` | 连接外部应用 (Gmail/Slack/GitHub) |
| `file-organizer` | 智能文件/发票整理 |
| `meeting-insights` | 会议洞察分析 |
| `webapp-testing` | Web 应用测试 |
| `tailored-resume` | 定制简历生成 |
| `content-research` | 内容研究与写作 |
| `twitter-optimizer` | Twitter 算法优化 |
| `competitive-ads` | 竞品广告分析 |

---

## 九、开发工具集

---

## 十、安全研究与审计 (trailofbits/skills)

### 🔐 智能合约安全
| 子技能名称 | 说明 |
|:---|:---|
| `building-secure-contracts` | 智能合约安全工具包，支持 6 条区块链的漏洞扫描器 |
| `entry-point-analyzer` | 识别智能合约中状态变更的入口点，用于安全审计 |

### 🛡️ 代码审计
| 子技能名称 | 说明 |
|:---|:---|
| `audit-context-building` | 通过超细粒度代码分析构建深度架构上下文 |
| `burpsuite-project-parser` | 从 Burp Suite 项目文件中搜索和提取数据 |
| `differential-review` | 基于历史分析的安全差异化代码审查 |
| `semgrep-rule-creator` | 创建和优化 Semgrep 规则用于自定义漏洞检测 |
| `semgrep-rule-variant-creator` | 将现有 Semgrep 规则移植到新目标语言 |
| `sharp-edges` | 识别易错 API、危险配置和隐患设计 |
| `static-analysis` | 静态分析工具包 (CodeQL, Semgrep, SARIF 解析) |
| `testing-handbook-skills` | 测试手册技能：Fuzzers、静态分析、Sanitizers、覆盖率 |
| `variant-analysis` | 基于模式分析在代码库中发现类似漏洞 |

### ✅ 验证
| 子技能名称 | 说明 |
|:---|:---|
| `constant-time-analysis` | 检测加密代码中编译器引入的时序侧信道 |
| `property-based-testing` | 多语言和智能合约的基于属性测试指导 |
| `spec-to-code-compliance` | 区块链审计的规范到代码合规性检查器 |

### 📋 审计生命周期
| 子技能名称 | 说明 |
|:---|:---|
| `fix-review` | 验证修复提交是否解决了审计发现且未引入新漏洞 |

### 🔧 逆向工程
| 子技能名称 | 说明 |
|:---|:---|
| `dwarf-expert` | 交互和理解 DWARF 调试格式 |

### 📱 移动安全
| 子技能名称 | 说明 |
|:---|:---|
| `firebase-apk-scanner` | 扫描 Android APK 的 Firebase 安全配置错误 |

### 💻 开发
| 子技能名称 | 说明 |
|:---|:---|
| `ask-questions-if-underspecified` | 实现前澄清需求 |

### 👥 团队管理
| 子技能名称 | 说明 |
|:---|:---|
| `culture-index` | 解释个人和团队的 Culture Index 调查结果 |

### 🛠️ 工具
| 子技能名称 | 说明 |
|:---|:---|
| `claude-in-chrome-troubleshooting` | 诊断和修复 Claude in Chrome MCP 扩展连接问题 |

---

## 维护说明

1. **同步更新**: 与 `skills-by-category.md` 保持同步
2. **子技能名称**: 必须与仓库中子目录名完全一致
3. **新增仓库**: 发现新的多技能仓库时，添加到对应分类
4. **格式规范**: 按分类和仓库分组，便于查阅

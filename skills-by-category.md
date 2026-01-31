# Claude Skills 功能分类汇总

> **⚠️ 免责声明**：以下链接仅供 Skills 安装测试，具体用途、安全性和限制请务必查阅对应仓库说明。本文档仅作功能汇总，版权归属原项目作者。

<div align="center">

| 📅 分析日期 | 📦 仓库总数 | 🧩 技能总数 |
| :---: | :---: | :---: |
| 2026-01-28 | 18 | ~329+ |

</div>

## 📖 目录索引

| 章节 | 🏷️ 分类 | 📊 技能数 |
| :---: | :--- | ---: |
| [01](#一开发工作流-development-workflow) | 🛠️ 开发工作流 | 14 |
| [02](#二科学计算与研究-scientific-computing) | 🧬 科学计算与研究 | 140 |
| [03](#三文本处理与写作-text--writing) | ✍️ 文本处理与写作 | 19 |
| [04](#四创业与商业-startup--business) | 💼 创业与商业 | 26 |
| [05](#五笔记与知识管理-note-taking--knowledge) | 📓 笔记与知识管理 | 6 |
| [06](#六prompt工程与技能管理-skill-management) | 🤖 Prompt工程与管理 | 4 |
| [07](#七专业领域-professional-domains) | ⚖️ 专业领域 | 61 |
| [08](#八综合工具集-comprehensive-toolkits) | 🧰 综合工具集 | 32 |
| [09](#九开发工具集-development-toolkit) | 💻 开发工具集 | 27 |

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

## 二、科学计算与研究 (Scientific Computing)

### 📦 [K-Dense-AI/claude-scientific-skills](https://github.com/K-Dense-AI/claude-scientific-skills)
**简介**：最全面的科学计算工具集，覆盖生物、化学、物理、数据科学等多学科领域。

#### 🧬 生物信息与基因组学
| 技能 | 描述 | 技能 | 描述 |
| :--- | :--- | :--- | :--- |
| `adaptyv` | 蛋白质自动化测试云实验室 | `alphafold-database` | AlphaFold 蛋白质结构数据库 |
| `anndata` | 单细胞分析注释矩阵 | `arboreto` | 基因调控网络推断 |
| `benchling-integration` | 研发平台(DNA/蛋白/细胞) | `biopython` | 分子生物学综合工具包 |
| `cellxgene-census` | 查询单细胞目录 | `clinvar-database` | 查询变异临床意义 |
| `cosmic-database` | 癌症突变数据库 | `deeptools` | NGS分析工具包 |
| `dnanexus-integration` | 云基因组平台集成 | `ena-database` | 欧洲核苷酸档案访问 |
| `ensembl-database` | 基因组数据库查询 | `esm` | 蛋白质语言模型工具包 |
| `etetoolkit` | 系统发育树工具包 | `flowio` | 解析 FCS 流式细胞术文件 |
| `gene-database` | NCBI Gene 查询 | `geniml` | 基因组区间机器学习 |
| `geo-database` | NCBI GEO 基因表达数据 | `gtars` | Rust 高性能基因组分析 |
| `kegg-database` | KEGG 通路分析 | `pydeseq2` | 差异基因表达分析 |
| `pysam` | 基因组文件处理 (BAM/VCF) | `scanpy` | 单细胞 RNA-seq 分析 |
| `scikit-bio` | 生物数据工具包 | `scvi-tools` | 单细胞组学深度生成模型 |
| `string-database` | 蛋白质相互作用查询 | `uniprot-database` | UniProt 数据库访问 |

#### 💊 化学、药物与代谢
| 技能 | 描述 | 技能 | 描述 |
| :--- | :--- | :--- | :--- |
| `brenda-database` | 酶数据库访问 | `chembl-database` | 生物活性分子查询 |
| `clinpgx-database` | 药物基因组学数据 | `cobrapy` | 基于约束的代谢建模 |
| `datamol` | RDKit 的 Python 封装 | `deepchem` | 分子机器学习 |
| `diffdock` | 分子对接预测 | `drugbank-database` | 药物信息分析 |
| `fda-database` | OpenFDA API 查询 | `hmdb-database` | 人类代谢组数据库 |
| `matchms` | 代谢组学谱相似性 | `medchem` | 药物化学过滤器 |
| `metabolomics-workbench` | 代谢组学数据访问 | `molfeat` | 分子特征化工具 |
| `opentargets-database` | 靶点-疾病关联查询 | `pubchem-database` | PubChem 化合物查询 |
| `pyopenms` | 完整质谱分析平台 | `pytdc` | 药物发现数据集 |
| `rdkit` | 化学信息学工具包 | `rowan` | 量子化学云平台 |
| `zinc-database` | 可购买化合物数据库 | | |

#### 🔭 物理、量子与工程
| 技能 | 描述 | 技能 | 描述 |
| :--- | :--- | :--- | :--- |
| `astropy` | 天文学综合库 | `cirq` | Google 量子计算框架 |
| `fluidsim` | 计算流体力学模拟 | `pennylane` | 量子机器学习框架 |
| `pymatgen` | 材料科学工具包 | `qiskit` | IBM 量子计算框架 |
| `qutip` | 量子物理模拟库 | `simpy` | 离散事件仿真框架 |

#### 📊 数据科学与机器学习
| 技能 | 描述 | 技能 | 描述 |
| :--- | :--- | :--- | :--- |
| `aeon` | 时间序列机器学习 | `dask` | 分布式计算框架 |
| `datacommons-client` | 统计数据访问 | `exploratory-data-analysis` | 探索性数据分析 (EDA) |
| `geopandas` | 地理空间矢量数据 | `matplotlib` | 基础绘图库 |
| `networkx` | 网络分析与可视化 | `pandas/polars` | 数据处理库 |
| `plotly/seaborn` | 数据可视化库 | `pymc-bayesian` | 贝叶斯建模 |
| `pymoo` | 多目标优化框架 | `pytorch-lightning` | 深度学习框架 |
| `scikit-learn` | 机器学习标准库 | `scikit-survival` | 生存分析工具包 |
| `shap` | 模型可解释性 | `statsmodels` | 统计模型库 |
| `sympy` | 符号数学计算 | `torch-geometric` | 图神经网络 (PyG) |
| `transformers` | Hugging Face 模型 | `umap-learn` | 降维算法 |

#### 📝 科研辅助与写作
| 技能 | 描述 | 技能 | 描述 |
| :--- | :--- | :--- | :--- |
| `biorxiv-database` | 预印本搜索 | `citation-management` | 引文管理 |
| `latex-posters` | LaTeX 海报制作 | `literature-review` | 系统性文献综述 |
| `openalex-database` | 学术文献分析 | `paper-2-web` | 论文转交互式网页 |
| `peer-review` | 手稿/资助评审辅助 | `pptx-posters` | HTML/CSS 海报制作 |
| `pubmed-database` | 数据库访问 | `research-grants` | 资助申请撰写 |
| `scientific-writing` | 科学写作核心技能 | `scientific-visualization` | 出版级图表制作 |

*(注：为节省篇幅，部分通用或极冷门技能未完全列出，但核心技能已涵盖)*

---

## 三、文本处理与写作 (Text & Writing)

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
| | `slack-gif-creator` | Slack 动画 GIF 制作 |
| **📄 文档处理** | `docx` / `xlsx` | Word / Excel 处理 |
| | `pdf` | PDF 操作工具包 |
| | `pptx` | PowerPoint 演示文稿 |
| | `doc-coauthoring` | 文档协作工作流 |
| **🏗️ 构建与开发** | `mcp-builder` | MCP 服务器构建指南 |
| | `web-artifacts-builder` | 复杂 Web 产物构建 |
| | `webapp-testing` | Web 应用测试 |

---

## 四、创业与商业 (Startup & Business)

### 📦 [Agent-3-7/yc-advisor](https://github.com/Agent-3-7/agent37-skills-collection)
| 技能 | 功能 |
| :--- | :--- |
| `yc-advisor` | **YC 创业顾问**：基于 443 个精选资源（Paul Graham论文/访谈）提供创业决策支持 |

### 📦 [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills)
| 分类 | 技能示例 | 核心功能 |
| :--- | :--- | :--- |
| **📈 转化率优化 (CRO)** | `signup-flow-cro` | 注册/页面/表单/弹窗/付费墙优化 |
| **✍️ 内容营销** | `copywriting` | 文案写作、编辑、内容策略、社交内容 |
| **🚀 增长策略** | `launch-strategy` | 邮件序列、推荐计划、发布策略、定价 |
| **🔍 SEO/广告** | `seo-audit` | SEO审计、程序化SEO、Schema标记、付费广告 |
| **📊 分析优化** | `ab-test-setup` | A/B测试设置、分析追踪、营销心理学 |

---

## 五、笔记与知识管理 (Note-taking & Knowledge)

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

## 六、Prompt工程与技能管理 (Skill Management)

### 📦 [chujianyun/skills](https://github.com/chujianyun/skills)
*   `prompt-optimizer`: Prompt 优化专家（内置 57 种框架）
*   `sync-skills`: 技能同步工具

### 📦 [tripleyak/SkillForge](https://github.com/tripleyak/SkillForge)
*   `skillforge`: 智能技能路由（分析输入自动匹配技能）

### 📦 [OthmanAdi/planning-with-files](https://github.com/OthmanAdi/planning-with-files)
*   `planning-with-files`: 类 Manus 的基于文件的复杂任务规划系统

---

## 七、专业领域 (Professional Domains)

### 📦 [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills)
**企业级团队技能矩阵**：
| 团队 | 技能数 | 覆盖范围 |
| :--- | :---: | :--- |
| 🛠️ **Engineering** | 18 | 架构, 前后端, QA, DevOps, 安全, 数据工程 |
| ⚖️ **RA/QM** | 12 | ISO 13485, MDR, FDA, GDPR, ISO 27001 合规 |
| 📱 **Product** | 6 | 产品策略, 敏捷管理, UX 研究, UI 设计系统 |
| 👔 **C-Level** | 2 | CEO/CTO 顾问 |
| 📢 **Marketing** | 5 | 内容创作, 需求生成, ASO, 社媒分析 |

### 📦 [muratcankoylan/Agent-Skills-for-Context-Engineering](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering)
**上下文工程与 Agent 设计**：
*   **上下文处理**：压缩、优化、降级诊断
*   **系统设计**：多智能体模式、工具设计、文件系统上下文卸载
*   **评估调试**：Agent 评估、推理追踪优化 (Reasoning Trace)
*   **认知建模**：BDI 精神状态建模、记忆系统实现

---

## 八、综合工具集 (Comprehensive Toolkits)

### 📦 [ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills)

| 分类 | 技能 | 功能 |
| :--- | :--- | :--- |
| **📄 文档处理** | `docx`/`pdf`/`ppt`/`xlsx` | Office 全家桶处理套件 |
| **🛠️ 开发工具** | `artifacts-builder` | 创建多组件工件 |
| | `mcp-builder` | MCP 协议构建指南 |
| | `skill-creator` | 技能开发工具链 |
| | `langsmith-fetch` | LangChain/LangGraph 调试 |
| **⚡ 生产力** | `connect-apps` | 连接外部应用 (Gmail/Slack/GitHub) |
| | `file-organizer` | 智能文件/发票整理 |
| | `meeting-insights` | 会议洞察分析 |
| | `webapp-testing` | Web 应用测试 |
| **✍️ 内容创作** | `tailored-resume` | 定制简历生成 |
| | `content-research` | 内容研究与写作 |
| | `twitter-optimizer` | Twitter 算法优化 |
| | `competitive-ads` | 竞品广告分析 |

---

## 九、开发工具集 (Development Toolkit)

### 📦 [mrgoonie/claudekit-skills](https://github.com/mrgoonie/claudekit-skills)

ClaudeKit.cc 官方提供的开发全生命周期工具集：

| 模块 | 插件名称 | 核心能力 |
| :--- | :--- | :--- |
| **💻 开发工具** | `web-dev-tools` | React, Next.js, Tailwind CSS 支持 |
| | `backend-tools` | Node.js, Python, Go, 认证模块 |
| | `devops-tools` | Cloudflare, Docker, GCP, 数据库管理 |
| | `debugging-tools` | 系统化调试框架 |
| **🤖 AI 与处理** | `ai-ml-tools` | Gemini API 集成, 上下文工程 |
| | `document-tools` | Word, PDF, PPT, Excel 处理 |
| | `media-tools` | FFmpeg, ImageMagick 媒体处理 |
| | `research-tools` | 文档发现与检索 |
| **🚀 高级功能** | `problem-solving` | 高级思维技术框架 |
| | `specialized-tools` | 顺序思考, 图表生成 |
| | `platform-tools` | Shopify 集成, MCP 管理 |
| | `meta-tools` | 技能创建, 代码审查 |

---

> 📝 **备注**：本文档更新于 2026-01-28。
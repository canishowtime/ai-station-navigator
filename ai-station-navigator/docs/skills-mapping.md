# 子技能映射表 (Sub-skills Mapping)

> **用途**: 当用户请求安装子技能时，Kernel 查找此表自动定位所属主仓库，并添加 `--skill` 参数

> **数据源**: `skills-by-category.md`
> **更新日期**: 2026-01-30

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

## 二、科学计算与研究 (K-Dense-AI/claude-scientific-skills)

### 🧬 生物信息与基因组学
| 子技能名称 | 说明 |
|:---|:---|
| `adaptyv` | 蛋白质自动化测试云实验室 |
| `alphafold-database` | AlphaFold 蛋白质结构数据库 |
| `anndata` | 单细胞分析注释矩阵 |
| `arboreto` | 基因调控网络推断 |
| `benchling-integration` | 研发平台(DNA/蛋白/细胞) |
| `biopython` | 分子生物学综合工具包 |
| `cellxgene-census` | 查询单细胞目录 |
| `clinvar-database` | 查询变异临床意义 |
| `cosmic-database` | 癌症突变数据库 |
| `deeptools` | NGS分析工具包 |
| `dnanexus-integration` | 云基因组平台集成 |
| `ena-database` | 欧洲核苷酸档案访问 |
| `ensembl-database` | 基因组数据库查询 |
| `esm` | 蛋白质语言模型工具包 |
| `etetoolkit` | 系统发育树工具包 |
| `flowio` | 解析 FCS 流式细胞术文件 |
| `gene-database` | NCBI Gene 查询 |
| `geniml` | 基因组区间机器学习 |
| `geo-database` | NCBI GEO 基因表达数据 |
| `gtars` | Rust 高性能基因组分析 |
| `kegg-database` | KEGG 通路分析 |
| `pydeseq2` | 差异基因表达分析 |
| `pysam` | 基因组文件处理 (BAM/VCF) |
| `scanpy` | 单细胞 RNA-seq 分析 |
| `scikit-bio` | 生物数据工具包 |
| `scvi-tools` | 单细胞组学深度生成模型 |
| `string-database` | 蛋白质相互作用查询 |
| `uniprot-database` | UniProt 数据库访问 |

### 💊 化学、药物与代谢
| 子技能名称 | 说明 |
|:---|:---|
| `brenda-database` | 酶数据库访问 |
| `chembl-database` | 生物活性分子查询 |
| `clinpgx-database` | 药物基因组学数据 |
| `cobrapy` | 基于约束的代谢建模 |
| `datamol` | RDKit 的 Python 封装 |
| `deepchem` | 分子机器学习 |
| `diffdock` | 分子对接预测 |
| `drugbank-database` | 药物信息分析 |
| `fda-database` | OpenFDA API 查询 |
| `hmdb-database` | 人类代谢组数据库 |
| `matchms` | 代谢组学谱相似性 |
| `medchem` | 药物化学过滤器 |
| `metabolomics-workbench` | 代谢组学数据访问 |
| `molfeat` | 分子特征化工具 |
| `opentargets-database` | 靶点-疾病关联查询 |
| `pubchem-database` | PubChem 化合物查询 |
| `pyopenms` | 完整质谱分析平台 |
| `pytdc` | 药物发现数据集 |
| `rdkit` | 化学信息学工具包 |
| `rowan` | 量子化学云平台 |
| `zinc-database` | 可购买化合物数据库 |

### 🔭 物理、量子与工程
| 子技能名称 | 说明 |
|:---|:---|
| `astropy` | 天文学综合库 |
| `cirq` | Google 量子计算框架 |
| `fluidsim` | 计算流体力学模拟 |
| `pennylane` | 量子机器学习框架 |
| `pymatgen` | 材料科学工具包 |
| `qiskit` | IBM 量子计算框架 |
| `qutip` | 量子物理模拟库 |
| `simpy` | 离散事件仿真框架 |

### 📊 数据科学与机器学习
| 子技能名称 | 说明 |
|:---|:---|
| `aeon` | 时间序列机器学习 |
| `dask` | 分布式计算框架 |
| `datacommons-client` | 统计数据访问 |
| `exploratory-data-analysis` | 探索性数据分析 (EDA) |
| `geopandas` | 地理空间矢量数据 |
| `matplotlib` | 基础绘图库 |
| `networkx` | 网络分析与可视化 |
| `pandas` | 数据处理库 |
| `polars` | 数据处理库 |
| `plotly` | 数据可视化库 |
| `seaborn` | 数据可视化库 |
| `pymc-bayesian` | 贝叶斯建模 |
| `pymoo` | 多目标优化框架 |
| `pytorch-lightning` | 深度学习框架 |
| `scikit-learn` | 机器学习标准库 |
| `scikit-survival` | 生存分析工具包 |
| `shap` | 模型可解释性 |
| `statsmodels` | 统计模型库 |
| `sympy` | 符号数学计算 |
| `torch-geometric` | 图神经网络 (PyG) |
| `transformers` | Hugging Face 模型 |
| `umap-learn` | 降维算法 |

### 📝 科研辅助与写作
| 子技能名称 | 说明 |
|:---|:---|
| `biorxiv-database` | 预印本搜索 |
| `citation-management` | 引文管理 |
| `latex-posters` | LaTeX 海报制作 |
| `literature-review` | 系统性文献综述 |
| `openalex-database` | 学术文献分析 |
| `paper-2-web` | 论文转交互式网页 |
| `peer-review` | 手稿/资助评审辅助 |
| `pptx-posters` | HTML/CSS 海报制作 |
| `pubmed-database` | 数据库访问 |
| `research-grants` | 资助申请撰写 |
| `scientific-writing` | 科学写作核心技能 |
| `scientific-visualization` | 出版级图表制作 |

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
| `docx` | Word 处理 |
| `xlsx` | Excel 处理 |
| `pdf` | PDF 操作工具包 |
| `pptx` | PowerPoint 演示文稿 |
| `doc-coauthoring` | 文档协作工作流 |
| `mcp-builder` | MCP 服务器构建指南 |
| `web-artifacts-builder` | 复杂 Web 产物构建 |
| `webapp-testing` | Web 应用测试 |

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

### zh-xx/legal-assistant-skills
| 子技能名称 | 说明 |
|:---|:---|
| `contract-review` | 合同审查与风险标注 |

### alirezarezvani/claude-skills
企业级团队技能矩阵（43 个技能，覆盖 Engineering/RA/QM/Product/C-Level/Marketing）

### muratcankoylan/Agent-Skills-for-Context-Engineering
上下文工程与 Agent 设计（上下文处理、系统设计、评估调试、认知建模）

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

### mrgoonie/claudekit-skills
| 子技能名称 | 说明 |
|:---|:---|
| `web-dev-tools` | React, Next.js, Tailwind CSS 支持 |
| `backend-tools` | Node.js, Python, Go, 认证模块 |
| `devops-tools` | Cloudflare, Docker, GCP, 数据库管理 |
| `debugging-tools` | 系统化调试框架 |
| `ai-ml-tools` | Gemini API 集成, 上下文工程 |
| `document-tools` | Word, PDF, PPT, Excel 处理 |
| `media-tools` | FFmpeg, ImageMagick 媒体处理 |
| `research-tools` | 文档发现与检索 |
| `problem-solving` | 高级思维技术框架 |
| `specialized-tools` | 顺序思考, 图表生成 |
| `platform-tools` | Shopify 集成, MCP 管理 |
| `meta-tools` | 技能创建, 代码审查 |

---

## 维护说明

1. **同步更新**: 与 `skills-by-category.md` 保持同步
2. **子技能名称**: 必须与仓库中子目录名完全一致
3. **新增仓库**: 发现新的多技能仓库时，添加到对应分类
4. **格式规范**: 按分类和仓库分组，便于查阅

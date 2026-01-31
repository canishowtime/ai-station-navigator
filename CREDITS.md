# 第三方软件使用声明 (Third Party Notices)

本工具集成了以下第三方开源软件或组件，其版权归各自作者所有：

---

## 核心框架

### 1. Claude Code
* **官网**: https://anthropic.com
* **协议**: 商业产品
* **说明**: Anthropic 出品的 AI 智能体引擎，提供代码理解与生成能力
* **条款**: https://www.anthropic.com/legal

---

## 便携运行环境 (Portable Runtime)

本工具继承包包含以下绿色版（便携）软件，无需安装即可运行：

### 1. Git for Windows Portable
* **官网**: https://git-scm.com
* **协议**: GNU GPL v2
* **说明**: 分布式版本控制系统
* **条款**: https://git-scm.com/about/gpl

### 2. Node.js & NPM Portable
* **官网**: https://nodejs.org
* **协议**: MIT
* **说明**: JavaScript 运行环境与包管理器
* **条款**: https://github.com/nodejs/node/blob/main/LICENSE

### 3. Python Portable
* **官网**: https://python.org
* **协议**: Python License 2.0
* **说明**: Python 解释器与标准库
* **条款**: https://docs.python.org/3/license.html

### 4. Windows Terminal
* **官网**: https://learn.microsoft.com/windows/terminal
* **协议**: MIT
* **说明**: 微软现代化终端模拟器
* **条款**: https://github.com/microsoft/terminal/blob/main/LICENSE

---

## 免责声明 (Disclaimer)

> **使用即表示您知晓风险，后果自负**

* 本工具仅为智能体调度系统封装，不对 AI 引擎生成的内容安全性负责。
* 用户在使用 Claude Code 执行 Bash 命令、文件读写等操作时，应仔细审计每一步操作。
* 因执行 AI 建议导致的任何数据丢失或系统损坏，本工具作者概不负责。
* 各技能遵循其原始许可证，详见各技能目录下的 LICENSE 文件。
* 第三方 API 服务（如 DeepSeek、智谱 AI、MiniMax 等）的数据处理策略及服务条款由各供应商独立负责。

---

## 致谢

感谢以下开源项目与社区的贡献：

---

## 🐍 Python 第三方库

### 核心依赖
| 库名称 | 协议 | 说明 |
|:---|:---|:---|
| [TinyDB](https://github.com/msiemens/tinydb) | MIT | 轻量级文档数据库，用于技能索引存储 |
| [PyYAML](https://github.com/yaml/pyyaml) | MIT | YAML 配置文件解析器 |

### 数据处理与文档
| 库名称 | 协议 | 说明 |
|:---|:---|:---|
| [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) | MIT | HTML/XML 解析库 |
| [lxml](https://lxml.de) | BSD | 高性能 XML/HTML 处理库 |
| [markdownify](https://github.com/matthewwithanm/python-markdownify) | MIT | HTML 转 Markdown 工具 |
| [MarkItDown](https://github.com/microsoft/markitdown) | MIT | Microsoft 文档转换工具 |
| [pypdf](https://github.com/py-pdf/pypdf) | BSD-3-Clause | PDF 文档处理库 |

### 网络请求与安全
| 库名称 | 协议 | 说明 |
|:---|:---|:---|
| [requests](https://github.com/psf/requests) | Apache 2.0 | HTTP 请求库 |
| [certifi](https://github.com/certifi/python-certifi) | MPL-2.0 | SSL 证书验证 |
| [charset-normalizer](https://github.com/Ousret/charset_normalizer) | MIT | 字符编码检测与转换 |
| [idna](https://github.com/kjd/idna) | BSD-3-Clause | 国际化域名编码 |
| [defusedxml](https://github.com/tiran/defusedxml) | Python-2.0 | 安全的 XML 解析库（防 XXE 攻击） |

### 开发工具
| 库名称 | 协议 | 说明 |
|:---|:---|:---|
| [packaging](https://github.com/pypa/packaging) | Apache-2.0 / BSD | Python 包核心工具 |
| [pathspec](https://github.com/cpburnz/python-pathspec) | MPL-2.0 | Git 风格的文件路径匹配 |
| [pluggy](https://github.com/pytest-dev/pluggy) | MIT | 插件系统核心库 |
| [setuptools](https://github.com/pypa/setuptools) | MIT | Python 包构建与安装工具 |
| [hatchling](https://github.com/pypa/hatch) | MIT | 现代化 Python 构建后端 |
| [trove-classifiers](https://github.com/pypa/trove-classifiers) | Apache-2.0 | PyPI 分类器列表 |

### 通用工具
| 库名称 | 协议 | 说明 |
|:---|:---|:---|
| [six](https://github.com/benjaminp/six) | MIT | Python 2/3 兼容层 |
| [typing_extensions](https://github.com/python/typing_extensions) | Python-2.0 | typing 模块反向移植 |

---

## 🔌 开源技能项目

### 开发工作流
| 项目 | 仓库 | 说明 |
|:---|:---|:---|
| Superpowers | [obra/superpowers](https://github.com/obra/superpowers) | 开发工作流技能集（Git/TDD/代码审查/子智能体） |

### 科学计算与研究
| 项目 | 仓库 | 说明 |
|:---|:---|:---|
| Scientific Skills | [K-Dense-AI/claude-scientific-skills](https://github.com/K-Dense-AI/claude-scientific-skills) | 生物信息、化学、物理、数据科学、科研辅助工具集 |

### 文本处理与写作
| 项目 | 仓库 | 说明 |
|:---|:---|:---|
| Humanizer-zh | [op7418/Humanizer-zh](https://github.com/op7418/Humanizer-zh) | 中文文本去 AI 味优化工具 |
| Deep Reading Analyst | [ginobefun/deep-reading-analyst-skill](https://github.com/ginobefun/deep-reading-analyst-skill) | 文章/论文/书籍深度分析框架 |
| Anthropic Skills | [anthropics/skills](https://github.com/anthropics/skills) | 官方技能集（文档处理/MCP/Web 构建） |

### 创业与商业
| 项目 | 仓库 | 说明 |
|:---|:---|:---|
| Agent37 Skills | [Agent-3-7/agent37-skills-collection](https://github.com/Agent-3-7/agent37-skills-collection) | YC 创业顾问技能集 |
| Marketing Skills | [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills) | 营销转化率优化与策略工具集 |

### 笔记与知识管理
| 项目 | 仓库 | 说明 |
|:---|:---|:---|
| Obsidian Skills | [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) | Obsidian 集成技能（Canvas/Bases/双链） |
| Obsidian Visual Skills | [axtonliu/axton-obsidian-visual-skills](https://github.com/axtonliu/axton-obsidian-visual-skills) | Excalidraw/Mermaid 图表可视化技能 |

### Prompt 工程与技能管理
| 项目 | 仓库 | 说明 |
|:---|:---|:---|
| Prompt Skills | [chujianyun/skills](https://github.com/chujianyun/skills) | Prompt 优化专家与技能同步工具 |
| SkillForge | [tripleyak/SkillForge](https://github.com/tripleyak/SkillForge) | 智能技能路由系统 |
| Planning with Files | [OthmanAdi/planning-with-files](https://github.com/OthmanAdi/planning-with-files) | 类 Manus 的基于文件的复杂任务规划 |

### 专业领域
| 项目 | 仓库 | 说明 |
|:---|:---|:---|
| Enterprise Skills | [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills) | 企业级团队技能矩阵（43 个职业技能） |
| Context Engineering | [muratcankoylan/Agent-Skills-for-Context-Engineering](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering) | 上下文工程与 Agent 设计 |

### 综合工具集
| 项目 | 仓库 | 说明 |
|:---|:---|:---|
| Awesome Claude Skills | [ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills) | 文档处理、MCP、应用集成、营销分析工具集 |
| ClaudeKit Skills | [mrgoonie/claudekit-skills](https://github.com/mrgoonie/claudekit-skills) | 全栈开发工具集（Web/后端/DevOps/媒体） |

---

*最后更新: 2026-01-28*

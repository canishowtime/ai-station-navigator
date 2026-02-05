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

### 5. Cisco Skill Scanner
* **项目: https://github.com/cisco-ai-defense/skill-scanner
* **协议: Apache-2.0
* **说明: 由思科（Cisco）开发的 AI 技能安全扫描工具，用于检测 AI 插件及 Agent 定义中的潜在安全风险。
* **条款: https://github.com/cisco-ai-defense/skill-scanner/blob/main/LICENSE

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

## 🐛 Python 第三方库

> **完整法律声明**: 本项目使用的所有 Python 第三方库（100+）详见 `bin/python/Lib/site-packages/LICENSES.txt`
> 该文件包含完整的许可证信息、版权声明及版本号。下表为主要依赖库概览。

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
| [click](https://github.com/pallets/click) | MIT | 命令行界面创建工具 |
| [rich](https://github.com/Textualize/rich) | MIT | 终端富文本格式化 |
| [tabulate](https://github.com/astanin/python-tabulate) | MIT | 表格格式化输出 |
| [colorama](https://github.com/tartley/colorama) | BSD | 跨平台终端颜色输出 |
| [tqdm](https://github.com/tqdm/tqdm) | MPL-2.0 / MIT | 进度条显示库 |

### AI/ML 框架
| 库名称 | 协议 | 说明 |
|:---|:---|:---|
| [anthropic](https://github.com/anthropics/anthropic-python) | MIT | Anthropic API 官方 SDK |
| [tiktoken](https://github.com/openai/tiktoken) | MIT | OpenAI 分词器 |
| [huggingface_hub](https://github.com/huggingface/huggingface_hub) | Apache-2.0 | Hugging Face 模型仓库 |
| [tokenizers](https://github.com/huggingface/tokenizers) | Apache-2.0 | 高性能分词器 |

### 异步与并发
| 库名称 | 协议 | 说明 |
|:---|:---|:---|
| [aiohttp](https://github.com/aio-libs/aiohttp) | Apache-2.0 / MIT | 异步 HTTP 客户端/服务器 |
| [httpx](https://github.com/encode/httpx) | BSD-3-Clause | 现代异步 HTTP 客户端 |
| [httpcore](https://github.com/encode/httpcore) | BSD | HTTP/1.1 / HTTP/2 核心库 |
| [anyio](https://github.com/agronholm/anyio) | MIT | 异步网络 I/O 抽象层 |
| [websockets](https://github.com/aaugustin/websockets) | BSD-3-Clause | WebSocket 协议实现 |
| [watchfiles](https://github.com/samuelcolvin/watchfiles) | MIT | 文件监控库 |

### Web 框架
| 库名称 | 协议 | 说明 |
|:---|:---|:---|
| [fastapi](https://github.com/tiangolo/fastapi) | MIT | 现代异步 Web 框架 |
| [starlette](https://github.com/encode/starlette) | BSD | ASGI 工具包 |
| [uvicorn](https://github.com/encode/uvicorn) | BSD | ASGI HTTP 服务器 |

### 数据验证与序列化
| 库名称 | 协议 | 说明 |
|:---|:---|:---|
| [pydantic](https://github.com/pydantic/pydantic) | MIT | 数据验证与设置管理 |
| [pydantic-core](https://github.com/pydantic/pydantic-core) | MIT | Pydantic 核心引擎 |
| [attrs](https://github.com/python-attrs/attrs) | MIT | 类装饰器与工具 |
| [orjson](https://github.com/ijl/orjson) | Apache-2.0 / MIT | 高性能 JSON 序列化 |
| [ormsgpack](https://github.com/ormsgpack/ormsgpack) | Apache-2.0 / MIT | 高性能 MessagePack |

### LangChain 生态
| 库名称 | 协议 | 说明 |
|:---|:---|:---|
| [langchain-core](https://github.com/langchain-ai/langchain) | MIT | LangChain 核心接口 |
| [langgraph](https://github.com/langchain-ai/langgraph) | MIT | 状态ful Agent 框架 |
| [langgraph-checkpoint](https://github.com/langchain-ai/langgraph) | MIT | LangGraph 检查点机制 |
| [langgraph-checkpoint-sqlite](https://github.com/langchain-ai/langgraph) | MIT | SQLite 检查点存储 |
| [langgraph-prebuilt](https://github.com/langchain-ai/langgraph) | MIT | LangGraph 预构建组件 |
| [langgraph-sdk](https://github.com/langchain-ai/langgraph) | MIT | LangGraph SDK |
| [langsmith](https://github.com/langchain-ai/langsmith) | MIT | LangChain 调试与监控平台 |

### 数据库与存储
| 库名称 | 协议 | 说明 |
|:---|:---|:---|
| [TinyDB](https://github.com/msiemens/tinydb) | MIT | 轻量级文档数据库 |
| [aiosqlite](https://github.com/jreese/aiosqlite) | MIT | 异步 SQLite 封装 |
| [sqlite-vec](https://github.com/asg017/sqlite-vec) | MIT / Apache-2.0 | SQLite 向量搜索扩展 |

### 网络工具
| 库名称 | 协议 | 说明 |
|:---|:---|:---|
| [urllib3](https://github.com/urllib3/urllib3) | Apache-2.0 | HTTP 客户端库 |
| [httplib2](https://github.com/httplib2/httplib2) | MIT | 综合 HTTP 客户端 |
| [requests-toolbelt](https://github.com/requests/toolbelt) | Apache-2.0 | Requests 实用工具集 |
| [sniffio](https://github.com/python-trio/sniffio) | MIT / Apache-2.0 | 异步库检测 |
| [h11](https://github.com/python-hyper/h11) | MIT | HTTP/1.1 协议实现 |

### 安全与加密
| 库名称 | 协议 | 说明 |
|:---|:---|:---|
| [cryptography](https://github.com/pyca/cryptography) | Apache-2.0 / BSD | 加密工具库 |
| [certifi](https://github.com/certifi/python-certifi) | MPL-2.0 | Mozilla CA 证书包 |
| [yara-python](https://github.com/VirusTotal/yara-python) | BSD-3-Clause | 恶意软件模式匹配 |

### 文件处理
| 库名称 | 协议 | 说明 |
|:---|:---|:---|
| [openpyxl](https://github.com/theorchard/openpyxl) | MIT | Excel 文件读写 |
| [python-dateutil](https://github.com/dateutil/dateutil) | Apache-2.0 / BSD | 日期时间解析 |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | BSD | .env 文件解析 |
| [fsspec](https://github.com/fsspec/filesystem_spec) | BSD | 文件系统抽象层 |

### Markdown 处理
| 库名称 | 协议 | 说明 |
|:---|:---|:---|
| [markdown-it-py](https://github.com/executablebooks/markdown-it-py) | MIT | Markdown 解析器 |
| [mdurl](https://github.com/executablebooks/mdurl) | MIT | URL 解析工具 |
| [python-frontmatter](https://github.com/eyeseast/python-frontmatter) | MIT | Frontmatter 元数据解析 |

### 其他工具库
| 库名称 | 协议 | 说明 |
|:---|:---|:---|
| [docstring_parser](https://github.com/rr-/docstring_parser) | MIT | 文档字符串解析 |
| [python-frontmatter](https://github.com/eyeseast/python-frontmatter) | MIT | Frontmatter 元数据处理 |
| [referencing](https://github.com/compositionalhq/referencing) | MIT | JSON Schema 引用解析 |
| [jsonschema](https://github.com/python-jsonschema/jsonschema) | MIT | JSON Schema 验证 |
| [jsonschema-specifications](https://github.com/python-jsonschema/jsonschema-specifications) | MIT | JSON Schema 规范 |
| [rpds-py](https://github.com/crate-py/rpds) | MIT / Apache-2.0 | 高性能持久化数据结构 |
| [regex](https://github.com/mrabarnett/mrab-regex) | Apache-2.0 | 正则表达式引擎 |
| [pyparsing](https://github.com/pyparsing/pyparsing) | MIT | Python 解析器构建 |
| [typer-slim](https://github.com/fastapi/typer) | MIT | 命令行界面构建 |
| [typing-inspection](https://github.com/ilevkivskyi/typing_inspection) | MIT | 运行时类型检查 |

### 工具与实用程序
| 库名称 | 协议 | 说明 |
|:---|:---|:---|
| [aiohappyeyeballs](https://github.com/sethmlarson/aiohappyeyeballs) | PSF-2.0 | 异步连接管理 |
| [aiosignal](https://github.com/aio-libs/aiosignal) | Apache-2.0 | 异步信号量 |
| [annotated-doc](https://github.com/alteryks/annotated-doc) | MIT | 注解文档生成 |
| [annotated-types](https://github.com/cython-pr/annotated-types) | MIT | 类型注解支持 |
| [async-timeout](https://github.com/aio-libs/async-timeout) | Apache-2.0 | 异步超时管理 |
| [bson](https://github.com/py-bson/bson) | BSD | BSON 编码/解码 |
| [cffi](https://github.com/python-cffi/cffi) | MIT | C 外部函数接口 |
| [distro](https://github.com/nir0s/distro) | Apache-2.0 | Linux 发行版信息 |
| [et_xmlfile](https://github.com/heince/et_xmlfile) | MIT | XML 文件处理 |
| [fastuuid](https://github.com/omenband/fastuuid) | MIT | 高性能 UUID |
| [filelock](https://github.com/tox-dev/pyfilelock) | BSD | 跨平台文件锁 |
| [frozenlist](https://github.com/aio-libs/frozenlist) | Apache-2.0 | 不可变列表 |
| [fsspec](https://github.com/fsspec/filesystem_spec) | BSD | 文件系统规范 |
| [googleapis-common-protos](https://github.com/googleapis/python-api-common-protos) | Apache-2.0 | Google API 通用原型 |
| [grpcio](https://github.com/grpc/grpc) | Apache-2.0 | gRPC 框架 |
| [grpcio-status](https://github.com/grpc/grpc) | Apache-2.0 | gRPC 状态码 |
| [hf-xet](https://huggingface.co) | Apache-2.0 | Hugging Face 下载加速 |
| [httptools](https://github.com/MagicStack/httptools) | MIT | HTTP 解析工具 |
| [importlib_metadata](https://github.com/python/cpython) | Apache-2.0 | 元数据读取 |
| [jiter](https://github.com/urantkristian/jiter) | MIT | JSON 迭代器 |
| [jsonpatch](https://github.com/stefankoegl/python-jsonpatch) | BSD | JSON Patch 实现 |
| [jsonpointer](https://github.com/stefankoegl/python-jsonpointer) | BSD | JSON Pointer 实现 |
| [multidict](https://github.com/aio-libs/multidict) | Apache-2.0 | 多键字典 |
| [propcache](https://github.com/aio-libs/propcache) | Apache-2.0 | 属性缓存 |
| [proto-plus](https://github.com/ebookapps/python-proto-plus) | Apache-2.0 | Protocol Buffers 增强 |
| [pyasn1](https://github.com/pyasn1/pyasn1) | BSD-2-Clause | ASN.1 数据结构 |
| [pyasn1_modules](https://github.com/pyasn1/pyasn1-modules) | BSD | ASN.1 模块 |
| [pycparser](https://github.com/eliben/pycparser) | BSD | C 语言解析器 |
| [python-multipart](https://github.com/Kludex/python-multipart) | Apache-2.0 | Multipart 表单数据 |
| [referencing](https://github.com/compositionalhq/referencing) | MIT | JSON Schema 引用 |
| [rsa](https://github.com/sybrenstuvel/python-rsa) | Apache-2.0 | RSA 加密 |
| [shellingham](https://github.com/sarugaku/shellingham) | ISC | Shell 检测 |
| [soupsieve](https://github.com/facelessuser/soupsieve) | MIT | CSS 选择器过滤器 |
| [tenacity](https://github.com/jd/tenacity) | Apache-2.0 | 重试逻辑库 |
| [typer-slim](https://github.com/fastapi/typer) | MIT | CLI 构建工具 |
| [typing-inspection](https://github.com/ilevkivskyi/typing_inspection) | MIT | 类型内省 |
| [uritemplate](https://github.com/python-hyper/uritemplate) | BSD / Apache-2.0 | URI 模板 |
| [uuid_utils](https://github.com/aminalaee/uuid-utils) | BSD-3-Clause | UUID 工具 |
| [wheel](https://github.com/pypa/wheel) | MIT | Wheel 包格式 |
| [xxhash](https://github.com/ifduyue/python-xxhash) | BSD | xxHash 哈希 |
| [yarl](https://github.com/aio-libs/yarl) | Apache-2.0 | URL 处理 |
| [zipp](https://github.com/jaraco/zipp) | MIT | Zipfile 路径兼容 |
| [zstandard](https://github.com/indygreg/python-zstandard) | BSD-3-Clause | Zstandard 压缩 |

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

*最后更新: 2026-02-05*

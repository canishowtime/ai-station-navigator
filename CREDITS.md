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

### 2. Python Portable
* **官网**: https://python.org
* **协议**: Python License 2.0
* **说明**: Python 解释器与标准库
* **条款**: https://docs.python.org/3/license.html

### 3. Windows Terminal
* **官网**: https://learn.microsoft.com/windows/terminal
* **协议**: MIT
* **说明**: 微软现代化终端模拟器
* **条款**: https://github.com/microsoft/terminal/blob/main/LICENSE

---

## Python 核心依赖 (Required)

本项目依赖以下 Python 库才能正常运行：

| 包名 | 版本 | 协议 | 用途 |
|:---|:---|:---|:---|
| **pip** | 26.0.1 | MIT | Python 包管理器 |
| **TinyDB** | 4.8.2 | MIT | 技能索引存储 |
| **PyYAML** | 6.0.3 | MIT | YAML 配置解析 |
| **yara-x** | 1.13.0 | Apache 2.0 | YARA 规则匹配 (Rust 实现) |
| **python-frontmatter** | 1.1.0 | MIT | SKILL.md 解析 |
| **confusable_homoglyphs** | 3.3.1 | MIT | Unicode 混淆字符检测 |
| **httpx** | 0.28.1 | BSD-3-Clause | HTTP 客户端 (cisco-ai-skill-scanner 依赖) |
| **httpcore** | 1.0.9 | BSD-3-Clause | HTTP 核心库 (cisco-ai-skill-scanner 依赖) |
| **h11** | 0.16.0 | MIT | HTTP/1.1 协议 (cisco-ai-skill-scanner 依赖) |
| **anyio** | 4.12.1 | MIT | 异步框架 (cisco-ai-skill-scanner 依赖) |
| **certifi** | 2026.2.25 | MPL-2.0 | SSL 证书 (cisco-ai-skill-scanner 依赖) |
| **idna** | 3.11 | BSD-3-Clause | 域名编码 (cisco-ai-skill-scanner 依赖) |
| **typing_extensions** | 4.15.0 | Python Software Foundation | 类型提示 (cisco-ai-skill-scanner 依赖) |
| **cisco-ai-skill-scanner** | 2.0.0 | Apache 2.0 | 安全扫描 (Static + Behavioral 分析器) |

> **完整声明**: 本项目使用的所有 Python 第三方库详见 `bin/python/Lib/site-packages/LICENSES.txt`

---

## 离线安装包 (Offline Packages)

为支持离线安装，以下预编译包已包含在项目中：

```
mybox/cache/packages/
├── windows/          # Windows 平台 wheels (13 个)
│   ├── pip-26.0.1-py3-none-any.whl
│   ├── tinydb-4.8.2-py3-none-any.whl
│   ├── pyyaml-6.0.3-cp311-cp311-win_amd64.whl
│   ├── python_frontmatter-1.1.0-py3-none-any.whl
│   ├── yara_x-1.13.0-cp38-abi3-win_amd64.whl
│   ├── confusable_homoglyphs-3.3.1-py2.py3-none-any.whl
│   ├── httpx-0.28.1-py3-none-any.whl
│   ├── httpcore-1.0.9-py3-none-any.whl
│   ├── h11-0.16.0-py3-none-any.whl
│   ├── anyio-4.12.1-py3-none-any.whl
│   ├── certifi-2026.2.25-py3-none-any.whl
│   ├── idna-3.11-py3-none-any.whl
│   └── typing_extensions-4.15.0-py3-none-any.whl
├── darwin/           # macOS 平台 wheels (15 个)
│   ├── pip-26.0.1-py3-none-any.whl
│   ├── tinydb-4.8.2-py3-none-any.whl
│   ├── pyyaml-6.0.3-cp311-cp311-macosx_10_13_x86_64.whl
│   ├── pyyaml-6.0.3-cp311-cp311-macosx_11_0_arm64.whl
│   ├── python_frontmatter-1.1.0-py3-none-any.whl
│   ├── yara_x-1.4.0-cp38-abi3-macosx_10_12_x86_64.whl
│   ├── yara_x-1.4.0-cp38-abi3-macosx_11_0_arm64.whl
│   ├── confusable_homoglyphs-3.3.1-py2.py3-none-any.whl
│   ├── httpx-0.28.1-py3-none-any.whl
│   ├── httpcore-1.0.9-py3-none-any.whl
│   ├── h11-0.16.0-py3-none-any.whl
│   ├── anyio-4.12.1-py3-none-any.whl
│   ├── certifi-2026.2.25-py3-none-any.whl
│   ├── idna-3.11-py3-none-any.whl
│   └── typing_extensions-4.15.0-py3-none-any.whl
└── source/           # 源码分发
    └── cisco-skill-scanner-lite.zip
```

**注意**:
- yara-x 替代了 yara-python (Rust 实现，性能更优)
- cisco-ai-skill-scanner 2.0.0 包含 StaticAnalyzer 和 BehavioralAnalyzer
- LLM 相关功能已禁用，无需安装 anthropic/openai/google-genai 等依赖

---

## 开源技能项目 (Third-Party Skills)

本项目集成了以下第三方 Claude Code 技能，遵循各自的原许可证：

### 核心技能集

| 项目 | 协议 | 技能数 |
|:---|:---|:---:|
| **coreyhaines31/marketingskills** | MIT | 20 |
| **ComposioHQ/awesome-claude-skills** | Apache 2.0 | 11 |
| **obra/superpowers** | MIT | 2 |
| **JimLiu/baoyu-skills** | MIT | 2 |
| **ClickHouse/agent-skills** | Apache 2.0 | 1 |
| **ginobefun/deep-reading-analyst-skill** | MIT | 1 |
| **op7418/Humanizer-zh** | MIT | 1 |

### 技能来源

| 类别 | 项目 | 说明 |
|:---|:---|:---|
| **开发工作流** | [obra/superpowers](https://github.com/obra/superpowers) | Git/TDD/代码审查/子智能体 |
| **营销优化** | [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills) | 转化率优化与策略工具 |
| **综合工具** | [ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills) | 文档处理/MCP/应用集成 |
| **写作辅助** | [op7418/Humanizer-zh](https://github.com/op7418/Humanizer-zh) | 中文文本去 AI 味 |
| **深度分析** | [ginobefun/deep-reading-analyst-skill](https://github.com/ginobefun/deep-reading-analyst-skill) | 文章/论文深度分析 |

---

## 许可证参考 (License References)

### MIT License

全文: https://opensource.org/licenses/MIT

用于: pip, TinyDB, PyYAML, python-frontmatter, confusable_homoglyphs, h11, anyio, coreyhaines31/marketingskills, obra/superpowers, JimLiu/baoyu-skills, ginobefun/deep-reading-analyst-skill, op7418/Humanizer-zh, Windows Terminal

### Apache License 2.0

全文: https://www.apache.org/licenses/LICENSE-2.0

用于: yara-x, cisco-ai-skill-scanner, ComposioHQ/awesome-claude-skills, ClickHouse/agent-skills

### BSD-3-Clause

全文: https://opensource.org/licenses/BSD-3-Clause

用于: httpx, httpcore, idna

### MPL-2.0 (Mozilla Public License)

全文: https://www.mozilla.org/en-US/MPL/2.0/

用于: certifi

### Python Software Foundation License

全文: https://docs.python.org/3/license.html

用于: typing_extensions

### GNU GPL v2

全文: https://git-scm.com/about/gpl

用于: Git for Windows Portable

### Python License 2.0

全文: https://docs.python.org/3/license.html

用于: Python Portable

---

## 免责声明 (Disclaimer)

> **使用即表示您知晓风险，后果自负**

* 本工具仅为智能体调度系统封装，不对 AI 引擎生成的内容安全性负责。
* 用户在使用 Claude Code 执行 Bash 命令、文件读写等操作时，应仔细审计每一步操作。
* 因执行 AI 建议导致的任何数据丢失或系统损坏，本工具作者概不负责。
* 各技能遵循其原始许可证，详见各技能目录下的 LICENSE 文件。
* 第三方 API 服务的数据处理策略及服务条款由各供应商独立负责。

---

*最后更新: 2026-02-28 (迁移到 yara-x 1.13.0，添加 confusable_homoglyphs 和传递依赖)*

# Security Scanner Guide

**Agent Skills 安全扫描器**

基于 cisco-ai-skill-scanner 封装，提供静态分析和行为分析能力，检测潜在安全威胁。

---

## 功能概览

| 功能 | 说明 |
|:---|:---|
| **静态扫描** | 代码模式匹配分析 |
| **行为分析** | 运行时行为检测 |
| **批量扫描** | 并发扫描多个技能 |
| **威胁评级** | LOW/MEDIUM/HIGH/CRITICAL |

---

## 命令参考

### 1. 扫描单个技能

```bash
python bin/security_scanner.py scan <skill_path> [options]
```

**参数**:
- `<skill_path>` - 技能目录路径
- `--output, -o <file>` - 输出结果到文件
- `--format {json|text}` - 输出格式

**示例**:
```bash
# 扫描技能
python bin/security_scanner.py scan .claude/skills/markdown-converter

# 输出 JSON 格式
python bin/security_scanner.py scan .claude/skills/markdown-converter --format json

# 保存结果
python bin/security_scanner.py scan .claude/skills/markdown-converter -o scan-result.json
```

### 2. 扫描所有技能

```bash
python bin/security_scanner.py scan-all [options]
```

**参数**:
- `--concurrency <n>` - 并发数（默认: 3）
- `--output, -o <file>` - 输出结果到文件

**示例**:
```bash
# 扫描所有已安装技能
python bin/security_scanner.py scan-all

# 高并发扫描
python bin/security_scanner.py scan-all --concurrency 5
```

### 3. 查看配置

```bash
python bin/security_scanner.py config
```

显示当前扫描器配置，包括引擎开关和分析器列表。

---

## 扫描结果

### 输出格式

**Text 格式**:
```
✅ Scan Complete: markdown-converter
State: success
Severity: LOW
Findings: 2
Threats:
  - [INFO] 使用了 subprocess 模块
  - [WARN] 检测到网络请求代码
```

**JSON 格式**:
```json
{
  "status": "success",
  "severity": "LOW",
  "findings_count": 2,
  "threats": [
    {
      "level": "INFO",
      "message": "使用了 subprocess 模块"
    }
  ]
}
```

### 威胁级别

| 级别 | 含义 | 处理建议 |
|:---|:---|:---|
| `LOW` | 低风险 | 信息提示，可忽略 |
| `MEDIUM` | 中风险 | 需要人工审查 |
| `HIGH` | 高风险 | 建议不要安装 |
| `CRITICAL` | 严重威胁 | 禁止安装 |

---

## 扫描引擎

### 静态分析 (StaticAnalyzer)
- 代码模式匹配
- 危险函数检测
- 权限声明分析

### 行为分析 (BehavioralAnalyzer)
- 运行时行为推断
- 网络操作检测
- 文件系统操作分析

**引擎配置** (可通过 `config.json` 调整):

```json
{
  "engines": {
    "static": true,
    "behavioral": true
  }
}
```

---

## 使用场景

### 场景 1: 安装前扫描

```bash
# 先扫描再决定是否安装
python bin/security_scanner.py scan mybox/temp/repo/skills/my-skill
```

### 场景 2: 批量安全检查

```bash
# 定期扫描所有已安装技能
python bin/security_scanner.py scan-all -o security-report.json
```

### 场景 3: CI/CD 集成

```bash
# 在技能发布前进行安全检查
python bin/security_scanner.py scan . --format json --output ci-scan.json
```

---

## 依赖安装

```bash
# 安装 cisco-ai-skill-scanner
pip install cisco-ai-skill-scanner>=0.1.0

# 可选：卸载不必要的 LLM 依赖以节省空间
pip uninstall -y google-generativeai litellm openai google-api-python-client google-auth
```

---

## 注意事项

1. **Windows 兼容性**: 已内置 YARA 修复补丁
2. **并发限制**: 默认 3 个并发，避免资源耗尽
3. **误报处理**: 行为分析可能产生误报，建议人工审查

---

## 故障排查

**Q: 提示 "cisco-ai-skill-scanner 未安装"？**
A: 运行 `pip install cisco-ai-skill-scanner>=0.1.0`

**Q: 扫描结果不准确？**
A: 行为分析基于静态推断，可能存在误报，建议人工确认

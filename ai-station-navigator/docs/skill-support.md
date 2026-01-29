# 技能格式支持

**skill_manager.py 支持的技能格式及扩展指南**

---

## 已支持格式

| 格式ID | 名称 | 识别标记 | 状态 |
|:---|:---|:---|:---:|
| **official** | Claude Code Official | `SKILL.md` + YAML frontmatter | ✅ 稳定 |
| **claude-plugin** | Claude Plugin | `.claude-plugin/`, `plugin.json` | ✅ 稳定 |
| **agent-skills** | Anthropic Agent Skills | `skills/`, `SKILL.md` | ✅ 稳定 |
| **cursor-rules** | Cursor Rules | `.cursor/rules/`, `*.md` | ✅ 稳定 |
| **unknown-md** | 通用 Markdown | 任意 `*.md` 文件 | ⚠️ 基础 |

---

## 代码实现位置

| 功能 | 文件 | 行号 |
|:---|:---|:---|
| 格式定义 | `bin/skill_manager.py` | 79-105 |
| 格式检测 | `FormatDetector.detect_skill_format()` | 304-337 |
| 格式转换 | `SkillNormalizer.convert_to_official_format()` | 780-820 |
| Claude Plugin 转换 | `SkillNormalizer._convert_claude_plugin()` | 832-856 |
| Agent Skills 转换 | `SkillNormalizer._convert_agent_skills()` | 860-871 |
| Cursor Rules 转换 | `SkillNormalizer._convert_cursor_rules()` | 875-892 |
| 通用转换 | `SkillNormalizer._convert_generic()` | 898-912 |

---

## 添加新格式

### 1. 在 SUPPORTED_FORMATS 中添加格式定义

```python
# bin/skill_manager.py (约第 79 行)

SUPPORTED_FORMATS = {
    # ... 现有格式 ...

    "new-format": {
        "name": "New Format Name",
        "markers": ["marker-file-1", "marker-file-2"],
        "handler": None,  # 目前保留为 None
    },
}
```

### 2. 在 FormatDetector 中添加检测逻辑 (可选)

如果标记文件检测不足，在 `detect_skill_format()` 中添加特殊检测：

```python
# bin/skill_manager.py (约第 304 行)

@staticmethod
def detect_skill_format(skill_dir: Path) -> Tuple[str, List[str]]:
    # ... 现有检测逻辑 ...

    # 添加新格式检测
    if (skill_dir / "special-file").exists():
        return "new-format", ["special-file"]

    # ... 其他逻辑 ...
```

### 3. 在 SkillNormalizer 中添加转换方法

```python
# bin/skill_manager.py (约第 780 行)

def convert_to_official_format(source_dir: Path, target_dir: Path) -> Tuple[bool, str]:
    # ... 现有逻辑 ...

    elif format_type == "new-format":
        SkillNormalizer._convert_new_format(source_dir, target_dir)
    # ...

@staticmethod
def _convert_new_format(source: Path, target: Path) -> None:
    """转换新格式到官方格式"""
    # 1. 提取/生成 SKILL.md
    # 2. 复制资源文件
    # 3. 处理特殊情况
    pass
```

---

## 待支持格式

| 格式ID | 来源 | 优先级 |
|:---|:---|:---:|
| **cursor-plugin** | Cursor 插件 (package.json) | 🟡 中 |
| **vscode-extension** | VS Code 扩展 | 🟢 低 |
| **windsurf-rules** | Windsurf 编辑器 | 🟢 低 |

---

## 测试

```bash
# 测试格式检测
python bin/skill_manager.py convert path/to/skill

# 验证结果
python bin/skill_manager.py validate .claude/skills/skill-name
```

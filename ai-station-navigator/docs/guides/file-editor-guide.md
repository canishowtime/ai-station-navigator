# File Editor Guide

**无预览文件编辑工具**

避免终端闪烁的轻量级文件编辑器，支持精确替换和正则表达式替换。

---

## 功能概览

| 功能 | 说明 |
|:---|:---|
| **精确替换** | 替换指定字符串 |
| **正则替换** | 使用正则表达式替换 |
| **批量编辑** | JSON 格式批量操作 |

---

## 命令参考

### 1. 精确替换

```bash
python bin/file_editor.py replace <file> <old_string> <new_string>
```

**参数**:
- `<file>` - 文件路径
- `<old_string>` - 要替换的旧字符串
- `<new_string>` - 新字符串

**示例**:
```bash
python bin/file_editor.py replace config.py "localhost" "127.0.0.1"
```

### 2. 正则替换

```bash
python bin/file_editor.py regex <file> <pattern> <replacement>
```

**参数**:
- `<file>` - 文件路径
- `<pattern>` - 正则表达式模式
- `<replacement>` - 替换内容（支持分组引用）

**示例**:
```bash
# 替换所有版本号
python bin/file_editor.py regex package.json '"version": ".*"' '"version": "2.0.0"'

# 使用分组引用
python bin/file_editor.py regex file.py 'def (\w+)\(.*\):' 'def \1(self):'
```

### 3. 批量编辑 (JSON)

```bash
python bin/file_editor.py batch <file> <operations.json>
```

**operations.json 格式**:
```json
[
  {"op": "replace", "old": "foo", "new": "bar"},
  {"op": "regex", "pattern": "v1\\.\\d+\\.\\d+", "replacement": "v2.0.0"}
]
```

**示例**:
```bash
python bin/file_editor.py batch config.py edits.json
```

---

## 使用场景

### 场景 1: 配置文件更新

```bash
# 更新数据库连接
python bin/file_editor.py replace .env "DB_HOST=localhost" "DB_HOST=prod.example.com"
```

### 场景 2: 代码重构

```bash
# 批量重命名函数
python bin/file_editor.py regex app.py "def old_name\(" "def new_name("
```

### 场景 3: 版本号更新

```bash
# 更新版本号
python bin/file_editor.py regex setup.py "version='.*'" "version='2.0.0'"
```

---

## 注意事项

1. **编码**: 默认使用 UTF-8 编码
2. **精确匹配**: `replace` 命令要求完全匹配
3. **转义字符**: 在命令行中使用时注意特殊字符转义
4. **备份**: 重要文件修改前建议先备份

---

## 退出码

| 代码 | 含义 |
|:---|:---|
| 0 | 成功 |
| 1 | 文件未找到或读取失败 |
| 2 | 替换字符串未找到 |

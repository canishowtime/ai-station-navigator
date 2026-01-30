#!/usr/bin/env python3
"""
File Editor - 无预览文件编辑工具
替代 Edit 工具避免终端闪烁
"""

import sys
import json
import re
from pathlib import Path
from datetime import datetime


def read_file(file_path: str) -> str:
    """读取文件内容"""
    try:
        return Path(file_path).read_text(encoding='utf-8')
    except FileNotFoundError:
        print(f"❌ Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error reading file: {e}", file=sys.stderr)
        sys.exit(1)


def write_file(file_path: str, content: str) -> None:
    """写入文件内容"""
    try:
        Path(file_path).write_text(content, encoding='utf-8')
    except Exception as e:
        print(f"❌ Error writing file: {e}", file=sys.stderr)
        sys.exit(1)


def replace(file_path: str, old: str, new: str) -> None:
    """精确替换字符串

    Args:
        file_path: 文件路径
        old: 要替换的旧字符串
        new: 新字符串
    """
    content = read_file(file_path)

    if old not in content:
        print(f"⚠️ Warning: '{old[:50]}...' not found in file")
        return

    content = content.replace(old, new)
    write_file(file_path, content)
    print(f"✅ Replaced in {file_path}")


def regex_replace(file_path: str, pattern: str, replacement: str, count: int = 0) -> None:
    """正则表达式替换

    Args:
        file_path: 文件路径
        pattern: 正则表达式模式
        replacement: 替换字符串
        count: 替换次数（0=全部）
    """
    content = read_file(file_path)

    try:
        if count > 0:
            content = re.sub(pattern, replacement, content, count=count)
        else:
            content = re.sub(pattern, replacement, content)
    except re.error as e:
        print(f"❌ Regex error: {e}", file=sys.stderr)
        sys.exit(1)

    write_file(file_path, content)
    print(f"✅ Regex replaced in {file_path}")


def append(file_path: str, content: str, newline: bool = True) -> None:
    """追加内容到文件末尾

    Args:
        file_path: 文件路径
        content: 要追加的内容
        newline: 是否在内容前添加换行符
    """
    try:
        # 先读取现有内容检查换行
        if newline:
            try:
                existing = read_file(file_path)
                needs_newline = existing and not existing.endswith('\n')
            except:
                needs_newline = False

        with open(file_path, 'a', encoding='utf-8') as f:
            if newline and needs_newline:
                f.write('\n')
            f.write(content)
        print(f"✅ Appended to {file_path}")
    except Exception as e:
        print(f"❌ Error appending to file: {e}", file=sys.stderr)
        sys.exit(1)


def prepend(file_path: str, content: str) -> None:
    """在文件开头插入内容

    Args:
        file_path: 文件路径
        content: 要插入的内容
    """
    text = read_file(file_path)
    write_file(file_path, content + '\n' + text)
    print(f"✅ Prepended to {file_path}")


def insert_after(file_path: str, marker: str, content: str) -> None:
    """在标记后插入内容

    Args:
        file_path: 文件路径
        marker: 定位标记字符串
        content: 要插入的内容
    """
    text = read_file(file_path)

    if marker not in text:
        print(f"⚠️ Warning: Marker '{marker[:50]}...' not found")
        return

    text = text.replace(marker, marker + '\n' + content, 1)
    write_file(file_path, text)
    print(f"✅ Inserted after marker in {file_path}")


def insert_before(file_path: str, marker: str, content: str) -> None:
    """在标记前插入内容

    Args:
        file_path: 文件路径
        marker: 定位标记字符串
        content: 要插入的内容
    """
    text = read_file(file_path)

    if marker not in text:
        print(f"⚠️ Warning: Marker '{marker[:50]}...' not found")
        return

    text = text.replace(marker, content + '\n' + marker, 1)
    write_file(file_path, text)
    print(f"✅ Inserted before marker in {file_path}")


def delete_between(file_path: str, start_marker: str, end_marker: str) -> None:
    """删除两个标记之间的内容（包含标记）

    Args:
        file_path: 文件路径
        start_marker: 起始标记
        end_marker: 结束标记
    """
    text = read_file(file_path)

    if start_marker not in text or end_marker not in text:
        print(f"⚠️ Warning: Markers not found")
        return

    pattern = re.escape(start_marker) + r'.*?' + re.escape(end_marker)
    text = re.sub(pattern, '', text, flags=re.DOTALL)
    write_file(file_path, text)
    print(f"✅ Deleted between markers in {file_path}")


def update_json_field(file_path: str, field_path: str, value: str) -> None:
    """更新 JSON 文件中的字段

    Args:
        file_path: JSON 文件路径
        field_path: 字段路径（如 "a.b.c"）
        value: 新值（自动推断类型）
    """
    try:
        data = json.loads(read_file(file_path))
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    # 推断值类型
    try:
        value = json.loads(value)
    except json.JSONDecodeError:
        # 保持为字符串
        pass

    # 导航到目标字段
    keys = field_path.split('.')
    target = data
    for key in keys[:-1]:
        if key not in target:
            target[key] = {}
        target = target[key]

    # 更新值
    target[keys[-1]] = value

    write_file(file_path, json.dumps(data, ensure_ascii=False, indent=2))
    print(f"✅ Updated JSON field '{field_path}' in {file_path}")


def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    operation = sys.argv[1].lower()
    args = sys.argv[2:]

    operations = {
        'replace': (3, replace),
        'regex': (3, regex_replace),
        'append': (2, append),
        'prepend': (2, prepend),
        'insert-after': (3, insert_after),
        'insert-before': (3, insert_before),
        'delete-between': (3, delete_between),
        'update-json': (3, update_json_field),
    }

    if operation not in operations:
        print(f"❌ Unknown operation: {operation}", file=sys.stderr)
        print_usage()
        sys.exit(1)

    min_args, func = operations[operation]

    if len(args) < min_args:
        print(f"❌ Not enough arguments for '{operation}'", file=sys.stderr)
        print_usage()
        sys.exit(1)

    try:
        func(*args)
    except TypeError as e:
        print(f"❌ Argument error: {e}", file=sys.stderr)
        print_usage()
        sys.exit(1)


def print_usage():
    """打印使用说明"""
    usage = """
File Editor - 无预览文件编辑工具

用法:
  python bin/file_editor.py <operation> [arguments...]

操作:
  replace <file> <old> <new>
      精确替换字符串

  regex <file> <pattern> <replacement> [count=0]
      正则表达式替换（count=0 表示全部替换）

  append <file> <content>
      追加内容到文件末尾

  prepend <file> <content>
      在文件开头插入内容

  insert-after <file> <marker> <content>
      在标记后插入内容

  insert-before <file> <marker> <content>
      在标记前插入内容

  delete-between <file> <start_marker> <end_marker>
      删除两个标记之间的内容

  update-json <file> <field_path> <value>
      更新 JSON 字段（field_path: "a.b.c"）

示例:
  python bin/file_editor.py replace mybox/config.yaml "old" "new"
  python bin/file_editor.py append mybox/log.txt "New entry"
  python bin/file_editor.py regex mybox/data.txt "\d+" "X"
  python bin/file_editor.py update-json mybox/config.json "version" "1.2.3"
"""
    print(usage)


if __name__ == '__main__':
    main()

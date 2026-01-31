# 技能系统快速上手

**版本**: v2.1 | **更新**: 2026-01-28

---

## 导航地图

```
┌─────────────────────────────────────────────────────────┐
│                    技能系统快速导航                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  📥 [安装/转换技能] ──→ guides/skill-manager-guide.md   │
│  ✨ [创建新技能]   ──→ guides/skill-creator-guide.md   │
│  🔧 [扩展格式]     ──→ skill-support.md                │
│  🔧 [扩展格式]     ──→ skill-support.md                │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 核心命令

| 命令 | 说明 | 详细指南 |
|:---|:---|:---|
| `python bin/skill_manager.py list` | 列出已安装技能 | [manager-guide](./guides/skill-manager-guide.md) |
| `python bin/skill_manager.py search <关键词>` | 搜索技能 | [manager-guide](./guides/skill-manager-guide.md) |
| `python bin/skill_manager.py install <url>` | 安装技能 | [manager-guide](./guides/skill-manager-guide.md) |
| `python bin/skill_creator.py init <name>` | 创建新技能 | [creator-guide](./guides/skill-creator-guide.md) |
| `/Skill <name>` | 调用技能 | [commands.md](./commands.md) |

---

## 安装来源

```bash
# GitHub 仓库
python bin/skill_manager.py install https://github.com/user/repo

# 批量安装
python bin/skill_manager.py install <url> --batch

# 本地目录
python bin/skill_manager.py install path/to/skill

# 强制覆盖
python bin/skill_manager.py install <source> --force
```

---

## 验证安装

```bash
# 1. 列出技能
python bin/skill_manager.py list

# 2. 验证特定技能
python bin/skill_manager.py validate .claude/skills/<name>

# 3. 测试调用
/Skill <name>
```

---

## 常见问题

**Q: 技能不生效？**
```bash
# 检查 SKILL.md 是否存在
cat .claude/skills/<name>/SKILL.md

# 检查 frontmatter 格式
head -5 .claude/skills/<name>/SKILL.md
```

**Q: 删除技能？**
```bash
rm -rf .claude/skills/<name>/
```

---

## 相关文档

### 深入阅读
- [Skill Manager 使用指南](./guides/skill-manager-guide.md) - 安装、转换、管理技能
- [Skill Creator 使用指南](./guides/skill-creator-guide.md) - 从零创建自定义技能

### 参考
- [commands.md](./commands.md) - 完整命令参考
- [skill-support.md](./skill-support.md) - 技能格式扩展参考
- [tinydb-schema.md](./tinydb-schema.md) - 数据库结构

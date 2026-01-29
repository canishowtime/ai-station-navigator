# mybox/ - 领航员操作系统的沙箱工作区

**定位**：安全隔离区 + 临时数据中转站 + Sub-agent 试验场

---

## 目录结构

```
mybox/
├── workspace/           # 🟢 用户任务区
│   ├── current/         # 当前正在进行的任务产生的文件
│   └── outputs/         # 最终生成的成品（图表、文档），等待用户取走
│
├── downloads/           # 🟠 下载缓存区
│   └── (AI 从互联网下载的原始素材，定期清理)
│
├── debug/               # 🔴 维修区 (Doctor Agent 专用)
│   └── (用于复现 Bug 的隔离环境)
│
└── logs/                # 📝 运行日志
    ├── install.log      # 安装日志
    └── error_trace.log  # 报错堆栈
```

---

## 核心规则

### 1. 安全隔离
- ✅ **读操作**：可以读取项目任何位置
- ⚠️ **写操作**：默认只能在 `mybox/` 内执行
- 🛡️ **系统修改**：必须调用 `pkg_manager.py` 或 `builder_tools.py`

### 2. 临时文件生命周期
```
用户任务 → 在 mybox/workspace/current/ 处理
         → 生成成品到 mybox/workspace/outputs/
         → 用户取走后清理
```

### 3. 禁止操作
- ❌ 直接在根目录执行 `rm *`
- ❌ 直接修改 `skills-store/` 或 `skills-runtime/`
- ❌ 在非 `mybox/` 位置创建临时文件

---

## 使用场景

### 场景 1：文件处理
```
用户: "提取 PDF 里的图片"
AI: 在 mybox/workspace/current/ 提取
   → mybox/workspace/outputs/images.zip
   → 用户下载后清理
```

### 场景 2：安装测试
```
Builder Agent: 先下载到 mybox/downloads/
            → 检查是否有恶意代码
            → 通过后才搬运到 skills-store/
```

### 场景 3：代码修复
```
Doctor Agent: 复制问题脚本到 mybox/debug/
           → 尝试修复并测试
           → 成功后才覆盖回正式目录
```

---

## 清理策略

- **自动清理**：每次任务结束后清理 `mybox/workspace/current/`
- **定期清理**：每周清理 `mybox/downloads/` 和 `mybox/logs/`
- **手动清理**：`rm -rf mybox/workspace/current/*`

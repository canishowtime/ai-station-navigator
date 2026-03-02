# nul文件处理办法 / nul File Deletion Method

## 1. 问题描述 / Problem Description

**中文**: Windows下执行部分任务时，会在项目内创建"nul"文件，这个文件不能通过常用的系统操作删除，导致项目不可移动和删除。

**English**: When executing certain tasks on Windows, a "nul" file may be created within the project. This file cannot be deleted through standard system operations, preventing the project from being moved or deleted.

---

## 2. 解决办法 / Solution

**中文**: 让Claude Code帮你删除，即：
1. 复制"nul"文件
2. 打开Claude Code
3. 粘贴（会直接粘贴nul文件路径）
4. 指示Claude Code删除这个文件即可

Claude Code会尝试多种方法删除，注意仔细审计它的权限申请。

**English**: Let Claude Code delete it for you:
1. Copy the "nul" file
2. Open Claude Code
3. Paste (this will directly paste the nul file path)
4. Instruct Claude Code to delete this file

Claude Code will attempt multiple deletion methods. Please carefully review its permission requests.

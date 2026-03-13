---
name: threads-skills
description: |
  Threads 自动化技能集合。支持认证登录、内容发布、搜索发现、社交互动、复合运营。
  当用户要求操作 Threads（发帖、搜索、回复、点赞、关注、查看帖子/用户）时触发。
version: 1.0.0
metadata:
  openclaw:
    requires:
      bins:
        - python3
        - uv
    emoji: "🧵"
    os:
      - darwin
      - linux
---

# Threads 自动化 Skills

你是"Threads 自动化助手"。根据用户意图路由到对应的子技能完成任务。

## 🔒 技能边界（强制）

**所有 Threads 操作只能通过本项目的 `python scripts/cli.py` 完成：**

- **唯一执行方式**：只运行 `python scripts/cli.py <子命令>`。
- **完成即止**：任务完成后直接告知结果，等待用户下一步指令。

---

## 输入判断

按优先级判断用户意图，路由到对应子技能：

1. **认证相关**（"登录 / 检查登录 / 切换账号"）→ 执行 `threads-auth` 技能。
2. **内容发布**（"发帖 / 发布 / 发 Thread / 写帖子"）→ 执行 `threads-publish` 技能。
3. **搜索发现**（"搜索 / 查看帖子 / 浏览首页 / 查看用户"）→ 执行 `threads-explore` 技能。
4. **社交互动**（"点赞 / 回复 / 转发 / 关注"）→ 执行 `threads-interact` 技能。
5. **复合运营**（"竞品分析 / 热点追踪 / 批量互动 / 内容策划"）→ 执行 `threads-content-ops` 技能。
6. **批量回覆**（"批量回复 / 逐条回复 / 弹窗回复"）→ 执行 `threads-batch-reply` 技能。

## 全局约束

- 所有操作前应确认登录状态（通过 `check-login`）。
- **發文**操作需用户确认后执行；**回覆、點讚、轉發、關注**直接执行，完成后汇报结果。
- 文件路径必须使用绝对路径。
- CLI 输出为 JSON 格式，结构化呈现给用户。
- 操作频率不宜过高，保持合理间隔（Threads 有频率限制）。
- **語言規則（強制）**：所有由 AI 生成的發文、回覆內容，一律使用**繁體中文**撰寫，不得使用简体中文。
- **🚫 政治禁區（最高優先級）**：絕對禁止生成或回覆任何政治相關內容（政黨、選舉、兩岸、統獨、社會運動等）。遇到政治相關帖子直接跳過，不作任何回應。

## 子技能概览

### threads-auth — 认证管理

| 命令 | 功能 |
|------|------|
| `cli.py check-login` | 检查登录状态，返回用户名 |
| `cli.py login` | 打开登录页，等待用户手动完成 Instagram 登录 |
| `cli.py delete-cookies` | 清除 Cookies（退出/切换账号） |
| `cli.py add-account --name 名称` | 添加命名账号（自动分配端口） |
| `cli.py list-accounts` | 列出所有账号及端口号 |
| `cli.py set-default-account --name 名称` | 设置默认账号 |
| `cli.py remove-account --name 名称` | 删除账号 |
| `cli.py --account 名称 <子命令>` | 指定账号执行任意命令 |

### threads-publish — 内容发布

| 命令 | 功能 |
|------|------|
| `cli.py fill-thread` | 填写 Thread 内容（不发布，供预览） |
| `cli.py click-publish` | 用户确认后发布 |
| `cli.py post-thread` | 一步发布 Thread（含图片） |

### threads-explore — 内容发现

| 命令 | 功能 |
|------|------|
| `cli.py list-feeds` | 获取首页 Feed |
| `cli.py get-thread --url URL` | 获取单条 Thread 详情和回复 |
| `cli.py user-profile --username @用户名` | 获取用户主页 |
| `cli.py search --query 关键词` | 搜索 Threads |

### threads-interact — 社交互动

| 命令 | 功能 |
|------|------|
| `cli.py like-thread --url URL` | 点赞 / 取消点赞 |
| `cli.py repost-thread --url URL` | 转发 Thread |
| `cli.py reply-thread --url URL --content 内容` | 回复 Thread（自动防重复） |
| `cli.py follow-user --username @用户名` | 关注用户 |
| `cli.py list-replied` | 查看已回复的帖子 ID 列表 |

### threads-content-ops — 复合运营

组合多步骤完成运营工作流：竞品分析、热点追踪、内容创作、互动管理。

### threads-batch-reply — 批量回覆助手

GUI 弹窗逐條填寫評論，GUI 與瀏覽器並行執行，填完即發不等待。

## 快速开始

```bash
# 1. 启动 Chrome
python scripts/chrome_launcher.py

# 2. 检查登录状态
python scripts/cli.py check-login

# 3. 登录（如需要）
python scripts/cli.py login
# → 在浏览器中完成 Instagram 登录后，Cookie 自动保存

# 4. 浏览首页
python scripts/cli.py list-feeds

# 5. 搜索
python scripts/cli.py search --query "AI"

# 6. 发帖（分步，推荐）
python scripts/cli.py fill-thread --content "Hello Threads!"
# 在浏览器中预览确认后
python scripts/cli.py click-publish

# 7. 点赞
python scripts/cli.py like-thread --url "https://www.threads.net/@user/post/xxx"

# 8. 回复
python scripts/cli.py reply-thread \
  --url "https://www.threads.net/@user/post/xxx" \
  --content "Great post!"
```

## 失败处理

- **未登录**：提示用户执行登录流程（threads-auth）。
- **Chrome 未启动**：使用 `chrome_launcher.py` 启动浏览器。
- **操作超时**：检查网络连接，适当增加等待时间。
- **频率限制**：降低操作频率，增大间隔后重试。
- **选择器失效**：Threads 界面可能更新，更新 `scripts/threads/publish.py` 中的选择器常量。

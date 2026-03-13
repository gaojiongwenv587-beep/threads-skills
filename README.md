# Threads Skills

> **Claude Code Skill** — 可在 [OpenClaw](https://openclaw.dev) 中直接安装使用。

基于 Chrome CDP 的 Threads 自动化工具，作为 Claude Code Skill 使用。

## 系统要求

- macOS / Linux
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) 包管理器
- Google Chrome（用于浏览器自动化）

## 快速开始

### 1. 安装依赖

```bash
uv sync
```

### 2. 启动 Chrome

```bash
python scripts/chrome_launcher.py
```

Chrome 启动后会保持运行，无需每次重启。

### 3. 登录 Threads

Threads 使用 Instagram 账号登录，登录一次后 Cookie 长期有效。

```bash
# 检查是否已登录
python scripts/cli.py check-login

# 未登录则执行（浏览器会自动打开登录页）
python scripts/cli.py login
# → 在浏览器中输入 Instagram 账号密码完成登录
# → 登录完成后再次 check-login 确认
```

### 4. 开始使用

```bash
# 浏览首页
python scripts/cli.py list-feeds

# 搜索
python scripts/cli.py search --query "AI"

# 发帖（分步，推荐）
python scripts/cli.py fill-thread --content "今天天氣真好 ☀️"
# 在浏览器中确认内容后
python scripts/cli.py click-publish

# 获取帖子详情
python scripts/cli.py get-thread --url "https://www.threads.net/@user/post/xxx"
```

## 所有命令

| 命令 | 说明 |
|------|------|
| `check-login` | 检查登录状态 |
| `login` | 打开登录页（手动完成） |
| `delete-cookies` | 清除 Cookie（切换账号） |
| `list-feeds [--limit N]` | 获取首页 Feed |
| `get-thread --url URL` | 获取帖子详情和回复 |
| `user-profile --username @用户名 [--limit N]` | 获取用户主页 |
| `search --query 关键词 [--type all\|recent\|profiles] [--limit N]` | 搜索 |
| `fill-thread --content 内容 [--images 路径或URL ...]` | 填写帖子（预览用） |
| `click-publish` | 确认发布（fill-thread 之后调用） |
| `post-thread --content 内容 [--images 路径或URL ...]` | 一步发布 |
| `reply-thread --url URL --content 内容` | 回复帖子（自动防重复） |
| `list-replied` | 查看已回复帖子 ID 列表 |
| `like-thread --url URL` | 点赞 / 取消点赞 |
| `repost-thread --url URL` | 转发 |
| `follow-user --username @用户名` | 关注用户 |
| `add-account --name 名称 [--description 描述]` | 添加多账号 |
| `list-accounts` | 列出所有账号 |
| `set-default-account --name 名称` | 设置默认账号 |
| `remove-account --name 名称` | 删除账号 |

所有命令均支持 `--account 账号名` 参数指定账号。

## 多账号

每个账号使用独立的 Chrome Profile 和调试端口（默认 8666，命名账号从 8667 递增），账号间完全隔离。

```bash
# 添加账号
python scripts/cli.py add-account --name "work" --description "工作号"

# 用指定账号执行命令
python scripts/cli.py --account work post-thread --content "工作帖子"

# 查看所有账号
python scripts/cli.py list-accounts
```

## 批量回覆助手

> 需要 tkinter：`brew install python-tk`（macOS）

GUI 弹窗逐条填写评论，填写与发送**并行执行**，无需等待。

```bash
# 1. 获取帖子并写入临时文件（由 OpenClaw 完成）
python scripts/cli.py list-feeds --limit 20

# 2. 启动助手
uv run python scripts/reply_assistant.py --posts-file /tmp/threads_batch.json

# 多账号：
uv run python scripts/reply_assistant.py --posts-file /tmp/threads_batch.json --account myaccount
```

弹窗操作：**發布**（Ctrl+Enter）/ **跳過**（Esc）/ **結束**

- 填完一条点发布，下一条弹窗**立即出现**，背景同时执行回复
- 已回复过的帖子自动跳过（`~/.threads/replied_posts.json` 去重）
- 脚本退出后向 stdout 输出摘要 JSON，供 OpenClaw 读取

## 图片发布

支持本地路径和图片 URL，URL 会自动下载缓存到 `~/.threads/images/`：

```bash
python scripts/cli.py post-thread \
  --content "今天的照片" \
  --images "/path/to/photo.jpg" "https://example.com/image.png"
```

## 内容规则

- 字符上限：500 字符
- 图片：最多 10 张，支持 JPG/PNG/GIF/WEBP
- AI 生成内容一律使用**繁體中文**

## 选择器维护

Threads 界面更新时，CSS 选择器可能失效。使用 inspector 重新探查：

```bash
# 在首页探查选择器
python scripts/inspector.py --url "https://www.threads.net"

# 根据 ✅ 命中结果更新 scripts/threads/selectors.py
```

## 开发

```bash
uv run ruff check .    # Lint
uv run ruff format .   # 格式化
uv run pytest          # 测试
```

## 故障排除

| 问题 | 原因 | 解决 |
|------|------|------|
| 连接 Chrome 失败 | Chrome 未启动或端口错误 | 运行 `python scripts/chrome_launcher.py` |
| 未登录 | Cookie 过期 | 运行 `python scripts/cli.py login` |
| 发布失败 | 选择器失效 | 运行 `python scripts/inspector.py` 重新探查 |
| 频率限制 | 操作过于频繁 | 等待 5-10 分钟后重试 |

---
name: threads
description: Threads 全功能自动化。支持登录管理、浏览、搜索、发帖、互动、多账号及批量运营。
---

# threads — Threads 全功能自动化

基于 Chrome CDP 的 Threads.net 自动化工具，支持登录、浏览、发帖、互动、多账号管理和复合运营。

## 前置条件：Chrome 必须先启动

所有命令依赖 Chrome 调试端口，使用前确认 Chrome 已运行：

```bash
python scripts/chrome_launcher.py
```

Chrome 启动后会保持运行，无需每次重启。

---

## 一、认证管理

### 检查登录状态

```bash
python scripts/cli.py check-login
```

### 登录（Instagram 账号）

```bash
python scripts/cli.py login
```

浏览器自动打开登录页，手动输入账号密码后 Cookie 自动保存，长期有效。

### 退出 / 切换账号

```bash
python scripts/cli.py delete-cookies
```

### 多账号管理

```bash
python scripts/cli.py add-account --name "work" --description "工作号"
python scripts/cli.py list-accounts
python scripts/cli.py set-default-account --name "work"
python scripts/cli.py remove-account --name "work"

# 指定账号执行任意命令
python scripts/cli.py --account work post-thread --content "..."
```

---

## 二、内容发现

### 首页 Feed

```bash
python scripts/cli.py list-feeds
python scripts/cli.py list-feeds --limit 30
```

### 搜索

```bash
python scripts/cli.py search --query "AI"
python scripts/cli.py search --query "AI" --type recent   # 最新
python scripts/cli.py search --query "AI" --type profiles # 用户
python scripts/cli.py search --query "AI" --limit 10
```

### 帖子详情

```bash
python scripts/cli.py get-thread --url "https://www.threads.net/@user/post/xxx"
```

### 用户主页

```bash
python scripts/cli.py user-profile --username "@someuser"
python scripts/cli.py user-profile --username "someuser" --limit 20
```

---

## 三、内容发布

### 分步发布（推荐，可预览）

```bash
# 第一步：填写内容
python scripts/cli.py fill-thread --content "今天天氣真好 ☀️"

# 含图片
python scripts/cli.py fill-thread --content "今天的風景" --images "/path/photo.jpg"

# 第二步：浏览器确认后发布
python scripts/cli.py click-publish
```

### 一步发布

```bash
python scripts/cli.py post-thread --content "Hello Threads！"
python scripts/cli.py post-thread --content "今天的照片" --images "/path/photo1.jpg" "/path/photo2.jpg"
```

**内容规则**：≤ 500 字符，图片最多 10 张（JPG/PNG/GIF/WEBP），使用绝对路径。
所有 AI 生成内容一律使用**繁體中文**。

---

## 四、社交互动

### 点赞 / 取消点赞

```bash
python scripts/cli.py like-thread --url "https://www.threads.net/@user/post/xxx"
```

### 转发

```bash
python scripts/cli.py repost-thread --url "https://www.threads.net/@user/post/xxx"
```

### 回复

```bash
python scripts/cli.py reply-thread --url "https://www.threads.net/@user/post/xxx" --content "這個觀點很有意思！"
```

系统自动记录已回复帖子（`~/.threads/replied_posts.json`），防止重复回复。

### 关注用户

```bash
python scripts/cli.py follow-user --username "@someuser"
```

---

## 五、复合运营

### 批量互动

操作间隔 ≥ 3 秒，单次会话点赞 ≤ 50，关注 ≤ 20。

### 批量回复（GUI 助手）

```bash
# 1. 获取目标帖子
python scripts/cli.py search --query "關鍵詞" --type recent --limit 20

# 2. 将帖子写入临时文件，调用 GUI 助手
uv run python scripts/reply_assistant.py --posts-file /tmp/threads_batch.json
```

弹窗操作：**發布**（Ctrl+Enter）/ **跳過**（Esc）/ **結束**

---

## 决策逻辑

| 用户意图 | 操作 |
|----------|------|
| "检查登录" / "未登录报错" | `check-login` → 未登录则 `login` |
| "首页" / "刷一下" | `list-feeds` |
| 提供关键词"搜索" | `search --query` |
| 提供 Thread URL | `get-thread` |
| 提供用户名 | `user-profile` |
| "发帖" / "写内容" | `fill-thread` 预览 → 用户确认 → `click-publish` |
| "直接发" | `post-thread` |
| "点赞" / "转发" / "回复" / "关注" | 直接执行对应命令 |
| 遇到政治相关内容 | 直接跳过，不作任何分析或互动 |

## 失败处理

| 错误 | 原因 | 处理 |
|------|------|------|
| 连接 Chrome 失败 | Chrome 未启动 | 运行 `python scripts/chrome_launcher.py` |
| 未登录 | Cookie 失效 | 执行 `login` |
| 选择器失效 | Threads 界面更新 | 运行 `python scripts/inspector.py` 重新探查 |
| 频率限制 | 操作过于频繁 | 等待 5-10 分钟后重试 |

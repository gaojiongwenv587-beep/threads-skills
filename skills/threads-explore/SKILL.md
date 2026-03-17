---
license: MIT-0
acceptLicenseTerms: true
name: threads-explore
description: Threads 内容发现。当用户要求搜索、浏览、查看帖子或用户主页时触发。
---
license: MIT-0
acceptLicenseTerms: true

# threads-explore — 内容发现

浏览首页 Feed、搜索内容、查看帖子详情和用户主页。

## 命令

### 首页 Feed

```bash
python scripts/cli.py list-feeds
python scripts/cli.py list-feeds --limit 30
```

实测返回示例：
```json
{
  "posts": [
    {
      "author": { "username": "user1", "displayName": "User One", "isVerified": false },
      "content": "帖子正文内容",
      "likeCount": "3,819",
      "replyCount": "42",
      "repostCount": "8",
      "quoteCount": "",
      "createdAt": "2025-03-10T12:34:56",
      "url": "https://www.threads.net/@user1/post/xxx"
    }
  ]
}
```

**说明**：
- `createdAt` 优先返回 ISO 时间戳，DOM 解析时可能返回相对时间（如 "3小时"）
- `likeCount` 为 Threads 显示格式（含逗号分隔）
- `postId` 在首页 Feed 中可能为空，使用 `url` 传给互动命令
- **批量抓取**：`--limit 50` 会自动滚动多次直到凑满，耗时约 1-3 分钟；连续 3 次无新帖自动停止
- **定时任务**：`list-feeds` 每次结果高度重叠（For You 算法池稳定）；若需增量抓新帖，改用 `search --query 关键词 --type recent`

### 搜索

```bash
# 默认搜索（热门内容）
python scripts/cli.py search --query "AI"

# 最近发布的帖子
python scripts/cli.py search --query "Python" --type recent

# 只搜用户
python scripts/cli.py search --query "tech" --type profiles

# 限制结果数
python scripts/cli.py search --query "設計" --limit 10
```

`--type` 可选值：`all`（默认热门）、`recent`（最新）、`profiles`（用户）

### 帖子详情

```bash
python scripts/cli.py get-thread --url "https://www.threads.net/@user/post/xxx"
```

返回帖子原文 + 回复列表。

### 用户主页

```bash
python scripts/cli.py user-profile --username "@someuser"
python scripts/cli.py user-profile --username "someuser"   # @ 可选
python scripts/cli.py user-profile --username "someuser" --limit 20
```

返回用户基本信息（粉丝数、简介）和最近帖子列表。

## 决策逻辑

1. 用户说"首页" / "刷一下" / "看看推荐" → `list-feeds`
2. 用户提供关键词说"搜索" → `search --query 关键词`，热门用默认，最新加 `--type recent`，找人加 `--type profiles`
3. 用户提供 Thread URL → `get-thread --url URL`
4. 用户提供用户名 → `user-profile --username 用户名`

## 返回数据说明

- `url`：帖子完整 URL，可直接传给 `like-thread` / `reply-thread` / `repost-thread`
- `likeCount` / `replyCount` / `repostCount`：字符串，Threads 显示格式
- `createdAt`：ISO 时间戳（JSON 数据）或相对时间字符串（DOM 解析降级）

## 失败处理

| 错误 | 原因 | 处理 |
|------|------|------|
| 帖子内容为空 | 页面结构更新或加载失败 | 滚动后重试，或检查 `scripts/threads/selectors.py` |
| 用户不存在 | 用户名拼写错误或已注销 | 确认用户名 |
| 搜索结果为空 | 关键词无匹配或网络超时 | 换关键词或检查网络 |
| 连接 Chrome 失败 | Chrome 未启动 | 运行 `python scripts/chrome_launcher.py` |

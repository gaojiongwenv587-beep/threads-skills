---
license: MIT-0
acceptLicenseTerms: true
name: threads-interact
description: Threads 社交互动。当用户要求点赞、转发、回复、关注时触发。
---
license: MIT-0
acceptLicenseTerms: true

# threads-interact — 社交互动

发起点赞、转发、回复、关注等社交互动。

## 🚫 內容禁區（最高優先級）

**絕對禁止生成或回覆任何政治相關內容**，包括但不限於：
- 政黨、選舉、政治人物、政府政策
- 兩岸關係、統獨議題、領土主權
- 社會運動、抗議示威
- 任何可能引發政治爭議的話題

遇到政治相關帖子，**直接跳過，不作任何回應**。

## 語言規則（強制）

所有 AI 生成的回覆內容一律使用**繁體中文**撰寫，不得使用简体中文。

## 確認規則

所有互動操作**直接執行，無需事先確認**，完成後彙報結果。用戶如認為回覆不妥可手動刪除。

## 防重複回覆（自動）

系統自動記錄已回覆的帖子 ID（`~/.threads/replied_posts.json`），對同一帖子不會重複回覆，跳過時返回：
```json
{ "status": "skipped", "message": "已回复过该帖子，跳过", "url": "..." }
```

查看已回覆記錄：
```bash
python scripts/cli.py list-replied
```

## 命令

### 点赞 / 取消点赞

```bash
python scripts/cli.py like-thread --url "https://www.threads.net/@user/post/xxx"
```

第二次调用同一帖子会取消点赞（toggle 逻辑）。

### 转发（Repost）

```bash
python scripts/cli.py repost-thread --url "https://www.threads.net/@user/post/xxx"
```

### 回复

```bash
# 内联内容
python scripts/cli.py reply-thread \
  --url "https://www.threads.net/@user/post/xxx" \
  --content "這個觀點很有意思！"

# 从文件读取内容
python scripts/cli.py reply-thread \
  --url "https://www.threads.net/@user/post/xxx" \
  --content-file /absolute/path/reply.txt
```

回复内容同样受 500 字符限制。

### 关注用户

```bash
python scripts/cli.py follow-user --username "@someuser"
python scripts/cli.py follow-user --username "someuser"   # @ 可选
```

## 决策逻辑

1. 用户说"点赞" + 提供 URL → 直接执行 `like-thread`
2. 用户说"转发" / "Repost" + 提供 URL → 直接执行 `repost-thread`
3. 用户说"回复" + 提供内容 → AI 生成繁体中文回覆，直接执行 `reply-thread`
4. 用户说"关注" + 提供用户名 → 直接执行 `follow-user`
5. 遇到政治相关帖子 → 跳过，告知用户跳过原因

## 批量互动注意

批量点赞/关注时，每次操作之间**至少间隔 3-5 秒**，避免触发 Threads 频率限制。

## 失败处理

| 错误 | 原因 | 处理 |
|------|------|------|
| 找不到点赞按钮 | 帖子已删除或界面更新 | 确认 URL 有效，检查 `scripts/threads/selectors.py` |
| 回复失败 | 内容超过 500 字符或 URL 错误 | 精简内容，确认 URL 正确 |
| 关注失败 | 私密账号或用户不存在 | 确认用户名有效 |
| 未登录 | Cookie 失效 | 执行 threads-auth 登录流程 |

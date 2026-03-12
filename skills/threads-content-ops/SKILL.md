---
name: threads-content-ops
description: Threads 复合运营。当用户要求竞品分析、热点追踪、批量互动、内容策划时触发。
---

# threads-content-ops — 复合运营

通过组合基础命令完成复杂运营工作流。

## 🚫 內容禁區（最高優先級）

絕對禁止生成、分析或互動任何政治相關內容。遇到政治相關帖子直接跳過。

## 語言規則（強制）

所有 AI 生成的發文、回覆內容一律使用**繁體中文**撰寫，不得使用简体中文。

## 工作流示例

### 竞品分析

> "分析 @competitor 最近 10 条帖子的互动情况"

```bash
python scripts/cli.py user-profile --username "@competitor" --limit 10
```

步骤：获取帖子列表 → 提取 likeCount / replyCount / repostCount → 汇总平均互动量、最高互动内容、发帖频率

### 热点追踪

> "搜索 'AI' 最近的高互动帖子"

```bash
# 获取最新帖子
python scripts/cli.py search --query "AI" --type recent --limit 20

# 获取热门帖子
python scripts/cli.py search --query "AI" --limit 20
```

步骤：搜索帖子 → 按 likeCount 排序 → 提取热门内容和话题标签

### 内容创作

> "根据最热的 5 条 AI 帖子，帮我写一条新 Thread"

步骤：
1. `search --query "AI" --limit 20` — 获取热帖
2. 分析热帖特征（长度、語氣、話題角度）
3. 生成**繁體中文**新内容（≤ 500 字符）
4. `fill-thread --content "..."` — 预览
5. 等待用户确认后 `click-publish`

### 批量互动

> "给搜索结果中前 5 条帖子都点赞"

步骤：
1. `search --query "关键词" --limit 5` — 获取 URL 列表
2. 逐一执行 `like-thread --url URL`，**每次间隔 3-5 秒**

### 话题研究

> "找讨论'设计系统'的活跃用户，看他们还聊什么"

步骤：
1. `search --query "設計系統" --type recent --limit 20`
2. 提取作者用户名
3. `user-profile --username @author` — 查看典型用户主页
4. 总结相关话题方向

## 运营规范

| 规则 | 说明 |
|------|------|
| 操作频率 | 点赞/回复间隔 ≥ 3 秒，关注间隔 ≥ 5 秒 |
| 批量上限 | 单次会话点赞 ≤ 50，关注 ≤ 20 |
| 内容长度 | 帖子/回复 ≤ 500 字符 |
| 發文確認 | 發帖前展示預覽，等待用戶確認；回覆直接執行 |
| 政治内容 | 遇到政治相关帖子直接跳过，不作任何分析或互动 |

## 失败处理

| 错误 | 原因 | 处理 |
|------|------|------|
| 频率限制 | 操作过于频繁 | 降低频率，等待 5-10 分钟后继续 |
| 数据提取不完整 | 页面未完全渲染 | 滚动后重试 |
| 账号风控 | 批量操作触发检测 | 停止操作，等待 24 小时 |

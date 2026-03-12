---
name: threads-publish
description: Threads 内容发布。当用户要求发帖、发布 Thread、写内容时触发。
---

# threads-publish — 内容发布

发布 Thread 到 Threads.net，支持纯文字和图文。

## 🚫 內容禁區（最高優先級）

絕對禁止發布任何政治相關內容（政黨、選舉、兩岸、統獨、社會運動等），遇到此類需求直接拒絕。

## 語言規則（強制）

所有 AI 生成的發文內容一律使用**繁體中文**撰寫，不得使用简体中文。

## Threads 内容规则

- **字符上限**：500 字符（中英文均计 1 字符）
- **图片**：最多 10 张，支持 JPG/PNG/GIF/WEBP，路径必须为绝对路径

## 分步发布（推荐）

用户可在浏览器中预览内容后再确认发布。

```bash
# 第一步：填写内容（打开撰写框，填入内容，不发布）
python scripts/cli.py fill-thread --content "今天天氣真好 ☀️"

# 含图片
python scripts/cli.py fill-thread \
  --content "今天的風景" \
  --images "/absolute/path/photo.jpg"

# 从文件读取长文本
python scripts/cli.py fill-thread --content-file /absolute/path/content.txt

# 第二步：用户在浏览器确认后，执行发布
python scripts/cli.py click-publish
```

**注意**：`fill-thread` 执行后不关闭浏览器标签页，`click-publish` 会复用该标签页完成发布。

## 一步发布

内容已确认、无需预览时使用：

```bash
python scripts/cli.py post-thread --content "Hello Threads！"

# 含图片
python scripts/cli.py post-thread \
  --content "今天的照片" \
  --images "/path/photo1.jpg" "/path/photo2.jpg"
```

## 实测返回示例

```json
{ "status": "success", "message": "Thread 发布成功" }
{ "error": "内容长度 523 超过上限 500 字符" }
```

## 决策逻辑

1. **用户提供内容** → 默认使用分步流程：先 `fill-thread` 展示内容，**询问用户确认**后再 `click-publish`
2. **用户明确说「直接发」/ 「一步发布」** → 使用 `post-thread`，无需再次确认
3. **内容超过 500 字符** → 提示用户精简，或拆分为多条 Thread
4. **含图片 URL（非本地路径）** → 先用 `image_downloader.py` 下载到本地再上传

## 失败处理

| 错误 | 原因 | 处理 |
|------|------|------|
| 未登录 | Cookie 失效 | 执行 threads-auth 登录流程 |
| 内容超长 | 超过 500 字符 | 精简内容后重试 |
| 找不到发布入口 | Threads 界面更新 | 检查 `scripts/threads/selectors.py` 中的选择器 |
| 上传图片失败 | 路径非绝对路径或文件不存在 | 确认路径正确，使用绝对路径 |

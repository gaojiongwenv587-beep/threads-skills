---
license: MIT-0
acceptLicenseTerms: true
name: threads-batch-reply
description: Threads 批量回覆助手。當用戶要批量逐條回覆多個帖子時觸發，用 GUI 弹窗替代聊天框輸入。
---

# threads-batch-reply — 批量回覆助手

透過 GUI 弹窗逐條填寫評論，自動執行 `reply-thread`，結果匯總回報。

## 🚫 內容禁區（最高優先級）

絕對禁止生成、分析或互動任何政治相關內容。遇到政治相關帖子直接跳過。

## 語言規則（強制）

所有 AI 生成的回覆內容一律使用**繁體中文**，不得使用简体中文。

---

## 工作流程

### 第一步：拉取目標帖子

```bash
# 從首頁 Feed 取帖
python scripts/cli.py list-feeds --limit 30

# 或按關鍵詞搜尋
python scripts/cli.py search --query "設計系統" --type recent --limit 20
```

### 第二步：篩選帖子，寫入臨時文件

從 CLI 輸出中取出目標帖子（按互動量、話題等篩選），寫成 JSON 文件：

```python
import json, tempfile, pathlib

posts = [...]  # 篩選後的帖子子集，格式同 CLI 輸出的 posts 陣列

tmp = pathlib.Path(tempfile.mktemp(suffix=".json", prefix="threads_batch_"))
tmp.write_text(json.dumps(posts, ensure_ascii=False), encoding="utf-8")
print(tmp)  # 輸出臨時文件路徑供下一步使用
```

每條帖子需包含以下欄位（直接使用 CLI 輸出即可）：

```json
{
  "postId": "DVxppvZCAAl",
  "url": "https://www.threads.net/@user/post/DVxppvZCAAl",
  "author": { "username": "someuser", "displayName": "顯示名稱" },
  "content": "帖子正文",
  "likeCount": "1,234",
  "replyCount": "56"
}
```

### 第三步：啟動批量回覆助手

```bash
uv run python scripts/reply_assistant.py --posts-file /tmp/threads_batch_xxx.json

# 多帳號：
uv run python scripts/reply_assistant.py --posts-file /tmp/threads_batch_xxx.json --account myaccount --port 8666
```

腳本啟動後 GUI 與瀏覽器並行運行：用戶在彈窗填完一條點「發布」，回覆立即在背景執行，同時下一條彈窗立刻出現。全部填完後等待剩餘回覆執行完畢自動退出。

### 第四步：讀取結果 JSON，匯報給用戶

腳本完成後向 stdout 輸出摘要：

```json
{
  "total": 10,
  "replied": 3,
  "skipped": 5,
  "already_replied": 2,
  "replied_ids": ["DVxppvZCAAl", "DVxHauYk1YQ", "DVxWF-hiayK"]
}
```

向用戶報告：成功回覆 N 條、跳過 M 條、已回覆過 K 條。

---

## GUI 弹窗操作說明

```
┌──────────────────────────────────────────┐
│  批量回覆  3 / 10  @bigbigburger1        │
├──────────────────────────────────────────┤
│  帖子正文（可滾動）                       │
│  ❤️ 1,234   💬 56                        │
├──────────────────────────────────────────┤
│  ┌────────────────────────────────────┐  │
│  │ 在此輸入評論...                     │  │
│  └────────────────────────────────────┘  │
│                           字符: 0 / 500  │
├──────────────────────────────────────────┤
│     [ 發布 ]     [ 跳過 ]    [ 結束 ]    │
└──────────────────────────────────────────┘
```

| 按鈕 | 快捷鍵 | 行為 |
|------|--------|------|
| 發布 | Ctrl+Enter | 提交評論，執行 reply-thread |
| 跳過 | Esc / 關閉視窗 | 跳過當前帖子，繼續下一條 |
| 結束 | — | 立即退出，剩餘帖子標記為 skipped |

- 輸入為空或超 500 字符時「發布」按鈕自動置灰
- 已回覆過的帖子自動跳過（不彈窗）

---

## 前置條件

1. Chrome 已啟動並登入 Threads：
```bash
python scripts/chrome_launcher.py
python scripts/cli.py check-login
```

2. tkinter 可用（macOS 可能需要）：
```bash
brew install python-tk
```

---

## 失敗處理

| 錯誤 | 原因 | 處理 |
|------|------|------|
| `無法連接 Chrome` | Chrome 未啟動或端口不符 | 執行 `chrome_launcher.py`，確認 `--port` 參數 |
| `未登錄` | Cookie 失效 | 執行 `python scripts/cli.py login` |
| tkinter 無法導入 | 缺少 tk 依賴 | `brew install python-tk` |
| 回覆未成功 | 頁面未渲染 / 選擇器失效 | 稍後重試；若持續失敗執行 `inspector.py` 驗證選擇器 |

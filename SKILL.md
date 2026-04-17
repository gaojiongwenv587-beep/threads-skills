---
license: MIT-0
acceptLicenseTerms: true
name: threads-skills
description: "Threads 平台全自動化操作套件。觸發詞：登錄、登出、檢查登錄、是否已登錄、切換帳號、清除Cookie、多帳號管理、搜索、查找、瀏覽首頁、刷一下、抓帖子、獲取帖子、看帖子詳情、查看用戶、用戶主頁、歷史回復、發帖、發布、寫帖子、po文、發Thread、帶圖發帖、點讚、轉發、回覆、評論、關注、批量回覆、批量評論、GUI回覆、篩選帖子、智能篩選、熱度評分、競品分析、熱點追蹤、批量互動、運營計劃、自動評論。"
version: 1.0.0
metadata:
  openclaw:
    homepage: https://github.com/gaojiongwenv587-beep/threads-skills
    requires:
      bins:
        - python3
        - uv
    emoji: "🧵"
    os:
      - darwin
      - linux
---

# threads-skills — Threads 平台全自動化套件

基於 Chrome CDP 驅動真實瀏覽器，涵蓋認證、抓取、發布、互動、篩選、批量回覆、運營工作流全套能力。

> **所有 AI 生成內容一律使用繁體中文，政治相關帖子直接跳過。**

---

## 前置條件：啟動 Chrome

所有命令依賴 Chrome 調試端口，使用前確認 Chrome 已運行：

```bash
python scripts/chrome_launcher.py
```

---

## 一、認證與帳號管理

### 登錄狀態

```bash
python scripts/cli.py check-login
python scripts/cli.py login           # 瀏覽器打開登錄頁，手動完成
python scripts/cli.py delete-cookies  # 退出 / 切換帳號
```

### 多帳號

```bash
python scripts/cli.py add-account --name "work" --description "工作號"
python scripts/cli.py list-accounts
python scripts/cli.py set-default-account --name "work"
python scripts/cli.py remove-account --name "work"
python scripts/cli.py --account work check-login   # 指定帳號執行任意命令
```

**決策邏輯：**
1. 其他操作報「未登錄」→ 先 `check-login`，未登錄則執行 `login`
2. 用戶說「退出」/「切換帳號」→ `delete-cookies` 後 `login`
3. 用戶說「換個號操作」→ `--account <name>` 參數，無需重新登錄

---

## 二、內容瀏覽與抓取

### 首頁 Feed

```bash
python scripts/cli.py list-feeds
python scripts/cli.py list-feeds --limit 50   # 自動滾動直到湊滿
```

### 搜索

```bash
python scripts/cli.py search --query "AI"
python scripts/cli.py search --query "Python" --type recent   # 最新
python scripts/cli.py search --query "tech" --type profiles   # 只搜用戶
python scripts/cli.py search --query "設計" --limit 10
```

### 帖子詳情 / 用戶主頁

```bash
python scripts/cli.py get-thread --url "https://www.threads.net/@user/post/xxx"
python scripts/cli.py user-profile --username "@someuser" --limit 20
python scripts/cli.py user-replies --username "@someuser" --limit 30
```

**決策邏輯：**
1. 用戶說「首頁」/「刷一下」→ `list-feeds`
2. 用戶提供關鍵詞說「搜索」→ `search --query 關鍵詞`（最新加 `--type recent`，找人加 `--type profiles`）
3. 用戶提供 Thread URL → `get-thread --url URL`
4. 用戶提供用戶名 → `user-profile --username 用戶名`
5. 用戶說「歷史回覆」→ `user-replies --username 用戶名`

---

## 三、發帖

### 分步發布（推薦，可在瀏覽器預覽後確認）

```bash
python scripts/cli.py fill-thread --content "今天天氣真好 ☀️"
python scripts/cli.py fill-thread --content "今天的風景" --images "/path/photo.jpg"
python scripts/cli.py click-publish   # 用戶在瀏覽器確認後執行
```

### 一步發布

```bash
python scripts/cli.py post-thread --content "Hello Threads！"
python scripts/cli.py post-thread --content "今天的照片" --images "/path/photo1.jpg" "/path/photo2.jpg"
```

**規則：** 字符上限 500，圖片最多 10 張（JPG/PNG/GIF/WEBP），路徑必須為絕對路徑。

**決策邏輯：**
1. 用戶提供內容 → 默認分步：`fill-thread` 預覽，詢問確認後 `click-publish`
2. 用戶說「直接發」→ `post-thread`，無需再次確認
3. 內容超 500 字符 → 提示精簡或拆分

---

## 四、社交互動

```bash
python scripts/cli.py like-thread --url URL          # 點讚（再次調用則取消）
python scripts/cli.py repost-thread --url URL        # 轉發
python scripts/cli.py reply-thread --url URL --content "回覆內容"
python scripts/cli.py follow-user --username "@user"
python scripts/cli.py list-replied                   # 查看已回覆記錄
```

**防重複回覆：** 系統自動記錄已回覆帖子（`~/.threads/replied_posts.json`），對同一帖子不會重複回覆。

**批量互動：** 每次操作間隔 ≥ 3 秒，單次會話點讚 ≤ 50，關注 ≤ 20。

**決策邏輯：**
1. 遇到政治相關帖子 → 直接跳過，告知用戶
2. 所有互動操作直接執行，完成後彙報結果

---

## 五、批量回覆助手

> 需要 tkinter：`brew install python-tk`（macOS）

### 第一步：準備帖子 JSON 文件

```python
import json, tempfile, pathlib
posts = [...]  # 從 list-feeds / search 取出的帖子子集
tmp = pathlib.Path(tempfile.mktemp(suffix=".json", prefix="threads_batch_"))
tmp.write_text(json.dumps(posts, ensure_ascii=False), encoding="utf-8")
print(tmp)
```

### 第二步：啟動助手

```bash
# GUI 彈窗版
uv run python scripts/reply_assistant.py --posts-file /tmp/threads_batch_xxx.json

# 終端交互版（tkinter 不可用時）
uv run python scripts/reply_assistant_cli.py --posts-file /tmp/threads_batch_xxx.json

# 多帳號
uv run python scripts/reply_assistant.py --posts-file /tmp/... --account myaccount
```

**彈窗操作：** 發布（Ctrl+Enter）/ 跳過（Esc）/ 結束

### 第三步：讀取結果

```json
{ "total": 10, "replied": 3, "skipped": 5, "already_replied": 2, "replied_ids": [...] }
```

---

## 六、智能篩選（三維評分）

> 三源採集（Feed + 關鍵詞 + 對標帳號）→ Python 評分腳本 → 輸出評論候選列表

### 首次配置

觸發條件：`~/.threads-filter-comment.json` 不存在，或用戶說「重新配置篩選」

向導步驟：
1. 高優先核心詞（韓國、首爾等）+ 一般關鍵詞
2. 排除詞庫（競品名稱、廣告詞等）
3. AI 配置（api_url / api_key / model，可選）

### 執行篩選

```bash
FILTER_SCRIPT=~/Desktop/threads-filter-comment/filter-comment.py

# 三源模式
python3 "$FILTER_SCRIPT" \
  --feed-file      /tmp/threads-filter/feed.json \
  --keyword-file   /tmp/threads-filter/keyword.json \
  --benchmark-file /tmp/threads-filter/benchmark.json \
  > /tmp/threads-filter/result.json

# 僅 Feed 模式
python3 "$FILTER_SCRIPT" --feed-file /tmp/threads-filter/feed.json > /tmp/threads-filter/result.json

# 關閉 AI 快速模式
python3 "$FILTER_SCRIPT" --no-ai --feed-file ... --keyword-file ... > /tmp/threads-filter/result.json
```

### 三維評分（真實 Python 代碼，非估算）

| 維度 | 滿分 | 計算方式 |
|------|------|---------|
| 互動分 | 40 | 歸一化（點讚 + 回覆×2 + 轉發×3） |
| 跨源分 | 35 | 三源都出現 35 / Feed+對標 22 / 僅 Feed 10 |
| 時效分 | 25 | 0-6h 滿分 → 48h+ 最低 |

**決策邏輯：**
1. 用戶說「篩選帖子」→ 先採集三源，再呼叫評分腳本，最後呈現候選列表
2. 用戶說「不用 AI，只做關鍵詞篩選」→ 加 `--no-ai`
3. 篩選完成後 → 結果交給互動命令執行 `reply-thread`

---

## 七、複合運營工作流

### 推廣型評論（定時任務場景）

```bash
# 抓帖
python scripts/cli.py --account account2 list-feeds --limit 15

# 兩層篩選：關鍵詞規則（零延遲）→ 只對命中的 1 條調用 AI 生成評論
# 評論風格：先呼應帖子 1 句，再帶出話題 1 句，50–150 字符，禁止硬廣詞彙

# 發布評論
python scripts/cli.py --account account2 reply-thread --url URL --content "評論內容"
```

### 競品分析

```bash
python scripts/cli.py user-profile --username "@competitor" --limit 10
# → 提取 likeCount / replyCount / repostCount → 彙總平均互動、最高互動內容、發帖頻率
```

### 熱點追蹤

```bash
python scripts/cli.py search --query "關鍵詞" --type recent --limit 20
# → 按 likeCount 排序 → 提取熱門內容和話題標籤
```

**運營規範：**

| 規則 | 說明 |
|------|------|
| 操作頻率 | 點讚/回覆間隔 ≥ 3 秒，關注間隔 ≥ 5 秒 |
| 批量上限 | 單次點讚 ≤ 50，關注 ≤ 20 |
| 內容長度 | 帖子/回覆 ≤ 500 字符 |
| 發文確認 | 發帖前展示預覽，等待確認；回覆直接執行 |
| 政治內容 | 遇到政治相關帖子直接跳過 |

---

## 故障排除

| 錯誤 | 原因 | 處理 |
|------|------|------|
| 連接 Chrome 失敗 | Chrome 未啟動 | `python scripts/chrome_launcher.py` |
| 未登錄 | Cookie 過期 | `python scripts/cli.py login` |
| 發布失敗 | 選擇器失效 | `python scripts/inspector.py` 重新探查 |
| 頻率限制 | 操作過於頻繁 | 等待 5-10 分鐘後重試 |
| tkinter 無法導入 | 缺少依賴 | `brew install python-tk` |

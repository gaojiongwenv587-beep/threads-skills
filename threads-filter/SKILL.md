---
license: MIT-0
acceptLicenseTerms: true
name: threads-filter
description: "Threads 智能篩選 Skill。三源採集（Feed+關鍵詞+對標帳號）+ 三維熱度評分（互動/跨源/時效）+ AI雙關篩選（排除詞→語境判斷）。觸發詞：篩選帖子、智能篩選、找目標帖子、哪些帖子適合評論、評論目標篩選、抓帖篩選、先篩選再評論、find posts to comment、filter posts、三維評分、熱度評分。輸出按優先級排序的評論候選列表。"
version: 1.1.0
metadata:
  openclaw:
    homepage: https://github.com/gaojiongwenv587-beep/threads-skills
    requires:
      bins:
        - python3
        - uv
    emoji: "🎯"
    os:
      - darwin
      - linux
---

# threads-filter — 智能篩選 Skill

> 三源採集 → 存檔 → `filter-comment.py` 三維評分 → 輸出評論候選列表

**評分邏輯是真正的 Python 代碼**，不是提示詞估算。
篩選腳本位於：`~/Desktop/threads-filter-comment/filter-comment.py`

---

## PHASE SETUP：首次配置向導

**觸發條件**：`~/.threads-filter-comment.json` 不存在，或用戶說「重新配置篩選」。

### 向導流程

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 threads-filter 首次配置向導
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step 1/4：關鍵詞矩陣（keywords / priority_keywords）
Step 2/4：排除詞庫（exclude_keywords）
Step 3/4：AI 配置（api_url / api_key / model）
Step 4/4：確認並寫入
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

**Step 1 / 4 — 關鍵詞矩陣**

```
請提供兩類關鍵詞：

🔑 高優先核心詞（命中即標記 high priority）：
   例：韓國、首爾、江南、釜山、韓國醫美、飛韓國

🏷️ 一般關鍵詞（命中標記 medium priority）：
   例：醫美、整形、微整、玻尿酸、保養、護膚、外貌焦慮
```

→ 儲存為 `priority_keywords`、`keywords`

---

**Step 2 / 4 — 排除詞庫**

```
哪些帖子要直接跳過？
預設已包含：醫院、診所、歡迎預約、歡迎諮詢、價格、優惠、促銷、line:、微信
需要補充同業競品名稱嗎？
```

→ 儲存為 `exclude_keywords`

---

**Step 3 / 4 — AI 配置**

```
是否啟用 AI 語境判斷？（預設：啟用）
如果啟用，請提供：
  ai_api_url：（OpenAI 相容端點）
  ai_api_key：
  ai_model：（預設 Qwen/Qwen3.5-27B-FP8）
```

---

**Step 4 / 4 — 寫入配置**

配置寫入 `~/.threads-filter-comment.json`：

```json
{
  "ai_enabled": true,
  "ai_api_url": "https://...",
  "ai_api_key": "sk-...",
  "ai_model": "Qwen/Qwen3.5-27B-FP8",
  "keywords": ["醫美", "整形", "保養", "護膚", "外貌焦慮"],
  "exclude_keywords": ["診所", "歡迎預約", "促銷", "line:"],
  "priority_keywords": ["韓國", "首爾", "江南", "釜山", "韓國醫美"]
}
```

---

## 使用方式

```
執行篩選（三源）     → 「幫我篩選適合評論的帖子」
只用 Feed 篩選       → 「只抓首頁 Feed 篩選」
關閉 AI 快速篩選     → 「不用 AI，只做關鍵詞篩選」
指定帳號             → 「用 account2 篩選帖子」
重新配置             → 「重新配置篩選」
```

---

## PHASE 1：三源採集 → 存至暫存文件

三個來源分別採集，存為獨立 JSON 文件，供 `filter-comment.py` 讀取。

```bash
ACCOUNT="default"   # 或用戶指定帳號
TMPDIR="/tmp/threads-filter"
mkdir -p "$TMPDIR"
```

---

### 來源 A：首頁 Feed（50條）→ `/tmp/threads-filter/feed.json`

```bash
uv run python scripts/cli.py --account "$ACCOUNT" list-feeds --limit 50 \
  > /tmp/threads-filter/feed.json
```

---

### 來源 B：關鍵詞搜索 → `/tmp/threads-filter/keyword.json`

讀取配置中 `priority_keywords` + `keywords`，逐一搜索（每個取最新 20 條），合併輸出：

```bash
# 對每個關鍵詞執行：
uv run python scripts/cli.py --account "$ACCOUNT" \
  search --query "[關鍵詞]" --type recent --limit 20
# 將所有結果的 posts 陣列合併，寫入 /tmp/threads-filter/keyword.json
```

若關鍵詞較多（>5個），逐一執行後在內存合併，最終輸出格式：
```json
{"posts": [ ...所有帖子... ]}
```

---

### 來源 C：對標帳號（可選）→ `/tmp/threads-filter/benchmark.json`

若用戶提供對標帳號列表，抓取每個帳號近期 15 條：

```bash
uv run python scripts/cli.py --account "$ACCOUNT" \
  user-profile --username "@帳號名" --limit 15
# 合併後寫入 /tmp/threads-filter/benchmark.json
```

---

## PHASE 2：呼叫 filter-comment.py 執行三維評分

採集完成後，呼叫真正的 Python 評分腳本：

```bash
FILTER_SCRIPT=~/Desktop/threads-filter-comment/filter-comment.py

# 三源模式
python3 "$FILTER_SCRIPT" \
  --feed-file      /tmp/threads-filter/feed.json \
  --keyword-file   /tmp/threads-filter/keyword.json \
  --benchmark-file /tmp/threads-filter/benchmark.json \
  > /tmp/threads-filter/result.json

# 僅 Feed 模式
python3 "$FILTER_SCRIPT" \
  --feed-file /tmp/threads-filter/feed.json \
  > /tmp/threads-filter/result.json

# 關閉 AI（快速模式）
python3 "$FILTER_SCRIPT" --no-ai \
  --feed-file      /tmp/threads-filter/feed.json \
  --keyword-file   /tmp/threads-filter/keyword.json \
  > /tmp/threads-filter/result.json
```

### 三維評分說明（代碼實現，非估算）

| 維度 | 滿分 | 計算方式 |
|------|------|---------|
| 互動分 | 40 | 歸一化(點贊 + 回覆×2 + 轉發×3)，以本批次最高值為基準 |
| 跨源分 | 35 | 按來源組合給分（見下表） |
| 時效分 | 25 | 按發帖時間衰減（見下表） |
| **綜合分** | **100** | 互動×0.4 + 跨源×0.35 + 時效×0.25 |

**跨源分對照：**

| 出現來源 | 得分 |
|---------|------|
| 三源都出現 | 35 |
| Feed + 對標帳號 | 22 |
| Feed + 關鍵詞 | 20 |
| 僅 Feed | 10 |
| 僅關鍵詞 | 8 |
| 僅對標帳號 | 8 |

**時效分對照：**

| 發帖時間 | 得分 |
|---------|------|
| 0–6 小時 | 25.0（滿分） |
| 6–24 小時 | 16.7 |
| 24–48 小時 | 10.0 |
| 48 小時以上 | 3.3 |

---

## PHASE 3：解析結果並呈現

讀取 `/tmp/threads-filter/result.json`，按以下格式呈現給用戶：

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 篩選完成（YYYY-MM-DD HH:mm）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
採集來源
  Feed          XX 條
  關鍵詞搜索    XX 條
  對標帳號      XX 條
  去重後總計    XX 條

關鍵詞篩選後   XX 條候選
AI 語境判斷後  XX 條適合評論

優先級分布
  🔴 高優先（priority: high）  X 條
  🟡 中優先（priority: medium）X 條

建議本次執行：取高優先全部 + 中優先前 N 條
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

高優先帖子：
1. [@用戶] 帖子摘要（30字內）
   綜合分：XX｜互動：XX｜跨源：XX｜時效：XX
   來源：feed + keyword
   URL: https://...
   AI評論：「...」

2. ...
```

結果 JSON 欄位說明：

```json
{
  "total_input": 120,
  "total_deduplicated": 95,
  "total_filtered": 8,
  "results": [
    {
      "post": { "postId": "...", "content": "...", ... },
      "sources": ["feed", "keyword"],
      "priority": "high",
      "match_reason": "韓國/首爾相關",
      "score_total": 72.3,
      "score_interaction": 35.0,
      "score_cross_source": 20.0,
      "score_timeliness": 25.0,
      "ai_should_comment": true,
      "ai_comment": "...",
      "ai_reason": "..."
    }
  ]
}
```

---

## 與其他 Skill 的配合

```
篩選完成後 → 交給 threads-interact 執行 reply-thread 評論
篩選結果   → /tmp/threads-filter/result.json 可直接作為下一步輸入
配置管理   → 說「重新配置篩選」進入向導
```

---
license: MIT-0
acceptLicenseTerms: true
name: threads-filter
description: "Threads 智能篩選 Skill。三源採集（Feed+關鍵詞+對標帳號）+ 三維熱度評分（互動/跨源/時效）+ AI雙關篩選（排除詞→語境判斷）。觸發詞：篩選帖子、智能篩選、找目標帖子、哪些帖子適合評論、評論目標篩選、抓帖篩選、先篩選再評論、find posts to comment、filter posts、三維評分、熱度評分。輸出按優先級排序的評論候選列表。"
version: 1.0.0
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

> 三源採集 → 三維評分 → 雙關篩選 → 輸出評論候選列表
> Claude 是決策引擎，不是關鍵詞匹配器。

---

## PHASE SETUP：首次配置向導

**觸發條件**：`~/.threads/filter-config.json` 不存在，或用戶說「重新配置篩選」。

### 向導流程

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 threads-filter 首次配置向導
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step 1/5：帳號基本資訊
Step 2/5：目標受眾定義
Step 3/5：關鍵詞矩陣
Step 4/5：排除詞庫
Step 5/5：對標帳號
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

**Step 1 / 5 — 帳號基本資訊**

```
帳號名稱（@xxx）是什麼？

帳號身份簡介（1-3句，AI篩選時會以此身份判斷是否適合介入）：
例：「台灣醫美診所，專注韓式自然整形，擅長雙眼皮修復與輪廓調整。」
```

→ 儲存為 `ACCOUNT_NAME`、`ACCOUNT_PROFILE`

---

**Step 2 / 5 — 目標受眾**

```
你最想觸達的受眾是誰？（1-2句）
例：「25-40歲台灣女性，對韓國醫美有興趣或正在考慮整形的潛在客戶。」
```

→ 儲存為 `ACCOUNT_AUDIENCE`

---

**Step 3 / 5 — 關鍵詞矩陣**

```
請提供 3 類關鍵詞（每類 3-8 個）：

🔑 核心詞（最精準，最高優先級）：
   例：韓國、首爾、江南、釜山

🏷️ 行業詞（領域相關）：
   例：醫美、整形、雙眼皮、皮膚科、微整形

👥 受眾詞（目標用戶常用語）：
   例：外貌、保養、護膚、皮膚問題、自信
```

→ 儲存為 `KEYWORDS.core`、`KEYWORDS.industry`、`KEYWORDS.audience`

---

**Step 4 / 5 — 排除詞庫**

```
哪些帖子要直接跳過？（預設已包含政治/廣告類，你可以補充同業競品名稱）

預設排除：政治、歡迎預約、歡迎諮詢、價格優惠、促銷、line:、微信
需要補充同業競品名稱嗎？（例：「診所A、診所B」）
```

→ 儲存為 `EXCLUDE_KEYWORDS`

---

**Step 5 / 5 — 對標帳號**

```
想監控哪些同類帳號的近期帖子？（最多5個）
用來發現對方在爆什麼、抓取熱點方向。
例：@competitor1、@kol_medbeauty
（不填也可以，後續可補充）
```

→ 儲存為 `BENCHMARK_ACCOUNTS`

---

**配置完成，儲存至 `~/.threads/filter-config.json`：**

```json
{
  "account_name": "@xxx",
  "account_profile": "帳號身份簡介",
  "account_audience": "目標受眾描述",
  "keywords": {
    "core": ["韓國", "首爾", "江南"],
    "industry": ["醫美", "整形", "雙眼皮"],
    "audience": ["外貌", "保養", "護膚"]
  },
  "exclude_keywords": ["政治", "歡迎預約", "促銷", "line:"],
  "benchmark_accounts": ["@account1", "@account2"]
}
```

---

## 使用方式

```
執行篩選               → 「幫我篩選適合評論的帖子」
指定帳號篩選           → 「用 account2 篩選帖子」
只用 Feed 篩選         → 「只抓首頁 Feed 篩選」
重新配置               → 「重新配置篩選」
```

---

## PHASE 1：三源採集

> 三個來源並行採集，互相驗證熱度，消除單一信源偏差。

**讀取配置**：

```bash
# 確認登入
uv run python scripts/cli.py --account "$ACCOUNT" check-login
```

---

### 來源 A：首頁 Feed（50條）

平台算法選出的高潛力內容，代表當前平台推流偏好。

```bash
uv run python scripts/cli.py --account "$ACCOUNT" list-feeds --limit 50
```

---

### 來源 B：關鍵詞矩陣近期搜索

讀取 `KEYWORDS.core` + `KEYWORDS.industry` 中的所有詞，逐一搜索（每個取最新 20 條）：

```bash
# 遍歷每個關鍵詞
uv run python scripts/cli.py --account "$ACCOUNT" search --query "[關鍵詞]" --type recent --limit 20
```

---

### 來源 C：對標帳號近期帖子

若 `BENCHMARK_ACCOUNTS` 不為空，抓取每個對標帳號近期 15 條：

```bash
uv run python scripts/cli.py --account "$ACCOUNT" user-profile --username "@帳號名" --limit 15
```

**重點關注**：
- 近 48 小時內發布的帖子
- 互動數異常高的帖子（爆款信號）

---

### 採集彙總

記錄每條帖子：`postId`、`url`、`content`、`likeCount`、`replyCount`、`createdAt`、`author`、`source`（feed/keyword/benchmark）。

去重（同一 `postId` 只保留一條，但記錄其出現在幾個來源）。

---

## PHASE 2：三維熱度評分

對每條帖子計算綜合熱度分（滿分 100）：

---

**維度一：互動數據分（40分）**

```
= 標準化((點贊數 + 回覆數×2 + 轉發數×3))

回覆權重最高，因為回覆代表主動參與，是真實熱度的最強信號。
```

---

**維度二：跨源驗證分（35分）**

```
僅在 Feed 出現            → +10分
僅在關鍵詞搜索出現        → +8分
僅在對標帳號出現          → +8分
Feed + 關鍵詞 同時出現    → +20分
Feed + 對標帳號 同時出現  → +22分
三源都出現                → +35分（極強熱點）
```

---

**維度三：時效性分（25分）**

```
0-6 小時內   → ×1.5（發酵中，參與價值最高）
6-24 小時    → ×1.0（正常）
24-48 小時   → ×0.6（熱度衰減）
48 小時以上  → ×0.2（基本冷卻）
```

**綜合熱度分 = 互動分×0.4 + 跨源分×0.35 + 時效分×0.25**

---

## PHASE 3：雙關篩選

### 第一關：排除詞過濾（機械過濾）

直接跳過含以下任一條件的帖子：

- 含 `EXCLUDE_KEYWORDS` 中任一詞
- 政治/歧視/醫療事故等敏感內容
- 發帖時間 > 48 小時
- 已評論過（`list-replied` 防重複）

---

### 第二關：AI 語境判斷（核心篩選）

對通過第一關的每條帖子，逐條進行語境分析：

```
你是「{ACCOUNT_NAME}」的官方帳號。
帳號定位：{ACCOUNT_PROFILE}
目標受眾：{ACCOUNT_AUDIENCE}

現在要判斷是否以這個帳號的身份在這條帖子下留言。

帖子內容：[帖子全文]

請仔細閱讀後回答：
1. 這個人是什麼身份？（目標受眾/潛在用戶/從業者/在吐槽/其他）
2. 他現在的情緒是？（期待/糾結/擔憂/負面/中性）
3. 他真正的需求是什麼？（想要建議/想要比較/想要安全感/單純分享/其他）
4. 如果以「{ACCOUNT_NAME}」的專業身份回應，能為對方提供真正有價值的資訊嗎？
   還是會顯得突兀、像在打廣告？

判斷標準：
✅ 適合：對方有真實需求，本帳號的專業判斷能真正幫到他，介入自然不違和
❌ 不適合：純粹在吐槽 / 是同行或競品 / 情緒激烈不適合介入 / 插嘴只會顯得刻意

返回 JSON（不要其他文字）：
{"should_comment": true/false, "identity": "身份", "emotion": "情緒", "need": "需求", "reason": "判斷理由", "priority": "high/medium/low"}
```

**優先級規則**：

| 條件 | 優先級 |
|------|--------|
| `should_comment: true` + 含核心詞 + 熱度高 | high |
| `should_comment: true` + 含行業詞 | medium |
| `should_comment: true` + 受眾相關 | low |
| `should_comment: false` | 跳過（僅點贊候選） |

---

## 輸出格式

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 篩選完成（YYYY-MM-DD HH:mm）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
採集來源
  Feed          XX 條
  關鍵詞搜索    XX 條（X 個詞）
  對標帳號      XX 條（X 個帳號）
  去重後總計    XX 條

排除詞過濾後   XX 條候選
AI 語境判斷後  XX 條適合評論

優先級分布
  🔴 高優先    X 條（核心詞命中 + 有真實需求）
  🟡 中優先    X 條（行業詞命中 + 適合介入）
  🟢 低優先    X 條（潛在受眾相關）

建議本次執行：取 高優先全部 + 中優先前 N 條
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

高優先帖子：
1. [@用戶] 帖子摘要（30字內）
   熱度分：XX｜身份：潛在用戶｜情緒：糾結｜需求：想要建議
   URL: https://...

2. ...
```

---

## 與其他 Skill 的配合

```
篩選完成後 → 交給 threads-interact 執行 reply-thread 評論
篩選結果   → 可直接輸入 threads-filter-comment 做進一步 AI 評論生成
配置管理   → 說「重新配置篩選」進入向導
```

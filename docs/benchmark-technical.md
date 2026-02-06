# ollama-benchmark.py 基準測試工具 — 技術文件

## 概述

`ollama-benchmark.py` 是一個自動化基準測試工具，透過預定義的多種 prompt 評估所有可用 Ollama 模型的回應速度與品質，並產生 JSON 原始數據和包含互動式圖表的 HTML 分析報告。

## 模組結構

```
ollama-benchmark.py
├── 常數與設定
│   ├── OLLAMA_BASE_URL
│   ├── CHATS_DIR
│   ├── BENCHMARK_PROMPTS
│   ├── CHART_COLORS / CHART_BORDERS
│   └── argparse（--auto 參數）
│
├── Ollama API 層
│   ├── get_available_models()      ← /api/tags
│   └── ollama_generate()           ← /api/generate（非 Streaming）
│
├── 評測執行
│   ├── run_benchmark_for_model()
│   └── interactive_chat()
│
├── HTML 報告生成
│   └── _build_html_report()
│
└── 進入點
    └── main()
```

---

## 評測項目定義

`BENCHMARK_PROMPTS` 定義了 4 個測試項目，涵蓋不同的能力面向：

| 名稱 | 測試能力 | Prompt 內容 |
|------|---------|------------|
| `greeting` | 語言理解 + 自然對話 | 「你好，請以繁體中文簡單自我介紹。」 |
| `reasoning` | 邏輯推理 + 數學計算 | 「如果一個房間裡有 3 個人，每個人各養 2 隻貓，請問房間裡總共有幾隻腳？」 |
| `coding` | 程式碼生成 | 「請用 Python 寫一個函式，判斷一個數字是否為質數。」 |
| `expression` | 表達能力 + 概念解釋 | 「請用繁體中文解釋什麼是 RESTful API，對象是完全沒有技術背景的人。」 |

每個 prompt 的設計考量：
- **greeting**：最簡單的測試，用於驗證模型是否能正常回應和使用繁體中文
- **reasoning**：需要多步驟計算（3 人 × 2 隻 = 6 隻，加上人腳 6 隻 + 貓腳 24 隻 = 30 隻），測試邏輯推理
- **coding**：要求生成可執行的 Python 程式碼，測試程式理解能力
- **expression**：要求用非技術語言解釋技術概念，測試表達與教學能力

---

## 函式詳細說明

### `get_available_models() -> list[str]`

**用途**：取得 Ollama 伺服器上所有已安裝的模型名稱。

**API 呼叫**：`GET /api/tags`（逾時 30 秒）

**回傳**：模型名稱列表，如 `["qwen3-vl:30b", "llama3.1:8b"]`

---

### `ollama_generate(model: str, prompt: str) -> dict`

**用途**：發送 prompt 到指定模型並等待完整回應（非 Streaming），同時測量延遲時間。

**API 呼叫**：`POST /api/generate`（`stream: False`，逾時 600 秒）

**延遲測量**：
```python
start = time.time()
# ... API 呼叫 ...
latency = round(time.time() - start, 3)
```

延遲時間包含：
1. 模型載入時間（若尚未載入）
2. 推理計算時間
3. 回應傳輸時間

**回傳結構**：
```python
{
    "response": "模型的完整回覆文字",
    "latency": 18.946,   # 延遲秒數（小數點 3 位）
    "length": 141         # 回覆的字元數
}
```

---

### `run_benchmark_for_model(model: str) -> list[dict]`

**用途**：對指定模型執行所有 4 個測試項目。

**執行流程**：
1. 印出模型標題
2. 遍歷 `BENCHMARK_PROMPTS`，對每個項目：
   - 印出測試名稱
   - 呼叫 `ollama_generate()` 取得結果
   - 成功：印出延遲和回應長度
   - 失敗：印出錯誤訊息
3. 回傳所有測試結果的列表

**成功時的結果結構**：
```python
{
    "test": "greeting",
    "prompt": "你好，請以繁體中文簡單自我介紹。",
    "response": "你好！我是...",
    "latency": 18.946,
    "length": 141,
    "success": True
}
```

**失敗時的結果結構**：
```python
{
    "test": "greeting",
    "prompt": "你好，請以繁體中文簡單自我介紹。",
    "response": "",
    "latency": None,
    "length": 0,
    "success": False,
    "error": "Connection timed out"
}
```

---

### `interactive_chat(model: str) -> None`

**用途**：在基準測試完成後，提供可選的互動聊天模式。

**實作細節**：
- 使用 `ollama_generate()` 發送使用者輸入
- 輸入空字串或 `n`/`no` 結束聊天
- 僅在非 `--auto` 模式下會被呼叫

---

### `_build_html_report(report: dict) -> str`

**用途**：根據完整的評測報告 JSON 結構，產生自包含的 HTML 頁面。

這是整個檔案中最長的函式，以下分段說明。

#### 資料轉換

從 report JSON 中提取資料並轉換為圖表所需的格式：

```python
# 輸入結構
report = {
    "generated_at": "20260206_114947",
    "models": {
        "qwen3-vl:30b": {
            "benchmark": [
                {"test": "greeting", "latency": 18.946, "length": 141, ...},
                ...
            ]
        },
        ...
    }
}

# 轉換後的資料結構
latency_data = {
    "greeting":    [18.946, 7.412, 33.65],   # 每個模型在此測試的延遲
    "reasoning":   [26.61, 6.977, 43.439],
    "coding":      [44.743, 8.411, 78.514],
    "expression":  [45.366, 29.111, 121.834],
}

avg_latencies = [33.916, 12.978, 69.359]     # 每個模型的平均延遲
total_lengths = [3082, 1393, 2661]            # 每個模型的總回應長度
```

#### 模型名稱處理

圖表標籤使用簡短名稱（取 `:` 前的部分）：
```python
# "qwen3-vl:30b" → "qwen3-vl"
# "llama3.1:8b" → "llama3.1"
short_names = [m.split(":")[0] if ":" in m else m for m in models]
```

#### HTML 結構

生成的 HTML 頁面包含以下區塊：

```
┌───────────────────────────────────────────────┐
│          Ollama Benchmark 分析報告            │
│          測試時間：20260206_114947            │
├───────────────────────────────────────────────┤
│  📋 模型總覽（表格）                          │
│  ┌────────┬──────────┬────────────┬────────┐  │
│  │ 模型   │ 平均延遲 │ 總回應長度 │ 成功率 │  │
│  ├────────┼──────────┼────────────┼────────┤  │
│  │ model1 │ 33.9s    │ 3082       │ 4/4    │  │
│  │ model2 │ 13.0s    │ 1393       │ 4/4    │  │
│  └────────┴──────────┴────────────┴────────┘  │
├──────────────────────┬────────────────────────┤
│ ⏱ 平均延遲圖表      │ 📏 總回應長度圖表      │
│  （長條圖）          │  （長條圖）            │
├──────────────────────┼────────────────────────┤
│ ⏱ 各項目延遲比較    │ 📏 各項目長度比較      │
│  （分組長條圖）      │  （分組長條圖）        │
├───────────────────────────────────────────────┤
│  💬 各模型詳細回覆                            │
│  ├─ model1                                    │
│  │  ├─ ✅ greeting (18.9s | 141 chars)        │
│  │  │  └─ [展開回覆]                          │
│  │  ├─ ✅ reasoning (26.6s | 326 chars)       │
│  │  ...                                       │
│  ├─ model2                                    │
│  ...                                          │
└───────────────────────────────────────────────┘
```

#### Chart.js 圖表設定

產生 4 個 Chart.js 圖表，全部嵌入 `<script>` 標籤中：

| 圖表 ID | 類型 | X 軸 | Y 軸 | 說明 |
|---------|------|------|------|------|
| `chartAvgLatency` | bar | 模型名稱 | 秒 | 各模型平均延遲 |
| `chartTotalLength` | bar | 模型名稱 | 字元 | 各模型總回應長度 |
| `chartLatencyByTest` | grouped bar | 測試項目 | 秒 | 各測試中各模型的延遲 |
| `chartLengthByTest` | grouped bar | 測試項目 | 字元 | 各測試中各模型的回應長度 |

**調色盤**：使用 8 色 RGBA 循環，支援最多 8 個模型不重複配色：
```python
CHART_COLORS = [
    "rgba(54, 162, 235, 0.8)",    # 藍
    "rgba(255, 99, 132, 0.8)",    # 紅
    "rgba(75, 192, 192, 0.8)",    # 青
    "rgba(255, 206, 86, 0.8)",    # 黃
    "rgba(153, 102, 255, 0.8)",   # 紫
    "rgba(255, 159, 64, 0.8)",    # 橙
    "rgba(46, 204, 113, 0.8)",    # 綠
    "rgba(231, 76, 60, 0.8)",     # 暗紅
]
```

邊框色由背景色的透明度 0.8 替換為 1 生成。

#### CSS 設計

- **主題**：深色主題（`--bg: #0f1117`）
- **佈局**：CSS Grid 兩欄佈局，900px 以下自動切換為單欄
- **元件**：`.card` 圓角卡片、`.test-card` 測試結果卡片
- **互動**：`<details>` 標籤實現可展開/收合的回覆內容
- **字型**：使用系統字型堆疊（`-apple-system, BlinkMacSystemFont, ...`）

#### XSS 防護

所有動態內容使用 `html.escape()` 跳脫，防止模型回覆中的 HTML/JS 被瀏覽器解析執行：
```python
html.escape(b['test'])       # 測試名稱
html.escape(b['prompt'])     # prompt 內容
html.escape(b.get('response', ''))  # 模型回覆
html.escape(model)           # 模型名稱
```

---

### `main() -> None`

**用途**：程式進入點，解析命令列參數並協調整體流程。

#### 命令列參數

使用 `argparse` 模組處理：

| 參數 | 類型 | 預設 | 說明 |
|------|------|------|------|
| `--auto` | flag | `False` | 跳過互動確認，自動完成所有模型評測 |

#### 執行流程

```
1. 解析命令列參數（argparse）
2. 取得可用模型列表
3. 印出模型列表
4. 若 --auto 模式，顯示提示
5. 遍歷每個模型：
   a. run_benchmark_for_model() 執行 4 項測試
   b. 非 --auto：詢問是否互動
   c. --auto：直接繼續
6. 建立 chats/benchmark_{timestamp}/ 目錄
7. 寫入 benchmark_report.json
8. 生成並寫入 benchmark_report.html
9. 印出完成訊息與檔案路徑
```

---

## 輸出目錄結構

每次執行會在 `chats/` 下建立獨立的時間戳記目錄：

```
chats/
├── benchmark_20260206_114947/
│   ├── benchmark_report.json    # 原始評測數據
│   └── benchmark_report.html    # 互動式分析報告
├── benchmark_20260206_120210/
│   ├── benchmark_report.json
│   └── benchmark_report.html
└── ...
```

### JSON 報告結構

```json
{
  "generated_at": "20260206_114947",
  "models": {
    "qwen3-vl:30b": {
      "benchmark": [
        {
          "test": "greeting",
          "prompt": "你好，請以繁體中文簡單自我介紹。",
          "response": "你好！我是通義千問...",
          "latency": 18.946,
          "length": 141,
          "success": true
        },
        // ... 其餘 3 個測試
      ]
    },
    // ... 其餘模型
  }
}
```

### HTML 報告功能

- **模型總覽表格**：快速比較平均延遲、總回應長度、成功率
- **4 個互動式圖表**：支援 hover 顯示數值、點擊圖例篩選
- **可展開的詳細回覆**：使用 `<details>` 標籤，預設收合以節省空間
- **響應式設計**：適配桌面和行動裝置
- **自包含**：唯一的外部依賴是 Chart.js CDN

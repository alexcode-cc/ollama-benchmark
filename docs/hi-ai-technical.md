# hi-ai.py 互動式聊天 — 技術文件

## 概述

`hi-ai.py` 是一個互動式命令列聊天工具，用於依序與所有可用的 Ollama 模型進行對話測試。它具備自動記憶體管理、逾時控制、OOM 診斷和即時資源監控功能。

## 模組結構

```
hi-ai.py
├── 常數與設定
│   ├── OLLAMA_BASE_URL
│   ├── GREETING_PROMPT
│   ├── GREETING_TIMEOUT_SECONDS
│   └── OOM_KEYWORDS
│
├── Ollama API 層
│   ├── get_available_models()      ← /api/tags
│   ├── get_running_models()        ← /api/ps
│   ├── unload_model()              ← /api/chat (keep_alive=0)
│   └── unload_all_models()
│
├── 工具函式
│   ├── _is_oom_error()
│   ├── _format_bytes()
│   └── show_model_resource_usage() ← /api/ps
│
├── 診斷函式
│   └── diagnose_timeout()          ← /api/ps
│
├── 生成函式
│   ├── llama_local()               ← /api/generate (stream)
│   └── llama_local_greeting()      ← /api/generate (stream + 診斷)
│
├── 互動流程
│   ├── greeting_for_model()
│   └── chat_with_model()
│
├── 自訂例外
│   ├── OllamaError
│   └── TimeoutWithDiagnosis
│
└── 進入點
    └── main()
```

---

## 函式詳細說明

### `get_available_models() -> list[str]`

**用途**：從 Ollama 伺服器取得目前安裝的模型名稱列表。

**API 呼叫**：`GET /api/tags`

**實作細節**：
- 逾時設定為 `GREETING_TIMEOUT_SECONDS`（30 秒）
- 從回應 JSON 的 `models` 陣列中擷取 `name` 欄位
- 回傳值範例：`["llama3.1:8b", "qwen3-vl:30b", "glm-4.7-flash:q8_0"]`

---

### `get_running_models() -> list[dict]`

**用途**：取得目前已載入記憶體（VRAM / RAM）的模型清單及其資源佔用資訊。

**API 呼叫**：`GET /api/ps`

**實作細節**：
- 逾時設定為 10 秒
- 回傳值包含每個模型的 `name`、`size`（總大小）、`size_vram`（VRAM 佔用）等欄位
- 用於記憶體管理和 OOM 診斷

---

### `unload_model(model_name: str) -> bool`

**用途**：卸載指定的單一模型以釋放記憶體。

**API 呼叫**：`POST /api/chat`

**請求內容**：
```json
{
  "model": "模型名稱",
  "messages": [],
  "keep_alive": 0
}
```

**實作細節**：
- 發送空的 `messages` 陣列搭配 `keep_alive: 0`，Ollama 會立即卸載該模型
- 逾時設定為 `GREETING_TIMEOUT_SECONDS`（30 秒）
- 回傳 `True` 表示成功，`False` 表示失敗
- 失敗時印出警告訊息但不拋出例外，確保不會中斷整體流程

---

### `unload_all_models() -> None`

**用途**：卸載所有目前已載入記憶體的模型，在切換模型前呼叫以確保有足夠記憶體。

**實作細節**：
1. 呼叫 `get_running_models()` 取得已載入的模型清單
2. 若清單為空，直接返回
3. 印出總數量和總佔用大小（例如：「🧹 正在卸載 2 個已載入的模型以釋放記憶體（共 40.9 GB）…」）
4. 逐一呼叫 `unload_model()` 卸載，並即時顯示每個模型的卸載結果（✅ / ❌）
5. 若 `/api/ps` 連線失敗，靜默處理（不影響後續流程）

---

### `_is_oom_error(error_msg: str) -> bool`

**用途**：判斷錯誤訊息是否與記憶體不足（OOM）相關。

**實作細節**：
- 將訊息轉為小寫後，比對 `OOM_KEYWORDS` 列表中的關鍵字
- 關鍵字包括：`"out of memory"`、`"oom"`、`"not enough memory"`、`"failed to load"`、`"insufficient memory"`、`"cuda out of memory"`、`"memory"`、`"alloc"`

---

### `_format_bytes(n: int) -> str`

**用途**：將位元組數轉換為人類可讀的格式。

**轉換邏輯**：
```
1024 B = 1 KB
1024 KB = 1 MB
1024 MB = 1 GB
1024 GB = 1 TB
1024 TB = 1 PB
```

**輸出範例**：`"40.9 GB"`、`"512.0 MB"`

---

### `show_model_resource_usage(model: str) -> None`

**用途**：在模型開始回覆時，顯示該模型的記憶體與 VRAM 佔用情形。

**觸發時機**：在 `llama_local()` 和 `llama_local_greeting()` 中，收到第一個 token 後呼叫。

**顯示邏輯**：
1. 呼叫 `get_running_models()` 取得執行清單
2. 比對 `name` 或 `model` 欄位找到目標模型
3. 若 `size > 0`：
   - 計算 VRAM 佔用百分比 `(size_vram / size) * 100`
   - 印出：`📊 資源佔用：模型大小 X GB，VRAM Y GB (Z%)`
   - 若 VRAM < 總大小的 95%，額外顯示系統記憶體警告
4. 若模型不在清單中，印出：`📊 資源佔用：模型資訊無法取得`
5. API 連線失敗時靜默處理

---

### `diagnose_timeout(model: str, got_any_token: bool) -> str`

**用途**：在逾時發生後，分析可能的原因並回傳診斷描述字串。

**參數**：
- `model`：逾時的模型名稱
- `got_any_token`：在逾時前是否已收到任何生成的 token

**診斷邏輯**：

```
got_any_token == False
  │
  ├─ 模型在 /api/ps 中？
  │   ├─ 是 → 檢查 VRAM 佔用
  │   │        ├─ VRAM < size → "模型未完全載入 VRAM，部分使用系統記憶體"
  │   │        └─ VRAM == size → "模型已載入但載入階段逾時"
  │   │
  │   └─ 否 → "模型未出現在執行清單中，很可能因記憶體不足 (OOM) 無法載入"
  │            └─ 列出其他佔用記憶體的模型
  │
got_any_token == True
  └─ "模型已開始生成但回應過慢"
```

**回傳範例**：
```
模型在載入階段即逾時（尚未產生任何 token）；⚠️  模型未出現在執行清單中，很可能因記憶體不足 (OOM) 無法載入；目前已載入的模型：llama3.3:70b (40.9 GB)
```

---

### `llama_local(prompt, model, *, timeout, show_resource) -> str`

**用途**：一般聊天用的文字生成函式，使用 Streaming 模式。

**API 呼叫**：`POST /api/generate`（`stream: True`）

**參數**：
| 參數 | 型別 | 預設值 | 說明 |
|------|------|--------|------|
| `prompt` | `str` | （必填） | 使用者的 prompt |
| `model` | `str` | （必填） | 模型名稱 |
| `timeout` | `int` | `GREETING_TIMEOUT_SECONDS * 60`（1800 秒） | 讀取逾時 |
| `show_resource` | `bool` | `True` | 是否顯示資源佔用 |

**逾時設定**：
- 使用 tuple `(10, timeout)` 設定連線逾時（10 秒）和讀取逾時
- 讀取逾時是指「兩個 chunk 之間」的最大等待時間，不是總時間

**Streaming 處理流程**：
1. 發送 POST 請求，啟用 `stream=True`
2. 使用 `resp.iter_lines()` 逐行讀取 NDJSON 串流
3. 每行解析為 JSON，提取 `response` 欄位中的 token
4. 收到第一個 token 時，呼叫 `show_model_resource_usage()` 顯示資源
5. 若 chunk 中包含 `error` 欄位，拋出 `OllamaError`
6. 當 `done: true` 時結束串流
7. 組合所有 token 並回傳完整回覆

---

### `llama_local_greeting(prompt, model, *, timeout) -> str`

**用途**：專為打招呼測試設計的生成函式，額外追蹤 token 接收狀態以便逾時診斷。

**與 `llama_local()` 的差異**：
- 預設逾時為 `GREETING_TIMEOUT_SECONDS`（30 秒）
- 追蹤 `got_any_token` 變數
- 捕捉 `requests.Timeout` 例外後呼叫 `diagnose_timeout()` 進行診斷
- 捕捉 `requests.HTTPError` 後檢查是否為 OOM 錯誤

**例外處理**：
| 例外類型 | 處理方式 |
|---------|---------|
| `requests.Timeout` | 呼叫 `diagnose_timeout()`，拋出 `TimeoutWithDiagnosis` |
| `requests.HTTPError` + OOM | 拋出 `OllamaError("記憶體不足 (OOM)：...")` |
| `requests.HTTPError`（其他） | 原樣重新拋出 |

---

### `greeting_for_model(model: str) -> str | None`

**用途**：對單一模型執行打招呼測試的外層包裝函式。

**回傳**：模型回覆的字串，或 `None`（失敗 / 逾時）

**例外處理策略**：
| 例外類型 | 使用者看到的訊息 |
|---------|---------------|
| `TimeoutWithDiagnosis` | `⏱️  超過 30 秒未完成回應，跳過此模型。` + 診斷資訊 |
| `OllamaError`（OOM） | `💥 記憶體不足 (OOM)，無法載入或執行此模型：...` |
| `OllamaError`（其他） | `❌ Ollama 錯誤：...` |
| `requests.RequestException` | `❌ 取得回覆失敗：...` |

---

### `chat_with_model(model: str) -> None`

**用途**：單一模型的完整互動流程——從卸載、打招呼到聊天。

**流程**：

```
1. 印出模型標題
2. unload_all_models()      ← 卸載所有已載入模型
3. greeting_for_model()     ← 打招呼測試
   ├─ None → 印出「略過此模型」，return
   └─ 有回覆 → 印出回覆
4. 詢問使用者：
   ├─ q/quit/exit → exit(0)  離開程式
   ├─ n/no/next   → return   切換下一個模型
   └─ y/yes/Enter → 進入聊天迴圈
5. 聊天迴圈：
   ├─ 使用者輸入 → llama_local() 生成回覆
   ├─ n/q/quit → return 切換下一個模型
   └─ 空輸入 → continue 跳過
```

---

### `main() -> None`

**用途**：程式進入點，協調整體執行流程。

**流程**：
1. 呼叫 `get_available_models()` 取得模型列表
2. 若無可用模型，印出警告並結束
3. 印出所有偵測到的模型
4. 迴圈遍歷每個模型，呼叫 `chat_with_model()`
5. 全部完成後印出「✅ 所有模型測試完成」

---

## 自訂例外類別

### `OllamaError(Exception)`

當 Ollama API 在串流中回傳 `error` 欄位時拋出。用於區分 Ollama 層級的錯誤（如 OOM）與網路層級的錯誤（如 Timeout）。

### `TimeoutWithDiagnosis(Exception)`

在打招呼逾時後拋出，`str(exception)` 包含完整的診斷資訊字串。

---

## 輸出 flush 策略

所有 `print()` 呼叫都加上 `flush=True`，原因：
1. **避免「看起來卡住」**：Python 的 stdout 在某些環境下會緩衝輸出，導致等待 API 回應時畫面上看不到任何提示
2. **即時回饋**：確保使用者能看到「⏳ 正在取得…」等等待訊息
3. **診斷資訊可見性**：逾時後的診斷訊息必須立即顯示

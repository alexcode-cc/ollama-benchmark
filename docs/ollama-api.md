# Ollama API 串接說明

## 概述

本專案透過 HTTP REST API 與本地運行的 Ollama 伺服器溝通。所有 API 呼叫都使用 Python `requests` 套件實作。

**伺服器位址**：`http://localhost:11434`（硬編碼於 `OLLAMA_BASE_URL` 常數）

## 使用的 API 端點

| 端點 | 方法 | 用途 | 使用腳本 |
|------|------|------|---------|
| `/api/tags` | GET | 列出所有已安裝的模型 | 兩者 |
| `/api/generate` | POST | 文字生成（Streaming / 非 Streaming） | 兩者 |
| `/api/chat` | POST | 卸載模型（`keep_alive: 0`） | hi-ai.py |
| `/api/ps` | GET | 查詢已載入記憶體的模型狀態 | hi-ai.py |

---

## API 端點詳細說明

### 1. GET /api/tags — 列出模型

**用途**：取得 Ollama 伺服器上所有已安裝的模型列表。

**請求**：
```http
GET /api/tags HTTP/1.1
Host: localhost:11434
```

**回應範例**：
```json
{
  "models": [
    {
      "name": "llama3.1:8b",
      "model": "llama3.1:8b",
      "modified_at": "2026-02-06T10:00:00Z",
      "size": 4661224448,
      "digest": "...",
      "details": {
        "parent_model": "",
        "format": "gguf",
        "family": "llama",
        "families": ["llama"],
        "parameter_size": "8.0B",
        "quantization_level": "Q4_0"
      }
    }
  ]
}
```

**程式碼使用方式**：
```python
resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=30)
resp.raise_for_status()
data = resp.json()
models = [m["name"] for m in data.get("models", [])]
```

**注意事項**：
- 回傳的模型列表包含所有已安裝的模型，無論是否已載入記憶體
- `name` 欄位格式為 `模型名:標籤`，例如 `llama3.1:8b`

---

### 2. POST /api/generate — 文字生成

**用途**：向指定模型發送 prompt 並取得回應。支援 Streaming 和非 Streaming 兩種模式。

#### 2a. 非 Streaming 模式（ollama-benchmark.py 使用）

**請求**：
```http
POST /api/generate HTTP/1.1
Host: localhost:11434
Content-Type: application/json

{
  "model": "llama3.1:8b",
  "prompt": "你好",
  "stream": false
}
```

**回應**：
```json
{
  "model": "llama3.1:8b",
  "created_at": "2026-02-06T10:00:00Z",
  "response": "你好！我是一個AI助手...",
  "done": true,
  "done_reason": "stop",
  "context": [1, 2, 3, ...],
  "total_duration": 5000000000,
  "load_duration": 1000000000,
  "prompt_eval_count": 10,
  "prompt_eval_duration": 500000000,
  "eval_count": 50,
  "eval_duration": 3500000000
}
```

**程式碼使用方式**：
```python
resp = requests.post(
    f"{OLLAMA_BASE_URL}/api/generate",
    json={"model": model, "prompt": prompt, "stream": False},
    timeout=600,
)
resp.raise_for_status()
text = resp.json().get("response", "")
```

**注意**：非 Streaming 模式下，整個回應會在模型生成完畢後一次回傳，等待時間可能很長。

#### 2b. Streaming 模式（hi-ai.py 使用）

**請求**：
```http
POST /api/generate HTTP/1.1
Host: localhost:11434
Content-Type: application/json

{
  "model": "llama3.1:8b",
  "prompt": "你好",
  "stream": true
}
```

**回應**（NDJSON 格式，每行一個 JSON 物件）：
```json
{"model":"llama3.1:8b","created_at":"2026-02-06T10:00:00Z","response":"你","done":false}
{"model":"llama3.1:8b","created_at":"2026-02-06T10:00:00Z","response":"好","done":false}
{"model":"llama3.1:8b","created_at":"2026-02-06T10:00:01Z","response":"！","done":false}
...
{"model":"llama3.1:8b","created_at":"2026-02-06T10:00:05Z","response":"","done":true,"done_reason":"stop"}
```

**程式碼使用方式**：
```python
resp = requests.post(
    f"{OLLAMA_BASE_URL}/api/generate",
    json={"model": model, "prompt": prompt, "stream": True},
    stream=True,
    timeout=(10, 30),  # (連線逾時, 讀取逾時)
)
resp.raise_for_status()

for line in resp.iter_lines():
    if not line:
        continue
    chunk = json.loads(line)
    if "error" in chunk:
        raise OllamaError(chunk["error"])
    token = chunk.get("response", "")
    if chunk.get("done"):
        break
```

**串流中的錯誤處理**：

Ollama 可能在串流過程中回傳錯誤物件：
```json
{"error": "model failed to generate a response"}
```

由於 HTTP 狀態碼已經回傳 200，此時需要在每個 chunk 中檢查 `error` 欄位。

#### Streaming vs 非 Streaming 選擇

| 特性 | 非 Streaming | Streaming |
|------|-------------|-----------|
| 回應方式 | 一次回傳完整回應 | 逐 token 回傳 |
| 延遲測量 | 從發送到收到整個回應 | 可測量首 token 延遲 |
| 逾時控制 | 單一逾時值 | 可設定連線/讀取分別逾時 |
| 錯誤偵測 | HTTP 狀態碼 | HTTP 狀態碼 + 串流中 error |
| 使用場景 | 基準測試（需要精確測量） | 互動式聊天（需要即時回饋） |

---

### 3. POST /api/chat — 卸載模型

**用途**：透過發送空對話搭配 `keep_alive: 0` 來卸載指定模型。

**請求**：
```http
POST /api/chat HTTP/1.1
Host: localhost:11434
Content-Type: application/json

{
  "model": "llama3.1:8b",
  "messages": [],
  "keep_alive": 0
}
```

**回應**：
```json
{
  "model": "llama3.1:8b",
  "created_at": "2026-02-06T10:00:00Z",
  "message": {"role": "assistant", "content": ""},
  "done_reason": "unload",
  "done": true
}
```

**關鍵參數說明**：
- `messages: []`：空的訊息陣列，不觸發任何生成
- `keep_alive: 0`：指示 Ollama 在處理完請求後立即卸載模型，釋放 VRAM / RAM

**程式碼使用方式**：
```python
resp = requests.post(
    f"{OLLAMA_BASE_URL}/api/chat",
    json={
        "model": model_name,
        "messages": [],
        "keep_alive": 0,
    },
    timeout=30,
)
resp.raise_for_status()
```

**注意**：此技巧利用了 Ollama 的 `keep_alive` 機制。正常情況下，`keep_alive` 用於控制模型在最後一次請求後保持載入的時間（預設 5 分鐘）。設為 0 則表示「立即卸載」。

---

### 4. GET /api/ps — 查詢執行中模型狀態

**用途**：取得目前已載入記憶體的所有模型及其資源佔用狀態。

**請求**：
```http
GET /api/ps HTTP/1.1
Host: localhost:11434
```

**回應範例**：
```json
{
  "models": [
    {
      "name": "llama3.3:70b-instruct-q4_K_M",
      "model": "llama3.3:70b-instruct-q4_K_M",
      "size": 43948064768,
      "digest": "...",
      "details": {
        "parent_model": "",
        "format": "gguf",
        "family": "llama",
        "parameter_size": "70.6B",
        "quantization_level": "Q4_K_M"
      },
      "size_vram": 43948064768,
      "expires_at": "2026-02-06T10:10:00Z"
    }
  ]
}
```

**關鍵欄位**：

| 欄位 | 型別 | 說明 |
|------|------|------|
| `name` | string | 模型名稱（含標籤） |
| `size` | integer | 模型總大小（位元組） |
| `size_vram` | integer | VRAM 佔用（位元組） |
| `expires_at` | string | 預計卸載時間（基於 keep_alive） |

**資源佔用判斷邏輯**：

```python
size = m.get("size", 0)          # 模型總大小
size_vram = m.get("size_vram", 0) # VRAM 佔用

if size_vram == size:
    # 模型完全載入 VRAM — 最佳效能
elif size_vram < size:
    # 部分載入 VRAM，其餘使用系統 RAM — 效能下降
    system_mem = size - size_vram
elif size_vram == 0:
    # 完全使用系統 RAM — 效能最差
```

**使用場景**：
1. **資源監控**：在模型回覆前顯示 VRAM 佔用（`show_model_resource_usage()`）
2. **逾時診斷**：判斷逾時原因是否為 OOM（`diagnose_timeout()`）
3. **記憶體管理**：確認卸載是否成功（`unload_all_models()`）

---

## 逾時策略

各 API 呼叫的逾時設定：

| API 呼叫 | 逾時值 | 說明 |
|----------|--------|------|
| GET /api/tags | 30 秒 | 模型列表查詢 |
| POST /api/generate（非 Streaming） | 600 秒 | benchmark 評測 |
| POST /api/generate（Streaming 連線） | 10 秒 | 建立連線 |
| POST /api/generate（Streaming 讀取） | 30 秒（打招呼）/ 1800 秒（聊天） | 兩次 chunk 之間 |
| POST /api/chat（卸載） | 30 秒 | 卸載模型 |
| GET /api/ps | 5 ~ 10 秒 | 狀態查詢 |

### requests 的 timeout 參數形式

```python
# 單一值：同時作為連線和讀取逾時
requests.get(url, timeout=30)

# tuple：分別設定連線和讀取逾時
requests.post(url, timeout=(10, 30))
#                           │   └── 讀取逾時（兩次資料之間的最大等待）
#                           └────── 連線逾時（建立 TCP 連線的最大等待）
```

---

## 錯誤回應格式

Ollama API 在錯誤時回傳以下格式：

**HTTP 錯誤（4xx / 5xx）**：
```json
{"error": "model 'xxx' not found"}
```

**串流中錯誤**（HTTP 200 但生成過程出錯）：
```json
{"error": "the model failed to generate a response"}
```

**常見錯誤碼**：

| HTTP 狀態碼 | 說明 |
|------------|------|
| 400 | 請求格式錯誤 |
| 404 | 模型不存在 |
| 500 | 伺服器內部錯誤（可能是 OOM） |

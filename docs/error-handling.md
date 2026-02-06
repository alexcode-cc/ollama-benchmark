# 錯誤處理與 OOM 診斷機制

## 概述

本專案實作了多層次的錯誤處理策略，特別針對 LLM 推理中常見的記憶體不足（OOM）問題設計了完整的偵測、診斷和預防機制。本文件僅涵蓋 `hi-ai.py`，因為 `ollama-benchmark.py` 使用較簡單的 try/except 錯誤處理。

## 錯誤處理架構

```
                    ┌─────────────────────────┐
                    │    使用者發送 prompt      │
                    └───────────┬─────────────┘
                                │
                    ┌───────────▼─────────────┐
                    │  unload_all_models()     │  ← 預防 OOM
                    │  卸載所有已載入的模型      │
                    └───────────┬─────────────┘
                                │
                    ┌───────────▼─────────────┐
                    │  llama_local_greeting()   │
                    │  Streaming 模式生成       │
                    └───────────┬─────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                   │
    ┌─────────▼───────┐ ┌──────▼──────┐ ┌─────────▼──────────┐
    │ requests.Timeout │ │ OllamaError │ │ requests.HTTPError  │
    │    逾時例外      │ │ 串流中錯誤   │ │   HTTP 錯誤         │
    └─────────┬───────┘ └──────┬──────┘ └─────────┬──────────┘
              │                │                   │
    ┌─────────▼───────┐       │         ┌─────────▼──────────┐
    │diagnose_timeout()│       │         │  _is_oom_error()   │
    │  逾時原因診斷    │       │         │  判斷是否為 OOM     │
    └─────────┬───────┘       │         └─────────┬──────────┘
              │                │                   │
    ┌─────────▼───────┐ ┌─────▼─────┐   ┌────────▼─────────┐
    │TimeoutWithDiag- │ │ _is_oom   │   │ 是 OOM → 拋出    │
    │nosis            │ │ _error()  │   │ OllamaError      │
    │ 附帶診斷資訊     │ │ 關鍵字比對│   │                  │
    └─────────────────┘ └───────────┘   └──────────────────┘
```

---

## 三道防線

### 第一道防線：OOM 預防（主動卸載）

**機制**：在每個模型打招呼前，先卸載所有已載入的模型。

**流程**：
```
chat_with_model()
  └→ unload_all_models()
       └→ get_running_models()   ← GET /api/ps
       └→ unload_model(name)     ← POST /api/chat (keep_alive=0)
           × N 個已載入的模型
```

**設計理由**：
- 大型模型（如 70B）可能佔用 40+ GB 記憶體
- 若前一個模型仍佔用記憶體，新模型可能無法載入
- 主動卸載確保每個模型都在「乾淨的」記憶體環境下啟動

**容錯設計**：
- `/api/ps` 連線失敗 → 靜默返回，不阻斷流程
- 單一模型卸載失敗 → 印出警告，繼續卸載其他模型
- 所有卸載都失敗 → 流程繼續，由第二/三道防線處理

---

### 第二道防線：逾時控制與診斷

**機制**：使用 Streaming 模式搭配逾時控制，在模型無回應時及時中斷並診斷原因。

#### 逾時偵測

使用 requests 的 tuple 逾時設定：
```python
timeout=(10, GREETING_TIMEOUT_SECONDS)
#        │    └── 讀取逾時：兩次 chunk 之間的最大等待（30 秒）
#        └────── 連線逾時：建立 TCP 連線的最大等待（10 秒）
```

**為什麼用 Streaming 而非非 Streaming？**

| 模式 | 非 Streaming | Streaming |
|------|-------------|-----------|
| 逾時意義 | 整個回應的等待時間 | 兩次 chunk 之間的等待時間 |
| 首 token 偵測 | ❌ 無法偵測 | ✅ 可精確偵測 |
| OOM 階段判斷 | ❌ 無法判斷 | ✅ 載入階段 vs 生成階段 |
| 記憶體狀態 | ❌ 只知道逾時 | ✅ 可查詢 /api/ps |

#### Token 追蹤變數

`llama_local_greeting()` 使用兩個追蹤變數：

```python
got_any_token = False      # 是否收到過任何 token
first_token_received = False  # 是否已顯示資源資訊
```

- `got_any_token`：用於逾時診斷，判斷模型是在載入階段還是生成階段逾時
- `first_token_received`：用於資源顯示，確保只在第一個 token 時呼叫 `show_model_resource_usage()`

#### 逾時診斷流程

```
逾時發生（requests.Timeout）
  │
  ├─ got_any_token == False（載入階段逾時）
  │   │
  │   └→ diagnose_timeout()
  │       └→ GET /api/ps
  │           ├─ 模型在列表中
  │           │   ├─ VRAM < size → "部分使用系統記憶體，效能大幅下降"
  │           │   └─ VRAM == size → "模型已載入但載入階段逾時"
  │           │
  │           └─ 模型不在列表中
  │               └→ "很可能因記憶體不足 (OOM) 無法載入"
  │                  └→ 列出其他佔用記憶體的模型
  │
  └─ got_any_token == True（生成階段逾時）
      └→ "模型已開始生成但回應過慢"
```

---

### 第三道防線：錯誤訊息解析

**機制**：解析 Ollama 回傳的錯誤訊息，識別 OOM 相關的錯誤。

#### 錯誤來源

**來源 1：串流中的 error 欄位**

Ollama 在 Streaming 模式下，可能在串流過程中回傳錯誤：
```json
{"error": "out of memory"}
```

程式碼處理：
```python
for line in resp.iter_lines():
    chunk = json.loads(line)
    if "error" in chunk:
        raise OllamaError(chunk["error"])
```

**來源 2：HTTP 錯誤回應體**

Ollama 回傳 4xx / 5xx 時，回應體可能包含 OOM 相關訊息：
```python
except requests.HTTPError as e:
    error_body = e.response.text
    if _is_oom_error(error_body):
        raise OllamaError(f"記憶體不足 (OOM)：{error_body}")
```

#### OOM 關鍵字比對

`_is_oom_error()` 使用以下關鍵字列表進行比對：

```python
OOM_KEYWORDS = [
    "out of memory",        # CUDA / 通用 OOM 錯誤
    "oom",                  # 縮寫
    "not enough memory",    # 通用記憶體不足
    "failed to load",       # 模型載入失敗
    "insufficient memory",  # 記憶體不足
    "cuda out of memory",   # NVIDIA GPU 專用
    "memory",               # 廣泛比對
    "alloc",                # 記憶體配置失敗
]
```

比對方式：將錯誤訊息轉小寫後，檢查是否包含任一關鍵字：
```python
def _is_oom_error(error_msg: str) -> bool:
    lower = error_msg.lower()
    return any(kw in lower for kw in OOM_KEYWORDS)
```

---

## 例外類別層級

```
Exception
├── OllamaError              # Ollama API 層級錯誤
│   └── 用途：串流中的 error、OOM 錯誤
│
├── TimeoutWithDiagnosis     # 逾時 + 診斷資訊
│   └── 用途：打招呼逾時後的診斷結果
│
└── requests.RequestException（第三方）
    ├── requests.Timeout     # 網路逾時
    ├── requests.HTTPError   # HTTP 4xx / 5xx
    └── requests.ConnectionError  # 連線失敗
```

---

## greeting_for_model() 的例外處理策略

`greeting_for_model()` 是最外層的錯誤處理入口，負責捕捉所有可能的例外並轉換為使用者友善的訊息：

```python
def greeting_for_model(model: str) -> str | None:
    try:
        reply = llama_local_greeting(...)
        return reply  # 成功

    except TimeoutWithDiagnosis as e:
        # ⏱️  超過 30 秒未完成回應，跳過此模型。
        #    診斷：模型在載入階段即逾時...
        return None

    except OllamaError as e:
        if _is_oom_error(str(e)):
            # 💥 記憶體不足 (OOM)，無法載入或執行此模型：...
        else:
            # ❌ Ollama 錯誤：...
        return None

    except requests.RequestException as e:
        # ❌ 取得回覆失敗：...
        return None
```

**設計原則**：
1. **永不拋出例外**：所有錯誤都被捕捉，回傳 `None` 表示失敗
2. **區分錯誤類型**：OOM、逾時、一般錯誤使用不同的圖示和訊息
3. **提供診斷資訊**：逾時時附帶原因分析，幫助使用者理解問題
4. **不中斷流程**：失敗的模型被跳過，繼續測試下一個

---

## 使用者訊息對照表

| 情境 | 圖示 | 訊息範例 |
|------|------|---------|
| 正在等待回覆 | ⏳ | `正在取得 llama3.3:70b 的打招呼回覆…（逾時 30 秒）` |
| 模型資源資訊 | 📊 | `資源佔用：模型大小 40.9 GB，VRAM 38.2 GB (93.4%)` |
| VRAM 不足警告 | ⚠️ | `系統記憶體 2.7 GB（效能可能下降）` |
| 正在卸載模型 | 🧹 | `正在卸載 1 個已載入的模型以釋放記憶體（共 40.9 GB）…` |
| 卸載成功 | ✅ | `卸載 llama3.3:70b (40.9 GB)… ✅` |
| 卸載失敗 | ❌ | `卸載 llama3.3:70b (40.9 GB)… ❌` |
| 逾時跳過 | ⏱️ | `超過 30 秒未完成回應，跳過此模型。` |
| OOM 錯誤 | 💥 | `記憶體不足 (OOM)，無法載入或執行此模型` |
| 一般錯誤 | ❌ | `Ollama 錯誤：model not found` |
| 連線失敗 | ❌ | `取得回覆失敗：Connection refused` |

---

## 完整診斷範例

### 場景 1：模型因 OOM 無法載入

```
============================================================
🤖 使用模型：llama3.3:70b-instruct-q4_K_M
============================================================
🧹 正在卸載 1 個已載入的模型以釋放記憶體（共 17.1 GB）…
   卸載 qwen3-vl:30b (17.1 GB)… ✅
⏳ 正在取得 llama3.3:70b-instruct-q4_K_M 的打招呼回覆…（逾時 30 秒）
⏱️  超過 30 秒未完成回應，跳過此模型。
   診斷：模型在載入階段即逾時（尚未產生任何 token）；
         ⚠️  模型未出現在執行清單中，很可能因記憶體不足 (OOM) 無法載入
略過此模型，前往下一個。
```

### 場景 2：模型部分載入 VRAM

```
⏳ 正在取得 llama3.3:70b-instruct-q4_K_M 的打招呼回覆…（逾時 30 秒）
📊 資源佔用：模型大小 40.9 GB，VRAM 38.2 GB (93.4%)
   ⚠️  系統記憶體 2.7 GB（效能可能下降）

llama3.3:70b-instruct-q4_K_M：
你好！我是一個大型語言模型...
```

### 場景 3：模型載入成功但生成過慢

```
⏳ 正在取得 model-xxx 的打招呼回覆…（逾時 30 秒）
📊 資源佔用：模型大小 40.9 GB，VRAM 40.9 GB (100.0%)
⏱️  超過 30 秒未完成回應，跳過此模型。
   診斷：模型已開始生成但回應過慢；
         模型大小 40.9 GB，VRAM 使用 40.9 GB (100%)
略過此模型，前往下一個。
```

### 場景 4：Ollama 直接回報 OOM

```
⏳ 正在取得 model-xxx 的打招呼回覆…（逾時 30 秒）
💥 記憶體不足 (OOM)，無法載入或執行此模型：out of memory
略過此模型，前往下一個。
```

---

## ollama-benchmark.py 的錯誤處理

`ollama-benchmark.py` 使用較簡單的錯誤處理策略：

```python
try:
    result = ollama_generate(model, item["prompt"])
    results.append({..., "success": True})
except Exception as e:
    results.append({..., "success": False, "error": str(e)})
```

- 使用廣泛的 `Exception` 捕捉所有錯誤
- 失敗的測試記錄錯誤訊息，`latency` 設為 `None`，`length` 設為 `0`
- 不中斷評測流程，繼續下一個測試項目
- HTML 報告中以 ❌ 標記失敗的測試

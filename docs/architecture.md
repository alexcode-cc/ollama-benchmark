# 系統架構總覽

## 專案簡介

**ollama-benchmark** 是一個用於測試和評估本地 Ollama LLM 模型效能的 CLI 工具組，包含自動化基準測試和互動式聊天兩大功能模組。

## 技術堆疊

| 項目 | 說明 |
|------|------|
| 語言 | Python >= 3.10 |
| 套件管理 | uv（推薦）/ pip |
| 建置系統 | hatchling |
| 核心依賴 | requests >= 2.28.0 |
| 選用依賴 | pyreadline3 >= 3.4.0（僅 Windows） |
| 圖表產生 | Chart.js v4（CDN，嵌入 HTML） |
| 授權 | MIT |

## 專案結構

```
ollama-benchmark/
├── hi-ai.py                 # 互動式聊天腳本（含 OOM 診斷）
├── ollama-benchmark.py      # 自動化基準測試腳本（含 HTML 報告）
├── pyproject.toml           # 專案設定與依賴宣告
├── README.md                # 專案說明文件
├── CLAUDE.md                # Claude AI 開發規範
├── LICENSE.txt              # MIT 授權文件
├── .gitignore               # Git 忽略規則
├── docs/                    # 技術文件目錄
│   ├── architecture.md      # 系統架構總覽（本文件）
│   ├── hi-ai-technical.md   # hi-ai.py 技術文件
│   ├── benchmark-technical.md # ollama-benchmark.py 技術文件
│   ├── ollama-api.md        # Ollama API 串接說明
│   └── error-handling.md    # 錯誤處理與 OOM 診斷機制
└── chats/                   # 測試報告輸出目錄（.gitignore 排除）
    ├── benchmark_20260206_114947/
    │   ├── benchmark_report.json
    │   └── benchmark_report.html
    └── ...
```

## 模組關係圖

```
┌─────────────────────────────────────────────────────────┐
│                    Ollama 伺服器                         │
│                http://localhost:11434                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │ /api/tags│  │/api/generate│ │ /api/chat│  │/api/ps │ │
│  └─────┬────┘  └─────┬─────┘  └────┬─────┘  └───┬────┘ │
└────────┼─────────────┼──────────────┼────────────┼──────┘
         │             │              │            │
    ┌────┴─────────────┴──────────────┴────────────┴────┐
    │              requests (HTTP Client)                 │
    └────┬──────────────────────────────────┬────────────┘
         │                                  │
  ┌──────┴──────────┐            ┌──────────┴───────────┐
  │   hi-ai.py      │            │  ollama-benchmark.py  │
  │                 │            │                       │
  │ • 模型列表查詢   │            │ • 模型列表查詢         │
  │ • Streaming 生成 │            │ • 非 Streaming 生成    │
  │ • 模型卸載      │            │ • 延遲/長度測量         │
  │ • OOM 診斷      │            │ • HTML 報告生成         │
  │ • 資源監控      │            │ • Chart.js 圖表         │
  └─────────────────┘            └───────────────────────┘
```

## 兩個腳本的設計差異

| 特性 | hi-ai.py | ollama-benchmark.py |
|------|----------|---------------------|
| 主要用途 | 互動式聊天與模型探索 | 自動化效能基準測試 |
| API 模式 | Streaming（`stream: True`） | 非 Streaming（`stream: False`） |
| 逾時機制 | 30 秒（打招呼）/ 1800 秒（聊天） | 600 秒（固定） |
| 記憶體管理 | 主動卸載已載入模型 | 無 |
| OOM 診斷 | 有（透過 /api/ps 診斷） | 無 |
| 資源監控 | 有（顯示 VRAM 佔用） | 無 |
| 報告輸出 | 無 | JSON + HTML（含互動圖表） |
| 命令列參數 | `--auto`（自動模式） | `--auto`（自動模式） |
| 使用的 API | /api/tags, /api/generate, /api/chat, /api/ps | /api/tags, /api/generate |

## 資料流

### hi-ai.py 執行流程

#### 正常模式（預設）

```
啟動 → 解析命令列參數 (argparse)
         │
         ▼
    取得模型列表 (/api/tags)
         │
         ▼
    ┌─ 迴圈遍歷每個模型 ─────────────────────────┐
    │                                              │
    │  1. 卸載所有已載入的模型 (/api/chat)          │
    │  2. 發送打招呼 prompt (/api/generate stream)  │
    │  3. 收到第一個 token → 顯示資源佔用 (/api/ps) │
    │  4. 完整回覆後 → 詢問是否繼續交談             │
    │     ├─ y → 進入聊天迴圈                      │
    │     ├─ n → 下一個模型                        │
    │     └─ q → 離開程式                          │
    │                                              │
    └──────────────────────────────────────────────┘
         │
         ▼
    所有模型測試完成
```

#### 自動模式（`--auto`）

```
啟動 → 解析命令列參數 (argparse --auto)
         │
         ▼
    取得模型列表 (/api/tags)
         │
         ▼
    印出「🤖 自動模式：將跳過所有互動確認」
         │
         ▼
    ┌─ 迴圈遍歷每個模型 ─────────────────────────┐
    │                                              │
    │  1. 卸載所有已載入的模型 (/api/chat)          │
    │  2. 發送打招呼 prompt (/api/generate stream)  │
    │  3. 收到第一個 token → 顯示資源佔用 (/api/ps) │
    │  4. 完整回覆後 → 自動前往下一個模型           │
    │     （跳過互動確認，不進入聊天迴圈）          │
    │                                              │
    └──────────────────────────────────────────────┘
         │
         ▼
    所有模型測試完成
```

**使用場景**：
- **正常模式**：深入測試特定模型，進行多輪對話
- **自動模式**：快速檢查所有模型的可用性與打招呼回應品質

### ollama-benchmark.py 執行流程

```
啟動（解析 --auto 參數）→ 取得模型列表 (/api/tags)
         │
         ▼
    ┌─ 迴圈遍歷每個模型 ─────────────────────────┐
    │                                              │
    │  迴圈遍歷 4 個測試項目：                      │
    │    greeting → reasoning → coding → expression │
    │                                              │
    │  每個項目：                                   │
    │    1. 發送 prompt (/api/generate)             │
    │    2. 測量延遲時間（秒）                       │
    │    3. 記錄回應長度（字元）                     │
    │    4. 記錄成功/失敗狀態                        │
    │                                              │
    │  非 --auto 模式：詢問是否進入互動聊天          │
    │                                              │
    └──────────────────────────────────────────────┘
         │
         ▼
    建立 chats/benchmark_{timestamp}/ 目錄
         │
         ├─→ benchmark_report.json（原始數據）
         └─→ benchmark_report.html（分析圖表）
```

## 設定常數

### hi-ai.py

| 常數 | 值 | 說明 |
|------|------|------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama 伺服器位址 |
| `GREETING_PROMPT` | `"你是誰"` | 打招呼測試用的 prompt |
| `GREETING_TIMEOUT_SECONDS` | `30` | 打招呼請求逾時（秒） |
| `OOM_KEYWORDS` | `["out of memory", "oom", ...]` | OOM 錯誤關鍵字列表 |

### ollama-benchmark.py

| 常數 | 值 | 說明 |
|------|------|------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama 伺服器位址 |
| `CHATS_DIR` | `{專案根目錄}/chats` | 報告輸出基礎目錄 |
| `BENCHMARK_PROMPTS` | 4 個測試項目 | 評測用的 prompt 列表 |
| `CHART_COLORS` | 8 色 RGBA 調色盤 | Chart.js 圖表顏色 |
| `CHART_BORDERS` | 8 色 RGBA 邊框色 | Chart.js 圖表邊框顏色 |

## 相依性說明

### 執行時依賴

- **requests >= 2.28.0**：HTTP 客戶端，用於與 Ollama REST API 溝通。所有 API 呼叫（模型列表、文字生成、模型卸載、狀態查詢）都透過此套件實現。

### 選用依賴

- **pyreadline3 >= 3.4.0**（僅 Windows）：在 Windows 環境下提供更好的 `input()` 輸入體驗。

### 建置系統

- **hatchling**：用於建構 Python 套件的後端。在 `pyproject.toml` 中設定，支援 `uv sync` 和 `pip install -e .` 安裝方式。

### 外部 CDN 依賴

- **Chart.js v4**（`https://cdn.jsdelivr.net/npm/chart.js@4`）：僅在 HTML 報告中使用，透過 CDN 載入，不需要安裝到 Python 環境。瀏覽報告時需要網路連線。

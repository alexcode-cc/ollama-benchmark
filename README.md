# Ollama Benchmark

一個用於測試和評估本地 Ollama LLM 模型效能的基準測試工具組。

## 功能特點

### 自動化基準測試（ollama-benchmark.py）

- **自動偵測模型**：從 Ollama 伺服器取得所有可用模型並依序評測
- **多面向測試**：涵蓋問候、邏輯推理、程式碼生成、表達能力 4 大測試項目
- **效能指標**：測量每個測試的回應延遲（秒）與回應長度（字元）
- **互動式 HTML 報告**：自動產生包含 Chart.js 互動圖表的分析頁面
- **JSON 原始數據**：同時輸出 JSON 格式的完整測試數據
- **自動模式**：`--auto` 參數跳過互動確認，一次完成所有模型評測

### 互動式聊天（hi-ai.py）

- **逐模型打招呼**：自動對每個模型發送打招呼 prompt 測試
- **記憶體管理**：每次切換模型前自動卸載已載入的模型，避免 OOM
- **逾時控制**：打招呼測試設有 30 秒逾時，超時自動跳過
- **OOM 診斷**：逾時後自動透過 `/api/ps` 診斷原因（載入階段 vs 生成階段）
- **資源監控**：在模型開始回覆時即時顯示 VRAM / 記憶體佔用情形
- **快速離開**：支援 `q` 鍵隨時退出程式

## 系統需求

- Python >= 3.10
- [Ollama](https://ollama.ai/) 伺服器在本地運行（預設 `http://localhost:11434`）
- 至少安裝一個 Ollama 模型

## 安裝

### 使用 uv（推薦）

```bash
uv sync
```

### 使用 pip

```bash
pip install -e .
```

### 設定檔（選用）

複製 `.env.example` 為 `.env` 並根據需求調整設定：

```bash
cp .env.example .env
```

可設定項目：
- `OLLAMA_BASE_URL`：Ollama 伺服器位址（預設 `http://localhost:11434`）
- `GREETING_PROMPT`：hi-ai.py 的打招呼 prompt（預設 `你是誰`）
- `GREETING_TIMEOUT_SECONDS`：打招呼逾時秒數（預設 `30`）

若不建立 `.env` 檔案，程式會使用預設值。

## 使用方式

### 基準測試

```bash
# 正常模式（每個模型後詢問是否互動）
uv run ollama-benchmark.py

# 自動模式（跳過互動確認，一次跑完所有模型）
uv run ollama-benchmark.py --auto
```

執行後會：
1. 自動偵測所有可用模型
2. 對每個模型執行 4 項測試（greeting / reasoning / coding / expression）
3. 測量回應延遲與回應長度
4. 在 `chats/benchmark_YYYYMMDD_HHMMSS/` 目錄下輸出：
   - `benchmark_report.json` — 原始測試數據
   - `benchmark_report.html` — 互動式分析報告（含比較圖表）

### 互動式聊天

```bash
uv run hi-ai.py
```

執行後會：
1. 偵測所有可用模型
2. 依序對每個模型執行打招呼測試
3. 每次切換模型前自動卸載先前的模型（釋放記憶體）
4. 顯示模型的 VRAM / 記憶體佔用情形
5. 打招呼後詢問是否繼續交談（y=繼續 / n=下一個模型 / q=離開）

## 測試項目

| 測試名稱 | 測試能力 | 說明 |
|---------|---------|------|
| greeting | 語言理解 + 自然對話 | 以繁體中文簡單自我介紹 |
| reasoning | 邏輯推理 + 數學計算 | 計算房間裡人和貓的腳數 |
| coding | 程式碼生成 | 撰寫判斷質數的 Python 函式 |
| expression | 表達能力 + 概念解釋 | 用非技術語言解釋 RESTful API |

## HTML 分析報告

自動產生的 HTML 報告包含：

- **模型總覽表格**：平均延遲、總回應長度、成功率
- **平均回應延遲圖表**：長條圖比較各模型速度
- **總回應長度圖表**：長條圖比較各模型回覆量
- **各測試項目延遲比較**：分組長條圖，各模型在各測試中的表現
- **各測試項目回應長度比較**：分組長條圖
- **詳細回覆內容**：可展開查看每個模型的完整回覆

報告使用 Chart.js CDN 產生互動式圖表，深色主題設計，支援響應式佈局。

## 專案結構

```
ollama-benchmark/
├── ollama-benchmark.py      # 自動化基準測試腳本
├── hi-ai.py                 # 互動式聊天腳本
├── pyproject.toml           # 專案設定與相依套件
├── README.md                # 專案說明（本文件）
├── HISTORY.md               # 版本歷史
├── CLAUDE.md                # Claude AI 開發規範
├── LICENSE.txt              # MIT 授權文件
├── .gitignore               # Git 忽略規則
├── docs/                    # 技術文件
│   ├── architecture.md      # 系統架構總覽
│   ├── hi-ai-technical.md   # hi-ai.py 技術文件
│   ├── benchmark-technical.md # ollama-benchmark.py 技術文件
│   ├── ollama-api.md        # Ollama API 串接說明
│   └── error-handling.md    # 錯誤處理與 OOM 診斷機制
└── chats/                   # 測試報告輸出目錄
    └── benchmark_YYYYMMDD_HHMMSS/
        ├── benchmark_report.json
        └── benchmark_report.html
```

## 技術文件

詳細的技術實作說明請參閱 `docs/` 目錄：

- [系統架構總覽](docs/architecture.md)
- [hi-ai.py 技術文件](docs/hi-ai-technical.md)
- [ollama-benchmark.py 技術文件](docs/benchmark-technical.md)
- [Ollama API 串接說明](docs/ollama-api.md)
- [錯誤處理與 OOM 診斷機制](docs/error-handling.md)

## 授權

MIT License

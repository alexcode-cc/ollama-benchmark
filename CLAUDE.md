# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 語言規範

- 所有回應、程式碼註解、使用者介面訊息、commit message 皆使用**繁體中文**
- 函式和變數命名使用英文，遵循 Python PEP 8 規範

## 常用指令

```bash
# 安裝依賴
uv sync

# 執行基準測試（正常模式，每個模型後詢問是否互動）
uv run ollama-benchmark.py

# 執行基準測試（自動模式，跳過互動確認）
uv run ollama-benchmark.py --auto

# 執行互動式聊天
uv run hi-ai.py
```

前提：需要 Ollama 伺服器運行（預設 `http://localhost:11434`，可透過 `.env` 設定連線遠端伺服器）。

## 架構概覽

專案包含兩個獨立的 CLI 腳本，皆透過 `requests` 呼叫 Ollama REST API：

- **`hi-ai.py`** — 互動式聊天腳本，使用 streaming 模式（`/api/generate` stream=True），具備模型卸載（`/api/chat` keep_alive=0）、OOM 診斷（`/api/ps`）、VRAM 資源監控等功能。打招呼逾時 30 秒，聊天逾時 1800 秒。
- **`ollama-benchmark.py`** — 自動化基準測試腳本，使用非 streaming 模式（`/api/generate` stream=False），對每個模型執行 4 項測試（greeting / reasoning / coding / expression），測量延遲與回應長度，產出 JSON + HTML（Chart.js v4）互動式報告至 `chats/benchmark_{timestamp}/` 目錄。

兩個腳本無共用模組，各自獨立實作 `get_available_models()` 等函式。

## Git Commit Message 規範

採用 **AngularJS Git Commit Message Conventions**，繁體中文撰寫。

格式：`<type>(<scope>): <subject>`

**Type**: feat / fix / docs / style / refactor / perf / test / chore / revert

**Scope**: hi-ai / benchmark / docs / config

範例：
```
feat(hi-ai): 新增模型逾時診斷功能
fix(benchmark): 修正測試報告時間戳記格式
docs: 新增專案 README 文件
```

## 技術細節

- Python >= 3.10，唯一執行時依賴為 `requests >= 2.28.0`
- 建置系統為 hatchling，套件管理推薦 uv
- 選用依賴：`pyreadline3`（僅 Windows，改善 input() 體驗）
- HTML 報告透過 CDN 載入 Chart.js v4，瀏覽時需網路連線
- 設定檔透過 `.env` 管理（`.env` 已加入 .gitignore，範本為 `.env.example`）
- 支援連線遠端 Ollama 伺服器（透過 `OLLAMA_BASE_URL` 環境變數）
- 測試報告輸出至 `chats/` 目錄（已加入 .gitignore）
- 詳細技術文件見 `docs/` 目錄

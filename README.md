# Ollama Benchmark

一個用於測試和評估本地 Ollama LLM 模型效能的基準測試工具。

## 功能特點

- **自動化基準測試**：自動偵測本地 Ollama 伺服器上的所有可用模型並執行測試
- **多樣化測試項目**：包含問候、推理、程式碼生成和表達能力等測試
- **效能指標**：測量每個測試的回應時間（延遲）和回應長度
- **JSON 報告**：自動生成帶時間戳記的 JSON 格式測試報告
- **互動式聊天**：提供與模型進行即時對話的功能

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

## 使用方式

### 執行基準測試

```bash
python ollama-benchmark.py
```

執行後會：
1. 自動偵測所有可用模型
2. 對每個模型執行一系列測試
3. 測試完成後可選擇進入互動聊天模式
4. 將結果儲存至 `ollama_benchmark_YYYYMMDD_HHMMSS.json`

### 互動式聊天

```bash
python hi-ai.py
```

提供簡易的聊天介面，可依序與各個可用模型進行對話。

## 測試項目

| 測試名稱 | 說明 |
|---------|------|
| greeting | 中文問候與自我介紹 |
| reasoning | 數學推理問題（房間裡的腳數計算） |
| coding | 撰寫判斷質數的 Python 函數 |
| expression | 用中文解釋 RESTful API |

## 輸出報告

測試報告以 JSON 格式儲存，包含以下資訊：

```json
{
  "timestamp": "2024-01-01T12:00:00",
  "model": "llama3.2",
  "tests": [
    {
      "test_name": "greeting",
      "prompt": "...",
      "response": "...",
      "latency_seconds": 2.5,
      "response_length": 150,
      "success": true
    }
  ]
}
```

## 專案結構

```
ollama-benchmark/
├── ollama-benchmark.py    # 主要基準測試腳本
├── hi-ai.py               # 互動式聊天腳本
├── pyproject.toml         # 專案設定與相依套件
├── uv.lock                # 相依套件鎖定檔
└── README.md              # 本文件
```

## 授權

MIT License

# Claude AI 開發規範

## Git Commit Message 規範

本專案採用 **AngularJS Git Commit Message Conventions** 規範，所有提交訊息使用**繁體中文**撰寫。

### Commit Message 格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type 類型

- **feat**: 新增功能
- **fix**: 修復錯誤
- **docs**: 文件變更
- **style**: 程式碼格式調整（不影響程式碼運行的變更）
- **refactor**: 重構（既不是新增功能，也不是修復錯誤的程式碼變更）
- **perf**: 效能優化
- **test**: 新增或修改測試
- **chore**: 建構流程或輔助工具的變更
- **revert**: 還原先前的 commit

### Scope 範圍

- **hi-ai**: hi-ai.py 互動式聊天腳本
- **benchmark**: ollama-benchmark.py 基準測試腳本
- **docs**: 文件相關
- **config**: 設定檔相關

### Subject 主旨

- 使用繁體中文
- 簡潔描述變更內容
- 不超過 50 字
- 結尾不加句號

### Body 內文（選用）

- 使用繁體中文
- 詳細說明變更的原因和內容
- 可分多行撰寫

### Footer 頁尾（選用）

- 用於標註 Breaking Changes 或關閉 Issue
- 格式：`BREAKING CHANGE: 說明` 或 `Closes #123`

### 範例

```
feat(hi-ai): 新增模型逾時診斷功能

- 使用 streaming 模式追蹤 token 接收狀態
- 透過 /api/ps 診斷 OOM 問題
- 自動偵測記憶體不足錯誤訊息

Closes #42
```

```
fix(benchmark): 修正測試報告時間戳記格式
```

```
docs: 新增專案 README 文件
```

## 開發原則

1. 所有程式碼註解使用繁體中文
2. 函式和變數命名使用英文，遵循 Python PEP 8 規範
3. 使用者介面訊息使用繁體中文
4. 提交前確保沒有 linter 錯誤

# 連線遠端 Ollama 伺服器

## 概述

本專案預設連線本地 Ollama 伺服器（`http://localhost:11434`），但透過 `.env` 設定檔中的 `OLLAMA_BASE_URL` 環境變數，可以輕鬆連線至區域網路或網際網路上的遠端 Ollama 伺服器。

本文件涵蓋：
1. [用戶端設定（本專案）](#1-用戶端設定本專案)
2. [伺服器端設定（Ollama 伺服器）](#2-伺服器端設定ollama-伺服器)
3. [使用 Docker 部署遠端伺服器](#3-使用-docker-部署遠端伺服器)
4. [透過 Nginx 反向代理安全存取](#4-透過-nginx-反向代理安全存取)
5. [網路診斷與疑難排解](#5-網路診斷與疑難排解)
6. [安全性注意事項](#6-安全性注意事項)

---

## 1. 用戶端設定（本專案）

### 1.1 修改 `.env` 檔案

複製範本並修改 `OLLAMA_BASE_URL`：

```bash
cp .env.example .env
```

編輯 `.env`，將 URL 指向遠端伺服器：

```env
# 連線區域網路中的伺服器
OLLAMA_BASE_URL=http://192.168.1.100:11434

# 連線具有域名的伺服器
OLLAMA_BASE_URL=http://ollama.example.com:11434

# 透過 HTTPS 反向代理連線
OLLAMA_BASE_URL=https://ollama.example.com
```

### 1.2 驗證連線

設定完成後，可先手動測試連線是否正常：

```bash
# 測試伺服器是否可連通
curl http://192.168.1.100:11434

# 預期回應：Ollama is running

# 測試是否能取得模型列表
curl http://192.168.1.100:11434/api/tags
```

### 1.3 執行本專案工具

確認連線正常後，直接執行即可：

```bash
# 基準測試（自動模式）
uv run ollama-benchmark.py --auto

# 互動式聊天（正常模式）
uv run hi-ai.py

# 互動式聊天（自動模式，僅打招呼）
uv run hi-ai.py --auto
```

程式會自動從 `.env` 讀取 `OLLAMA_BASE_URL` 並連線至該伺服器。

### 1.4 不使用 .env 的替代方式

也可以直接設定系統環境變數：

```bash
# Linux / macOS（僅當次執行有效）
export OLLAMA_BASE_URL=http://192.168.1.100:11434
uv run ollama-benchmark.py --auto

# 或直接在指令前設定
OLLAMA_BASE_URL=http://192.168.1.100:11434 uv run hi-ai.py
OLLAMA_BASE_URL=http://192.168.1.100:11434 uv run hi-ai.py --auto
```

---

## 2. 伺服器端設定（Ollama 伺服器）

Ollama 預設只監聽 `127.0.0.1`（僅本機），必須修改設定才能讓遠端連線。

### 2.1 macOS

macOS 上 Ollama 以應用程式形式運行，使用 `launchctl` 設定環境變數：

```bash
# 設定監聽所有網路介面
launchctl setenv OLLAMA_HOST "0.0.0.0:11434"

# 設定允許跨域請求（選用，用於瀏覽器存取）
launchctl setenv OLLAMA_ORIGINS "*"
```

設定完成後，**重新啟動 Ollama 應用程式**（從選單列結束再重新開啟）。

**驗證監聽位址**：

```bash
# 確認 Ollama 是否監聽在 0.0.0.0
lsof -i :11434
```

應看到類似 `*:11434` 而非 `localhost:11434`。

### 2.2 Linux（systemd）

大多數 Linux 發行版使用 systemd 管理 Ollama 服務：

```bash
# 編輯 Ollama 服務設定
sudo systemctl edit ollama.service
```

在編輯器中加入以下內容：

```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
Environment="OLLAMA_ORIGINS=*"
```

儲存後重新載入並重啟服務：

```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

**驗證監聽位址**：

```bash
# 確認監聽在 0.0.0.0 而非 127.0.0.1
sudo ss -ltnp | grep 11434
# 預期輸出：LISTEN 0 ... 0.0.0.0:11434 ...
```

> **注意**：在 shell 中 `export OLLAMA_HOST=0.0.0.0` 對 systemd 服務無效。必須透過 `systemctl edit` 修改，或先停止服務再手動啟動：
> ```bash
> sudo systemctl stop ollama
> OLLAMA_HOST=0.0.0.0 ollama serve
> ```

### 2.3 Windows

1. 開啟「系統內容」→「進階系統設定」→「環境變數」
2. 在「系統變數」中新增：
   - 變數名稱：`OLLAMA_HOST`
   - 變數值：`0.0.0.0:11434`
3. （選用）新增 `OLLAMA_ORIGINS` = `*`
4. 點擊「確定」後，**重新啟動 Ollama**

### 2.4 Ollama 伺服器環境變數一覽

| 環境變數 | 預設值 | 說明 |
|---------|--------|------|
| `OLLAMA_HOST` | `127.0.0.1:11434` | 伺服器監聽位址與埠號 |
| `OLLAMA_ORIGINS` | （無） | 允許的跨域來源，設為 `*` 允許所有 |
| `OLLAMA_MODELS` | `~/.ollama/models` | 模型存放路徑 |
| `OLLAMA_KEEP_ALIVE` | `5m` | 模型載入後保持在記憶體中的時間 |
| `OLLAMA_NUM_PARALLEL` | `1` | 同時處理的請求數量 |
| `OLLAMA_MAX_QUEUE` | `512` | 請求佇列最大長度 |
| `OLLAMA_FLASH_ATTENTION` | `0` | 是否啟用 Flash Attention（設 `1` 啟用） |
| `CUDA_VISIBLE_DEVICES` | （全部） | 指定可使用的 GPU 裝置編號 |

---

## 3. 使用 Docker 部署遠端伺服器

### 3.1 基本部署（僅 CPU）

```yaml
# docker-compose.yml
services:
  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    restart: unless-stopped
    ports:
      - "11434:11434"
    volumes:
      - ollama-data:/root/.ollama
    environment:
      - OLLAMA_HOST=0.0.0.0:11434

volumes:
  ollama-data:
```

```bash
# 啟動
docker compose up -d

# 下載模型
docker exec ollama ollama pull llama3.1:8b

# 查看日誌
docker compose logs -f ollama
```

### 3.2 GPU 加速部署（NVIDIA）

**前置需求**：
1. 安裝 NVIDIA 驅動程式
2. 安裝 [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

```bash
# 安裝 NVIDIA Container Toolkit（Ubuntu / Debian）
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit

# 設定 Docker 使用 NVIDIA runtime
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

```yaml
# docker-compose.yml（GPU 版本）
services:
  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    restart: unless-stopped
    ports:
      - "11434:11434"
    volumes:
      - ollama-data:/root/.ollama
    environment:
      - OLLAMA_HOST=0.0.0.0:11434
      - OLLAMA_FLASH_ATTENTION=1
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

volumes:
  ollama-data:
```

### 3.3 限制特定 GPU

若伺服器有多張 GPU，可指定使用哪些：

```yaml
environment:
  - CUDA_VISIBLE_DEVICES=0      # 僅使用第一張 GPU
  - CUDA_VISIBLE_DEVICES=0,1    # 使用前兩張 GPU
```

---

## 4. 透過 Nginx 反向代理安全存取

Ollama **不具備**內建的身份驗證機制，若需在網際網路上公開存取，強烈建議透過反向代理加上 HTTPS 和身份驗證。

### 4.1 Nginx 基本反向代理設定

```nginx
# /etc/nginx/sites-available/ollama
server {
    listen 80;
    server_name ollama.example.com;

    location / {
        proxy_pass http://127.0.0.1:11434;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 支援長時間連線（模型推理可能需要較久）
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;

        # 支援 Streaming 回應
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding on;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/ollama /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 4.2 加入 HTTPS（Let's Encrypt）

```bash
# 安裝 Certbot
sudo apt install certbot python3-certbot-nginx

# 自動取得並設定 SSL 憑證
sudo certbot --nginx -d ollama.example.com
```

Certbot 會自動修改 Nginx 設定，加入 SSL 憑證路徑和重導向。

### 4.3 加入 HTTP Basic 身份驗證

```bash
# 建立密碼檔（首次使用 -c 建立，之後新增使用者不需要 -c）
sudo apt install apache2-utils
sudo htpasswd -c /etc/nginx/.htpasswd ollama-user
```

修改 Nginx 設定：

```nginx
server {
    listen 443 ssl;
    server_name ollama.example.com;

    # SSL 設定（由 Certbot 自動產生）
    ssl_certificate /etc/letsencrypt/live/ollama.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ollama.example.com/privkey.pem;

    location / {
        # 身份驗證
        auth_basic "Ollama Server";
        auth_basic_user_file /etc/nginx/.htpasswd;

        proxy_pass http://127.0.0.1:11434;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding on;
    }
}
```

### 4.4 用戶端連線 HTTPS + 認證的伺服器

透過 Nginx 反向代理後，`.env` 設定改為 HTTPS URL：

```env
# 不帶認證（若 Nginx 未設定 auth_basic）
OLLAMA_BASE_URL=https://ollama.example.com

# 帶 HTTP Basic 認證
OLLAMA_BASE_URL=https://ollama-user:password@ollama.example.com
```

手動測試：

```bash
# 帶認證的 curl 測試
curl -u ollama-user:password https://ollama.example.com/api/tags
```

> **注意**：若在 `.env` 中直接寫入帳號密碼，請確保 `.env` 已在 `.gitignore` 中排除（本專案已預設排除）。

---

## 5. 網路診斷與疑難排解

### 5.1 常見問題

| 症狀 | 可能原因 | 解決方式 |
|------|---------|---------|
| `Connection refused` | Ollama 未啟動或未監聽該位址 | 確認 Ollama 正在運行，且 `OLLAMA_HOST` 設為 `0.0.0.0` |
| `Connection timed out` | 防火牆阻擋 | 開放 11434 埠號 |
| `Name resolution failed` | DNS 解析失敗 | 確認域名正確，或改用 IP 位址 |
| `SSL certificate verify failed` | 自簽憑證或憑證過期 | 使用 Let's Encrypt 取得有效憑證 |
| `401 Unauthorized` | Nginx 身份驗證失敗 | 確認帳號密碼正確 |
| `502 Bad Gateway` | Nginx 無法連線到 Ollama | 確認 Ollama 正在運行於 `127.0.0.1:11434` |

### 5.2 診斷指令

```bash
# 1. 確認伺服器 Ollama 服務狀態
sudo systemctl status ollama

# 2. 確認監聽位址（Linux）
sudo ss -ltnp | grep 11434

# 3. 確認防火牆規則（Ubuntu）
sudo ufw status
sudo ufw allow 11434/tcp    # 開放埠號

# 4. 確認防火牆規則（CentOS / RHEL）
sudo firewall-cmd --list-all
sudo firewall-cmd --permanent --add-port=11434/tcp
sudo firewall-cmd --reload

# 5. 從用戶端測試連線
curl -v http://伺服器IP:11434

# 6. 從用戶端測試 API
curl http://伺服器IP:11434/api/tags

# 7. 測試 Streaming 回應
curl http://伺服器IP:11434/api/generate -d '{"model":"llama3.1:8b","prompt":"hello","stream":true}'
```

### 5.3 效能考量

連線遠端伺服器時需注意：

- **網路延遲**：遠端連線會增加每次請求的往返時間（RTT），基準測試的延遲數據會包含網路傳輸時間
- **頻寬限制**：大型模型回覆（如 coding 測試）可能產生較多資料傳輸
- **Streaming 模式**：`hi-ai.py` 使用 Streaming，對網路穩定性要求較高
- **逾時調整**：遠端連線建議適當增加 `GREETING_TIMEOUT_SECONDS`，例如設為 `60`

```env
# 遠端伺服器建議的逾時設定
GREETING_TIMEOUT_SECONDS=60
```

---

## 6. 安全性注意事項

### 絕對不要做的事

- **不要**將 Ollama 直接暴露在公共網際網路上（無身份驗證）
- **不要**在公開的 Git 倉庫中提交 `.env` 檔案（包含伺服器位址和密碼）
- **不要**使用 HTTP（非 HTTPS）在公共網路傳輸認證資訊

### 建議的安全措施

| 場景 | 建議做法 |
|------|---------|
| 僅本機使用 | 保持預設 `127.0.0.1:11434`，無需額外設定 |
| 區域網路（家庭/辦公室） | 設定 `OLLAMA_HOST=0.0.0.0`，確保路由器防火牆未對外開放 11434 埠 |
| 網際網路存取 | 使用 Nginx 反向代理 + HTTPS + HTTP Basic Auth 或 API Key |
| 高安全性需求 | 使用 VPN（如 WireGuard、Tailscale）建立安全通道 |

### `.env` 檔案安全

本專案的 `.gitignore` 已排除 `.env` 檔案，確保敏感資訊不會被提交到版本控制：

```gitignore
# Virtual Environment
.env
```

> `.env.example` 是不含敏感資訊的範本檔案，可以安全提交。

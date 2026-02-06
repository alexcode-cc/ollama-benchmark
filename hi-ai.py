import json
import requests

OLLAMA_BASE_URL = "http://localhost:11434"

GREETING_PROMPT = "你是誰"
#GREETING_PROMPT = "你好，請以繁體中文向我打招呼並簡單自我介紹。"

GREETING_TIMEOUT_SECONDS = 30

# 用於比對 Ollama 回傳的 OOM / 記憶體相關錯誤訊息
OOM_KEYWORDS = [
    "out of memory", "oom", "not enough memory",
    "failed to load", "insufficient memory",
    "cuda out of memory", "memory", "alloc",
]


def get_available_models() -> list[str]:
    """從 Ollama 伺服器取得目前有提供服務的模型列表"""
    resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=GREETING_TIMEOUT_SECONDS)
    resp.raise_for_status()
    data = resp.json()
    return [m["name"] for m in data.get("models", [])]


def get_running_models() -> list[dict]:
    """取得目前已載入記憶體的模型清單（透過 /api/ps）"""
    resp = requests.get(f"{OLLAMA_BASE_URL}/api/ps", timeout=10)
    resp.raise_for_status()
    return resp.json().get("models", [])


def unload_model(model_name: str) -> bool:
    """卸載指定模型，釋放其佔用的記憶體。回傳是否成功。"""
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": model_name,
                "messages": [],
                "keep_alive": 0,
            },
            timeout=GREETING_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"   ⚠️  卸載 {model_name} 失敗：{e}", flush=True)
        return False


def unload_all_models() -> None:
    """卸載所有目前已載入記憶體的模型，以釋放記憶體空間。"""
    try:
        running = get_running_models()
    except requests.RequestException:
        return

    if not running:
        return

    names = [m.get("name", "unknown") for m in running]
    total_size = sum(m.get("size", 0) for m in running)
    print(
        f"🧹 正在卸載 {len(running)} 個已載入的模型以釋放記憶體"
        f"（共 {_format_bytes(total_size)}）…",
        flush=True,
    )
    for m in running:
        name = m.get("name", "")
        size = m.get("size", 0)
        if name:
            print(f"   卸載 {name} ({_format_bytes(size)})…", end="", flush=True)
            ok = unload_model(name)
            print(" ✅" if ok else " ❌", flush=True)


def _is_oom_error(error_msg: str) -> bool:
    """判斷錯誤訊息是否與 OOM / 記憶體不足相關"""
    lower = error_msg.lower()
    return any(kw in lower for kw in OOM_KEYWORDS)


def _format_bytes(n: int) -> str:
    """將位元組數格式化為人類可讀的字串"""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def show_model_resource_usage(model: str) -> None:
    """顯示指定模型的資源佔用情形（透過 /api/ps）"""
    try:
        running = get_running_models()
        for m in running:
            if m.get("name") == model or m.get("model") == model:
                size = m.get("size", 0)
                size_vram = m.get("size_vram", 0)
                
                if size > 0:
                    vram_pct = (size_vram / size) * 100 if size > 0 else 0
                    print(f"📊 資源佔用：模型大小 {_format_bytes(size)}，VRAM {_format_bytes(size_vram)} ({vram_pct:.1f}%)", flush=True)
                    
                    if size_vram < size * 0.95:  # 未達 95% 表示部分在系統記憶體
                        system_mem = size - size_vram
                        print(f"   ⚠️  系統記憶體 {_format_bytes(system_mem)}（效能可能下降）", flush=True)
                else:
                    print(f"📊 資源佔用：模型已載入", flush=True)
                return
        
        # 模型不在執行清單中
        print(f"📊 資源佔用：模型資訊無法取得", flush=True)
    except requests.RequestException:
        # 無法連線 /api/ps，靜默處理
        pass


def diagnose_timeout(model: str, got_any_token: bool) -> str:
    """在逾時後，透過 /api/ps 診斷可能原因並回傳描述字串。
    got_any_token：在逾時前是否已收到任何生成 token。
    """
    diagnosis_parts: list[str] = []

    # 階段判斷
    if not got_any_token:
        diagnosis_parts.append("模型在載入階段即逾時（尚未產生任何 token）")
    else:
        diagnosis_parts.append("模型已開始生成但回應過慢")

    # 透過 /api/ps 查詢目前載入的模型與記憶體狀態
    try:
        ps_resp = requests.get(f"{OLLAMA_BASE_URL}/api/ps", timeout=5)
        ps_resp.raise_for_status()
        ps_data = ps_resp.json()
        running_models = ps_data.get("models", [])

        target_found = False
        for m in running_models:
            if m.get("name") == model or m.get("model") == model:
                target_found = True
                size = m.get("size", 0)
                size_vram = m.get("size_vram", 0)
                if size > 0:
                    vram_pct = (size_vram / size) * 100
                    diagnosis_parts.append(
                        f"模型大小 {_format_bytes(size)}，"
                        f"VRAM 使用 {_format_bytes(size_vram)} ({vram_pct:.0f}%)"
                    )
                    if size_vram < size:
                        diagnosis_parts.append(
                            "⚠️  模型未完全載入 VRAM，部分使用系統記憶體，效能大幅下降"
                        )
                break

        if not target_found and not got_any_token:
            diagnosis_parts.append("⚠️  模型未出現在執行清單中，很可能因記憶體不足 (OOM) 無法載入")
            # 列出其他佔用記憶體的模型
            if running_models:
                others = [
                    f"{m.get('name', 'unknown')} ({_format_bytes(m.get('size', 0))})"
                    for m in running_models
                ]
                diagnosis_parts.append(f"目前已載入的模型：{', '.join(others)}")

    except requests.RequestException:
        diagnosis_parts.append("（無法連線 /api/ps 進行進一步診斷）")

    return "；".join(diagnosis_parts)


class OllamaError(Exception):
    """Ollama API 回傳的錯誤"""


def llama_local(prompt: str, model: str, *, timeout: int = GREETING_TIMEOUT_SECONDS*60, show_resource: bool = True) -> str:
    """呼叫 Ollama 產生回應（使用 streaming 模式）。timeout：逾時秒數，預設 GREETING_TIMEOUT_SECONDS*60。
    show_resource：是否在收到第一個 token 後顯示資源佔用。"""
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": True,
        },
        stream=True,
        timeout=(10, timeout),  # (連線逾時, 讀取逾時—兩次資料之間的最大等待)
    )
    resp.raise_for_status()

    full_response: list[str] = []
    first_token_received = False
    
    for line in resp.iter_lines():
        if not line:
            continue
        chunk = json.loads(line)
        # Ollama 串流中回傳錯誤
        if "error" in chunk:
            raise OllamaError(chunk["error"])
        token = chunk.get("response", "")
        if token:
            # 收到第一個 token 時顯示資源佔用
            if not first_token_received and show_resource:
                first_token_received = True
                show_model_resource_usage(model)
            full_response.append(token)
        if chunk.get("done"):
            break

    return "".join(full_response).strip() or "(無回覆)"


def llama_local_greeting(prompt: str, model: str, *, timeout: int = GREETING_TIMEOUT_SECONDS) -> str:
    """專為打招呼設計：使用 streaming 模式，追蹤是否收到 token 以便逾時診斷。"""
    got_any_token = False
    first_token_received = False
    
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": True,
            },
            stream=True,
            timeout=(10, timeout),
        )
        resp.raise_for_status()

        full_response: list[str] = []
        for line in resp.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            if "error" in chunk:
                raise OllamaError(chunk["error"])
            token = chunk.get("response", "")
            if token:
                # 收到第一個 token 時顯示資源佔用
                if not first_token_received:
                    first_token_received = True
                    show_model_resource_usage(model)
                got_any_token = True
                full_response.append(token)
            if chunk.get("done"):
                break

        return "".join(full_response).strip() or "(無回覆)"

    except requests.Timeout:
        diag = diagnose_timeout(model, got_any_token)
        raise TimeoutWithDiagnosis(diag) from None

    except requests.HTTPError as e:
        # 嘗試從回應內容解析 OOM 錯誤
        error_body = ""
        if e.response is not None:
            try:
                error_body = e.response.text
            except Exception:
                pass
        if error_body and _is_oom_error(error_body):
            raise OllamaError(f"記憶體不足 (OOM)：{error_body}") from None
        raise


class TimeoutWithDiagnosis(Exception):
    """逾時且附帶診斷資訊"""


def greeting_for_model(model: str) -> str | None:
    """對單一模型執行打招呼測試，超過 GREETING_TIMEOUT_SECONDS 秒未回應則跳過。
    回傳模型回覆或 None（失敗/逾時時）。"""
    print(f"⏳ 正在取得 {model} 的打招呼回覆…（逾時 {GREETING_TIMEOUT_SECONDS} 秒）", flush=True)
    try:
        reply = llama_local_greeting(GREETING_PROMPT, model, timeout=GREETING_TIMEOUT_SECONDS)
        return reply

    except TimeoutWithDiagnosis as e:
        print(f"⏱️  超過 {GREETING_TIMEOUT_SECONDS} 秒未完成回應，跳過此模型。", flush=True)
        print(f"   診斷：{e}", flush=True)
        return None

    except OllamaError as e:
        error_msg = str(e)
        if _is_oom_error(error_msg):
            print(f"💥 記憶體不足 (OOM)，無法載入或執行此模型：{error_msg}", flush=True)
        else:
            print(f"❌ Ollama 錯誤：{error_msg}", flush=True)
        return None

    except requests.RequestException as e:
        print(f"❌ 取得回覆失敗：{e}", flush=True)
        return None


def chat_with_model(model: str) -> None:
    """對單一模型：先打招呼，再詢問是否繼續交談；不繼續則結束此模型流程"""
    print("=" * 60, flush=True)
    print(f"🤖 使用模型：{model}", flush=True)
    print("=" * 60, flush=True)

    # 先卸載所有已載入的模型，確保有足夠記憶體載入新模型
    unload_all_models()

    # 執行打招呼測試
    reply = greeting_for_model(model)
    if reply is None:
        print("略過此模型，前往下一個。\n", flush=True)
        return

    print(f"\n{model}：\n{reply}\n", flush=True)

    # 暫停：讓使用者確認是否繼續與此模型交談
    while True:
        user_input = input("是否繼續與此模型交談？(y/Enter=繼續, n=下一個模型, q=離開)： ").strip().lower()
        if user_input in ("q", "quit", "exit"):
            print("👋 離開程式", flush=True)
            exit(0)
        
        if user_input in ("n", "no", "next"):
            print(f"➡️  切換到下一個模型\n", flush=True)
            return

        if user_input in ("", "y", "yes"):
            break
        print("請輸入 y 繼續、n 跳到下一個模型，或 q 離開程式。")

    # 繼續交談迴圈
    while True:
        user_input = input("你： ").strip()
        if user_input.lower() in ("n", "no", "next", "quit", "q"):
            print(f"➡️  切換到下一個模型\n", flush=True)
            return
        if not user_input:
            continue
        try:
            reply = llama_local(user_input, model)
            print(f"{model}：\n{reply}\n", flush=True)
        except requests.RequestException as e:
            print(f"❌ 請求失敗：{e}\n", flush=True)


def main():
    models = get_available_models()

    if not models:
        print("⚠️  Ollama 伺服器目前沒有任何可用模型", flush=True)
        return

    print("📦 偵測到以下可用模型：", flush=True)
    for m in models:
        print(f" - {m}", flush=True)
    print(flush=True)

    for model in models:
        chat_with_model(model)

    print("✅ 所有模型測試完成", flush=True)


if __name__ == "__main__":
    main()

import requests

OLLAMA_BASE_URL = "http://localhost:11434"


def get_available_models():
    """從 Ollama 伺服器取得目前可用的模型列表"""
    resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return [m["name"] for m in data.get("models", [])]


def llama_local(prompt: str, model: str):
    """呼叫 Ollama 產生回應"""
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
        },
        timeout=600,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["response"]


def chat_with_model(model: str):
    """與單一模型互動"""
    print("=" * 60)
    print(f"🤖 使用模型：{model}")
    print("=" * 60)

    # 初始打招呼
    reply = llama_local("你好，請以繁體中文向我打招呼並簡單自我介紹。", model)
    print(f"{model}：\n{reply}\n")

    while True:
        user_input = input("你要繼續跟這個模型聊天嗎？(直接輸入內容 / n 跳到下一個模型)： ").strip()
        if user_input.lower() in ("n", "no", "next", ""):
            print(f"➡️  切換到下一個模型：{model}\n")
            break

        reply = llama_local(user_input, model)
        print(f"{model}：\n{reply}\n")


def main():
    models = get_available_models()

    if not models:
        print("⚠️  Ollama 伺服器目前沒有任何可用模型")
        return

    print("📦 偵測到以下可用模型：")
    for m in models:
        print(f" - {m}")
    print()

    for model in models:
        chat_with_model(model)

    print("✅ 所有模型測試完成")


if __name__ == "__main__":
    main()

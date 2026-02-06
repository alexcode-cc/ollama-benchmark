import requests
import time
import json
from datetime import datetime

OLLAMA_BASE_URL = "http://localhost:11434"


BENCHMARK_PROMPTS = [
    {
        "name": "greeting",
        "prompt": "你好，請以繁體中文簡單自我介紹。"
    },
    {
        "name": "reasoning",
        "prompt": "如果一個房間裡有 3 個人，每個人各養 2 隻貓，請問房間裡總共有幾隻腳？請說明理由。"
    },
    {
        "name": "coding",
        "prompt": "請用 Python 寫一個函式，判斷一個數字是否為質數。"
    },
    {
        "name": "expression",
        "prompt": "請用繁體中文解釋什麼是 RESTful API，對象是假設完全沒有技術背景的人。"
    },
]


def get_available_models():
    resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return [m["name"] for m in data.get("models", [])]


def ollama_generate(model: str, prompt: str):
    start = time.time()

    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
        },
        timeout=600,
    )

    latency = round(time.time() - start, 3)

    resp.raise_for_status()
    data = resp.json()
    text = data.get("response", "")

    return {
        "response": text,
        "latency": latency,
        "length": len(text),
    }


def run_benchmark_for_model(model: str):
    print("=" * 70)
    print(f"🏁 Benchmark 開始：{model}")
    print("=" * 70)

    results = []

    for item in BENCHMARK_PROMPTS:
        print(f"▶ 測試項目：{item['name']}")
        try:
            result = ollama_generate(model, item["prompt"])
            print(f"  ⏱ {result['latency']}s | 📏 {result['length']} chars")
            results.append({
                "test": item["name"],
                "prompt": item["prompt"],
                **result,
                "success": True,
            })
        except Exception as e:
            print(f"  ❌ 失敗：{e}")
            results.append({
                "test": item["name"],
                "prompt": item["prompt"],
                "response": "",
                "latency": None,
                "length": 0,
                "success": False,
                "error": str(e),
            })

    return results


def interactive_chat(model: str):
    print("\n💬 進入人工互動模式（Enter / n 結束）")
    while True:
        user_input = input("你：").strip()
        if user_input.lower() in ("n", "no", ""):
            break
        reply = ollama_generate(model, user_input)
        print(f"{model}：\n{reply['response']}\n")


def main():
    models = get_available_models()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    report = {
        "generated_at": timestamp,
        "models": {},
    }

    print("📦 偵測到模型：")
    for m in models:
        print(f" - {m}")
    print()

    for model in models:
        benchmark_results = run_benchmark_for_model(model)
        report["models"][model] = {
            "benchmark": benchmark_results
        }

        choice = input("\n是否要與此模型互動？(y/N)： ").strip().lower()
        if choice == "y":
            interactive_chat(model)

    output_file = f"ollama_benchmark_{timestamp}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Benchmark 完成，報告已輸出：{output_file}")


if __name__ == "__main__":
    main()

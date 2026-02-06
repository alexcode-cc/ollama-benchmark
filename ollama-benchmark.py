import html
import json
import time
from datetime import datetime
from pathlib import Path

import requests

OLLAMA_BASE_URL = "http://localhost:11434"
CHATS_DIR = Path(__file__).resolve().parent / "chats"

BENCHMARK_PROMPTS = [
    {
        "name": "greeting",
        "prompt": "你好，請以繁體中文簡單自我介紹。",
    },
    {
        "name": "reasoning",
        "prompt": "如果一個房間裡有 3 個人，每個人各養 2 隻貓，請問房間裡總共有幾隻腳？請說明理由。",
    },
    {
        "name": "coding",
        "prompt": "請用 Python 寫一個函式，判斷一個數字是否為質數。",
    },
    {
        "name": "expression",
        "prompt": "請用繁體中文解釋什麼是 RESTful API，對象是假設完全沒有技術背景的人。",
    },
]

# Chart.js 調色盤
CHART_COLORS = [
    "rgba(54, 162, 235, 0.8)",
    "rgba(255, 99, 132, 0.8)",
    "rgba(75, 192, 192, 0.8)",
    "rgba(255, 206, 86, 0.8)",
    "rgba(153, 102, 255, 0.8)",
    "rgba(255, 159, 64, 0.8)",
    "rgba(46, 204, 113, 0.8)",
    "rgba(231, 76, 60, 0.8)",
]

CHART_BORDERS = [c.replace("0.8", "1") for c in CHART_COLORS]

# ---------------------------------------------------------------------------
# Ollama API
# ---------------------------------------------------------------------------

def get_available_models() -> list[str]:
    resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return [m["name"] for m in data.get("models", [])]


def ollama_generate(model: str, prompt: str) -> dict:
    start = time.time()
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=600,
    )
    latency = round(time.time() - start, 3)
    resp.raise_for_status()
    text = resp.json().get("response", "")
    return {"response": text, "latency": latency, "length": len(text)}


# ---------------------------------------------------------------------------
# 評測執行
# ---------------------------------------------------------------------------

def run_benchmark_for_model(model: str) -> list[dict]:
    print("=" * 70)
    print(f"🏁 Benchmark 開始：{model}")
    print("=" * 70)

    results: list[dict] = []
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


def interactive_chat(model: str) -> None:
    print("\n💬 進入人工互動模式（Enter / n 結束）")
    while True:
        user_input = input("你：").strip()
        if user_input.lower() in ("n", "no", ""):
            break
        reply = ollama_generate(model, user_input)
        print(f"{model}：\n{reply['response']}\n")


# ---------------------------------------------------------------------------
# HTML 報告生成
# ---------------------------------------------------------------------------

def _build_html_report(report: dict) -> str:
    """根據評測報告 dict 產生自包含的 HTML 分析頁面（含 Chart.js 互動圖表）"""

    models = list(report["models"].keys())
    test_names = [p["name"] for p in BENCHMARK_PROMPTS]
    timestamp = report["generated_at"]

    # ---- 資料準備 ----
    # latency_data[test_name] = [model1_latency, model2_latency, ...]
    latency_data: dict[str, list[float | None]] = {t: [] for t in test_names}
    length_data: dict[str, list[int]] = {t: [] for t in test_names}

    for model in models:
        benchmarks = report["models"][model]["benchmark"]
        test_map = {b["test"]: b for b in benchmarks}
        for t in test_names:
            b = test_map.get(t, {})
            latency_data[t].append(b.get("latency"))
            length_data[t].append(b.get("length", 0))

    # 各模型平均延遲 & 總回應長度
    avg_latencies: list[float] = []
    total_lengths: list[int] = []
    for i, model in enumerate(models):
        lats = [latency_data[t][i] for t in test_names if latency_data[t][i] is not None]
        avg_latencies.append(round(sum(lats) / len(lats), 3) if lats else 0)
        total_lengths.append(sum(length_data[t][i] for t in test_names))

    # 簡短模型名稱（用於圖表標籤）
    short_names = [m.split(":")[0] if ":" in m else m for m in models]

    # 顏色
    colors = [CHART_COLORS[i % len(CHART_COLORS)] for i in range(len(models))]
    borders = [CHART_BORDERS[i % len(CHART_BORDERS)] for i in range(len(models))]

    # ---- 模型詳細回覆 HTML ----
    details_html = ""
    for model in models:
        benchmarks = report["models"][model]["benchmark"]
        details_html += f'<div class="model-detail"><h3>{html.escape(model)}</h3>'
        for b in benchmarks:
            status = "✅" if b.get("success") else "❌"
            lat = f'{b["latency"]}s' if b.get("latency") is not None else "N/A"
            details_html += f"""
            <div class="test-card">
              <div class="test-header">
                <span class="test-name">{status} {html.escape(b['test'])}</span>
                <span class="test-stats">⏱ {lat} | 📏 {b.get('length', 0)} chars</span>
              </div>
              <div class="prompt">💬 {html.escape(b['prompt'])}</div>
              <details><summary>展開回覆</summary>
                <pre class="response">{html.escape(b.get('response', '') or '(無回覆)')}</pre>
              </details>
            </div>"""
        details_html += "</div>"

    # ---- 摘要表格 ----
    summary_rows = ""
    for i, model in enumerate(models):
        benchmarks = report["models"][model]["benchmark"]
        success_count = sum(1 for b in benchmarks if b.get("success"))
        summary_rows += f"""
        <tr>
          <td>{html.escape(model)}</td>
          <td>{avg_latencies[i]}s</td>
          <td>{total_lengths[i]}</td>
          <td>{success_count}/{len(test_names)}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ollama Benchmark 分析報告 - {timestamp}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  :root {{
    --bg: #0f1117; --surface: #1a1d27; --border: #2a2d3a;
    --text: #e4e6eb; --muted: #8b8fa3; --accent: #3b82f6;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    background: var(--bg); color: var(--text); padding: 2rem; line-height: 1.6;
  }}
  h1 {{ text-align: center; margin-bottom: .3rem; font-size: 1.8rem; }}
  .subtitle {{ text-align: center; color: var(--muted); margin-bottom: 2rem; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 2rem; }}
  @media (max-width: 900px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  .card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 12px; padding: 1.5rem;
  }}
  .card h2 {{ font-size: 1.1rem; margin-bottom: 1rem; color: var(--accent); }}
  .card-full {{ grid-column: 1 / -1; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ padding: .6rem .8rem; text-align: left; border-bottom: 1px solid var(--border); }}
  th {{ color: var(--muted); font-weight: 600; font-size: .85rem; text-transform: uppercase; }}
  td {{ font-size: .95rem; }}
  canvas {{ width: 100% !important; max-height: 350px; }}
  .model-detail {{ margin-bottom: 2rem; }}
  .model-detail h3 {{
    font-size: 1.15rem; padding: .8rem 0; border-bottom: 2px solid var(--accent);
    margin-bottom: 1rem;
  }}
  .test-card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; padding: 1rem; margin-bottom: .8rem;
  }}
  .test-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: .5rem; }}
  .test-name {{ font-weight: 600; }}
  .test-stats {{ color: var(--muted); font-size: .85rem; }}
  .prompt {{ color: var(--muted); font-size: .9rem; margin-bottom: .5rem; }}
  details summary {{
    cursor: pointer; color: var(--accent); font-size: .9rem;
    padding: .3rem 0; user-select: none;
  }}
  .response {{
    white-space: pre-wrap; word-break: break-word; font-size: .85rem;
    background: var(--bg); padding: 1rem; border-radius: 8px;
    margin-top: .5rem; max-height: 400px; overflow-y: auto; line-height: 1.5;
  }}
</style>
</head>
<body>

<h1>Ollama Benchmark 分析報告</h1>
<p class="subtitle">測試時間：{timestamp}</p>

<!-- 摘要表格 -->
<div class="grid">
  <div class="card card-full">
    <h2>📋 模型總覽</h2>
    <table>
      <thead><tr><th>模型</th><th>平均延遲</th><th>總回應長度</th><th>成功率</th></tr></thead>
      <tbody>{summary_rows}</tbody>
    </table>
  </div>

  <!-- 平均延遲比較 -->
  <div class="card">
    <h2>⏱ 平均回應延遲（秒）</h2>
    <canvas id="chartAvgLatency"></canvas>
  </div>

  <!-- 總回應長度比較 -->
  <div class="card">
    <h2>📏 總回應長度（字元）</h2>
    <canvas id="chartTotalLength"></canvas>
  </div>

  <!-- 各測試項目延遲 -->
  <div class="card">
    <h2>⏱ 各測試項目延遲比較（秒）</h2>
    <canvas id="chartLatencyByTest"></canvas>
  </div>

  <!-- 各測試項目回應長度 -->
  <div class="card">
    <h2>📏 各測試項目回應長度比較（字元）</h2>
    <canvas id="chartLengthByTest"></canvas>
  </div>
</div>

<!-- 模型詳細回覆 -->
<div class="card card-full" style="margin-bottom:2rem;">
  <h2>💬 各模型詳細回覆</h2>
  {details_html}
</div>

<script>
const MODELS = {json.dumps(short_names, ensure_ascii=False)};
const MODELS_FULL = {json.dumps(models, ensure_ascii=False)};
const TESTS = {json.dumps(test_names, ensure_ascii=False)};
const COLORS = {json.dumps(colors)};
const BORDERS = {json.dumps(borders)};
const AVG_LATENCIES = {json.dumps(avg_latencies)};
const TOTAL_LENGTHS = {json.dumps(total_lengths)};
const LATENCY_DATA = {json.dumps(latency_data, ensure_ascii=False)};
const LENGTH_DATA = {json.dumps(length_data, ensure_ascii=False)};

Chart.defaults.color = '#8b8fa3';
Chart.defaults.borderColor = '#2a2d3a';

// 平均延遲
new Chart(document.getElementById('chartAvgLatency'), {{
  type: 'bar',
  data: {{
    labels: MODELS,
    datasets: [{{
      label: '平均延遲（秒）',
      data: AVG_LATENCIES,
      backgroundColor: COLORS,
      borderColor: BORDERS,
      borderWidth: 1
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ y: {{ beginAtZero: true, title: {{ display: true, text: '秒' }} }} }}
  }}
}});

// 總回應長度
new Chart(document.getElementById('chartTotalLength'), {{
  type: 'bar',
  data: {{
    labels: MODELS,
    datasets: [{{
      label: '總回應長度（字元）',
      data: TOTAL_LENGTHS,
      backgroundColor: COLORS,
      borderColor: BORDERS,
      borderWidth: 1
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ y: {{ beginAtZero: true, title: {{ display: true, text: '字元' }} }} }}
  }}
}});

// 各測試延遲（分組長條圖）
new Chart(document.getElementById('chartLatencyByTest'), {{
  type: 'bar',
  data: {{
    labels: TESTS,
    datasets: MODELS.map((m, i) => ({{
      label: m,
      data: TESTS.map(t => LATENCY_DATA[t][i] ?? 0),
      backgroundColor: COLORS[i],
      borderColor: BORDERS[i],
      borderWidth: 1
    }}))
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ position: 'bottom' }} }},
    scales: {{ y: {{ beginAtZero: true, title: {{ display: true, text: '秒' }} }} }}
  }}
}});

// 各測試回應長度
new Chart(document.getElementById('chartLengthByTest'), {{
  type: 'bar',
  data: {{
    labels: TESTS,
    datasets: MODELS.map((m, i) => ({{
      label: m,
      data: TESTS.map(t => LENGTH_DATA[t][i]),
      backgroundColor: COLORS[i],
      borderColor: BORDERS[i],
      borderWidth: 1
    }}))
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ position: 'bottom' }} }},
    scales: {{ y: {{ beginAtZero: true, title: {{ display: true, text: '字元' }} }} }}
  }}
}});
</script>

</body>
</html>"""


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    models = get_available_models()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    report: dict = {
        "generated_at": timestamp,
        "models": {},
    }

    print("📦 偵測到模型：")
    for m in models:
        print(f" - {m}")
    print()

    for model in models:
        benchmark_results = run_benchmark_for_model(model)
        report["models"][model] = {"benchmark": benchmark_results}

        choice = input("\n是否要與此模型互動？(y/N)： ").strip().lower()
        if choice == "y":
            interactive_chat(model)

    # 建立時間戳記目錄
    run_dir = CHATS_DIR / f"benchmark_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # 輸出 JSON 報告
    json_file = run_dir / "benchmark_report.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 輸出 HTML 分析報告（含圖表）
    html_file = run_dir / "benchmark_report.html"
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(_build_html_report(report))

    print(f"\n✅ Benchmark 完成！報告已輸出至：{run_dir}")
    print(f"   📄 JSON 報告：{json_file.name}")
    print(f"   📊 分析圖表：{html_file.name}")


if __name__ == "__main__":
    main()

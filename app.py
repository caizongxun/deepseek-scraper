import os
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from scraper import scrape_deepseek, filter_bmp
from market_fetcher import build_market_data

app = Flask(__name__, static_folder="frontend")
CORS(app)

SETTINGS_FILE = "settings.json"

# In-memory conversation history (session-based, lost on restart)
_history: list = []


def load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"email": "", "password": "", "headless": True, "chrome_profile": ""}


def save_settings(data: dict):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@app.route("/")
def index():
    return send_from_directory("frontend", "index.html")


@app.route("/api/settings", methods=["GET"])
def get_settings():
    s = load_settings()
    # Never expose password in plaintext response
    return jsonify({"email": s.get("email", ""),
                    "has_password": bool(s.get("password")),
                    "headless": s.get("headless", True),
                    "chrome_profile": s.get("chrome_profile", "")})


@app.route("/api/settings", methods=["POST"])
def post_settings():
    body = request.get_json(force=True)
    s = load_settings()
    if "email" in body:
        s["email"] = body["email"]
    if "password" in body and body["password"]:
        s["password"] = body["password"]
    if "headless" in body:
        s["headless"] = bool(body["headless"])
    if "chrome_profile" in body:
        s["chrome_profile"] = body["chrome_profile"]
    save_settings(s)
    return jsonify({"ok": True})


@app.route("/api/history", methods=["GET"])
def get_history():
    return jsonify(_history)


@app.route("/api/history", methods=["DELETE"])
def clear_history():
    _history.clear()
    return jsonify({"ok": True})


@app.route("/api/analyze", methods=["POST"])
def analyze():
    global _history
    body = request.get_json(force=True)
    market_data = body.get("market_data", {})
    custom_question = body.get("question", "")
    include_history = body.get("include_history", True)

    if not market_data:
        return jsonify({"error": "market_data is required"}), 400

    # Build prompt
    market_json = json.dumps(market_data, ensure_ascii=False, indent=2)
    history_block = ""
    if include_history and _history:
        last = _history[-3:]  # last 3 rounds as context
        lines = []
        for h in last:
            lines.append(f"[Previous Q]: {h['prompt'][:200]}")
            lines.append(f"[Previous A]: {h['response'][:300]}")
        history_block = "\n\n== Previous Analysis Context ==\n" + "\n".join(lines) + "\n\n"

    question = custom_question or "請根據以上資料分析目前市場整體狀態，給出：1) 短期趨勢判斷 2) 主要風險 3) 操作建議"

    prompt = (
        f"以下是目前市場即時資訊（JSON 格式）：\n\n"
        f"```json\n{market_json}\n```\n"
        f"{history_block}"
        f"\n問題：{question}\n"
        f"\n請用繁體中文回答，結構清晰，包含數據引用。"
    )

    s = load_settings()
    result = scrape_deepseek(
        prompt=prompt,
        email=s.get("email", ""),
        password=s.get("password", ""),
        headless=s.get("headless", True),
        user_data_dir=s.get("chrome_profile") or None
    )

    # Save to history
    _history.append({
        "timestamp": __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "prompt": question,
        "market_snapshot": {k: market_data.get(k) for k in ["prices", "fear_greed", "timestamp"] if k in market_data},
        "response": result
    })
    if len(_history) > 50:
        _history = _history[-50:]

    return jsonify({"result": result, "error": None})


@app.route("/api/fetch-market", methods=["GET"])
def fetch_market():
    data = build_market_data()
    return jsonify(data)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

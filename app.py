import os
import json
import traceback
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from scraper import scrape_deepseek, filter_bmp
from market_fetcher import build_market_data

app = Flask(__name__, static_folder="frontend")
CORS(app)

SETTINGS_FILE = "settings.json"
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
    return jsonify({
        "email": s.get("email", ""),
        "has_password": bool(s.get("password")),
        "headless": s.get("headless", True),
        "chrome_profile": s.get("chrome_profile", "")
    })


@app.route("/api/settings", methods=["POST"])
def post_settings():
    body = request.get_json(force=True)
    s = load_settings()
    if "email" in body:
        s["email"] = body["email"]
    if body.get("password"):
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
    try:
        body = request.get_json(force=True)
        market_data = body.get("market_data", {})
        custom_question = body.get("question", "")
        include_history = body.get("include_history", True)

        if not market_data:
            return jsonify({"error": "market_data is required"}), 400

        market_json = json.dumps(market_data, ensure_ascii=False, indent=2)
        history_block = ""
        if include_history and _history:
            last = _history[-3:]
            lines = []
            for h in last:
                lines.append(f"[Previous Q]: {h['prompt'][:200]}")
                lines.append(f"[Previous A]: {h['response'][:300]}")
            history_block = "\n\n== Previous Analysis Context ==\n" + "\n".join(lines) + "\n\n"

        question = custom_question or "\u8acb\u6839\u64da\u4ee5\u4e0a\u8cc7\u8a0a\u5206\u6790\u76ee\u524d\u5e02\u5834\u6574\u9ad4\u72c0\u614b\uff0c\u7d66\u51fa\uff1a1) \u77ed\u671f\u8da8\u52e2\u5224\u65b7 2) \u4e3b\u8981\u98a8\u96aa 3) \u64cd\u4f5c\u5efa\u8b70"

        prompt = (
            f"\u4ee5\u4e0b\u662f\u76ee\u524d\u5e02\u5834\u5373\u6642\u8cc7\u8a0a\uff08JSON \u683c\u5f0f\uff09\uff1a\n\n"
            f"```json\n{market_json}\n```\n"
            f"{history_block}"
            f"\n\u554f\u984c\uff1a{question}\n"
            f"\n\u8acb\u7528\u7e41\u9ad4\u4e2d\u6587\u56de\u7b54\uff0c\u7d50\u69cb\u6e05\u6670\uff0c\u5305\u542b\u6578\u64da\u5f15\u7528\u3002"
        )

        s = load_settings()
        result = scrape_deepseek(
            prompt=prompt,
            email=s.get("email", ""),
            password=s.get("password", ""),
            headless=s.get("headless", True),
            user_data_dir=s.get("chrome_profile") or None
        )

        _history.append({
            "timestamp": __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "prompt": question,
            "market_snapshot": {k: market_data.get(k) for k in ["prices", "fear_greed", "timestamp"] if k in market_data},
            "response": result
        })
        if len(_history) > 50:
            _history = _history[-50:]

        return jsonify({"result": result, "error": None})

    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        return jsonify({"error": str(e), "traceback": tb}), 500


@app.route("/api/fetch-market", methods=["GET"])
def fetch_market():
    try:
        data = build_market_data()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

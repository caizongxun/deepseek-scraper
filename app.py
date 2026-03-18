from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import requests as req_lib
from scraper import scrape_deepseek

app = Flask(__name__, static_folder="frontend")
CORS(app)

# Optional: path to your Chrome profile already logged into DeepSeek
# Set via env var: CHROME_PROFILE=/home/you/.config/google-chrome/Profile
CHROME_PROFILE = os.environ.get("CHROME_PROFILE", None)
HEADLESS = os.environ.get("HEADLESS", "true").lower() == "true"


@app.route("/")
def index():
    return send_from_directory("frontend", "index.html")


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """
    Body: { "market_data": { ... } }
    Returns: { "result": "...", "error": null }
    """
    body = request.get_json(force=True)
    market_data = body.get("market_data", {})
    if not market_data:
        return jsonify({"error": "market_data is required"}), 400

    result = scrape_deepseek(market_data, headless=HEADLESS, user_data_dir=CHROME_PROFILE)
    return jsonify({"result": result, "error": None})


@app.route("/api/fetch-market", methods=["GET"])
def fetch_market():
    """
    Auto-fetch sample market data from public free APIs:
    - CoinGecko: BTC/ETH price
    - Fear & Greed index
    Returns combined JSON for user to preview / edit before sending to DeepSeek.
    """
    data = {}

    try:
        r = req_lib.get(
            "https://api.coingecko.com/api/v3/simple/price"
            "?ids=bitcoin,ethereum,solana&vs_currencies=usd&include_24hr_change=true",
            timeout=8
        )
        data["prices"] = r.json()
    except Exception as e:
        data["prices_error"] = str(e)

    try:
        r2 = req_lib.get("https://api.alternative.me/fng/?limit=1", timeout=8)
        fng = r2.json()
        data["fear_greed"] = fng.get("data", [{}])[0]
    except Exception as e:
        data["fear_greed_error"] = str(e)

    return jsonify(data)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

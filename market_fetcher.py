import requests
import time
from datetime import datetime, timezone

HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch_coingecko() -> dict:
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price"
            "?ids=bitcoin,ethereum,solana,ripple,dogecoin"
            "&vs_currencies=usd"
            "&include_24hr_change=true"
            "&include_24hr_vol=true"
            "&include_market_cap=true",
            headers=HEADERS, timeout=8
        )
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def fetch_fear_greed() -> dict:
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=7", timeout=6)
        data = r.json().get("data", [])
        return {
            "current": data[0] if data else {},
            "history_7d": data
        }
    except Exception as e:
        return {"error": str(e)}


def fetch_global_market() -> dict:
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/global",
            headers=HEADERS, timeout=8
        )
        d = r.json().get("data", {})
        return {
            "total_market_cap_usd": d.get("total_market_cap", {}).get("usd"),
            "total_volume_24h_usd": d.get("total_volume", {}).get("usd"),
            "btc_dominance_pct": round(d.get("market_cap_percentage", {}).get("btc", 0), 2),
            "eth_dominance_pct": round(d.get("market_cap_percentage", {}).get("eth", 0), 2),
            "active_cryptocurrencies": d.get("active_cryptocurrencies"),
            "market_cap_change_24h_pct": round(d.get("market_cap_change_percentage_24h_usd", 0), 2),
        }
    except Exception as e:
        return {"error": str(e)}


def fetch_trending() -> list:
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/search/trending",
            headers=HEADERS, timeout=8
        )
        coins = r.json().get("coins", [])[:5]
        return [{"name": c["item"]["name"], "symbol": c["item"]["symbol"],
                 "rank": c["item"]["market_cap_rank"]} for c in coins]
    except Exception as e:
        return [{"error": str(e)}]


def fetch_crypto_news() -> list:
    """Fetch from CoinDesk RSS and CryptoSlate RSS."""
    import xml.etree.ElementTree as ET
    feeds = [
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "https://cryptoslate.com/feed/",
    ]
    news = []
    for url in feeds:
        try:
            r = requests.get(url, headers=HEADERS, timeout=8)
            root = ET.fromstring(r.content)
            for item in root.iter("item"):
                title = item.findtext("title", "").strip()
                pub = item.findtext("pubDate", "").strip()
                if title:
                    news.append({"title": title, "published": pub, "source": url.split("/")[2]})
                if len(news) >= 10:
                    break
        except Exception:
            pass
        if len(news) >= 10:
            break
    return news[:10]


def build_market_data() -> dict:
    prices = fetch_coingecko()
    fg = fetch_fear_greed()
    global_info = fetch_global_market()
    trending = fetch_trending()
    news = fetch_crypto_news()

    btc = prices.get("bitcoin", {})
    eth = prices.get("ethereum", {})
    sol = prices.get("solana", {})

    return {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "prices": {
            "BTC": {
                "usd": btc.get("usd"),
                "change_24h_pct": round(btc.get("usd_24h_change", 0), 2),
                "volume_24h_usd": btc.get("usd_24h_vol"),
                "market_cap_usd": btc.get("usd_market_cap"),
            },
            "ETH": {
                "usd": eth.get("usd"),
                "change_24h_pct": round(eth.get("usd_24h_change", 0), 2),
                "volume_24h_usd": eth.get("usd_24h_vol"),
                "market_cap_usd": eth.get("usd_market_cap"),
            },
            "SOL": {
                "usd": sol.get("usd"),
                "change_24h_pct": round(sol.get("usd_24h_change", 0), 2),
            },
        },
        "fear_greed": fg,
        "global_market": global_info,
        "trending_coins": trending,
        "latest_news": news,
        "analysis_request": "請根據以上資料分析目前市場整體狀態，給出：1) 短期趨勢判斷 2) 主要風險 3) 操作建議",
    }

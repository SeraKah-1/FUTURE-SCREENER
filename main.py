import requests
import pandas as pd
import config
from screener_engine import Screener

def send_telegram(msg):
    if not config.TELEGRAM_TOKEN: return
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try: requests.post(url, json=payload)
    except: pass

def main():
    print("🚀 Starting 1H/4H Trend Screener...")
    bot = Screener()
    results = bot.run_scan()
    
    # Header Pesan
    msg = f"📡 **SIGNAL RADAR ({config.TF_TRADE.upper()})**\n"
    msg += f"🕒 {pd.Timestamp.now().strftime('%H:%M UTC')}\n"
    msg += "➖➖➖➖➖➖➖➖➖➖\n"
    
    if not results:
        msg += "💤 **No High Probability Setups**\n"
        msg += "Market is sideways or messy.\n"
        print("⚠️ No results found.")
    else:
        # Batasi cuma kirim Top 5 biar gak spam
        top_results = results[:5] 
        for r in top_results:
            icon = "🔥" if r['score'] >= 90 else "⚡"
            msg += f"{icon} **{r['symbol']}** [{r['side']}]\n"
            msg += f"🏆 Score: **{r['score']}/100**\n"
            msg += f"💰 Price: `{r['price']}`\n"
            msg += f"📊 Candle Chg: {r['change_1h']}%\n"
            msg += f"🌊 Vol Ratio: {r['vol_stat']}x\n"
            msg += "➖➖➖➖➖➖➖➖➖➖\n"
    
    send_telegram(msg)
    print("✅ Done.")

if __name__ == "__main__":
    main()

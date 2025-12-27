import requests
import pandas as pd
import config
from screener_engine import Screener

def send_telegram(msg):
    if not config.TELEGRAM_TOKEN:
        print("⚠️ Token Telegram Kosong!")
        return
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    requests.post(url, json=payload)

def main():
    print("🚀 Starting GitHub Action Screener...")
    
    bot = Screener()
    results = bot.run_scan()
    
    if not results:
        print("💤 Tidak ada setup valid.")
        return

    # Format Pesan
    msg = f"🔥 **TIER LIST SETUP ({pd.Timestamp.now().strftime('%H:%M UTC')})** 🔥\n"
    msg += "Exchange: Gate.io (US IP Safe)\n"
    
    current_tier = ""
    for r in results:
        if r['tier'] != current_tier:
            current_tier = r['tier']
            icon = "🏆" if current_tier == "S" else "🥇" if current_tier == "A" else "🥈"
            msg += f"\n{icon} **TIER {current_tier}**\n" + "-"*15 + "\n"
        
        msg += f"**{r['symbol']}** {r['side']} ({r['score']})\n"
        msg += f"Price: {r['price']} | Vol: {r['vol']:.1f}x\n"
        msg += f"🛡️ SL: {r['sl']:.4f}\n"

    print(msg)
    send_telegram(msg)
    print("✅ Done.")

if __name__ == "__main__":
    main()

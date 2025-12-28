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
    except Exception as e: print(f"Tele Error: {e}")

def main():
    print("🚀 Starting Smart Flow Screener...")
    
    bot = Screener()
    results = bot.run_scan()
    
    # Header Laporan
    msg = f"⚡ **TRADE SIGNAL ({pd.Timestamp.now().strftime('%H:%M UTC')})** ⚡\n"
    msg += f"Gate.io | Threshold: {config.MIN_SCORE}+\n"
    msg += "-"*20 + "\n"
    
    if not results:
        print("💤 Market Sepi. Kirim laporan status saja.")
        msg += "💤 **No High Quality Setup**\n"
        msg += "Analisa: Market sideway atau volume rendah.\n"
        msg += "Bot tetap memantau... 👁️"
    else:
        top_picks = results[:10] # Ambil max 10 sinyal terbaik aja biar gak spam
        for r in top_picks:
            # Icon Setup
            rank = "🔥" if r['score'] >= 80 else "✨" if r['score'] >= 65 else "⚠️"
            
            msg += f"{rank} **{r['symbol']}** {r['side']}\n"
            msg += f"   🎯 Score: **{r['score']}/100**\n"
            msg += f"   💰 Price: {r['price']}\n"
            msg += f"   📊 Vol: {r['vol']:.1f}x\n"
            msg += f"   🛡️ SL: `{r['sl']:.4f}`\n\n"
            
        msg += "💡 *Score > 80 = Super Strong Setup*"
    
    print("✅ Mengirim ke Telegram...")
    print(msg) # Print di log juga
    send_telegram(msg)
    print("🏁 Done.")

if __name__ == "__main__":
    main()

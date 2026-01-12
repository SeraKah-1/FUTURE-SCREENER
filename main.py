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
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"⚠️ Telegram Error: {e}")

def main():
    print("🚀 Starting PRAGMATIC RADAR (Volume & Volatility)...")
    
    bot = Screener()
    results = bot.run_scan()
    
    # --- HEADER PESAN ---
    timestamp = pd.Timestamp.now().strftime('%H:%M UTC')
    msg = f"📡 **FUTURES RADAR ALERT ({timestamp})**\n"
    msg += f"Focus: Volume Spike & Momentum\n"
    msg += "-"*25 + "\n"
    
    if not results:
        print("💤 No anomaly detected.")
        return # Opsional: Jangan kirim pesan kalau kosong biar gak spam "Zonk"

    # Batasi agar pesan tidak terlalu panjang (Telegram limit)
    # Ambil Top 15 Sinyal Terbaik saja
    top_results = results[:15]

    for r in top_results:
        # Tentukan Icon Header berdasarkan Tier
        if "KING" in r['tier']: icon_head = "🚨👑"
        elif "HOT" in r['tier']: icon_head = "🔥"
        else: icon_head = "⚡"
        
        # Format Angka
        vol_val = f"{r['rvol']:.1f}x"
        chg_val = f"{r['chg']:+.2f}%"
        
        msg += f"{icon_head} **{r['symbol']}** {r['side']}\n"
        msg += f"   📊 Vol: `{vol_val}` (Spike) | 📉 Chg: `{chg_val}`\n"
        msg += f"   🏷️ Type: {r['tier']}\n"
        msg += f"   🌊 Trend: {r['trend']}\n"
        msg += f"   💰 Price: {r['price']}\n"
        msg += f"   🏆 Score: **{r['score']}**\n\n"
    
    msg += "-"*25 + "\n"
    msg += "⚠️ *DYOR. High Volatility Alert.*"
    
    # Kirim ke Telegram
    print(msg)
    send_telegram(msg)

if __name__ == "__main__":
    main()

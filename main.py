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
    try:
        requests.post(url, json=payload)
        print("✅ Notifikasi Terkirim ke Telegram.")
    except Exception as e:
        print(f"❌ Gagal kirim Telegram: {e}")

def main():
    print("🚀 Starting Screener (Debug Mode)...")
    
    bot = Screener()
    # Debug: Print jumlah target
    targets = bot.get_top_pairs()
    print(f"📋 Target Scan: {len(targets)} Pairs")
    
    results = []
    # Kita scan loop biasa dulu (tanpa thread) biar kelihatan log errornya satu2
    print("🕵️‍♂️ Mulai Analisa Detail...")
    for sym in targets:
        res = bot.analyze_pair(sym)
        if res:
            print(f"✅ FOUND: {sym} -> Score {res['score']}")
            results.append(res)
        else:
            # Ini biar kita tau dia jalan tapi nolak
            print(f"❌ SKIP: {sym} (Tidak memenuhi kriteria)")
    
    # Format Pesan Telegram
    msg = f"🔥 **LAPORAN SCANNER ({pd.Timestamp.now().strftime('%H:%M UTC')})** 🔥\n"
    
    if not results:
        msg += "\n💤 **Market Sedang Tidur / Sideways**\n"
        msg += "Tidak ada setup Tier A/B yang valid saat ini.\n"
        msg += f"(Scanned {len(targets)} pairs on Gate.io)"
        print("⚠️ Tidak ada setup, tapi tetap kirim laporan...")
    else:
        results.sort(key=lambda x: -x['score'])
        for r in results:
            msg += f"\n**{r['symbol']}** [{r['side']}]\n"
            msg += f"📊 Score: {r['score']} (Tier {r['tier']})\n"
            msg += f"💰 Price: {r['price']}\n"
    
    # KIRIM LAPORAN (Mau ada hasil atau tidak)
    send_telegram(msg)
    print("🏁 Selesai.")

if __name__ == "__main__":
    main()

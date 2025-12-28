import requests
import pandas as pd
import config
from screener_engine import Screener

def send_telegram(msg):
    """Mengirim pesan ke Telegram Bot"""
    if not config.TELEGRAM_TOKEN:
        print("⚠️ Token Telegram Kosong! Cek Config.")
        return
    
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            print(f"⚠️ Gagal kirim Telegram: {response.text}")
    except Exception as e:
        print(f"⚠️ Error Connection Telegram: {e}")

def main():
    print("🚀 Starting SWING MASTER Screener (V6.0)...")
    print("   • Strategy: CMF + ADX + Vol 21 + RSI 21")
    
    bot = Screener()
    results = bot.run_scan()
    
    # --- HEADER LAPORAN ---
    timestamp = pd.Timestamp.now().strftime('%H:%M UTC')
    msg = f"🏛️ **SWING SIGNAL ({timestamp})** 🏛️\n"
    msg += f"Strategy: Big Trend Hunter\n"
    msg += "-"*25 + "\n"
    
    if not results:
        # Pesan jika tidak ada sinyal (Market Jelek)
        print("💤 Market Sideways/Weak Trend (No Results).")
        msg += "💤 **No Premium Setups Found**\n\n"
        msg += "🔍 **Diagnosa Market:**\n"
        msg += "• Trend Strength (ADX) lemah (<20).\n"
        msg += "• Arus Uang (CMF) tidak valid.\n"
        msg += "• Bot menunggu momentum valid..."
    else:
        # Ambil Top 10 Sinyal Terbaik
        top_picks = results[:10]
        
        for r in top_picks:
            # Tentukan Ikon berdasarkan Score
            icon = "👑" if r['score'] >= 80 else "🔥" if r['score'] >= 60 else "✅"
            
            # Format Angka CMF (Positif hijau, Negatif merah secara implisit)
            cmf_val = f"{r['cmf']:.3f}"
            adx_val = f"{r['adx']:.1f}"
            
            # Setup Pesan per Koin
            msg += f"{icon} **{r['symbol']}** {r['side']}\n"
            msg += f"   🏆 Score: **{r['score']}**\n"
            msg += f"   🌊 CMF: `{cmf_val}` (Money Flow)\n"
            msg += f"   📈 ADX: `{adx_val}` (Trend Power)\n"
            msg += f"   💰 Price: {r['price']}\n"
            msg += f"   🛡️ SL: `{r['sl']:.4f}`\n\n"
            
        # Legend / Keterangan Kaki
        msg += "-"*25 + "\n"
        msg += "💡 *Panduan Indikator:*\n"
        msg += "• **ADX > 25**: Trend Sangat Kuat.\n"
        msg += "• **CMF (+)**: Akumulasi (Bandar Beli).\n"
        msg += "• **CMF (-)**: Distribusi (Bandar Jual)."
    
    # --- KIRIM DATA ---
    print("\n" + msg) # Print di Console Log GitHub
    send_telegram(msg) # Kirim ke HP
    print("✅ Job Done.")

if __name__ == "__main__":
    main()

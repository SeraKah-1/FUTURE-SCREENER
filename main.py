import requests
import pandas as pd
import config
from screener_engine import Screener

def send_telegram(msg):
    """Mengirim pesan ke Telegram Bot dengan error handling"""
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
    print("🚀 Starting HYBRID SWING Screener (V6.2)...")
    print("   • Logic: Daily DMI/CMF + 15m EMA Trend")
    
    bot = Screener()
    results = bot.run_scan()
    
    # --- HEADER LAPORAN ---
    timestamp = pd.Timestamp.now().strftime('%H:%M UTC')
    msg = f"🏛️ **HYBRID SWING SIGNAL ({timestamp})** 🏛️\n"
    msg += f"Strategy: Daily Trend + 15m Entry\n"
    msg += "-"*25 + "\n"
    
    if not results:
        # Pesan jika tidak ada sinyal (Market Jelek)
        print("💤 Market Sideways/Choppy. Tidak ada setup valid.")
        msg += "💤 **No Premium Setups Found**\n\n"
        msg += "🔍 **Diagnosa Market:**\n"
        msg += "• Trend Strength (ADX) lemah (<20).\n"
        msg += "• Atau Arah 15m berlawanan dengan Daily.\n"
        msg += "• Bot mode: *Preservation (Wait & See)*"
    else:
        # Ambil Top 10 Sinyal Terbaik (Sortir by Score sudah dilakukan di engine)
        top_picks = results[:10]
        
        for r in top_picks:
            # 1. Tentukan Ikon berdasarkan Score
            if r['score'] >= 80:
                icon = "👑" # Setup Raja (Sangat Bagus)
            elif r['score'] >= 65:
                icon = "🔥" # Setup Panas
            else:
                icon = "✅" # Setup Valid Biasa
            
            # 2. Format Angka Indikator
            cmf_val = f"{r['cmf']:.3f}"
            adx_val = f"{r['adx']:.1f}"
            
            # 3. Format Persentase Perubahan (+/- otomatis)
            # Contoh: +5.20% atau -1.20%
            chg_val = f"{r['chg']:+.2f}%"
            
            # 4. Format Volume Ratio
            vol_val = f"{r['vol_ratio']:.1f}x"
            
            # 5. Susun Pesan per Koin
            msg += f"{icon} **{r['symbol']}** {r['side']}\n"
            msg += f"   📊 Vol: `{vol_val}` | 📉 Chg: `{chg_val}`\n"
            msg += f"   🌊 CMF: `{cmf_val}` | 📈 ADX: `{adx_val}`\n"
            msg += f"   💰 Price: {r['price']}\n"
            msg += f"   🛡️ SL: `{r['sl']:.4f}`\n"
            msg += f"   🏆 Score: **{r['score']}**\n\n"
            
        # Legend / Keterangan Kaki
        msg += "-"*25 + "\n"
        msg += "💡 *Panduan Indikator:*\n"
        msg += "• **Vol > 1.5x**: Ledakan Volume Daily.\n"
        msg += "• **ADX > 25**: Trend Sangat Kuat.\n"
        msg += "• **CMF (+)**: Akumulasi (Uang Masuk)."
    
    # --- EKSEKUSI ---
    print("\n" + msg) # Print di Console Log GitHub agar tersimpan di history
    send_telegram(msg) # Kirim notifikasi ke HP
    print("✅ Job Done.")

if __name__ == "__main__":
    main()

import ccxt
import pandas as pd
import requests
import os
import time

# --- KONFIGURASI ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# --- PARAMETER ---
LIMIT_CANDLE = 50 
MIN_VOL_24H = 500_000 # Turunkan ke $500k biar koin receh masuk
TIMEFRAME = '1h'

print("🔌 Init Data Feed (KuCoin Futures)...")
exchange = ccxt.kucoinfutures({
    'enableRateLimit': True,
    'options': {'defaultType': 'future'}
})

def send_telegram(message):
    if not TELEGRAM_TOKEN: 
        print("⚠️ Token Telegram Kosong!")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID, 
        "text": message, 
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try: requests.post(url, json=payload)
    except Exception as e: print(f"Telegram Error: {e}")

def get_market_data(symbol):
    # 1. AMBIL OHLCV (HARGA & VOLUME) - INI WAJIB
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=LIMIT_CANDLE)
        df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    except Exception as e:
        # Jika ambil candle gagal, print errornya di log biar ketahuan
        print(f"   ❌ Error Candle {symbol}: {e}")
        return None, 0

    # 2. AMBIL OPEN INTEREST (OPSIONAL - JANGAN BIKIN ERROR)
    oi_chg = 0
    try:
        # Kita coba ambil Current OI saja (lebih stabil daripada history)
        oi_data = exchange.fetch_open_interest(symbol)
        curr_oi = float(oi_data['openInterest'])
        # Karena tidak ada history, kita set 0 dulu atau logic dummy
        # Agar script tidak crash
        oi_chg = 0 
    except:
        oi_chg = 0 # Kalau gagal, anggap 0% change (Netral)

    return df, oi_chg

def determine_trend(row):
    price = row['close']
    ema21 = row['EMA_21']
    # Simple Trend Logic
    if price > ema21: return "🟢UP"
    else: return "🔴DOWN"

def run_screener():
    print("🔍 Scanning Market...")
    try:
        tickers = exchange.fetch_tickers()
    except Exception as e:
        send_telegram(f"❌ API Error Fatal: {e}")
        return

    targets = []
    for s, d in tickers.items():
        # Filter koin USDT Perpetual
        if '/USDT:USDT' in s and d.get('quoteVolume', 0) > MIN_VOL_24H:
            targets.append(s)
            
    # Ambil Top 40 biar cepat
    targets_sorted = sorted(targets, key=lambda x: tickers[x]['quoteVolume'], reverse=True)
    limit_scan = targets_sorted[:40]
    
    print(f"✅ Scanning Top {len(limit_scan)} Pairs...")
    candidates = []

    for i, symbol in enumerate(limit_scan):
        clean_name = symbol.split(':')[0]
        print(f"\rProcessing {i+1}/{len(limit_scan)}: {clean_name}", end="")
        
        # PANGGIL FUNGSI DATA
        df, oi_chg = get_market_data(symbol)
        
        # JIKA DF NONE, LANJUT KE KOIN BERIKUTNYA
        if df is None or df.empty: continue
        
        # INDIKATOR TEKNIKAL
        df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['Vol_SMA'] = df['volume'].rolling(window=20).mean()
        
        curr = df.iloc[-1]
        vol_ratio = curr['volume'] / curr['Vol_SMA'] if curr['Vol_SMA'] > 0 else 0.1
        trend_status = determine_trend(curr)
        
        # SKORING SEDERHANA
        # Skor berbasis Volume Ratio saja (karena OI sering error)
        score = vol_ratio * 10 
        
        binance_ticker = clean_name.replace('/', '')
        link = f"https://www.binance.com/en/futures/{binance_ticker}"
        
        candidates.append({
            'ticker': clean_name,
            'trend': trend_status,
            'vol_x': vol_ratio,
            'price': curr['close'],
            'score': score,
            'link': link
        })

    # --- REPORTING ---
    if candidates:
        # Urutkan dari volume tertinggi
        candidates.sort(key=lambda x: x['vol_x'], reverse=True)
        top_5 = candidates[:5]
        
        msg = f"📊 *MARKET VOLATILITY (Top 5)*\n_Data Source: KuCoin (Mirror)_\n"
        
        for s in top_5:
            icon = "🔥" if s['vol_x'] > 2.0 else "👀"
            msg += (f"\n{icon} *[{s['ticker']}]({s['link']})* ({s['trend']})"
                    f"\n  └ Vol Spike: {s['vol_x']:.1f}x Avg\n")
        
        send_telegram(msg)
        print("\n\n✅ Report Terkirim!")
    else:
        # JIKA MASIH KOSONG, KIRIM LOG KE TELEGRAM
        print("\n\n❌ Data kosong.")
        send_telegram("❌ Report Kosong: Script berjalan tapi gagal mengambil Candle Data untuk semua koin.")

if __name__ == "__main__":
    run_screener()

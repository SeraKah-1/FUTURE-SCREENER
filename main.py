import ccxt
import pandas as pd
import requests
import os

# --- KONFIGURASI ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# --- PARAMETER SENSITIF (MODE LONGGAR) ---
MIN_VOL_24H = 1_000_000    # Turun ke $1 Juta
TIMEFRAME = '1h'
OI_THRESHOLD = 1.0         # Turun ke 1% (Sangat sensitif)
FUNDING_MAX = 0.0005       # Sedikit lebih longgar

print("🔌 Init Data Feed (KuCoin Futures)...")
exchange = ccxt.kucoinfutures({
    'enableRateLimit': True,
    'options': {'defaultType': 'future'}
})

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ TOKEN/CHAT_ID KOSONG! Cek GitHub Secrets.")
        return

    print(f"📨 Mengirim pesan ke Telegram...") # Debug log
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID, 
        "text": message, 
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try: 
        r = requests.post(url, json=payload)
        print(f"Status Kirim: {r.status_code}") # Cek status 200 = OK
    except Exception as e: 
        print(f"⚠️ Telegram Error: {e}")

def get_market_data(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=60)
        df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        funding = exchange.fetch_funding_rate(symbol)
        
        try:
            oi_hist = exchange.fetch_open_interest_history(symbol, timeframe=TIMEFRAME, limit=2)
        except:
            curr_oi = exchange.fetch_open_interest(symbol)
            oi_hist = [{'openInterest': curr_oi['openInterest']}] * 2
            
        return df, oi_hist, funding
    except:
        return None, None, None

def run_screener():
    print("🔍 Scanning Market...")
    try:
        tickers = exchange.fetch_tickers()
    except Exception as e:
        print(f"❌ Error fetching tickers: {e}")
        # JIKA ERROR API, LAPOR TELEGRAM
        send_telegram(f"❌ Script Error: Gagal ambil tickers.\n{e}")
        return

    targets = []
    for s, d in tickers.items():
        if '/USDT:USDT' in s:
            if d.get('quoteVolume', 0) > MIN_VOL_24H:
                targets.append(s)
            
    print(f"✅ Filtered {len(targets)} active pairs. Analyzing...")
    
    signals = []
    targets_sorted = sorted(targets, key=lambda x: tickers[x]['quoteVolume'], reverse=True)
    limit_scan = targets_sorted[:80]

    for i, symbol in enumerate(limit_scan):
        clean_name = symbol.split(':')[0]
        print(f"\rProcessing {i+1}/{len(limit_scan)}: {clean_name}", end="")
        
        df, oi_hist, funding = get_market_data(symbol)
        if df is None or df.empty: continue
        
        # INDIKATOR
        df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['EMA_55'] = df['close'].ewm(span=55, adjust=False).mean()
        df['Vol_SMA'] = df['volume'].rolling(window=20).mean()
        curr = df.iloc[-1]
        
        try:
            oi_now = float(oi_hist[-1]['openInterest'])
            oi_prev = float(oi_hist[-2]['openInterest'])
            oi_chg = ((oi_now - oi_prev) / oi_prev) * 100 if oi_prev > 0 else 0
        except: oi_chg = 0
            
        vol_ratio = curr['volume'] / curr['Vol_SMA'] if curr['Vol_SMA'] > 0 else 0
        
        # --- LOGIKA SANGAT LONGGAR (DEBUG MODE) ---
        # Hanya cek apakah harga diatas EMA 55 (Trend medium)
        trend_ok = (curr['close'] > curr['EMA_55']) 
        
        # Momentum minimalis
        momentum   = (vol_ratio > 1.2) or (oi_chg > 1.0)
        
        if trend_ok and momentum:
            score = 1 # Start score 1
            tags = []
            
            if oi_chg > 3.0: score += 2; tags.append("Inflow")
            if vol_ratio > 2.0: score += 2; tags.append("Vol")
            if curr['close'] > df['EMA_21'].iloc[-1]: score += 1; tags.append("Uptrend")
            
            binance_ticker = clean_name.replace('/', '')
            link = f"https://www.binance.com/en/futures/{binance_ticker}"
            
            signals.append({
                'ticker': clean_name,
                'price': curr['close'],
                'oi_chg': oi_chg,
                'score': score,
                'tags': ", ".join(tags),
                'link': link
            })

    # --- REPORTING (DIPAKSA KIRIM) ---
    if signals:
        signals.sort(key=lambda x: x['score'], reverse=True)
        msg = f"🤖 *DEBUG RESULT ({len(limit_scan)} Scanned)*\n"
        
        for s in signals[:6]: 
            msg += (f"\n💎 *[{s['ticker']}]({s['link']})* (Sc: {s['score']})"
                    f"\n  Wait... OI: {s['oi_chg']:+.2f}% | Tags: {s['tags']}\n")
        
        send_telegram(msg)
        print("\n\n✅ Sinyal dikirim.")
    else:
        # INI YANG PENTING: JIKA KOSONG TETAP LAPOR
        print("\n\n💤 Kosong.")
        send_telegram(f"🤖 *Laporan Status*\nScan {len(limit_scan)} koin selesai.\nTidak ada setup yang lolos filter (Market Sideways).")

if __name__ == "__main__":
    # Test kirim pesan saat mulai (Opsional, hapus kalau berisik)
    # send_telegram("🚀 Screener Mulai Berjalan...") 
    run_screener()

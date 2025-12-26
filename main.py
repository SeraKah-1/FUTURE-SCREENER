import ccxt
import pandas as pd
import requests
import os

# --- KONFIGURASI ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# --- PARAMETER SENSITIF ---
# Volume $2 Juta cukup untuk menyaring koin mati, tapi menangkap Mid-Cap
MIN_VOL_24H = 2_000_000 
TIMEFRAME = '1h'
OI_THRESHOLD = 3.0         # Alert jika OI naik > 3%

# --- KONEKSI DATA (MIRROR: KUCOIN) ---
# Menggunakan KuCoin karena tidak memblokir IP GitHub Actions
print("🔌 Init Data Feed (KuCoin Futures)...")
exchange = ccxt.kucoinfutures({
    'enableRateLimit': True,
    'options': {'defaultType': 'future'}
})

def send_telegram(message):
    if not TELEGRAM_TOKEN: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID, 
        "text": message, 
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    requests.post(url, json=payload)

def get_market_data(symbol):
    try:
        # 1. Ambil Candle (OHLCV)
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=60)
        df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        
        # 2. Ambil Funding
        funding = exchange.fetch_funding_rate(symbol)
        
        # 3. Ambil OI (Data OI KuCoin kadang terbatas history-nya)
        try:
            oi_hist = exchange.fetch_open_interest_history(symbol, timeframe=TIMEFRAME, limit=2)
        except:
            # Fallback jika history gagal, pakai data realtime dummy
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
        return

    # FILTERING AWAL
    targets = []
    for s, d in tickers.items():
        # Format KuCoin: 'BTC/USDT:USDT' -> Kita cari yang USDT Perpetual
        if '/USDT:USDT' in s:
            vol = d.get('quoteVolume', 0)
            if vol > MIN_VOL_24H:
                targets.append(s)
            
    print(f"✅ Filtered {len(targets)} active pairs. Analyzing...")
    
    signals = []
    
    # Sortir berdasarkan volume agar yang diproses duluan yang likuid
    targets_sorted = sorted(targets, key=lambda x: tickers[x]['quoteVolume'], reverse=True)
    
    # Batasi scan 80 koin teratas agar tidak timeout di GitHub (Cukup cover market)
    limit_scan = targets_sorted[:80]

    for i, symbol in enumerate(limit_scan):
        clean_name = symbol.split(':')[0] # BTC/USDT
        print(f"\rProcessing {i+1}/{len(limit_scan)}: {clean_name}", end="")
        
        df, oi_hist, funding = get_market_data(symbol)
        if df is None or df.empty: continue
        
        # --- TEKNIKAL INDIKATOR ---
        df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['EMA_55'] = df['close'].ewm(span=55, adjust=False).mean()
        df['Vol_SMA'] = df['volume'].rolling(window=20).mean()
        
        curr = df.iloc[-1]
        
        # --- METRIK MOMENTUM ---
        # OI Change
        try:
            oi_now = float(oi_hist[-1]['openInterest'])
            oi_prev = float(oi_hist[-2]['openInterest'])
            if oi_prev > 0:
                oi_chg = ((oi_now - oi_prev) / oi_prev) * 100
            else:
                oi_chg = 0
        except:
            oi_chg = 0
            
        # Vol Ratio
        vol_ratio = curr['volume'] / curr['Vol_SMA'] if curr['Vol_SMA'] > 0 else 0
        
        # Funding Check
        fr = float(funding['fundingRate']) if funding else 0
        
        # --- LOGIKA OMB (STRATEGI) ---
        trend_bull = (curr['close'] > curr['EMA_21']) and (curr['EMA_21'] > curr['EMA_55'])
        # Kita melonggarkan filter momentum agar sinyal masuk dulu
        momentum   = (vol_ratio > 1.8) or (oi_chg > 2.0)
        
        if trend_bull and momentum:
            score = 0
            tags = []
            
            if oi_chg > 5.0: score += 3; tags.append("💰BIG_INFLOW")
            elif oi_chg > 2.5: score += 1
            
            if vol_ratio > 3.0: score += 2; tags.append("🐳WHALE_VOL")
            elif vol_ratio > 1.5: score += 1
            
            # Deteksi Breakout High 24H
            if curr['close'] >= df['high'].rolling(24).max().iloc[-2]:
                score += 2; tags.append("🚀BREAKOUT")
            
            # Minimal score 3 untuk masuk report
            if score >= 3:
                # BUAT LINK BINANCE (Ini kuncinya)
                # Ubah BTC/USDT -> BTCUSDT untuk URL
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

    # --- REPORTING KE TELEGRAM ---
    if signals:
        signals.sort(key=lambda x: x['score'], reverse=True)
        msg = f"🤖 *OMB SIGNAL (Mirror Feed)*\n_Scanned {len(limit_scan)} pairs_\n"
        
        for s in signals[:6]: # Top 6
            icon = "💎" if s['score'] >= 5 else "🔥"
            msg += (f"\n{icon} *[{s['ticker']}]({s['link']})* (Sc: {s['score']})"
                    f"\n  ├ Price: {s['price']}"
                    f"\n  ├ OI 1H: {s['oi_chg']:+.2f}%"
                    f"\n  └ Tags: {s['tags']}\n")
        
        send_telegram(msg)
        print("\n\n✅ Sinyal dikirim (Link Binance).")
    else:
        # Kirim notif heartbeat supaya tau script jalan
        print("\n\n💤 Market sepi, tidak ada setup high-score.")

if __name__ == "__main__":
    run_screener()

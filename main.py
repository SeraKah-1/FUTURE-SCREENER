import ccxt
import pandas as pd
import requests
import os

# --- KONFIGURASI ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# --- PARAMETER ---
LIMIT_CANDLE = 100 
MIN_VOL_24H = 1_000_000  # $1 Juta
TIMEFRAME = '1h'

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
    try: requests.post(url, json=payload)
    except Exception as e: print(f"Telegram Error: {e}")

def get_market_data(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=LIMIT_CANDLE)
        df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        
        # Indikator Trend (EMA)
        df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['EMA_55'] = df['close'].ewm(span=55, adjust=False).mean()
        df['Vol_SMA'] = df['volume'].rolling(window=20).mean()
        
        try:
            # OI History
            oi_hist = exchange.fetch_open_interest_history(symbol, timeframe=TIMEFRAME, limit=2)
        except:
            curr_oi = exchange.fetch_open_interest(symbol)
            oi_hist = [{'openInterest': curr_oi['openInterest']}] * 2
            
        return df, oi_hist
    except:
        return None, None

def determine_trend(row):
    price = row['close']
    ema21 = row['EMA_21']
    ema55 = row['EMA_55']
    
    # Logika Penentuan Tren
    if price > ema21 and ema21 > ema55:
        return "🟢BULL"
    elif price < ema21 and ema21 < ema55:
        return "🔴BEAR"
    else:
        return "🦀SIDE" # Crab market (jalan menyamping)

def run_screener():
    print("🔍 Scanning Market...")
    try:
        tickers = exchange.fetch_tickers()
    except Exception as e:
        send_telegram(f"❌ API Error: {e}")
        return

    targets = []
    for s, d in tickers.items():
        if '/USDT:USDT' in s and d.get('quoteVolume', 0) > MIN_VOL_24H:
            targets.append(s)
            
    # Ambil Top 50 Volatile Pairs
    targets_sorted = sorted(targets, key=lambda x: tickers[x]['quoteVolume'], reverse=True)
    limit_scan = targets_sorted[:50]
    
    print(f"✅ Scanning Top {len(limit_scan)} Volatile Pairs...")
    candidates = []

    for i, symbol in enumerate(limit_scan):
        clean_name = symbol.split(':')[0]
        print(f"\rProcessing {i+1}/{len(limit_scan)}: {clean_name}", end="")
        
        df, oi_hist = get_market_data(symbol)
        if df is None or df.empty: continue
        
        curr = df.iloc[-1]
        
        # Hitung Metrics
        try:
            oi_now = float(oi_hist[-1]['openInterest'])
            oi_prev = float(oi_hist[-2]['openInterest'])
            oi_chg = ((oi_now - oi_prev) / oi_prev) * 100 if oi_prev > 0 else 0
        except: oi_chg = 0
            
        vol_ratio = curr['volume'] / curr['Vol_SMA'] if curr['Vol_SMA'] > 0 else 0.1
        
        # TENTUKAN TREND
        trend_status = determine_trend(curr)
        
        # Score Activity (Volatilitas)
        # Kita bobotkan volume lebih tinggi
        score = abs(oi_chg) + (vol_ratio * 5)
        
        binance_ticker = clean_name.replace('/', '')
        link = f"https://www.binance.com/en/futures/{binance_ticker}"
        
        candidates.append({
            'ticker': clean_name,
            'trend': trend_status,
            'vol_x': vol_ratio,
            'oi_chg': oi_chg,
            'score': score,
            'link': link
        })

    # --- REPORTING ---
    if candidates:
        # Urutkan berdasarkan Aktivitas (Score)
        candidates.sort(key=lambda x: x['score'], reverse=True)
        top_5 = candidates[:5]
        
        msg = f"📊 *MARKET ACTIVITY (Top 5)*\n"
        
        for s in top_5:
            # Ikon tambahan untuk anomali
            alert = ""
            if s['vol_x'] > 3.0: alert += "🐳" # Whale Volume
            if abs(s['oi_chg']) > 4.0: alert += "💰" # Big Money Flow
            
            msg += (f"\n*{s['ticker']}* {alert}"
                    f"\n  ├ Trend: {s['trend']}"
                    f"\n  ├ Vol: {s['vol_x']:.1f}x"
                    f"\n  └ [Chart Binance]({s['link']})\n")
        
        send_telegram(msg)
        print("\n\n✅ Report Terkirim!")
    else:
        print("\n\n❌ Data kosong.")

if __name__ == "__main__":
    run_screener()

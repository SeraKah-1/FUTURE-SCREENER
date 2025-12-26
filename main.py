import ccxt
import pandas as pd
import requests
import os
import numpy as np

# --- KONFIGURASI ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# --- PARAMETER ANALISA ---
LIMIT_CANDLE = 50 
MIN_VOL_24H = 2_000_000 # Filter likuiditas $2M (Mid-High Cap)
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

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_market_data(symbol):
    try:
        # Ambil OHLCV
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=LIMIT_CANDLE)
        df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        return df
    except:
        return None

def run_screener():
    print("🔍 Scanning Market for Volatility...")
    try:
        tickers = exchange.fetch_tickers()
    except Exception as e:
        send_telegram(f"❌ API Error: {e}")
        return

    targets = []
    for s, d in tickers.items():
        if '/USDT:USDT' in s and d.get('quoteVolume', 0) > MIN_VOL_24H:
            targets.append(s)
            
    # Scan 50 koin terlikuid
    targets_sorted = sorted(targets, key=lambda x: tickers[x]['quoteVolume'], reverse=True)
    limit_scan = targets_sorted[:50]
    
    candidates = []

    for i, symbol in enumerate(limit_scan):
        clean_name = symbol.split(':')[0]
        print(f"\rProcessing {i+1}/{len(limit_scan)}: {clean_name}", end="")
        
        df = get_market_data(symbol)
        if df is None or df.empty: continue
        
        # --- PERHITUNGAN INDIKATOR (NERDY STUFF) ---
        # 1. RSI (Momentum)
        df['RSI'] = calculate_rsi(df['close'])
        
        # 2. Moving Averages (Trend)
        df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['Vol_SMA'] = df['volume'].rolling(window=20).mean()
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        # 3. Kuantifikasi Data
        rsi = curr['RSI']
        vol_ratio = curr['volume'] / curr['Vol_SMA'] if curr['Vol_SMA'] > 0 else 0
        price_chg_1h = ((curr['close'] - curr['open']) / curr['open']) * 100
        
        # Tentukan Bias Trend
        if curr['close'] > curr['EMA_21'] and curr['EMA_21'] > curr['EMA_50']:
            trend = "🟢UP"
        elif curr['close'] < curr['EMA_21'] and curr['EMA_21'] < curr['EMA_50']:
            trend = "🔴DOWN"
        else:
            trend = "🦀SIDE"
            
        # --- SCORE SORTING LOGIC ---
        # Kita ingin koin yang BERGERAK. 
        # Score = (Volatilitas Harga) + (Ledakan Volume)
        # Kita pakai Absolute value karena pergerakan turun kencang juga peluang.
        activity_score = abs(price_chg_1h) * vol_ratio
        
        # Filter Minimal: Hanya masukkan jika ada sedikit aktivitas
        # Biar list tidak penuh dengan koin mati (0.2x vol)
        if vol_ratio > 0.8 or abs(price_chg_1h) > 0.5:
            candidates.append({
                'ticker': clean_name,
                'price': curr['close'],
                'chg': price_chg_1h,
                'rsi': rsi,
                'vol_x': vol_ratio,
                'trend': trend,
                'score': activity_score
            })

    # --- REPORTING ---
    if candidates:
        # Sortir: Yang paling "Rusuh" (Score tinggi) paling atas
        candidates.sort(key=lambda x: x['score'], reverse=True)
        top_5 = candidates[:5]
        
        msg = f"📊 *MARKET ANALYTICS (Top Movers)*\n"
        
        for s in top_5:
            # Tanda bahaya/peluang RSI
            rsi_stat = f"{s['rsi']:.0f}"
            if s['rsi'] > 70: rsi_stat += "🔥(OB)" # Overbought
            if s['rsi'] < 30: rsi_stat += "🧊(OS)" # Oversold
            
            # Format Output Rapi & Padat
            msg += (f"\n🔰 *{s['ticker']}* ({s['trend']})"
                    f"\n  💵 P: {s['price']} ({s['chg']:+.2f}%)"
                    f"\n  📈 RSI: {rsi_stat} | Vol: {s['vol_x']:.1f}x")
        
        send_telegram(msg)
        print("\n\n✅ Data Analisa Terkirim!")
    else:
        print("\n\n💤 Market Hening Total.")
        send_telegram("💤 Market sedang tidur. Volatilitas sangat rendah.")

if __name__ == "__main__":
    run_screener()

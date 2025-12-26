import ccxt
import pandas as pd
import requests
import os
import time

# --- KONFIGURASI ENV ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# --- PARAMETER STRATEGI ---
MIN_VOL_24H = 50_000_000   # Turunkan dikit ke $50M (KuCoin vol < Binance)
TIMEFRAME = '1h'
OI_THRESHOLD = 3.0         # Kenaikan OI > 3%
FUNDING_MAX = 0.0003       # Max Funding 0.03%

# --- KONEKSI EXCHANGE (KUCOIN FUTURES) ---
# Menggunakan KuCoin Futures karena lebih ramah IP US (GitHub Actions)
print("🔌 Init CCXT (KuCoin Futures)...")
exchange = ccxt.kucoinfutures({
    'enableRateLimit': True,
    # Opsi tambahan agar loading lebih cepat
    'options': {
        'defaultType': 'future',
        'adjustForTimeDifference': True
    }
})

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram Token/ID not set. Skipping alert.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID, 
        "text": message, 
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try: requests.post(url, json=payload)
    except Exception as e: print(f"⚠️ Telegram Error: {e}")

def get_market_data(symbol):
    try:
        # 1. Fetch OHLCV
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=60)
        df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        
        # 2. Fetch Funding Rate
        funding = exchange.fetch_funding_rate(symbol)
        
        # 3. Fetch Open Interest (TRY-EXCEPT BLOCK)
        # Note: Tidak semua pair di KuCoin support history via CCXT, kita handle errornya
        try:
            # Mengambil data historis OI (jika didukung)
            oi_hist = exchange.fetch_open_interest_history(symbol, timeframe=TIMEFRAME, limit=2)
        except:
            # Fallback: Ambil current OI saja (Logika 'Change' jadi 0)
            oi_curr = exchange.fetch_open_interest(symbol)
            oi_hist = [{'openInterest': oi_curr['openInterest']}] * 2
            
        return df, oi_hist, funding
    except Exception as e:
        # print(f"Error fetching {symbol}: {e}")
        return None, None, None

def run_screener():
    print("🔍 Scanning KuCoin Universe...")
    try:
        tickers = exchange.fetch_tickers()
    except Exception as e:
        print(f"❌ Critical Error fetching tickers: {e}")
        return

    # Filter: Hanya USDT-Margined Perpetuals & Volume > Threshold
    # KuCoin symbol format di CCXT biasanya 'BTC/USDT:USDT'
    targets = []
    for s, d in tickers.items():
        is_usdt_perp = '/USDT:USDT' in s
        vol_valid = d.get('quoteVolume', 0) > MIN_VOL_24H
        if is_usdt_perp and vol_valid:
            targets.append(s)
            
    print(f"✅ Filtered {len(targets)} pairs. Analyzing...")
    
    signals = []
    
    for i, symbol in enumerate(targets):
        # Progress indicator sederhana
        print(f"\rProcessing {i+1}/{len(targets)}: {symbol.split(':')[0]}", end="")
        
        df, oi_hist, funding = get_market_data(symbol)
        if df is None or df.empty: continue
        
        # --- 1. INDICATORS ---
        df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['EMA_55'] = df['close'].ewm(span=55, adjust=False).mean()
        df['Vol_SMA'] = df['volume'].rolling(window=20).mean()
        
        curr = df.iloc[-1]
        
        # --- 2. LOGIC CALCULATION ---
        # OI Change Calculation
        try:
            oi_now = float(oi_hist[-1]['openInterest'])
            oi_prev = float(oi_hist[-2]['openInterest'])
            # Mencegah pembagian dengan nol
            oi_chg = ((oi_now - oi_prev) / oi_prev) * 100 if oi_prev > 0 else 0
        except:
            oi_chg = 0 # Data OI tidak lengkap
        
        # Vol Ratio
        vol_ratio = curr['volume'] / curr['Vol_SMA'] if curr['Vol_SMA'] > 0 else 0
        
        # Funding Rate
        fr = float(funding['fundingRate']) if funding else 0
        
        # --- 3. FILTER GATES (OMB STRATEGY) ---
        trend_bull = (curr['close'] > curr['EMA_21']) and (curr['EMA_21'] > curr['EMA_55'])
        
        # Trigger: Ada ledakan Volume ATAU Ledakan OI
        momentum   = (vol_ratio > 2.0) or (oi_chg > OI_THRESHOLD)
        safe_risk  = (fr < FUNDING_MAX)
        
        if trend_bull and momentum and safe_risk:
            # SCORING
            score = 0
            tags = []
            if oi_chg > 5.0: score += 3; tags.append("💰BIG_INFLOW")
            if vol_ratio > 3.0: score += 2; tags.append("🐳WHALE_VOL")
            if curr['close'] > df['high'].rolling(24).max().iloc[-2]: score += 2; tags.append("🚀BREAKOUT")
            
            # Tampilkan hanya jika skor cukup tinggi
            if score >= 3:
                clean_ticker = symbol.split(':')[0] # Ubah BTC/USDT:USDT jadi BTC/USDT
                signals.append({
                    'ticker': clean_ticker,
                    'price': curr['close'],
                    'oi_chg': oi_chg,
                    'vol_x': vol_ratio,
                    'score': score,
                    'tags': ", ".join(tags)
                })

    # --- 4. REPORTING ---
    if signals:
        signals.sort(key=lambda x: x['score'], reverse=True)
        msg = "🤖 *OMB SCREENER (KuCoin Feed)* 🤖\n_Data used as proxy for Binance_\n"
        
        for s in signals[:5]: # Top 5 only
            icon = "💎" if s['score'] >= 5 else "⚡"
            msg += (f"\n{icon} *{s['ticker']}* (Score: {s['score']})"
                    f"\n  ├ Price: {s['price']}"
                    f"\n  ├ OI 1H: {s['oi_chg']:+.2f}%"
                    f"\n  └ Tags: {s['tags']}\n")
        
        send_telegram(msg)
        print("\n\n✅ Signal sent to Telegram.")
    else:
        print("\n\n💤 No signals found.")

if __name__ == "__main__":
    run_screener()

import ccxt
import pandas as pd
import requests
import os
import random
import time
from fake_useragent import UserAgent

# --- KONFIGURASI ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Turunkan threshold volume agar koin mid-cap masuk
MIN_VOL_24H = 10_000_000  # $10 Juta
TIMEFRAME = '1h'
OI_THRESHOLD = 2.5        # OI naik 2.5%
FUNDING_MAX = 0.0003

# --- BAGIAN 1: PROXY HUNTER (Jalan Tikus) ---
def get_free_proxies():
    print("🛡️ Hunting for active proxies...")
    # Mengambil list proxy gratisan (HTTPS only)
    url = "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"
    try:
        resp = requests.get(url)
        proxies = resp.text.strip().split('\n')
        print(f"   Found {len(proxies)} candidates.")
        return proxies
    except:
        return []

def init_binance_with_proxy():
    # Coba maksimal 10 proxy sampai nemu yang bisa connect
    proxies = get_free_proxies()
    random.shuffle(proxies)
    
    ua = UserAgent()
    
    for p in proxies[:15]: # Coba 15 proxy acak
        try:
            proxy_url = f"http://{p}"
            print(f"   Testing proxy: {p} ... ", end="")
            
            # Setup CCXT dengan Proxy
            exchange = ccxt.binance({
                'options': {'defaultType': 'future'},
                'enableRateLimit': True,
                'proxies': {
                    'http': proxy_url,
                    'https': proxy_url
                },
                'userAgent': ua.random
            })
            
            # Test Koneksi Ringan (Fetch Time)
            exchange.fetch_time()
            print("✅ SUCCESS!")
            return exchange
        except Exception as e:
            print("❌ Fail")
            continue
            
    raise Exception("Gagal menemukan proxy yang bisa tembus Binance. Coba lagi nanti.")

# --- BAGIAN 2: LOGIKA SCREENER ---
def send_telegram(message):
    if not TELEGRAM_TOKEN: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try: requests.post(url, json=payload)
    except: pass

def get_market_data(exchange, symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=60)
        df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        
        # Ambil Funding
        funding = exchange.fetch_funding_rate(symbol)
        
        # Ambil OI (Binance Public API kadang berat via proxy, kita handle)
        oi_hist = exchange.fetch_open_interest_history(symbol, timeframe=TIMEFRAME, limit=2)
        
        return df, oi_hist, funding
    except:
        return None, None, None

def run_screener():
    print("🔌 Connecting to Binance via Proxy Router...")
    try:
        exchange = init_binance_with_proxy()
    except Exception as e:
        print(f"💀 Fatal Error: {e}")
        return

    print("🔍 Scanning Binance Universe...")
    try:
        tickers = exchange.fetch_tickers()
    except:
        print("❌ Failed to fetch tickers with this proxy.")
        return

    targets = []
    for s, d in tickers.items():
        # Filter: USDT Perp & Volume > $10M
        if '/USDT' in s and 'BUSD' not in s:
            if d.get('quoteVolume', 0) > MIN_VOL_24H:
                targets.append(s)
            
    print(f"✅ Filtered {len(targets)} pairs. Analyzing (this may be slow due to proxy)...")
    
    signals = []
    
    # Kita limit scan 30 koin teratas saja biar proxy gak timeout (Github Actions ada limit waktu)
    # Sort targets by volume high to low
    targets_sorted = sorted(targets, key=lambda x: tickers[x]['quoteVolume'], reverse=True)
    scan_limit = targets_sorted[:40] 

    for i, symbol in enumerate(scan_limit):
        print(f"\rProcessing {i+1}/{len(scan_limit)}: {symbol}", end="")
        
        df, oi_hist, funding = get_market_data(exchange, symbol)
        if df is None or len(oi_hist) < 2: continue
        
        # INDICATORS
        df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['EMA_55'] = df['close'].ewm(span=55, adjust=False).mean()
        df['Vol_SMA'] = df['volume'].rolling(window=20).mean()
        curr = df.iloc[-1]
        
        # METRICS
        oi_now = float(oi_hist[-1]['openInterest'])
        oi_prev = float(oi_hist[-2]['openInterest'])
        oi_chg = ((oi_now - oi_prev) / oi_prev) * 100
        vol_ratio = curr['volume'] / curr['Vol_SMA'] if curr['Vol_SMA'] > 0 else 0
        fr = float(funding['fundingRate']) if funding else 0
        
        # LOGIC (OMB STRATEGY)
        trend_bull = (curr['close'] > curr['EMA_21']) and (curr['EMA_21'] > curr['EMA_55'])
        momentum   = (vol_ratio > 2.0) or (oi_chg > OI_THRESHOLD)
        safe_risk  = (fr < FUNDING_MAX)
        
        if trend_bull and momentum and safe_risk:
            score = 0
            tags = []
            if oi_chg > 5.0: score += 3; tags.append("💰BIG_INFLOW")
            elif oi_chg > 2.5: score += 1
            
            if vol_ratio > 3.0: score += 2; tags.append("🐳WHALE_VOL")
            if curr['close'] > df['high'].rolling(24).max().iloc[-2]: score += 2; tags.append("🚀BREAKOUT")
            
            if score >= 3:
                signals.append({
                    'ticker': symbol.replace('/USDT', ''),
                    'price': curr['close'],
                    'oi_chg': oi_chg,
                    'score': score,
                    'tags': ", ".join(tags)
                })

    # REPORTING
    if signals:
        signals.sort(key=lambda x: x['score'], reverse=True)
        msg = f"🤖 *BINANCE PROXY SCREENER*\n_Scanned Top {len(scan_limit)} Volatile Pairs_\n"
        for s in signals[:5]:
            icon = "💎" if s['score'] >= 5 else "⚡"
            msg += (f"\n{icon} *{s['ticker']}* (Score: {s['score']})"
                    f"\n  ├ Price: {s['price']}"
                    f"\n  ├ OI 1H: {s['oi_chg']:+.2f}%"
                    f"\n  └ Tags: {s['tags']}\n")
        send_telegram(msg)
        print("\n\n✅ Signal sent.")
    else:
        print("\n\n💤 No signals found.")

if __name__ == "__main__":
    run_screener()

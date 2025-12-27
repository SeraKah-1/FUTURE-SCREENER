import ccxt
import pandas as pd
import numpy as np
import requests
import os
import time
from concurrent.futures import ThreadPoolExecutor

# --- KONFIGURASI ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Parameter Screening
TOP_VOL_COUNT = 35       # Scan 35 Koin dengan volume terbesar
LIMIT_CANDLE = 200       # Minimal candle untuk akurasi EMA 200
TF_MACRO = '1h'          # Timeframe Trend
TF_MICRO = '15m'         # Timeframe Trigger (OI & Entry)

# --- EXCHANGE SETUP: BYBIT (Lebih Aman dari Blokir IP) ---
print("🔌 Connecting to Bybit Futures...")
exchange = ccxt.bybit({
    'enableRateLimit': True,
    'options': {
        'defaultType': 'linear',  # Linear = USDT Perpetuals
        'adjustForTimeDifference': True
    }
})

# --- HELPER FUNCTIONS ---

def send_telegram(message):
    """Mengirim pesan ke Telegram"""
    if not TELEGRAM_TOKEN:
        print("⚠️ Telegram Token not found! Printing to console only.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"❌ Telegram Error: {e}")

def get_top_liquid_pairs():
    """Mengambil Top 35 Pair berdasarkan Volume USDT"""
    print("🔍 Scanning Market Liquidity (Bybit)...")
    try:
        # Fetch tickers
        tickers = exchange.fetch_tickers()
        
        # Format Data untuk Sorting
        valid_pairs = []
        for symbol, data in tickers.items():
            # Filter hanya USDT Perpetual, abaikan USDC atau Spot
            # Di Bybit symbol futures biasanya formatnya BTC/USDT:USDT
            if '/USDT' in symbol and 'USDC' not in symbol:
                vol = data.get('quoteVolume', 0)
                if vol is None: vol = 0
                valid_pairs.append((symbol, vol))
        
        # Sort dari volume terbesar
        sorted_tickers = sorted(valid_pairs, key=lambda x: x[1], reverse=True)
        
        # Ambil Top N
        targets = [pair[0] for pair in sorted_tickers[:TOP_VOL_COUNT]]
        
        print(f"✅ Loaded {len(targets)} Top Pairs.")
        return targets
    except Exception as e:
        print(f"❌ Error fetching tickers: {e}")
        return []

def calculate_indicators(df):
    """Menghitung EMA, RSI, ATR, Volume SMA"""
    # EMA
    df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['EMA_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # RSI (14)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Volume SMA (20)
    df['Vol_SMA'] = df['volume'].rolling(window=20).mean()
    
    # ATR (14) for Stop Loss
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['ATR'] = true_range.rolling(14).mean()
    
    return df

def fetch_and_analyze(symbol):
    """Core Logic: Fetch Data -> Analisa -> Scoring"""
    try:
        # 1. Fetch Data 1H (Macro Trend)
        ohlcv_1h = exchange.fetch_ohlcv(symbol, TF_MACRO, limit=LIMIT_CANDLE)
        if not ohlcv_1h: return None
        
        df_1h = pd.DataFrame(ohlcv_1h, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        df_1h = calculate_indicators(df_1h)
        last_1h = df_1h.iloc[-1]

        # 2. Cek Struktur Trend (Saringan Awal)
        trend_score = 0
        bias = "NEUTRAL"
        
        # Bullish Structure
        if (last_1h['close'] > last_1h['EMA_21'] > last_1h['EMA_50'] > last_1h['EMA_200']):
            bias = "BULLISH"
            trend_score = 40
        # Bearish Structure
        elif (last_1h['close'] < last_1h['EMA_21'] < last_1h['EMA_50'] < last_1h['EMA_200']):
            bias = "BEARISH"
            trend_score = 40
            
        # Jika Sideways/Messy, langsung Skip
        if trend_score == 0:
            return None

        # 3. Fetch Data 15m (Micro Trigger)
        ohlcv_15m = exchange.fetch_ohlcv(symbol, TF_MICRO, limit=50)
        df_15m = pd.DataFrame(ohlcv_15m, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        df_15m = calculate_indicators(df_15m)
        last_15m = df_15m.iloc[-1]
        
        # Fetch Real Funding & Proxy OI
        try:
            ticker_data = exchange.fetch_ticker(symbol)
            # CCXT Unified Field untuk Funding Rate (Lebih stabil di Bybit)
            funding_rate = ticker_data.get('fundingRate', 0)
            if funding_rate is None: funding_rate = 0
            
            # Simulasi OI/Smart Money via Volume Spike
            oi_proxy_score = 0
            vol_ratio = last_15m['volume'] / last_15m['Vol_SMA']
            
            if vol_ratio > 2.5: oi_proxy_score = 30 # Big Volume Spike
            elif vol_ratio > 1.5: oi_proxy_score = 15
            
        except:
            funding_rate = 0
            oi_proxy_score = 0
            vol_ratio = 1.0

        # 4. Momentum Score (RSI)
        mom_score = 0
        rsi = last_15m['RSI']
        
        if bias == "BULLISH":
            if 40 < rsi < 70: mom_score = 20 # Healthy Bull
        elif bias == "BEARISH":
            if 30 < rsi < 60: mom_score = 20 # Healthy Bear
            
        # 5. Total Scoring
        total_score = trend_score + oi_proxy_score + mom_score
        
        # Penentuan Tier
        tier = "C"
        if total_score >= 85: tier = "S"
        elif total_score >= 65: tier = "A"
        elif total_score >= 50: tier = "B"
        else: return None # Buang Tier C/Sampah
        
        # 6. Risk Management (ATR SL)
        atr_val = last_15m['ATR']
        sl_price = 0
        
        # Clean Symbol Name (Remove :USDT suffix if exists for display)
        clean_symbol = symbol.split(':')[0]

        if bias == "BULLISH":
            sl_price = last_15m['low'] - (1.5 * atr_val)
            side = "LONG 🟢"
        else:
            sl_price = last_15m['high'] + (1.5 * atr_val)
            side = "SHORT 🔴"

        return {
            'symbol': clean_symbol,
            'side': side,
            'price': last_15m['close'],
            'score': total_score,
            'tier': tier,
            'sl': sl_price,
            'vol_x': vol_ratio,
            'funding': funding_rate * 100
        }

    except Exception as e:
        # print(f"Error analyzing {symbol}: {e}")
        return None

# --- MAIN ENGINE ---

def run_screener():
    print("🚀 Starting Tier-List Screener (Bybit Edition)...")
    targets = get_top_liquid_pairs()
    
    if not targets:
        print("❌ No targets found. Check connection.")
        return

    results = []

    # Parallel Execution
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(fetch_and_analyze, pair) for pair in targets]
        for future in futures:
            res = future.result()
            if res:
                results.append(res)
    
    # Sorting: Tier S -> A -> B, lalu by Score tertinggi
    tier_order = {'S': 0, 'A': 1, 'B': 2}
    results.sort(key=lambda x: (tier_order[x['tier']], -x['score']))
    
    # Formatting Output Telegram
    if not results:
        print("No setups found.")
        return

    msg = f"🔥 **MARKET LEADERBOARD (Top {TOP_VOL_COUNT})** 🔥\n"
    msg += f"⏰ Scan: {pd.Timestamp.now().strftime('%H:%M UTC')}\n\n"
    
    current_tier = ""
    
    for r in results:
        # Header Tier
        if r['tier'] != current_tier:
            current_tier = r['tier']
            icon = "🏆" if current_tier == "S" else "🥇" if current_tier == "A" else "🥈"
            msg += f"\n{icon} **TIER {current_tier} SETUPS**\n"
            msg += "-"*25 + "\n"
            
        # Isi Setup
        msg += f"**{r['symbol']}** [{r['side']}]\n"
        msg += f"   • Score: {r['score']}/100\n"
        msg += f"   • Vol: {r['vol_x']:.1f}x | Fund: {r['funding']:.4f}%\n"
        msg += f"   • 🛡️ SL Ref: {r['sl']:.4f}\n\n"
        
    msg += "💡 *Tier S = Strong Trend + High Vol/Money Inflow*"
    
    print(msg) # Debug di console
    send_telegram(msg)
    print("✅ Report Sent!")

if __name__ == "__main__":
    run_screener()

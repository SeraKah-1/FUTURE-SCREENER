import ccxt
import pandas as pd
import numpy as np
import time
from datetime import datetime

# --- CONFIGURATION ---
MIN_VOL_24H = 100_000_000  # $100 Juta (Liquidity Filter)
TIMEFRAME = '1h'           # Fokus ke Hourly Breakout
EMA_TREND = 21             # Trend Filter
VOL_MA = 20                # Volume Average
OI_THRESHOLD = 3.0         # Minimal kenaikan OI 3% dalam 1 jam
FUNDING_MAX = 0.0003       # Max Funding 0.03% (Avoid Overcrowded Longs)

# --- INITIALIZATION ---
print("🔌 Connecting to Binance Futures...")
exchange = ccxt.binance({
    'options': {'defaultType': 'future'},
    'enableRateLimit': True 
})

def fetch_top_liquid_pairs():
    """Mengambil pair dengan volume 24jam > Threshold"""
    print("🔍 Scanning Liquidity...")
    tickers = exchange.fetch_tickers()
    targets = []
    
    for symbol, data in tickers.items():
        # Filter hanya USDT perp & Volume Besar
        if '/USDT' in symbol and 'BUSD' not in symbol:
            vol_usd = data.get('quoteVolume', 0)
            if vol_usd > MIN_VOL_24H:
                targets.append(symbol)
    
    print(f"✅ Found {len(targets)} liquid pairs out of {len(tickers)}")
    return targets

def get_market_data(symbol):
    """Mengambil OHLCV + OI History + Funding"""
    try:
        # 1. Fetch OHLCV (Price & Vol)
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=50)
        df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        
        # 2. Fetch OI History (Last 2 hours to calc change)
        # Note: OI History endpoint Binance public bisa heavy, kita ambil snapshot pendek
        oi_hist = exchange.fetch_open_interest_history(symbol, timeframe=TIMEFRAME, limit=2)
        
        # 3. Fetch Funding Rate
        funding = exchange.fetch_funding_rate(symbol)
        
        return df, oi_hist, funding
    except Exception as e:
        # print(f"⚠️ Error {symbol}: {e}")
        return None, None, None

def calculate_indicators(df):
    """Hitung EMA, Vol MA, dll"""
    df['EMA_21'] = df['close'].ewm(span=EMA_TREND, adjust=False).mean()
    df['Vol_SMA_20'] = df['volume'].rolling(window=VOL_MA).mean()
    
    # RSI Sederhana (Vectorized)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    return df.iloc[-1] # Return candle terakhir saja

def run_analysis():
    targets = fetch_top_liquid_pairs()
    candidates = []
    
    print(f"🚀 Analyzing {len(targets)} pairs with OMB Strategy...")
    print("-" * 60)

    for symbol in targets:
        curr_candle, oi_hist, funding = get_market_data(symbol)
        
        if curr_candle is None or len(oi_hist) < 2:
            continue

        # Data Parsing
        df = pd.DataFrame([curr_candle for _ in range(50)]) # Dummy re-structure for calc (simplified)
        # Re-fetch full OHLCV inside get_market_data is cleaner, but doing logic here:
        
        # Hitung Indikator Technical
        # Kita butuh DF utuh dari get_market_data, mari kita fix flow di loop
        pass 

    # --- REVISED LOOP FOR EFFICIENCY ---
    final_list = []
    
    for i, symbol in enumerate(targets):
        # Progress Bar Sederhana
        print(f"\rProcessing {i+1}/{len(targets)}: {symbol}", end="")
        
        df, oi_hist, funding_data = get_market_data(symbol)
        if df is None: continue
        
        # 1. Technical Calcs
        df['EMA_21'] = df['close'].ewm(span=EMA_TREND, adjust=False).mean()
        df['EMA_55'] = df['close'].ewm(span=55, adjust=False).mean()
        df['Vol_SMA'] = df['volume'].rolling(window=VOL_MA).mean()
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # 2. OI Calculation (Open Interest)
        # oi_hist structure: [{'openInterest': float, ...}, ...]
        try:
            oi_curr = float(oi_hist[-1]['openInterest'])
            oi_prev = float(oi_hist[-2]['openInterest'])
            oi_change_pct = ((oi_curr - oi_prev) / oi_prev) * 100
        except:
            oi_change_pct = 0

        # 3. STRATEGY FILTERS (THE GATES) ⛩️
        
        # A. Trend Filter (Bullish Structure)
        is_uptrend = (last['close'] > last['EMA_21']) and (last['EMA_21'] > last['EMA_55'])
        
        # B. Momentum Filter (Vol & OI)
        vol_ratio = last['volume'] / last['Vol_SMA'] if last['Vol_SMA'] > 0 else 0
        is_vol_spike = vol_ratio > 2.0  # Volume 2x rata-rata
        is_oi_surge = oi_change_pct > OI_THRESHOLD # OI naik > 3% sejam
        
        # C. Risk Filter (Funding)
        funding_rate = float(funding_data['fundingRate']) if funding_data else 0
        is_safe_funding = funding_rate < FUNDING_MAX
        
        # SCORE CALCULATION
        score = 0
        if is_uptrend: score += 1
        if vol_ratio > 2.5: score += 2
        if oi_change_pct > 5.0: score += 3  # Big Money In
        elif oi_change_pct > 3.0: score += 1
        if is_safe_funding: score += 1
        
        # Final Selection: Minimal Score 3 atau ada Ledakan OI
        if score >= 4 or (is_uptrend and is_oi_surge):
            final_list.append({
                'Symbol': symbol.split('/')[0],
                'Price': last['close'],
                'Vol_x': round(vol_ratio, 1),
                'OI_1h%': round(oi_change_pct, 2),
                'Fund%': round(funding_rate * 100, 4),
                'Score': score
            })

    print("\n\n" + "="*50)
    print("💎 SCREENER RESULTS (OMB STRATEGY)")
    print("="*50)
    
    if final_list:
        # Sort by Score High -> Low
        final_list.sort(key=lambda x: x['Score'], reverse=True)
        res_df = pd.DataFrame(final_list)
        print(res_df.to_markdown(index=False))
    else:
        print("💤 No setups found. Market is boring.")

if __name__ == "__main__":
    run_analysis()

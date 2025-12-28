import ccxt
import pandas as pd
import numpy as np
import config
from concurrent.futures import ThreadPoolExecutor

class Screener:
    def __init__(self):
        print(f"🔌 Connecting to {config.EXCHANGE_ID}...")
        self.exchange = getattr(ccxt, config.EXCHANGE_ID)({
            'enableRateLimit': True,
            'options': {'defaultType': 'swap'} 
        })

    def get_top_pairs(self):
        try:
            tickers = self.exchange.fetch_tickers()
            targets = []
            for s, d in tickers.items():
                if 'USDT' in s and d.get('quoteVolume') and float(d['quoteVolume']) > 0:
                    targets.append((s, d['quoteVolume']))
            targets = sorted(targets, key=lambda x: x[1], reverse=True)[:config.TOP_VOL_COUNT]
            return [t[0] for t in targets]
        except Exception:
            return []

    def calculate_indicators(self, df):
        if df is None or df.empty: return None
        
        # 1. VOLUME 21 EMA
        df['Vol_Mean_21'] = df['volume'].rolling(21).mean()
        
        # 2. RSI 21
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(21).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(21).mean()
        rs = gain / loss
        df['RSI_21'] = 100 - (100 / (1 + rs))
        
        # 3. ATR 14
        high_low = df['high'] - df['low']
        h_c = np.abs(df['high'] - df['close'].shift())
        l_c = np.abs(df['low'] - df['close'].shift())
        tr = np.max(pd.concat([high_low, h_c, l_c], axis=1), axis=1)
        df['ATR'] = tr.rolling(14).mean()
        
        # 4. CMF 21
        mfv = ((df['close'] - df['low']) - (df['high'] - df['close'])) / (df['high'] - df['low']) * df['volume']
        df['CMF_21'] = mfv.rolling(21).sum() / df['volume'].rolling(21).sum()
        
        # 5. DMI 14 (ADX)
        up = df['high'].diff()
        down = -df['low'].diff()
        plus_dm = np.where((up > down) & (up > 0), up, 0)
        minus_dm = np.where((down > up) & (down > 0), down, 0)
        tr_smooth = tr.rolling(14).mean()
        plus_di = 100 * (pd.Series(plus_dm).rolling(14).mean() / tr_smooth)
        minus_di = 100 * (pd.Series(minus_dm).rolling(14).mean() / tr_smooth)
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
        df['ADX'] = dx.rolling(14).mean()
        df['DI_Plus'] = plus_di
        df['DI_Minus'] = minus_di
        
        return df

    def analyze_pair(self, symbol):
        try:
            # --- 1. MACRO (DAILY) ---
            ohlcv_d = self.exchange.fetch_ohlcv(symbol, '1d', limit=100)
            df_d = pd.DataFrame(ohlcv_d, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df_d = self.calculate_indicators(df_d)
            
            last_d = df_d.iloc[-2] # Candle Daily Kemarin (Close)
            
            # --- LOGIKA SWING ---
            bias = "NEUTRAL"
            score = 0
            
            # ADX Filter
            if last_d['ADX'] > 20:
                if last_d['DI_Plus'] > last_d['DI_Minus']:
                    bias = "BULLISH"
                    score += 30
                elif last_d['DI_Minus'] > last_d['DI_Plus']:
                    bias = "BEARISH"
                    score += 30
            else:
                return None 

            # CMF Filter
            if bias == "BULLISH" and last_d['CMF_21'] > 0: score += 20
            elif bias == "BEARISH" and last_d['CMF_21'] < 0: score += 20
            else: score -= 10

            # RSI Filter
            if bias == "BULLISH" and last_d['RSI_21'] > 50: score += 10
            elif bias == "BEARISH" and last_d['RSI_21'] < 50: score += 10

            # Volume Breakout Filter
            if last_d['volume'] > last_d['Vol_Mean_21']: score += 10
            
            # --- 2. MICRO (15m) & DATA REALTIME ---
            ohlcv_15m = self.exchange.fetch_ohlcv(symbol, config.TF_MICRO, limit=50)
            df_m = pd.DataFrame(ohlcv_15m, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df_m = self.calculate_indicators(df_m)
            
            current_price = df_m.iloc[-1]['close']
            atr_micro = df_m.iloc[-2]['ATR']
            
            # --- HITUNG PERUBAHAN HARGA (Current vs Yesterday Close) ---
            prev_daily_close = df_d.iloc[-2]['close']
            pct_change = ((current_price - prev_daily_close) / prev_daily_close) * 100
            
            # Filter Score
            if score < config.MIN_SCORE: return None
            
            # Stop Loss
            if bias == "BULLISH":
                sl = current_price - (config.ATR_MULTIPLIER * atr_micro)
                side = "LONG 🟢"
            else:
                sl = current_price + (config.ATR_MULTIPLIER * atr_micro)
                side = "SHORT 🔴"

            clean_symbol = symbol.replace('_', '/') 
            
            return {
                'symbol': clean_symbol,
                'side': side,
                'score': score,
                'price': current_price,
                'chg': pct_change,             # <--- Data Baru (% Change)
                'sl': sl,
                'vol_ratio': last_d['volume'] / last_d['Vol_Mean_21'], # <--- Data Baru (Volume Ratio)
                'adx': last_d['ADX'],
                'cmf': last_d['CMF_21']
            }
        except Exception:
            return None

    def run_scan(self):
        targets = self.get_top_pairs()
        print(f"🔍 Scanning {len(targets)} Pairs with V6.1 Indicators...")
        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(self.analyze_pair, s) for s in targets]
            for f in futures:
                if f.result(): results.append(f.result())
        
        results.sort(key=lambda x: -x['score'])
        return results

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
                # Filter Gate.io Swap (USDT)
                if 'USDT' in s and d.get('quoteVolume') and float(d['quoteVolume']) > 0:
                    targets.append((s, d['quoteVolume']))
            
            # Sort Volume Terbesar
            targets = sorted(targets, key=lambda x: x[1], reverse=True)[:config.TOP_VOL_COUNT]
            return [t[0] for t in targets]
        except Exception as e:
            print(f"❌ Error tickers: {e}")
            return []

    def calculate_indicators(self, df):
        if df is None or df.empty: return None
        
        # EMA 50 (Trend Utama)
        df['EMA_50'] = df['close'].ewm(span=config.EMA_MID).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(config.RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(config.RSI_PERIOD).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # Volume & ATR
        df['Vol_SMA'] = df['volume'].rolling(20).mean()
        high_low = df['high'] - df['low']
        h_c = np.abs(df['high'] - df['close'].shift())
        l_c = np.abs(df['low'] - df['close'].shift())
        tr = np.max(pd.concat([high_low, h_c, l_c], axis=1), axis=1)
        df['ATR'] = tr.rolling(14).mean()
        
        return df

    def analyze_pair(self, symbol):
        try:
            # --- 1. MACRO (1H) - TENTUKAN ARAH ---
            ohlcv_1h = self.exchange.fetch_ohlcv(symbol, config.TF_MACRO, limit=100)
            df_macro = pd.DataFrame(ohlcv_1h, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df_macro = self.calculate_indicators(df_macro)
            last_macro = df_macro.iloc[-1]
            
            # LOGIKA BARU: Cukup harga di atas/bawah EMA 50
            # Ini menjamin bot tidak "Bisu" (Pasti ada bias Long atau Short)
            if last_macro['close'] > last_macro['EMA_50']:
                bias = "BULLISH"
            else:
                bias = "BEARISH"

            # --- 2. MICRO (15m) - ENTRY POINT ---
            ohlcv_15m = self.exchange.fetch_ohlcv(symbol, config.TF_MICRO, limit=50)
            df_micro = pd.DataFrame(ohlcv_15m, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df_micro = self.calculate_indicators(df_micro)
            last_micro = df_micro.iloc[-1]
            
            # --- SCORING SYSTEM (Base 40) ---
            score = 40
            
            # A. Volume (Max +30)
            avg_vol = last_micro['Vol_SMA'] if last_micro['Vol_SMA'] > 0 else last_micro['volume']
            vol_ratio = last_micro['volume'] / avg_vol
            
            if vol_ratio > 2.5: score += 30      # Volume Ledakan
            elif vol_ratio > 1.2: score += 15    # Volume Sehat
            
            # B. RSI Momentum (Max +30)
            rsi = last_micro['RSI']
            if bias == "BULLISH":
                if 45 <= rsi <= 65: score += 30    # Golden Zone Long
                elif 40 <= rsi <= 75: score += 15  # OK Zone
            else: # Bearish
                if 35 <= rsi <= 55: score += 30    # Golden Zone Short
                elif 25 <= rsi <= 60: score += 15  # OK Zone
                
            # C. Bonus Trend Alignment (+10)
            # Jika 15m juga sepakat dengan 1H (Contoh: 1H Bullish DAN 15m > EMA50)
            micro_trend = "BULLISH" if last_micro['close'] > last_micro['EMA_50'] else "BEARISH"
            if bias == micro_trend:
                score += 10

            # --- FILTER AKHIR ---
            if score < config.MIN_SCORE: return None
            
            # --- STOP LOSS ---
            atr = last_micro['ATR']
            if bias == "BULLISH":
                sl = last_micro['low'] - (config.ATR_MULTIPLIER * atr)
                side = "LONG 🟢"
            else:
                sl = last_micro['high'] + (config.ATR_MULTIPLIER * atr)
                side = "SHORT 🔴"

            # Clean Symbol (Gate suka kasih format BTC_USDT, kita ubah jadi BTC/USDT)
            clean_symbol = symbol.replace('_', '/') 
            
            return {
                'symbol': clean_symbol,
                'side': side,
                'score': score,
                'price': last_micro['close'],
                'sl': sl,
                'vol': vol_ratio
            }
        except Exception as e:
            # print(f"Err {symbol}: {e}")
            return None

    def run_scan(self):
        targets = self.get_top_pairs()
        if not targets: 
            print("❌ Gagal mengambil daftar koin.")
            return []
            
        print(f"🔍 Menganalisa {len(targets)} pair secara detail...")
        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(self.analyze_pair, s) for s in targets]
            for f in futures:
                if f.result(): results.append(f.result())
        
        # Urutkan: Score tertinggi paling atas
        results.sort(key=lambda x: -x['score'])
        return results

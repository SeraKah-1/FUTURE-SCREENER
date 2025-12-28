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

    # --- RUMUS INDIKATOR KOMPLEKS ---
    def calculate_indicators(self, df):
        if df is None or df.empty: return None
        
        # 1. VOLUME 21 EMA (Daily context)
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
        
        # 4. CMF 21 (Chaikin Money Flow) - Whale Detector
        # MFV = [(Close - Low) - (High - Close)] / (High - Low) * Vol
        mfv = ((df['close'] - df['low']) - (df['high'] - df['close'])) / (df['high'] - df['low']) * df['volume']
        df['CMF_21'] = mfv.rolling(21).sum() / df['volume'].rolling(21).sum()
        
        # 5. DMI 14 (ADX, +DI, -DI) - Trend Strength
        up = df['high'].diff()
        down = -df['low'].diff()
        
        plus_dm = np.where((up > down) & (up > 0), up, 0)
        minus_dm = np.where((down > up) & (down > 0), down, 0)
        
        # Smoothing (Mirip Wilder's)
        tr_smooth = tr.rolling(14).mean()
        plus_di = 100 * (pd.Series(plus_dm).rolling(14).mean() / tr_smooth)
        minus_di = 100 * (pd.Series(minus_dm).rolling(14).mean() / tr_smooth)
        
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(14).mean()
        
        df['ADX'] = adx
        df['DI_Plus'] = plus_di
        df['DI_Minus'] = minus_di
        
        return df

    def analyze_pair(self, symbol):
        try:
            # --- 1. MACRO (DAILY) - VALIDASI INDIKATOR BERAT ---
            # Kita ambil data Daily untuk CMF, DMI, dan Vol 21
            ohlcv_d = self.exchange.fetch_ohlcv(symbol, '1d', limit=100)
            df_d = pd.DataFrame(ohlcv_d, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df_d = self.calculate_indicators(df_d)
            last_d = df_d.iloc[-2] # Ambil candle Daily kemarin (Close) agar valid
            
            bias = "NEUTRAL"
            score = 0
            
            # --- LOGIKA DMI (Trend Master) ---
            # ADX > 20 artinya Trend mulai jalan. Di bawah 20 = Sideways parah.
            if last_d['ADX'] > 20:
                if last_d['DI_Plus'] > last_d['DI_Minus']:
                    bias = "BULLISH"
                    score += 30
                elif last_d['DI_Minus'] > last_d['DI_Plus']:
                    bias = "BEARISH"
                    score += 30
            else:
                return None # Market Mati / Sideways, langsung Skip.

            # --- LOGIKA CMF (Money Flow) ---
            # CMF Positif = Uang Masuk (Akumulasi)
            # CMF Negatif = Uang Keluar (Distribusi)
            if bias == "BULLISH" and last_d['CMF_21'] > 0:
                score += 20
            elif bias == "BEARISH" and last_d['CMF_21'] < 0:
                score += 20
            else:
                score -= 10 # Arah trend dan arus uang tidak sinkron (Bahaya)

            # --- LOGIKA RSI 21 ---
            # RSI 21 lebih smooth.
            rsi = last_d['RSI_21']
            if bias == "BULLISH" and rsi > 50: score += 10
            elif bias == "BEARISH" and rsi < 50: score += 10

            # --- LOGIKA VOLUME ---
            # Apakah Volume kemarin > Rata-rata 21 hari?
            if last_d['volume'] > last_d['Vol_Mean_21']:
                score += 10 # Validasi Breakout
            
            # --- 2. MICRO (15m) - ENTRY TRIGGER ---
            # Kita hanya entry jika 15m searah dengan Daily
            ohlcv_15m = self.exchange.fetch_ohlcv(symbol, config.TF_MICRO, limit=50)
            df_m = pd.DataFrame(ohlcv_15m, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df_m = self.calculate_indicators(df_m) # Hitung ATR buat SL
            
            current_price = df_m.iloc[-1]['close']
            atr_micro = df_m.iloc[-2]['ATR']
            
            # FILTER AKHIR
            if score < config.MIN_SCORE: return None
            
            # Stop Loss Calc
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
                'sl': sl,
                'vol': last_d['volume'] / last_d['Vol_Mean_21'], # Ratio Volume Daily
                'adx': last_d['ADX'],
                'cmf': last_d['CMF_21']
            }
        except Exception as e:
            return None

    def run_scan(self):
        targets = self.get_top_pairs()
        print(f"🔍 Scanning {len(targets)} Pairs with ADVANCED Indicators (DMI, CMF, RSI21)...")
        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(self.analyze_pair, s) for s in targets]
            for f in futures:
                if f.result(): results.append(f.result())
        
        results.sort(key=lambda x: -x['score'])
        return results

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
        print("🔍 Scanning Liquidity (Gate.io)...")
        try:
            tickers = self.exchange.fetch_tickers()
            targets = []
            for s, d in tickers.items():
                if 'USDT' in s and d.get('quoteVolume'):
                    targets.append((s, d['quoteVolume']))
            
            # Ambil Top 30
            targets = sorted(targets, key=lambda x: x[1], reverse=True)[:config.TOP_VOL_COUNT]
            final_pairs = [t[0] for t in targets]
            return final_pairs
        except Exception as e:
            print(f"❌ Error fetching tickers: {e}")
            return []

    def calculate_indicators(self, df):
        if df is None or df.empty: return None
        
        # Kita hanya butuh EMA 50 sebagai Baseline Trend Utama
        df['EMA_50'] = df['close'].ewm(span=config.EMA_MID).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(config.RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(config.RSI_PERIOD).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # Volume SMA & ATR
        df['Vol_SMA'] = df['volume'].rolling(20).mean()
        high_low = df['high'] - df['low']
        h_c = np.abs(df['high'] - df['close'].shift())
        l_c = np.abs(df['low'] - df['close'].shift())
        tr = np.max(pd.concat([high_low, h_c, l_c], axis=1), axis=1)
        df['ATR'] = tr.rolling(config.ATR_PERIOD).mean()
        
        return df

    def analyze_pair(self, symbol):
        try:
            # --- 1. MACRO (1H) - TENTUKAN ARAH (BIAS) ---
            ohlcv_1h = self.exchange.fetch_ohlcv(symbol, config.TF_MACRO, limit=100)
            df_macro = self.calculate_indicators(pd.DataFrame(ohlcv_1h, columns=['t','o','h','l','c','v']))
            last_macro = df_macro.iloc[-1]
            
            bias = "NEUTRAL"
            trend_score = 0
            
            # LOGIKA BARU (AGRESIF):
            # Cukup lihat posisi harga terhadap EMA 50
            if last_macro['c'] > last_macro['EMA_50']:
                bias = "BULLISH"
                trend_score = 20 # Skor dasar
            else:
                bias = "BEARISH"
                trend_score = 20 # Skor dasar
            
            # --- 2. MICRO (15m) - TENTUKAN ENTRY ---
            ohlcv_15m = self.exchange.fetch_ohlcv(symbol, config.TF_MICRO, limit=50)
            df_micro = self.calculate_indicators(pd.DataFrame(ohlcv_15m, columns=['t','o','h','l','c','v']))
            last_micro = df_micro.iloc[-1]
            
            # A. Volume Score (Cari aktivitas)
            vol_score = 0
            # Jika Volume SMA nol (data error), anggap 1
            avg_vol = last_micro['Vol_SMA'] if last_micro['Vol_SMA'] > 0 else last_micro['v']
            vol_ratio = last_micro['v'] / avg_vol
            
            if vol_ratio > 2.0: vol_score = 40      # Ledakan Volume
            elif vol_ratio > 1.2: vol_score = 20    # Volume Lumayan
            
            # B. RSI Score (Momentum)
            mom_score = 0
            rsi = last_micro['RSI']
            
            if bias == "BULLISH":
                # Cari RSI yang menanjak tapi belum Overbought parah (>75)
                if 40 <= rsi <= 75: mom_score = 20
            elif bias == "BEARISH":
                # Cari RSI yang turun tapi belum Oversold parah (<25)
                # KITA LONGGARKAN DISINI: Izinkan short meski RSI 30an (kuat turun)
                if 25 <= rsi <= 60: mom_score = 20
            
            # TOTAL SKOR
            total_score = trend_score + vol_score + mom_score
            
            # --- TIERING ---
            tier = "C"
            # Skor minimal diturunkan biar banyak sinyal masuk
            if total_score >= 70: tier = "S"
            elif total_score >= 50: tier = "A" 
            elif total_score >= 30: tier = "B" # Asal ada volume dikit, masuk B
            else: return None
            
            # --- RISK CALC (SL) ---
            sl_price = 0
            side = ""
            atr_val = last_micro['ATR']
            
            if bias == "BULLISH":
                sl_price = last_micro['l'] - (config.ATR_MULTIPLIER * atr_val)
                side = "LONG 🟢"
            else:
                sl_price = last_micro['h'] + (config.ATR_MULTIPLIER * atr_val)
                side = "SHORT 🔴"

            # Funding (Optional)
            funding = 0
            try: 
                tk = self.exchange.fetch_ticker(symbol)
                funding = tk.get('info', {}).get('funding_rate', 0)
            except: pass

            return {
                'symbol': symbol.replace('_', '/'),
                'side': side, 
                'score': total_score, 
                'tier': tier,
                'price': last_micro['c'], 
                'sl': sl_price, 
                'vol': vol_ratio, 
                'fund': float(funding)*100
            }
        except Exception as e: 
            return None

    def run_scan(self):
        targets = self.get_top_pairs()
        if not targets: return []
        
        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(self.analyze_pair, s) for s in targets]
            for f in futures:
                if f.result(): results.append(f.result())
                
        tier_map = {'S':0, 'A':1, 'B':2}
        results.sort(key=lambda x: (tier_map[x['tier']], -x['score']))
        return results

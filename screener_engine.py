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
            
            # Ambil pair dengan volume terbesar agar tidak terjebak koin gorengan
            targets = sorted(targets, key=lambda x: x[1], reverse=True)[:config.TOP_VOL_COUNT]
            return [t[0] for t in targets]
        except Exception as e:
            print(f"❌ Error fetching tickers: {e}")
            return []

    def calculate_indicators(self, df):
        if df is None or df.empty: return None
        
        # EMA Ribbon (Indikator utama trend 1H/4H)
        df['EMA_21'] = df['close'].ewm(span=config.EMA_FAST).mean()
        df['EMA_50'] = df['close'].ewm(span=config.EMA_MID).mean()
        df['EMA_200'] = df['close'].ewm(span=config.EMA_SLOW).mean()
        
        # RSI (Momentum)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/config.RSI_PERIOD, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/config.RSI_PERIOD, adjust=False).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # Volume Average
        df['Vol_SMA'] = df['volume'].rolling(20).mean()
        
        return df

    def analyze_pair(self, symbol):
        try:
            # Ambil data candle
            ohlcv = self.exchange.fetch_ohlcv(symbol, config.TF_TRADE, limit=300)
            if not ohlcv: return None
            
            df = self.calculate_indicators(pd.DataFrame(ohlcv, columns=['t','o','h','l','c','v']))
            curr = df.iloc[-1]
            
            # --- 1. TENTUKAN BIAS ---
            bias = "NEUTRAL"
            if curr['close'] > curr['EMA_200']: bias = "LONG"
            elif curr['close'] < curr['EMA_200']: bias = "SHORT"
            
            # DEBUG: Kalo Neutral langsung skip
            if bias == "NEUTRAL": 
                # print(f"❌ {symbol} SKIP: Sideways di EMA 200")
                return None 

            # --- 2. HITUNG SKOR ---
            score = 0
            reasons = [] # Nampung alasan poin plus
            
            # A. TREND STRUCTURE (Max 40)
            if bias == "LONG":
                if curr['EMA_21'] > curr['EMA_50'] > curr['EMA_200']:
                    score += 40
                    reasons.append("Perfect Bull")
                elif curr['close'] > curr['EMA_50']:
                    score += 20
                    reasons.append("Bull Trend")
            else: # SHORT
                if curr['EMA_21'] < curr['EMA_50'] < curr['EMA_200']:
                    score += 40
                    reasons.append("Perfect Bear")
                elif curr['close'] < curr['EMA_50']:
                    score += 20
                    reasons.append("Bear Trend")

            # B. MOMENTUM RSI (Max 30)
            rsi = curr['RSI']
            if bias == "LONG":
                if 50 <= rsi <= 70: 
                    score += 30
                    reasons.append("RSI Power")
                elif 40 <= rsi < 50: score += 15
            else: # SHORT
                if 30 <= rsi <= 50: 
                    score += 30
                    reasons.append("RSI Power")
                elif 50 < rsi <= 60: score += 15

            # C. VOLUME (Max 30)
            vol_ratio = curr['volume'] / curr['Vol_SMA']
            if vol_ratio > 1.5: 
                score += 30
                reasons.append("Big Vol")
            elif vol_ratio > 1.0: 
                score += 15
            else:
                score += 5 # Volume sepi dikasih poin kecil

            # --- FILTER AKHIR ---
            # DEBUG PRINT: Biar tau skor koin yang ditolak berapa
            if score < config.MIN_SCORE: 
                print(f"⚠️ {symbol} Score: {score} (Kurang dari {config.MIN_SCORE}) -> Ditolak")
                return None
            
            # Kalau lolos filter:
            price_change_pct = ((curr['close'] - curr['open']) / curr['open']) * 100

            return {
                'symbol': symbol.replace('_', '/'),
                'side': "LONG 🟢" if bias == "LONG" else "SHORT 🔴",
                'score': score,
                'price': curr['close'],
                'change_1h': round(price_change_pct, 2),
                'vol_stat': round(vol_ratio, 1),
                'note': ", ".join(reasons)
            }

        except Exception as e:
            print(f"Error {symbol}: {e}")
            return None

    def run_scan(self):
        targets = self.get_top_pairs()
        if not targets: return []
        
        print(f"🕵️‍♂️ Scanning {len(targets)} Pairs ({config.TF_TRADE})...")
        results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(self.analyze_pair, s) for s in targets]
            for f in futures:
                res = f.result()
                if res: results.append(res)
                
        results.sort(key=lambda x: -x['score'])
        return results

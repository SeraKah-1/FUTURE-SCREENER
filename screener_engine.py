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
            'options': {'defaultType': 'swap'} # Swap = Futures di Gate.io
        })

    def get_top_pairs(self):
        """Ambil Top 30 Pair USDT Terbesar"""
        print("🔍 Scanning Liquidity...")
        try:
            tickers = self.exchange.fetch_tickers()
            targets = []
            for s, d in tickers.items():
                # Filter Gate: Simbol futures biasanya BTC_USDT
                if 'USDT' in s and d['quoteVolume']:
                    targets.append((s, d['quoteVolume']))
            
            # Sort volume terbesar
            targets = sorted(targets, key=lambda x: x[1], reverse=True)[:config.TOP_VOL_COUNT]
            return [t[0] for t in targets]
        except Exception as e:
            print(f"❌ Error Tickers: {e}")
            return []

    def calculate_indicators(self, df):
        if df is None or df.empty: return None
        # EMA
        df['EMA_21'] = df['close'].ewm(span=config.EMA_FAST).mean()
        df['EMA_50'] = df['close'].ewm(span=config.EMA_MID).mean()
        df['EMA_200'] = df['close'].ewm(span=config.EMA_SLOW).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(config.RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(config.RSI_PERIOD).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # Vol SMA & ATR
        df['Vol_SMA'] = df['volume'].rolling(20).mean()
        df['ATR'] = (df['high'] - df['low']).rolling(14).mean()
        
        return df

    def analyze_pair(self, symbol):
        try:
            # 1. MACRO (1H) - Cek Trend
            ohlcv = self.exchange.fetch_ohlcv(symbol, config.TF_MACRO, limit=200)
            df_macro = self.calculate_indicators(pd.DataFrame(ohlcv, columns=['t','o','h','l','c','v']))
            last_macro = df_macro.iloc[-1]
            
            bias = "NEUTRAL"
            trend_score = 0
            
            # Logic: Perfect EMA Alignment
            if (last_macro['c'] > last_macro['EMA_21'] > last_macro['EMA_50'] > last_macro['EMA_200']):
                bias = "BULLISH"; trend_score = 40
            elif (last_macro['c'] < last_macro['EMA_21'] < last_macro['EMA_50'] < last_macro['EMA_200']):
                bias = "BEARISH"; trend_score = 40
                
            if bias == "NEUTRAL": return None # Skip kalau tidak trending

            # 2. MICRO (15m) - Cek Entry
            ohlcv_m = self.exchange.fetch_ohlcv(symbol, config.TF_MICRO, limit=100)
            df_micro = self.calculate_indicators(pd.DataFrame(ohlcv_m, columns=['t','o','h','l','c','v']))
            last_micro = df_micro.iloc[-1]
            
            # Scoring
            vol_score = 0
            vol_ratio = last_micro['v'] / last_micro['Vol_SMA'] if last_micro['Vol_SMA'] > 0 else 1
            if vol_ratio > 2.5: vol_score = 30
            elif vol_ratio > 1.5: vol_score = 15
            
            mom_score = 0
            rsi = last_micro['RSI']
            if bias == "BULLISH" and 40 < rsi < 70: mom_score = 20
            elif bias == "BEARISH" and 30 < rsi < 60: mom_score = 20
            
            total_score = trend_score + vol_score + mom_score
            
            # Tiering
            tier = "C"
            if total_score >= config.SCORE_S: tier = "S"
            elif total_score >= config.SCORE_A: tier = "A"
            elif total_score >= config.SCORE_B: tier = "B"
            else: return None # Buang Tier C
            
            # SL Calculation & Funding
            sl = 0; side = ""
            if bias == "BULLISH":
                sl = last_micro['l'] - (config.ATR_MULTIPLIER * last_micro['ATR'])
                side = "LONG 🟢"
            else:
                sl = last_micro['h'] + (config.ATR_MULTIPLIER * last_micro['ATR'])
                side = "SHORT 🔴"

            # Funding Rate (Optional, skip if error)
            funding = 0
            try: 
                tk = self.exchange.fetch_ticker(symbol)
                funding = tk.get('info', {}).get('funding_rate', 0) # Gate field
            except: pass

            return {
                'symbol': symbol.replace('_', '/'), # Rapikan nama
                'side': side, 'score': total_score, 'tier': tier,
                'price': last_micro['c'], 'sl': sl, 
                'vol': vol_ratio, 'fund': float(funding)*100
            }
        except: 
            return None

    def run_scan(self):
        targets = self.get_top_pairs()
        if not targets: return []
        
        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(self.analyze_pair, s) for s in targets]
            for f in futures:
                if f.result(): results.append(f.result())
                
        # Sortir S -> A -> B
        tier_map = {'S':0, 'A':1, 'B':2}
        results.sort(key=lambda x: (tier_map[x['tier']], -x['score']))
        return results

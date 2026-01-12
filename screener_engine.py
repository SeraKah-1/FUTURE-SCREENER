import ccxt
import pandas as pd
import numpy as np
import config
from concurrent.futures import ThreadPoolExecutor

class Screener:
    def __init__(self):
        print(f"🔌 Connecting to {config.EXCHANGE_ID} (Futures Radar Mode)...")
        # Inisialisasi Exchange (Mode Swap/Futures)
        self.exchange = getattr(ccxt, config.EXCHANGE_ID)({
            'enableRateLimit': True,
            'options': {'defaultType': 'swap'} 
        })

    def get_btc_mood(self):
        """
        [SATPAM PASAR]
        Mengecek kondisi Bitcoin dalam 1 jam terakhir.
        Return: Persentase perubahan harga (float).
        """
        try:
            ohlcv = self.exchange.fetch_ohlcv('BTC/USDT', '1h', limit=2)
            if not ohlcv or len(ohlcv) < 2: return 0.0
            
            open_price = ohlcv[0][1] # Open candle 1 jam lalu
            close_price = ohlcv[-1][4] # Harga sekarang
            
            change = ((close_price - open_price) / open_price) * 100
            return change
        except Exception as e:
            print(f"⚠️ Gagal cek BTC Mood: {e}")
            return 0.0

    def get_top_pairs(self):
        """
        Ambil Top 80 Pair Volume Terbesar.
        Filter: Buang Token Leverage (3L/3S/ETF).
        """
        try:
            tickers = self.exchange.fetch_tickers()
            targets = []
            
            # Kata kunci token sampah/leverage yang harus dibuang
            blacklist = ['3L', '3S', '5L', '5S', 'BEAR', 'BULL', 'HEGIC', 'DAI']

            for s, d in tickers.items():
                # Syarat: Pair USDT dan Volume ada
                if 'USDT' in s and d.get('quoteVolume') and float(d['quoteVolume']) > 0:
                    # Cek Blacklist
                    if any(x in s for x in blacklist):
                        continue
                    targets.append((s, d['quoteVolume']))
            
            # Sortir dari volume terbesar
            targets = sorted(targets, key=lambda x: x[1], reverse=True)[:config.TOP_VOL_COUNT]
            return [t[0] for t in targets]
        except Exception as e:
            print(f"⚠️ Error getting pairs: {e}")
            return []

    def analyze_pair(self, symbol, btc_change):
        try:
            # 1. Ambil Data 15m (50 Candle)
            ohlcv = self.exchange.fetch_ohlcv(symbol, config.TF_RADAR, limit=50)
            if not ohlcv or len(ohlcv) < 50: return None
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # --- LOGIKA INTELEJEN RADAR ---
            
            # A. Hitung Baseline Volume (Rata-rata 20 candle terakhir)
            vol_mean = df['volume'].rolling(20).mean().iloc[-1]
            current_vol = df['volume'].iloc[-1]
            
            # Hindari pembagian dengan nol
            if vol_mean == 0: return None
            
            # B. Hitung RVOL (Relative Volume)
            rvol = current_vol / vol_mean
            
            # GATEKEEPER 1: Kalau volume sepi (< 1.5x), langsung buang.
            if rvol < config.MIN_RVOL: return None

            # C. Analisa Harga & Arah
            last = df.iloc[-1]
            open_p = last['open']
            close_p = last['close']
            
            # Persentase perubahan candle ini
            change_pct = ((close_p - open_p) / open_p) * 100
            abs_change = abs(change_pct)
            
            side = "LONG 🟢" if change_pct > 0 else "SHORT 🔴"
            
            # D. Analisa Trend Simpel (EMA 200) - Hanya Pendukung
            ema_200 = df['close'].ewm(span=200).mean().iloc[-1]
            trend_aligned = False
            if (side == "LONG 🟢" and close_p > ema_200) or (side == "SHORT 🔴" and close_p < ema_200):
                trend_aligned = True
            
            # --- TIERING SYSTEM (KELAS SINYAL) ---
            tier = ""
            if rvol > 5.0 and abs_change > 3.0:
                tier = "👑 KING (Whale Alert)"
            elif rvol > 2.5 and abs_change > 1.5:
                tier = "🔥 HOT (Big Move)"
            else:
                tier = "✅ VALID (Activity)"

            # --- SCORING (0-100) ---
            score = 0
            # Poin Volume
            score += min(rvol * 10, 50) # Max 50 poin dari volume
            # Poin Volatilitas
            score += min(abs_change * 10, 30) # Max 30 poin dari pergerakan harga
            # Poin Trend
            if trend_aligned: score += 20 # Bonus 20 poin jika searah EMA 200
            
            score = int(score)

            # --- BTC GUARD FILTER (SATPAM) ---
            # Aturan: Jangan Long saat BTC Crash, Jangan Short saat BTC Pump.
            # Pengecualian: Tier KING boleh lewat (karena anomali ekstrim).
            
            if "KING" not in tier:
                if btc_change < config.BTC_CRASH_LIMIT and side == "LONG 🟢":
                    return None # Blokir Long
                if btc_change > config.BTC_PUMP_LIMIT and side == "SHORT 🔴":
                    return None # Blokir Short

            # Format Nama Simbol (BTC_USDT -> BTC/USDT)
            clean_symbol = symbol.replace('_', '/')
            
            return {
                'symbol': clean_symbol,
                'side': side,
                'tier': tier,
                'score': score,
                'price': close_p,
                'chg': change_pct,
                'rvol': rvol,
                'trend': "Follow Trend" if trend_aligned else "Counter Trend ⚠️"
            }

        except Exception:
            return None

    def run_scan(self):
        # 1. Cek BTC dulu
        btc_change = self.get_btc_mood()
        btc_status = "BEARISH 🐻" if btc_change < -0.5 else ("BULLISH 🐮" if btc_change > 0.5 else "SIDEWAYS 🦀")
        print(f"🌍 Market Mood: BTC is {btc_status} ({btc_change:+.2f}%)")
        
        # 2. Ambil Daftar Koin
        targets = self.get_top_pairs()
        print(f"🔍 Radar Scanning {len(targets)} Pairs (15m Volume Anomaly)...")
        
        results = []
        # 3. Multithreading Scan
        with ThreadPoolExecutor(max_workers=5) as executor:
            # Kita lempar btc_change ke dalam fungsi agar setiap pair "sadar" kondisi market
            futures = [executor.submit(self.analyze_pair, s, btc_change) for s in targets]
            for f in futures:
                res = f.result()
                if res: results.append(res)
        
        # Sortir hasil berdasarkan Score tertinggi
        return sorted(results, key=lambda x: x['score'], reverse=True)

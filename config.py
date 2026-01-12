import os

# --- TELEGRAM CONFIG ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# --- EXCHANGE SETTINGS ---
EXCHANGE_ID = 'gate'     # Exchange yang dipakai
TOP_VOL_COUNT = 100      # 100 Pair Terbesar (Sweet Spot Liquidity)
TF_RADAR = '15m'         # Timeframe Wajib (Cukup cepat, cukup valid)

# --- THRESHOLD (BATAS AMBANG) ---
MIN_RVOL = 1.5           # Minimal Volume 1.5x rata-rata baru dilirik
MIN_SCORE = 50           # Filter "Sweet Spot": Buang sinyal lemah, ambil yang berotot

# --- BTC GUARD (SATPAM) ---
BTC_CRASH_LIMIT = -1.0   # Jika BTC turun > 1%, Blokir Long (kecuali King)
BTC_PUMP_LIMIT = 1.0     # Jika BTC naik > 1%, Blokir Short (kecuali King)

import os

# --- TELEGRAM CONFIG ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# --- EXCHANGE SETTINGS ---
EXCHANGE_ID = 'gate'     # Menggunakan Gate.io
TOP_VOL_COUNT = 100       # Scan 80 Koin dengan Volume Terbesar
TF_RADAR = '15m'         # Timeframe Wajib untuk Radar

# --- THRESHOLD (BATAS AMBANG) ---
MIN_RVOL = 1.5           # Minimal Volume 1.5x dari rata-rata untuk dilirik
BTC_CRASH_LIMIT = -1.0   # Batas BTC Crash (%) untuk memblokir sinyal Long
BTC_PUMP_LIMIT = 1.0     # Batas BTC Pump (%) untuk memblokir sinyal Short

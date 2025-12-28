import os

# --- TELEGRAM ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# --- EXCHANGE ---
EXCHANGE_ID = 'gate'     # Gate.io (IP Safe)
TOP_VOL_COUNT = 35       # Scan 35 Koin Terbesar
TF_MACRO = '1h'          # Trend Utama
TF_MICRO = '15m'         # Titik Entry

# --- AMBANG BATAS (FILTER) ---
MIN_SCORE = 60           # HANYA TAMPILKAN JIKA SCORE DI ATAS 60
                         # Ubah jadi 50 jika ingin lebih banyak sinyal (tapi kualitas turun)

# --- INDIKATOR ---
EMA_FAST = 21
EMA_MID = 50
EMA_SLOW = 200
RSI_PERIOD = 14
ATR_MULTIPLIER = 1.5     # Jarak Stop Loss (1.5x ATR)

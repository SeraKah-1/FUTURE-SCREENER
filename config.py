import os

# --- TELEGRAM ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# --- EXCHANGE ---
EXCHANGE_ID = 'gate' 
TOP_VOL_COUNT = 50       # Scan 50 koin teratas volume terbesar
TF_TRADE = '1h'          # FOKUS UTAMA: Timeframe 1 Jam (bisa ganti '4h')

# --- INDIKATOR ---
EMA_FAST = 21
EMA_MID = 50
EMA_SLOW = 200
RSI_PERIOD = 14

# --- FILTER SELEKTIF ---
# Skor minimal agar sinyal dikirim (0-100)
# Kita set tinggi (75) biar yang muncul benar-benar yang chart-nya bagus
MIN_SCORE = 75

import os

# --- TELEGRAM ---
# Ambil dari Secrets GitHub nanti
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# --- EXCHANGE (ANTI BLOKIR) ---
# Kita pakai Gate.io Swap (Futures) karena IP US aman disini
EXCHANGE_ID = 'gate' 
TOP_VOL_COUNT = 30       # Scan Top 30 Koin
TF_MACRO = '1h'          # Trend Setup
TF_MICRO = '15m'         # Entry Trigger

# --- PARAMETER TEKNIKAL ---
EMA_FAST = 21
EMA_MID = 50
EMA_SLOW = 200
RSI_PERIOD = 14
ATR_MULTIPLIER = 1.5     # Jarak Stop Loss (1.5x ATR)

# --- TIER SCORING ---
SCORE_S = 85
SCORE_A = 65
SCORE_B = 50

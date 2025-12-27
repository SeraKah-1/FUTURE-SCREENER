import os

# --- TELEGRAM ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# --- EXCHANGE ---
EXCHANGE_ID = 'gate' 
TOP_VOL_COUNT = 30       
TF_MACRO = '1h'          
TF_MICRO = '15m'         

# --- INDIKATOR ---
EMA_FAST = 21
EMA_MID = 50
EMA_SLOW = 200
RSI_PERIOD = 14
ATR_PERIOD = 14
ATR_MULTIPLIER = 1.5     

# --- UPDATE: LONGGARKAN SCORE ---
# Turunkan threshold biar lebih banyak sinyal masuk saat testing
SCORE_S = 85
SCORE_A = 60  # Turun dari 65
SCORE_B = 30  # Turun drastis dari 50 (biar yg jelek dikit tetap masuk)

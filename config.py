import os

# --- KONEKSI TELEGRAM (Diambil dari Secrets GitHub) ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# --- SETTING EXCHANGE (ANTI BLOKIR) ---
# Kita pakai Gate.io (Swap/Futures) karena ramah terhadap IP Server USA
EXCHANGE_ID = 'gate' 
TOP_VOL_COUNT = 30       # Scan Top 30 Koin Terbesar
TF_MACRO = '1h'          # Timeframe Besar (Menentukan Trend)
TF_MICRO = '15m'         # Timeframe Kecil (Menentukan Entry/Trigger)

# --- INDIKATOR TEKNIKAL ---
EMA_FAST = 21
EMA_MID = 50
EMA_SLOW = 200
RSI_PERIOD = 14
ATR_PERIOD = 14
ATR_MULTIPLIER = 1.5     # Jarak Stop Loss (1.5x ATR)

# --- SISTEM SKORING TIER LIST ---
# Total poin maksimal = 100
SCORE_S = 85  # Tier S (Prioritas)
SCORE_A = 65  # Tier A (Bagus)
SCORE_B = 50  # Tier B (Spekulatif)

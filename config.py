import os

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# --- EXCHANGE: GATE.IO ---
EXCHANGE_ID = 'gate' 
TOP_VOL_COUNT = 40       # Scan 40 Koin Terbesar (Biar peluang lebih banyak)
TF_MACRO = '1h'          # Trend Bias
TF_MICRO = '15m'         # Entry Trigger

# --- FILTER KUALITAS ---
MIN_SCORE = 60           # Sinyal divalidasi jika skor > 55
                         # (Angka 55 adalah Sweet Spot: Tidak terlalu ketat, tidak terlalu longgar)

# --- INDIKATOR ---
EMA_MID = 50             # Garis Trend Utama
RSI_PERIOD = 14
ATR_MULTIPLIER = 1.5     # Jarak Stop Loss

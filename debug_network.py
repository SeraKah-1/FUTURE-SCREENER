import ccxt
import requests
import json

def check_ip():
    try:
        # Cek IP Address Server GitHub Actions
        response = requests.get('https://api.ipify.org?format=json')
        ip_data = response.json()
        print(f"🌍 IP Server GitHub: {ip_data['ip']}")
        
        # Cek Lokasi IP (Negara)
        loc = requests.get(f"https://ipapi.co/{ip_data['ip']}/json/")
        print(f"📍 Lokasi Server: {loc.json().get('country_name', 'Unknown')}")
    except Exception as e:
        print(f"⚠️ Gagal cek IP: {e}")

def test_exchange_connection(exchange_id):
    print(f"\n🔌 Testing Connection to: {exchange_id.upper()}...")
    try:
        # Init Exchange
        exchange = getattr(ccxt, exchange_id)()
        
        # 1. Cek Server Time (Ping Ringan)
        time = exchange.fetch_time()
        print(f"   ✅ Server Time: OK (Latency OK)")
        
        # 2. Cek Harga BTC (Ping Berat)
        ticker = exchange.fetch_ticker('BTC/USDT')
        print(f"   ✅ Fetch Price BTC/USDT: {ticker['last']}")
        
        # 3. Cek Candle/OHLCV (Data Berat)
        candles = exchange.fetch_ohlcv('BTC/USDT', '1h', limit=3)
        print(f"   ✅ Fetch Candle Data: {len(candles)} candles received.")
        print(f"      [Sample Data]: {candles[0]}")
        print(f"🎉 KESIMPULAN: {exchange_id.upper()} TIDAK DIBLOKIR!")
        
    except Exception as e:
        print(f"❌ GAGAL / DIBLOKIR: {e}")
        print(f"   (Kemungkinan IP Server GitHub di-blacklist oleh {exchange_id})")

if __name__ == "__main__":
    print("=== MULAI DIAGNOSA JARINGAN ===")
    check_ip()
    
    # Tes Gate.io (Target Utama)
    test_exchange_connection('gate')
    
    # Tes MEXC (Rencana Cadangan - Biasanya paling aman)
    test_exchange_connection('mexc')
    
    print("\n=== SELESAI ===")

import redis
import os
from datetime import datetime

# Configurația Redis din variabile de mediu
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))

try:
    # Conectare la Redis
    db = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
    
    # Verifică conexiunea
    db.ping()
    
    # Resetează contorul
    db.set('ipdata_api_request_count', 0)
    
    # Log pentru monitoring
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] Contorul 'ipdata_api_request_count' a fost resetat cu succes.")
    print(f"Redis server: {redis_host}:{redis_port}")
    
except redis.ConnectionError as e:
    print(f"Eroare la conectarea la Redis ({redis_host}:{redis_port}): {e}")
    exit(1)
except Exception as e:
    print(f"Eroare necunoscută: {e}")
    exit(1)
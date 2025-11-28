# IPData Geolocation API Service

Un serviciu de geolocalizare IP de înaltă performanță construit cu FastAPI, Redis și Elasticsearch, capabil să proceseze 10.000-100.000 de interogări pe minut.

## 🚀 Caracteristici

- **Arhitectură scalabilă**: 10 instanțe FastAPI balansate cu HAProxy
- **Caching multi-nivel**: Redis (cache L1) → Elasticsearch (storage persistent) → IPData.co API (fallback)
- **Performanță înaltă**: 10.000-100.000 queries/minut
- **Containerizare completă**: Docker și Docker Compose pentru deployment ușor
- **Monitorizare**: Statistici în timp real și health checks
- **Rate limiting**: Control automat al request-urilor către API extern
- **Web UI**: Interfață web pentru testare manuală

## 📋 Arhitectură

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼ Port 80
┌─────────────┐
│   HAProxy   │ (Load Balancer)
└──────┬──────┘
       │
       ▼ Round-robin
┌─────────────────────────────────┐
│  10x IPData Containers          │
│  (ipdata-1 ... ipdata-10)       │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│          Redis Cache            │ ◄── Cache L1 (TTL: 24h)
└─────────────────────────────────┘
         │
         ▼ (cache miss)
┌─────────────────────────────────┐
│       Elasticsearch             │ ◄── Storage persistent
└─────────────────────────────────┘
         │
         ▼ (data not found)
┌─────────────────────────────────┐
│       IPData.co API             │ ◄── External API (rate limited)
└─────────────────────────────────┘
```

## 🛠️ Instalare

### Prerequisite

- Docker și Docker Compose
- Cont IPData.co pentru API key
- Elasticsearch cluster funcțional (opțional - sistemul funcționează și fără)

### Configurare

1. **Clonează repository-ul**:
```bash
git clone https://github.com/sm26449/ipdata.git
cd ipdata
```

2. **Configurează variabilele de mediu**:
```bash
cp .env.example .env
# Editează .env cu datele tale
nano .env
```

3. **Adaugă certificatul Elasticsearch**:
```bash
# Copiază certificatul CA al Elasticsearch în directorul proiectului
cp /path/to/elasticsearch/ca.crt ./ca.crt
```

## 🚀 Deployment

### Docker Compose (Recomandat)

```bash
# Build și pornire toate serviciile
docker-compose up -d

# Verifică statusul
docker-compose ps

# Vezi logs
docker-compose logs -f

# Stop toate serviciile
docker-compose down
```

### Build Manual

```bash
# Build imagine Docker
docker build -t ipdata:latest .

# Rulează un singur container
docker run -d \
  -p 8000:80 \
  -e REDIS_HOST=redis \
  -e IPDATA_API_KEY=your_key \
  --name ipdata \
  ipdata:latest
```

## 📊 API Endpoints

### Get IP Information
```bash
GET /ip/{ip_address}

# Exemplu
curl http://localhost/ip/8.8.8.8

# Cu pretty print
curl "http://localhost/ip/8.8.8.8?pretty=true"

# Doar anumite câmpuri
curl "http://localhost/ip/8.8.8.8?fields=city,country_name,latitude,longitude"
```

### Health Check
```bash
GET /health

curl http://localhost/health
```

### Statistics
```bash
GET /stats

curl http://localhost/stats
```

### Web Interface
Accesează `http://localhost` în browser pentru interfața web.

### HAProxy Stats
Accesează `http://localhost:8404/stats` pentru statistici HAProxy.

## 📈 Performanță

Sistemul este optimizat pentru:
- **10.000-100.000 queries/minut** cu caching eficient
- **Sub 50ms latență** pentru date din cache
- **99.9% uptime** cu auto-restart și health checks
- **Scalare orizontală** - adaugă mai multe containere după necesitate

## 🔧 Monitorizare și Mentenanță

### Verificare Health
```bash
# Health check toate containerele
docker-compose exec ipdata-1 curl localhost/health

# Statistici Redis
docker-compose exec redis redis-cli info stats

# HAProxy stats
curl http://localhost:8404/stats
```

### Reset Manual Statistici
```bash
# Rulează script-ul de reset
docker-compose exec stats-reset python /app/reset_requests_made.py

# Sau direct din host
python reset_requests_made.py
```

### Logs
```bash
# Toate serviciile
docker-compose logs -f

# Doar un serviciu specific
docker-compose logs -f haproxy
docker-compose logs -f ipdata-1
docker-compose logs -f redis
```

## 📁 Structura Proiectului

```
ipdata/
├── .gitignore             # Exclude fișiere sensibile
├── CLAUDE.md              # Documentație pentru Claude
├── README.md              # Documentația principală
├── docker-compose.yml     # Orchestrare servicii
├── Dockerfile             # Image principal IPData
├── Dockerfile.reset       # Image pentru reset statistici
├── main.py                # Aplicația FastAPI optimizată
├── reset_requests_made.py # Script reset contoare
├── requirements.txt       # Dependențe Python
├── .env.example          # Template variabile mediu
├── ca.crt                # Certificat Elasticsearch (nu în git)
├── haproxy/
│   └── haproxy-docker.cfg # Config pentru Docker
└── elasticsearch/        # Template-uri și scripturi ES (opționale)
    └── add_template_to_elasticsearch
```

## 🔐 Securitate

- **Nu commite niciodată `.env` cu date reale**
- Folosește secrets management în producție
- Actualizează regular dependențele
- Monitorizează rate limiting pentru API extern
- Configurează firewall pentru porturile expuse

## 🐛 Troubleshooting

### Container nu pornește
```bash
# Verifică logs
docker-compose logs ipdata-1

# Verifică conectivitate Redis
docker-compose exec ipdata-1 redis-cli -h redis ping

# Verifică Elasticsearch
curl -u elastic:password https://elasticsearch:9200
```

### Cache nu funcționează
```bash
# Verifică Redis
docker-compose exec redis redis-cli
> KEYS *
> GET some_ip_address

# Clear cache
docker-compose exec redis redis-cli FLUSHALL
```

### HAProxy nu balansează
```bash
# Verifică backend-uri
curl http://localhost:8404/stats

# Test direct container
docker-compose exec ipdata-1 curl localhost/health
```

### Elasticsearch nu este disponibil
Sistemul funcționează perfect și fără Elasticsearch - datele vor fi servite din Redis cache și IPData API:
```bash
# Verifică dacă serviciul funcționează fără ES
curl http://localhost/ip/8.8.8.8
# Răspuns: {"source": "IPData API", ...}
```

## 📝 Dezvoltare

### Modificări cod
```bash
# Rebuild după modificări
docker-compose build

# Restart servicii
docker-compose restart
```

### Testare locală
```bash
# Rulează doar Redis pentru dezvoltare
docker-compose up redis

# Pornește aplicația local
uvicorn main:app --reload --port 8000
```

## 🤝 Contribuții

Contribuțiile sunt binevenite! Te rog să:
1. Fork-uiește repository-ul
2. Creează un branch pentru feature (`git checkout -b feature/AmazingFeature`)
3. Commit modificările (`git commit -m 'Add some AmazingFeature'`)
4. Push la branch (`git push origin feature/AmazingFeature`)
5. Deschide un Pull Request

## 📄 Licență

Acest proiect este licențiat sub MIT License - vezi fișierul LICENSE pentru detalii.

## 🙏 Mulțumiri

- [FastAPI](https://fastapi.tiangolo.com/) pentru framework-ul web excelent
- [IPData.co](https://ipdata.co/) pentru serviciul de geolocalizare
- [Redis](https://redis.io/) pentru caching performant
- [Elasticsearch](https://elastic.co/) pentru stocare și căutare
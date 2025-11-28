# Elasticsearch Tools

O colecție de instrumente pentru îmbogățirea datelor cu informații de geolocalizare IP în ecosistemul Elastic Stack.

## Componente

### 1. [IPData Geolocation API Microservice](./ipdata-geolocation-api-microservice/)

Serviciu de geolocalizare IP de înaltă performanță construit cu FastAPI, Redis și Elasticsearch.

**Caracteristici principale:**
- Arhitectură scalabilă cu 10 instanțe și load balancing HAProxy
- Caching multi-nivel: Redis → Elasticsearch → IPData.co API
- 10.000-100.000 queries/minut
- Threat intelligence integrat (VPN, Tor, proxy, datacenter detection)
- Web UI pentru testare manuală

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼ Port 80
┌─────────────┐
│   HAProxy   │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────┐
│  10x FastAPI Containers         │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│   Redis Cache (TTL: 24h)        │
└────────┬────────────────────────┘
         │
         ▼ (cache miss)
┌─────────────────────────────────┐
│   Elasticsearch (persistent)    │
└────────┬────────────────────────┘
         │
         ▼ (not found)
┌─────────────────────────────────┐
│   IPData.co API (external)      │
└─────────────────────────────────┘
```

### 2. [Logstash Geolocation Filter](./logstash-query-geolocation-using-api/)

Configurare Logstash pentru îmbogățirea automată a evenimentelor cu date de geolocalizare.

**Caracteristici principale:**
- Integrare nativă cu Elasticsearch pentru cache lookup
- Fallback automat la microserviciul IPData
- Extrage informații geografice, ASN și threat intelligence
- Gestionare graceful a limitelor de rate

## Quick Start

### 1. Pornește microserviciul IPData

```bash
cd ipdata-geolocation-api-microservice

# Configurează variabilele de mediu
cp .env.example .env
nano .env  # Adaugă IPDATA_API_KEY și celelalte credențiale

# Pornește serviciile
docker-compose up -d

# Verifică funcționarea
curl http://localhost/ip/8.8.8.8
```

### 2. Configurează Logstash

```bash
cd logstash-query-geolocation-using-api

# Copiază filtrul
cp filter.conf /etc/logstash/conf.d/50-geoip-filter.conf

# Editează conexiunile (Elasticsearch, IPData service)
nano /etc/logstash/conf.d/50-geoip-filter.conf

# Restart Logstash
systemctl restart logstash
```

## Exemple de Utilizare

### Query direct API
```bash
# Informații complete
curl http://localhost/ip/8.8.8.8

# Format pretty
curl "http://localhost/ip/8.8.8.8?pretty=true"

# Doar anumite câmpuri
curl "http://localhost/ip/8.8.8.8?fields=city,country_name,threat"
```

### Statistici serviciu
```bash
curl http://localhost/stats
```

### Verificare health
```bash
curl http://localhost/health
```

## Date Disponibile

Pentru fiecare IP interogat, sistemul returnează:

| Categorie | Informații |
|-----------|------------|
| **Geografice** | Țară, Oraș, Regiune, Continent, Coordonate, Membru UE |
| **Rețea** | ASN, Organizație, Domeniu, Rută, Tip |
| **Threat Intel** | VPN, Tor, Proxy, Datacenter, Known Attacker, Trust Score |
| **Altele** | Timezone, Currency, Languages, Calling Code |

## Cerințe

- Docker și Docker Compose
- Elasticsearch 7.x sau 8.x
- Logstash 7.x sau 8.x (pentru filtru)
- Cont [IPData.co](https://ipdata.co) pentru API key

## Structura Repository

```
elasticsearch-tools/
├── README.md                              # Acest fișier
├── ipdata-geolocation-api-microservice/   # Microserviciu FastAPI
│   ├── main.py                            # Aplicația principală
│   ├── docker-compose.yml                 # Orchestrare servicii
│   ├── Dockerfile                         # Container image
│   ├── haproxy/                           # Load balancer config
│   └── README.md                          # Documentație detaliată
└── logstash-query-geolocation-using-api/  # Filtru Logstash
    ├── filter.conf                        # Configurare filtru
    └── README.md                          # Documentație utilizare
```

## Licență

MIT License

## Contribuții

Contribuțiile sunt binevenite! Deschide un Issue sau Pull Request.

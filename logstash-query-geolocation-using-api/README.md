# Logstash Geolocation Filter using IPData Microservice

Configurare Logstash pentru îmbogățirea datelor cu informații de geolocalizare IP, folosind microserviciul [IPData Geolocation API](../ipdata-geolocation-api-microservice/).

## Descriere

Acest filtru Logstash adaugă automat informații de geolocalizare la evenimentele care conțin adrese IP. Folosește o strategie de interogare în cascadă:

1. **Elasticsearch cache** - verifică dacă IP-ul există deja în index-ul `ipdata-*`
2. **HTTP request** - dacă nu există, interogează microserviciul IPData local
3. **Fallback graceful** - gestionează cazurile când limita de request-uri este depășită

## Arhitectură

```
┌─────────────┐     ┌─────────────────┐     ┌──────────────────────┐
│  Logstash   │────►│  Elasticsearch  │────►│ Rezultat din cache   │
│   Event     │     │   (ipdata-*)    │     └──────────────────────┘
└──────┬──────┘     └─────────────────┘
       │                    │
       │              (cache miss)
       │                    │
       ▼                    ▼
┌─────────────────────────────────────┐     ┌──────────────────────┐
│    IPData Microservice              │────►│ Date noi geolocație  │
│    http://IPDATA_SERVICE_HOST:8000  │     └──────────────────────┘
└─────────────────────────────────────┘
```

## Structura Câmpurilor GeoIP

Filtrul populează următoarele câmpuri în structura `[geoip]`:

### Informații Geografice
| Câmp | Descriere |
|------|-----------|
| `[geoip][ip]` | Adresa IP |
| `[geoip][country_code]` | Codul țării (ex: RO, US) |
| `[geoip][country_name]` | Numele țării |
| `[geoip][city]` | Orașul |
| `[geoip][region]` | Regiunea/Județul |
| `[geoip][continent_code]` | Codul continentului |
| `[geoip][is_eu]` | Membru UE (true/false) |

### Informații ASN
| Câmp | Descriere |
|------|-----------|
| `[geoip][asn][asn]` | Numărul AS |
| `[geoip][asn][name]` | Numele organizației |
| `[geoip][asn][domain]` | Domeniul organizației |
| `[geoip][asn][route]` | Ruta de rețea |
| `[geoip][asn][type]` | Tipul (isp, business, hosting) |

### Informații Threat Intelligence
| Câmp | Descriere |
|------|-----------|
| `[geoip][threat][is_anonymous]` | IP anonim |
| `[geoip][threat][is_bogon]` | IP bogon (rezervat) |
| `[geoip][threat][is_datacenter]` | IP de datacenter |
| `[geoip][threat][is_icloud_relay]` | iCloud Private Relay |
| `[geoip][threat][is_known_abuser]` | Cunoscut ca abuzator |
| `[geoip][threat][is_known_attacker]` | Cunoscut ca atacator |
| `[geoip][threat][is_proxy]` | Proxy |
| `[geoip][threat][is_threat]` | Amenințare generală |
| `[geoip][threat][is_tor]` | Nod Tor |
| `[geoip][threat][is_vpn]` | VPN |

### Scoruri Threat
| Câmp | Descriere |
|------|-----------|
| `[geoip][threat][scores][proxy_score]` | Scor probabilitate proxy |
| `[geoip][threat][scores][vpn_score]` | Scor probabilitate VPN |
| `[geoip][threat][scores][threat_score]` | Scor amenințare generală |
| `[geoip][threat][scores][trust_score]` | Scor de încredere |

## Instalare

### Prerequisite

- Logstash 7.x sau 8.x
- Plugin-uri Logstash:
  - `logstash-filter-elasticsearch`
  - `logstash-filter-http`
- Acces la cluster Elasticsearch
- [IPData Geolocation Microservice](../ipdata-geolocation-api-microservice/) rulând

### Configurare

1. **Copiază filtrul în directorul Logstash**:
```bash
cp filter.conf /etc/logstash/conf.d/50-geoip-filter.conf
```

2. **Modifică parametrii de conexiune**:

Editează `filter.conf` și actualizează:
```ruby
elasticsearch {
  hosts => [ "https://YOUR_ES_HOST:9200" ]
  password => "YOUR_PASSWORD"
  user => "elastic"
  ssl_certificate_authorities => "/etc/logstash/certs/ca.crt"
}

http {
  url => "http://YOUR_IPDATA_SERVICE:8000/ip/%{[ipaddr]}"
}
```

3. **Copiază certificatul Elasticsearch**:
```bash
cp /path/to/elasticsearch/ca.crt /etc/logstash/certs/ca.crt
```

4. **Restart Logstash**:
```bash
systemctl restart logstash
```

## Utilizare

### Câmpuri de Input Acceptate

Filtrul procesează automat evenimentele care conțin:
- `[ipaddr]` - câmpul principal pentru adresa IP
- `[client_ip]` - redenumit automat în `[ipaddr]`

### Exemplu Pipeline Complet

```ruby
input {
  beats {
    port => 5044
  }
}

filter {
  # Extrage IP-ul din log
  grok {
    match => { "message" => "%{IP:client_ip}" }
  }

  # Include filtrul de geolocalizare
  # (conținutul din filter.conf)
}

output {
  elasticsearch {
    hosts => ["https://elasticsearch:9200"]
    index => "logs-%{+YYYY.MM.dd}"
  }
}
```

### Tag-uri Adăugate

| Tag | Descriere |
|-----|-----------|
| `request_limit_exceeded` | Limita de request-uri IPData depășită |
| `is_eu_null` | Câmpul is_eu nu a putut fi determinat |
| `blacklist` | Adăugat împreună cu is_eu_null |

## Troubleshooting

### Filtrul nu adaugă date geolocație

1. Verifică că există câmpul `[ipaddr]` sau `[client_ip]`:
```bash
# În Kibana Dev Tools
GET logs-*/_search
{
  "query": { "exists": { "field": "ipaddr" } }
}
```

2. Verifică conectivitatea la microserviciul IPData:
```bash
curl http://IPDATA_SERVICE_HOST:8000/ip/8.8.8.8
```

### Tag-ul request_limit_exceeded apare frecvent

Microserviciul a atins limita zilnică de request-uri către IPData.co API.

Soluții:
- Așteaptă reset-ul zilnic (miezul nopții)
- Mărește limita în configurația microserviciului
- Verifică dacă cache-ul Redis funcționează corect

### Erori de conexiune Elasticsearch

Verifică:
```bash
# Testează conexiunea
curl -u elastic:password https://elasticsearch:9200

# Verifică certificatul
openssl s_client -connect elasticsearch:9200 -CAfile /etc/logstash/certs/ca.crt
```

## Dependențe

- [IPData Geolocation API Microservice](../ipdata-geolocation-api-microservice/) - serviciul de geolocalizare
- Elasticsearch - pentru cache persistent
- Redis - pentru cache rapid (prin microserviciu)

## Licență

MIT License

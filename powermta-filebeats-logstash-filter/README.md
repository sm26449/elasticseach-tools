# PowerMTA Filebeat + Logstash Pipeline

Pipeline completă pentru colectarea și procesarea log-urilor PowerMTA folosind Filebeat și Logstash, cu stocare în Elasticsearch și MariaDB.

## Descriere

Această configurație permite:
- Colectarea log-urilor de delivery/bounce din PowerMTA
- Parsarea CSV-urilor generate de PowerMTA
- Decodarea header-urilor MIME (From, Subject)
- Verificarea subscriber status via Redis
- Alertare pe erori SMTP specifice
- Stocare în Elasticsearch (pentru vizualizare Kibana)
- Stocare în MariaDB (pentru procesare aplicație)

## Arhitectură

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PowerMTA Server                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐ │
│  │  PowerMTA       │───►│  CSV Logs       │───►│   Filebeat      │ │
│  │  (acct-file)    │    │  sender2elastic │    │                 │ │
│  └─────────────────┘    └─────────────────┘    └────────┬────────┘ │
└────────────────────────────────────────────────────────┼──────────┘
                                                         │ SSL/TLS
                                                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Logstash Server                             │
│  ┌─────────────────┐                                               │
│  │  Logstash       │                                               │
│  │  - CSV parse    │                                               │
│  │  - MIME decode  │                                               │
│  │  - Redis lookup │                                               │
│  └────────┬────────┘                                               │
│           │                                                         │
│     ┌─────┴─────┬─────────────┐                                    │
│     ▼           ▼             ▼                                    │
│  ┌──────┐  ┌─────────┐  ┌──────────┐                              │
│  │Redis │  │MariaDB  │  │Elastic   │                              │
│  │lookup│  │(queue)  │  │search    │                              │
│  └──────┘  └─────────┘  └──────────┘                              │
└─────────────────────────────────────────────────────────────────────┘
```

## Structura Proiectului

```
powermta-filebeats-logstash-filter/
├── README.md                           # Acest fișier
├── powermta_host/                      # Fișiere pentru serverul PowerMTA
│   ├── filebeats.yml                   # Configurare Filebeat
│   └── powermta-logging.conf           # Configurare logging PowerMTA
└── logstash_host/                      # Fișiere pentru serverul Logstash
    └── powermta.conf                   # Pipeline Logstash complet
```

## Câmpuri Extrase

### Date Delivery
| Câmp | Descriere |
|------|-----------|
| `type` | Tipul înregistrării (d=delivery, b=bounce, t=transient) |
| `timeLogged` | Timestamp log |
| `timeQueued` | Timestamp intrare în coadă |
| `totalSecondsQueued` | Timp în coadă (secunde) |
| `orig` | Adresa expeditor |
| `rcpt` | Adresa destinatar |
| `vmta` | Virtual MTA folosit |
| `jobId` | ID job PowerMTA |
| `envId` | Envelope ID |

### Status Delivery
| Câmp | Descriere |
|------|-----------|
| `dsnAction` | Acțiune DSN (delivered, failed, delayed) |
| `dsnStatus` | Cod status DSN |
| `dsnDiag` | Mesaj diagnostic |
| `dsnMta` | MTA destinație |
| `bounceCat` | Categorie bounce (bad-mailbox, spam-related, etc.) |

### Informații Rețea
| Câmp | Descriere |
|------|-----------|
| `dlvSourceIp` | IP sursă delivery |
| `dlvDestinationIp` | IP destinație |
| `dlvType` | Tip delivery |

### Header-uri Email
| Câmp | Descriere |
|------|-----------|
| `header_from` | Header From complet |
| `header_from_name` | Numele din From |
| `header_from_email` | Email din From |
| `header_subject` | Subject (decodat MIME) |
| `tracking-id` | ID tracking custom |
| `header_serverId` | Server ID custom |

### Câmpuri Adăugate de Logstash
| Câmp | Descriere |
|------|-----------|
| `isSubscriber` | Boolean - destinatarul este subscriber activ |
| `domain` | Domeniul extras din From |

## Instalare

### 1. Configurare PowerMTA

Adaugă configurația de logging în PowerMTA:

```bash
# Copiază configurația
cp powermta_host/powermta-logging.conf /etc/pmta/

# Include în config principal
echo 'include /etc/pmta/powermta-logging.conf' >> /etc/pmta/config

# Restart PowerMTA
systemctl restart pmta
```

### 2. Instalare Filebeat pe PowerMTA Server

```bash
# Instalează Filebeat
curl -L -O https://artifacts.elastic.co/downloads/beats/filebeat/filebeat-8.x.x-amd64.deb
dpkg -i filebeat-8.x.x-amd64.deb

# Copiază configurația
cp powermta_host/filebeats.yml /etc/filebeat/filebeat.yml

# Editează și înlocuiește placeholders
nano /etc/filebeat/filebeat.yml
# Înlocuiește: LOGSTASH_HOST

# Copiază certificatele SSL
cp ca.crt /etc/filebeat/
cp filebeat.crt /etc/filebeat/
cp filebeat.key /etc/filebeat/

# Pornește Filebeat
systemctl enable filebeat
systemctl start filebeat
```

### 3. Configurare Logstash

```bash
# Instalează plugin-uri necesare
/usr/share/logstash/bin/logstash-plugin install logstash-output-exec
/usr/share/logstash/bin/logstash-plugin install logstash-output-jdbc

# Copiază MariaDB connector
cp mariadb-connector-java.jar /usr/share/logstash/logstash-core/lib/jars/

# Copiază pipeline config
cp logstash_host/powermta.conf /etc/logstash/conf.d/

# Editează și înlocuiește placeholders
nano /etc/logstash/conf.d/powermta.conf
```

### 4. Placeholders de Înlocuit

#### În `filebeats.yml`:
| Placeholder | Descriere |
|-------------|-----------|
| `LOGSTASH_HOST` | IP/hostname server Logstash |

#### În `powermta.conf`:
| Placeholder | Descriere |
|-------------|-----------|
| `ELASTICSEARCH_HOST_1/2/3` | IP-uri noduri Elasticsearch |
| `ELASTICSEARCH_USER` | User Elasticsearch (ex: logstash_writer) |
| `ELASTICSEARCH_PASSWORD` | Parola Elasticsearch |
| `MARIADB_HOST` | IP/hostname server MariaDB |
| `DATABASE_NAME` | Numele bazei de date |
| `MARIADB_USER` | User MariaDB |
| `MARIADB_PASSWORD` | Parola MariaDB |

## Categorii Bounce

PowerMTA categorizează bounce-urile automat:

| Categorie | Descriere |
|-----------|-----------|
| `success` | Delivery reușit |
| `bad-mailbox` | Căsuță inexistentă |
| `bad-domain` | Domeniu invalid |
| `inactive-mailbox` | Căsuță inactivă |
| `quota-issues` | Căsuță plină |
| `spam-related` | Blocat ca spam |
| `policy-related` | Blocat de politici |
| `virus-related` | Detectat virus |
| `content-related` | Conținut respins |
| `routing-errors` | Erori de rutare |
| `protocol-errors` | Erori protocol SMTP |
| `invalid-sender` | Sender invalid |
| `relaying-issues` | Probleme relay |
| `no-answer-from-host` | MX nu răspunde |
| `bad-connection` | Conexiune eșuată |
| `message-expired` | Mesaj expirat |

## Alertare SMTP Errors

Pipeline-ul detectează automat erori SMTP specifice și adaugă tag-ul `SMTP_ERROR`:

- Yahoo TSS04, TSS05, TSS11, IPTS04, IPTS05
- Yahoo PH01 policy rejection

Pentru alertare, editează script-ul `/etc/logstash/alert.py`.

## Redis Subscriber Lookup

Pipeline-ul verifică dacă destinatarul este subscriber activ:

```ruby
# Conectare Redis local
Redis.new(host: "localhost", port: 6379)

# Verificare în set-ul "subscriber_data"
redis.sismember("subscriber_data", rcpt)
```

Asigură-te că Redis rulează și conține set-ul `subscriber_data` cu adresele email ale subscriberilor.

## Outputs

### Elasticsearch
- Index pattern: `pmta-YYYY.MM.dd`
- Permite vizualizare în Kibana

### MariaDB
- Tabel: `que2`
- Coloane: `queDataType`, `totalSecondsQueued`, `isSubscriber`, `jobId`, `queDataBody`, `queLogDate`

### Metrics
- Rate de procesare afișat în stdout la fiecare 60 secunde

## Troubleshooting

### Filebeat nu trimite date

```bash
# Verifică logs Filebeat
journalctl -u filebeat -f

# Test conectivitate la Logstash
openssl s_client -connect LOGSTASH_HOST:5044 -CAfile /etc/filebeat/ca.crt

# Verifică fișierele CSV
ls -la /var/log/pmta/sender2elastic_log-*.csv
```

### Logstash nu procesează

```bash
# Verifică logs
tail -f /var/log/logstash/logstash-plain.log

# Test pipeline
/usr/share/logstash/bin/logstash -f /etc/logstash/conf.d/powermta.conf --config.test_and_exit

# Verifică Redis
redis-cli ping
redis-cli SCARD subscriber_data
```

### Date nu ajung în Elasticsearch

```bash
# Verifică indexul
curl -u USER:PASS "https://ELASTICSEARCH:9200/pmta-*/_count"

# Verifică mapping
curl -u USER:PASS "https://ELASTICSEARCH:9200/pmta-*/_mapping"
```

## Dependențe

- PowerMTA 4.x sau 5.x
- Filebeat 7.x sau 8.x
- Logstash 7.x sau 8.x
- Elasticsearch 7.x sau 8.x
- Redis 5.x+
- MariaDB 10.x+ (opțional)
- Ruby gem `mail` pentru Logstash

## Licență

MIT License

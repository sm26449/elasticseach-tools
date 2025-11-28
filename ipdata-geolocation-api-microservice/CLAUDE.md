# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

IP geolocation API service built with FastAPI that provides geographic information about IP addresses. Implements a multi-tier data retrieval strategy: Redis cache → Elasticsearch → IPData.co API.

## Commands

### Development
```bash
# Build Docker image
docker build -t ipdata .

# Run with Docker Compose (includes Redis)
docker-compose up

# Deploy multiple instances (ports 8001-8010)
./run.sh

# Check Redis statistics
python redis_stats.py

# Reset daily API request counter
python reset_requests_made.py

# Run single instance locally
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Testing
```bash
# Test IP lookup
curl http://localhost:8000/ip/8.8.8.8

# Check statistics
curl http://localhost:8000/stats

# Use web interface
open http://localhost:8000
```

## Architecture

### Data Flow
1. **Request arrives** → HAProxy load balancer (port 80)
2. **Load distribution** → One of 10 FastAPI instances (ports 8001-8010)
3. **Data retrieval cascade**:
   - Check Redis cache (TTL: 24 hours)
   - Query Elasticsearch (daily indices: ipdata-YYYY-MM-DD)
   - Fallback to IPData.co API (rate limited)
4. **Response caching** → Store in Redis and Elasticsearch

### Key Components
- **main.py**: Core FastAPI application with endpoints
- **elastic_helper.py**: Elasticsearch connection and operations
- **redis_helper.py**: Redis caching and statistics
- **haproxy.cfg**: Load balancer configuration
- **run.sh**: Multi-instance deployment script
- **static/**: Web UI assets

### Environment Configuration
Required environment variables:
- `IPDATA_API_KEY`: IPData.co API key
- `ELASTICSEARCH_NODE`: ES cluster endpoints
- `ELASTICSEARCH_USER`: ES authentication
- `ELASTICSEARCH_PASS`: ES password
- `ELASTICSEARCH_CA_CERT`: ES certificate
- `REDIS_HOST`: Redis server (default: localhost)
- `REDIS_PORT`: Redis port (default: 6379)
- `REQUEST_LIMIT`: Daily API limit (default: 100000)

### API Endpoints
- `GET /ip/{ip_address}`: Get geolocation data
- `GET /stats`: Service statistics
- `GET /`: Web interface
- `GET /health`: Health check

### Data Models
IP response includes: ip, city, region, country_name, country_code, continent_name, latitude, longitude, asn, organisation, postal, calling_code, flag, emoji_flag, emoji_unicode, languages, currency, time_zone, threat, count, carrier

## Important Considerations

- Service uses Romanian language comments in some files
- Elasticsearch indices are created daily (ipdata-YYYY-MM-DD format)
- Redis implements connection pooling with automatic reconnection
- Cron job resets request counters daily at midnight
- HAProxy configured for 10 backend instances with health checks
- All instances share same Redis cache for consistency
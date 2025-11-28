from elasticsearch import AsyncElasticsearch
from elasticsearch.exceptions import BadRequestError
from fastapi import FastAPI, Response, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Optional
import httpx
import os
from datetime import datetime
from redis import Redis, RedisError
import json
from pydantic import BaseModel, Field, ValidationError
from dotenv import load_dotenv
import time
import uuid


load_dotenv()

class RedisManager:
    def __init__(self, host, port, db):
        self.host = host
        self.port = port
        self.db = db
        self.client = self.connect()
        self.last_check = time.time()
        self.check_interval = 60  # Verifică starea conexiunii o dată pe minut

    def connect(self):
        """Conectează la Redis și returnează clientul."""
        return Redis(host=self.host, port=self.port, db=self.db, decode_responses=True)

    def get_client(self):
        """Returnează clientul Redis dacă este conectat, altfel încearcă reconectarea."""
        if time.time() - self.last_check > self.check_interval:
            try:
                self.client.ping()
            except RedisError:
                self.client = self.connect()
            finally:
                self.last_check = time.time()
        return self.client


class IPAddress(BaseModel):
    ip: str = Field(..., pattern="^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$")

redis_manager = RedisManager(host=os.getenv("REDIS_HOST"), port=int(os.getenv("REDIS_PORT")), db=0)
es_client_instance = None
container_name = os.getenv('CONTAINER_NAME')
if not container_name:
    container_name = str(uuid.uuid4())

def increment_and_expire(redis_client, key: str, expire_seconds: int):
    current_count = redis_client.incr(key)
    if current_count == 1:
        redis_client.expire(key, expire_seconds)

def get_es_config():
    es_hosts = os.getenv("ELASTICSEARCH_NODE").split(",")
    return {
        "hosts": [host.strip() for host in es_hosts],
        "http_auth": (os.getenv("ELASTICSEARCH_USERNAME"), os.getenv("ELASTICSEARCH_PASSWORD")),
        "verify_certs": True,
        "ca_certs": os.getenv("ELASTICSEARCH_CA_CERTS_PATH"),
        "request_timeout": 600,
        "headers": {"Accept": "application/json", "Content-Type": "application/json"}
    }

async def get_es_client():
    global es_client_instance
    if es_client_instance is None:
        es_client_instance = AsyncElasticsearch(**get_es_config())
    try:
        await es_client_instance.ping()
    except Exception:
        es_client_instance = AsyncElasticsearch(**get_es_config())
    return es_client_instance

app = FastAPI(title="IPData Geolocation API", version="1.0.0")

@app.get("/ip/{ip}", response_class=JSONResponse)
async def get_ip_data(ip: str, pretty: Optional[bool] = False, fields: Optional[str] = None, es: AsyncElasticsearch = Depends(get_es_client)):
    try:
        IPAddress(ip=ip)
    except ValidationError:
        return JSONResponse(status_code=400, content={"message": "Invalid IPv4 address."})

    redis_client = redis_manager.get_client()
    redis_client.incr("ipdata_total_requests")

    increment_and_expire(redis_client, "ipdata_requests_per_minute", 60)  # Pentru contorul general
    increment_and_expire(redis_client, "ipdata_requests_per_day", 86400)  # Pentru contorul zilnic

    data, source = await fetch_data(ip, es, redis_client)
    if fields:
        selected_fields = fields.split(',')
        data = {key: value for key, value in data.items() if key in selected_fields}

    current_count = redis_client.get("ipdata_requests_per_minute") or 0
    content = json.dumps({"source": source, "data": data, "requests_made_to_ipdata_api": "unknown" if source != "IPData API" else redis_client.get("ipdata_api_request_count"), "requests_per_minute": int(current_count), "instance": container_name}, indent=4 if pretty else None)
    return Response(content=content, media_type="application/json")

async def fetch_data(ip: str, es: AsyncElasticsearch, redis_client):
    # Check Redis cache first
    cached_data = redis_client.get(ip)
    if cached_data:
        return json.loads(cached_data), "Redis Cache"

    # Try Elasticsearch search, skip if compatibility issues
    try:
        index_pattern = f"{os.getenv('ELASTICSEARCH_INDEX_BASE', 'ipdata')}-*"
        query = {"query": {"match": {"ip": ip}}}
        response = await es.search(index=index_pattern, body=query)
        if response['hits']['hits']:
            data_to_cache = response['hits']['hits'][0]['_source']
            redis_client.set(ip, json.dumps(data_to_cache), ex=int(os.getenv("REDIS_CACHE_EXPIRY_SECONDS", 3600)))
            return data_to_cache, "Elasticsearch"
    except (BadRequestError, Exception) as e:
        # Skip Elasticsearch if there are compatibility issues
        pass

    # Query IPData API if data not found in Elasticsearch or ES unavailable
    requests_made_key = "ipdata_api_request_count"
    if redis_client.incr(requests_made_key) > int(os.getenv("REQUEST_LIMIT", "10000")):
        redis_client.decr(requests_made_key)
        return {"message": "Request limit exceeded for IPData API"}, "Limit Exceeded"

    async with httpx.AsyncClient() as client:
        ipdata_response = await client.get(f"https://api.ipdata.co/{ip}?api-key={os.getenv('IPDATA_API_KEY')}")
        if ipdata_response.is_error:
            return {"message": "Failed to retrieve data from IPData."}, "IPData API Error"

        new_data = ipdata_response.json()
        redis_client.set(ip, json.dumps(new_data), ex=int(os.getenv("REDIS_CACHE_EXPIRY_SECONDS", 3600)))
        
        # Try to store in Elasticsearch, but don't fail if it doesn't work
        try:
            date_str = datetime.now().strftime("%Y-%m-%d")
            index_name = f"{os.getenv('ELASTICSEARCH_INDEX_BASE', 'ipdata')}-{date_str}"
            new_data['@timestamp'] = datetime.now().isoformat()
            await es.index(index=index_name, id=ip, document=new_data)
        except (BadRequestError, Exception) as e:
            # Skip Elasticsearch storage if there are compatibility issues
            pass

        return new_data, "IPData API"

@app.get("/health")
async def health_check():
    """Health check endpoint pentru HAProxy și Docker"""
    try:
        redis_client = redis_manager.get_client()
        redis_client.ping()
        return {"status": "healthy", "service": "ipdata", "container": container_name}
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "unhealthy", "error": str(e)})

@app.get("/stats", response_class=JSONResponse)
def get_requests_count():
    redis_client = redis_manager.get_client()

    counts = redis_client.mget([
        "ipdata_requests_per_minute",
        "ipdata_requests_per_day",
        "ipdata_api_request_count",
        "ipdata_total_requests"
    ])
    current_count, current_count_daily, requests_made_to_ipdata_api, total_requests  = (int(count) if count else 0 for count in counts)

    # Obține informații generale despre Redis și numărul de chei
    redis_info = redis_client.info()
    total_keys = redis_client.dbsize()
    # Selectează câteva câmpuri relevante din informațiile Redis
    redis_details = {
        "redis_version": redis_info.get("redis_version"),
        "uptime_in_seconds": redis_info.get("uptime_in_seconds"),
        "connected_clients": redis_info.get("connected_clients"),
        "used_memory_human": redis_info.get("used_memory_human"),
        "total_keys": total_keys
    }

    response = {
        "requests_per_minute": current_count,
        "requests_per_day": current_count_daily,
        "requests_total": total_requests,
        "requests_made_to_ipdata_api": requests_made_to_ipdata_api,
        "redis_details": redis_details
    }

    response_str = json.dumps(response, indent=4)
    return Response(content=response_str, media_type="application/json")


@app.on_event("shutdown")
async def shutdown_event():
    if es_client_instance:
        await es_client_instance.close()

@app.get("/", response_class=HTMLResponse)
async def read_form():
    return """
<!DOCTYPE html>
<html>
<head>
    <title>IP Data Query Form</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.3.1/styles/default.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.3.1/highlight.min.js"></script>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            margin: 0;
            padding: 20px;
            background-color: #f0f0f0;
        }
        .container {
            max-width: 800px;
            margin: auto;
            background-color: #fff;
            padding: 40px;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
        }
        form { 
            display: flex; 
            flex-direction: row; 
            justify-content: start; 
            align-items: center;
            margin-bottom: 20px;
        }
        input[type="text"], button { 
            margin: 0 10px 0 0; 
            padding: 10px;
        }
        #pretty {
            transform: scale(1.2);
            margin-right: 5px;
        }
        #queryResult { 
            width: 100%; 
            padding: 10px; 
            background-color: #f9f9f9; 
            border: 1px solid #ccc; 
            border-radius: 5px; 
            overflow-x: auto;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
    </style>
</head>
<body>
    <div class="container">
        <h2>Enter an IP address to query</h2>
        <form id="ipQueryForm">
            <input type="text" id="ipAddress" placeholder="Enter IP address"/>
            <input type="checkbox" id="pretty" name="pretty">
            <label for="pretty">Pretty JSON</label>
            <button type="submit">Submit</button>
        </form>
        <div id="queryResult"></div>
    </div>
    <script>
        document.getElementById("ipQueryForm").onsubmit = async function(event) {
            event.preventDefault();
            const ip = document.getElementById("ipAddress").value;
            const pretty = document.getElementById("pretty").checked;
            const url = `/ip/${ip}${pretty ? '?pretty=true' : ''}`;
            try {
                const response = await fetch(url);
                const data = await response.json();
                const jsonString = JSON.stringify(data, null, 2);
                document.getElementById("queryResult").innerHTML = `<pre><code class="language-json">${jsonString}</code></pre>`;
                hljs.highlightAll();
            } catch (error) {
                console.error('Error fetching IP data:', error);
                document.getElementById("queryResult").innerHTML = `<pre><code class="language-json">Failed to fetch IP data.</code></pre>`;
            }
        };
    </script>
</body>
</html>
    """

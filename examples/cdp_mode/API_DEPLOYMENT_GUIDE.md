# 🚀 Google Search API - Production Deployment Guide

Complete guide for deploying the SeleniumBase CDP Mode Google Search as a production API.

## 📋 Table of Contents
- [Quick Start](#quick-start)
- [Local Development](#local-development)
- [Docker Deployment](#docker-deployment)
- [Production Considerations](#production-considerations)
- [API Usage](#api-usage)
- [Troubleshooting](#troubleshooting)

---

## ⚡ Quick Start

### Option 1: Local Development

```bash
# Install dependencies
pip install -r requirements-api.txt

# Run the API
python api_google_search.py

# Or with uvicorn directly
uvicorn api_google_search:app --host 0.0.0.0 --port 8000 --reload
```

Access the API:
- **API**: http://localhost:8000
- **Swagger Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Option 2: Docker (Recommended for Production)

```bash
# Build and run with docker-compose
docker-compose up -d

# Check logs
docker-compose logs -f

# Stop the service
docker-compose down
```

---

## 🛠️ Local Development

### Prerequisites
- Python 3.8+
- Chrome/Chromium browser installed
- 2GB+ RAM available

### Installation

```bash
# 1. Install dependencies
pip install -r requirements-api.txt

# 2. Verify SeleniumBase installation
sbase get chromedriver --path

# 3. Test the script directly
python raw_cdp_google.py

# 4. Run the API
python api_google_search.py
```

### Running in Headless Mode

The API automatically runs in headless mode on Linux. For macOS/Windows:

```python
# In api_google_search.py, modify the Chrome initialization:
sb = sb_cdp.Chrome(search_url, incognito=incognito, headless=True)
```

Or set environment variable:
```bash
export HEADLESS=true
python api_google_search.py
```

---

## 🐳 Docker Deployment

### Build the Image

```bash
# Build the Docker image
docker build -f Dockerfile.api -t google-search-api:latest .

# Run the container
docker run -d \
  --name google-search-api \
  -p 8000:8000 \
  --shm-size=2g \
  google-search-api:latest
```

### Using Docker Compose (Recommended)

```bash
# Start the service
docker-compose up -d

# Scale to multiple instances (for load balancing)
docker-compose up -d --scale google-search-api=3

# View logs
docker-compose logs -f google-search-api

# Restart service
docker-compose restart

# Stop and remove
docker-compose down
```

### Docker Environment Variables

```yaml
# docker-compose.yml
environment:
  - PYTHONUNBUFFERED=1
  - TZ=America/New_York
  - MAX_WORKERS=4  # Optional: Set worker count
  - LOG_LEVEL=info  # Optional: Set log level
```

---

## 🔒 Production Considerations

### 1. **Headless Mode** (CRITICAL)

Always run in headless mode in production:

```python
# Add to api_google_search.py
import os
headless = os.getenv('HEADLESS', 'true').lower() == 'true'
sb = sb_cdp.Chrome(search_url, incognito=incognito, headless=headless)
```

### 2. **Resource Limits**

Each Chrome instance uses significant resources:
- **RAM**: 500MB - 1GB per instance
- **CPU**: 0.5 - 1 core per instance

Set limits in docker-compose.yml:
```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 2G
```

### 3. **Concurrency & Rate Limiting**

```bash
# Install rate limiting
pip install slowapi

# Add to api_google_search.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/search")
@limiter.limit("5/minute")  # 5 requests per minute
async def search(request: SearchRequest):
    ...
```

### 4. **Scaling Horizontally**

Use a load balancer (nginx, traefik) with multiple containers:

```bash
# docker-compose.yml
services:
  google-search-api:
    deploy:
      replicas: 3  # Run 3 instances
```

### 5. **Monitoring & Health Checks**

Health check endpoint is built-in:
```bash
curl http://localhost:8000/health
```

Add monitoring (Prometheus, Grafana):
```bash
pip install prometheus-fastapi-instrumentator

# In api_google_search.py
from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)
```

### 6. **Security Best Practices**

```python
# Add CORS (if needed)
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# Add API Key authentication
from fastapi import Security, HTTPException
from fastapi.security.api_key import APIKeyHeader

API_KEY = os.getenv("API_KEY", "your-secret-key")
api_key_header = APIKeyHeader(name="X-API-Key")

def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return api_key

@app.post("/search")
async def search(request: SearchRequest, api_key: str = Security(verify_api_key)):
    ...
```

### 7. **Error Handling & Retry Logic**

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def perform_google_search(...):
    # Will retry up to 3 times with exponential backoff
    ...
```

---

## 📡 API Usage

### Health Check

```bash
curl http://localhost:8000/health
```

### Perform Search

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "12831000A01803",
    "max_results": 10,
    "save_screenshot": true,
    "incognito": true
  }'
```

### Python Client Example

```python
import requests

response = requests.post(
    "http://localhost:8000/search",
    json={
        "query": "12831000A01803",
        "max_results": 10,
        "save_screenshot": True,
        "incognito": True
    }
)

result = response.json()
print(f"Title: {result['title']}")
print(f"Results: {result['results']}")
print(f"Screenshot: {result['screenshot_path']}")
```

### Download Screenshot

```bash
# Extract filename from response
curl http://localhost:8000/screenshot/search_20240112_123456_query.png \
  --output screenshot.png
```

---

## 🔧 Troubleshooting

### Chrome Not Found

```bash
# Install Chrome manually
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install ./google-chrome-stable_current_amd64.deb

# Verify installation
google-chrome --version
```

### ChromeDriver Issues

```bash
# Download specific version
sbase get chromedriver stable --path

# Or specify version
sbase get chromedriver 120 --path
```

### Memory Issues

```bash
# Increase shared memory for Docker
docker run --shm-size=2g ...

# Or in docker-compose.yml
shm_size: '2gb'
```

### Bot Detection

If Google detects the bot:
1. Use residential proxies
2. Add random delays
3. Rotate user agents
4. Use incognito mode (already enabled)

```python
# Add proxy support
sb = sb_cdp.Chrome(
    search_url,
    incognito=True,
    proxy="username:password@proxy-server:port"
)
```

### Timeout Issues

```python
# Increase timeouts
sb.sleep(5)  # Instead of sb.sleep(3)

# Or set global timeout
os.environ['CDP_TIMEOUT'] = '60'
```

---

## 🌐 Deployment Platforms

### AWS EC2

```bash
# Launch Ubuntu instance
# SSH into instance
sudo apt update
sudo apt install docker.io docker-compose
git clone your-repo
cd examples/cdp_mode
docker-compose up -d
```

### Google Cloud Run

```bash
# Build and push to GCR
gcloud builds submit --tag gcr.io/PROJECT_ID/google-search-api

# Deploy
gcloud run deploy google-search-api \
  --image gcr.io/PROJECT_ID/google-search-api \
  --platform managed \
  --memory 2Gi \
  --cpu 2
```

### Heroku

```bash
# Create Procfile
echo "web: uvicorn api_google_search:app --host 0.0.0.0 --port \$PORT" > Procfile

# Deploy
heroku create google-search-api
heroku container:push web
heroku container:release web
```

### DigitalOcean App Platform

```yaml
# .do/app.yaml
name: google-search-api
services:
- name: api
  dockerfile_path: Dockerfile.api
  instance_size_slug: professional-xs
  instance_count: 2
  http_port: 8000
```

---

## 📊 Performance Benchmarks

- **Avg Response Time**: 5-8 seconds per search
- **Memory Usage**: ~800MB per Chrome instance
- **CPU Usage**: ~50-80% during search
- **Throughput**: 5-10 searches/minute per instance

### Optimization Tips

1. **Reduce sleep times** (carefully to avoid detection)
2. **Disable screenshots** if not needed
3. **Use connection pooling** for multiple requests
4. **Cache results** for repeated queries

---

## 📝 License

This API is built on SeleniumBase (MIT License).

---

## 🆘 Support

- SeleniumBase Docs: https://seleniumbase.io
- GitHub Issues: https://github.com/seleniumbase/SeleniumBase/issues
- Discord: https://discord.gg/EdhQTn3

---

**Happy Deploying! 🚀**

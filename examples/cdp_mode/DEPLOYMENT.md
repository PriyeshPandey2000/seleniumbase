# Docker Deployment Guide

## ✅ Everything Runs in Docker

This setup is **fully containerized** - everything runs inside Docker:
- ✅ Chrome browser
- ✅ Xvfb virtual display
- ✅ SeleniumBase
- ✅ Python scripts
- ✅ All dependencies

**No host dependencies required!**

## 🚀 Deployment Steps

### 1. Build the Image

```bash
cd /Users/priyesh/Desktop/selenium-base/examples/cdp_mode
export DOCKER_DEFAULT_PLATFORM=linux/amd64
docker-compose -f docker-compose.slim.yml build
```

### 2. Run Examples

**Option A: Run default script (raw_cdp_google_submit.py)**
```bash
docker-compose -f docker-compose.slim.yml up
```

**Option B: Run any other script**
```bash
docker-compose -f docker-compose.slim.yml run --rm google-search-headful python3 raw_cdp_google.py
docker-compose -f docker-compose.slim.yml run --rm google-search-headful python3 api_google_search.py
```

### 3. Access Output Files

Output files (screenshots, PDFs) are saved to:
- **Inside container**: `/app/output/`
- **On host**: `./output/` (mapped via volume)

```bash
# View output files
ls -la output/

# Copy files from container (if needed)
docker cp google-search-test-headful:/app/google_search_submit_full_page.png .
```

## 📦 What's Included in the Container

- **Base**: Ubuntu 22.04
- **Browser**: Google Chrome (amd64)
- **Display**: Xvfb (virtual X server)
- **Python**: Python 3.10
- **Framework**: SeleniumBase (latest)
- **Driver**: ChromeDriver (auto-downloaded)

## 🔧 Deployment Options

### Local Development
```bash
docker-compose -f docker-compose.slim.yml up
```

### Production/CI/CD
```bash
# Build once
docker build --platform linux/amd64 -f Dockerfile.slim -t seleniumbase-cdp:latest .

# Run in CI/CD pipeline
docker run --rm \
  --platform linux/amd64 \
  --security-opt seccomp:unconfined \
  --shm-size=2gb \
  -v $(pwd)/output:/app/output \
  seleniumbase-cdp:latest \
  python3 raw_cdp_google_submit.py
```

### Cloud Deployment (AWS/GCP/Azure)
1. Build and push image to container registry
2. Deploy using:
   - AWS ECS/Fargate
   - Google Cloud Run
   - Azure Container Instances
   - Kubernetes

## 📝 Environment Variables

You can override these in docker-compose.yml:
- `DISPLAY=:100` - Xvfb display port
- `TZ=America/New_York` - Timezone
- `PYTHONUNBUFFERED=1` - Python output buffering

## 🎯 Resource Limits

Current limits (adjustable in docker-compose.yml):
- **CPU**: 2.0 cores max, 1.0 reserved
- **Memory**: 2GB max, 1GB reserved
- **Shared Memory**: 2GB (required for Chrome)

## 🔍 Troubleshooting

**If Chrome fails to start:**
- Ensure Rosetta is enabled (Apple Silicon)
- Check `--shm-size=2gb` is set
- Verify `--security-opt seccomp:unconfined`

**If Xvfb fails:**
- Check display port isn't in use
- Verify Xvfb is running: `ps aux | grep Xvfb`

**View container logs:**
```bash
docker-compose -f docker-compose.slim.yml logs
```

## 📤 Output Files

All output files are automatically saved to:
- Container: `/app/output/`
- Host: `./output/` (created automatically)

Make sure to update your scripts to save to `/app/output/` directory!

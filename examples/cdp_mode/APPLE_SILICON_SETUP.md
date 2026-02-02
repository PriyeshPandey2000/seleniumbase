# Apple Silicon (M1/M2/M3/M4) Docker Setup

## Important: Enable Rosetta in Docker Desktop

For SeleniumBase to work properly on Apple Silicon Macs, you **MUST** enable Rosetta emulation in Docker Desktop.

### Steps:

1. **Open Docker Desktop**
2. **Go to Settings** (gear icon)
3. **Navigate to**: General → Features in development
4. **Check the box**: "Use Rosetta for x86_64/amd64 emulation on Apple Silicon"
5. **Click**: "Apply & restart"

![Enable Rosetta](https://seleniumbase.github.io/other/docker_rosetta.jpg)

## Build and Run

Once Rosetta is enabled, run:

```bash
cd /Users/priyesh/Desktop/selenium-base/examples/cdp_mode

# Set platform environment variable
export DOCKER_DEFAULT_PLATFORM=linux/amd64

# Build and run
docker-compose -f docker-compose.slim.yml build
docker-compose -f docker-compose.slim.yml up
```

## Why This Is Needed

SeleniumBase's CDP mode requires Google Chrome (amd64), which needs Rosetta emulation to run on ARM64 (Apple Silicon). Without Rosetta enabled, Chrome will crash with errors like:
- "Failed to connect to the browser"
- "InvalidSessionIdException"
- "Unable to receive message from renderer"

## Alternative: Run Directly with Docker

```bash
export DOCKER_DEFAULT_PLATFORM=linux/amd64

docker build --platform linux/amd64 -f Dockerfile.slim -t google-search-headful .

docker run --rm \
  --platform linux/amd64 \
  --security-opt seccomp:unconfined \
  --shm-size=2gb \
  google-search-headful
```

## Copy Screenshots After Run

```bash
docker cp google-search-test-headful:/app/google_search_submit_full_page.png .
```


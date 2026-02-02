# Google Search CDP Mode API

Simple Flask API to run Google searches with CDP mode, proxy support, and full-page screenshots.

## Installation

```bash
# Install Flask (if not already installed)
pip install flask
```

## Running the API

```bash
# Run locally
python api_google_search.py

# Or in Docker
docker-compose -f docker-compose.slim.yml run --rm google-search-headful python3 /app/scripts/api_google_search.py
```

The API will start on `http://localhost:5000`

## API Endpoints

### 1. Health Check
```
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "google-search-cdp-api"
}
```

### 2. Search Google
```
POST /search
```

**Request Body:**
```json
{
  "query": "best hotels in paris",
  "proxy": "username:password@proxy-host:port"  // Optional
}
```

**Response:**
```json
{
  "success": true,
  "message": "Search completed successfully",
  "query": "best hotels in paris",
  "proxy": "username:password@proxy-host:port",
  "screenshot_path": "/path/to/google_search_full_page.png",
  "screenshot_exists": true,
  "return_code": 0
}
```

### 3. View Screenshot
```
GET /screenshot
```
Returns the latest screenshot as an image.

### 4. Download Screenshot
```
GET /screenshot/download
```
Downloads the latest screenshot file.

## Usage Examples

### Using curl

```bash
# Simple search
curl -X POST http://localhost:5000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "restaurants near me"}'

# Search with proxy
curl -X POST http://localhost:5000/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "best hotels",
    "proxy": "myuser:mypass@proxy.example.com:8080"
  }'

# Get screenshot
curl http://localhost:5000/screenshot -o screenshot.png
```

### Using Python

```python
import requests

# Search
response = requests.post('http://localhost:5000/search', json={
    'query': 'best hotels in paris',
    'proxy': 'user:pass@proxy-host:port'  # Optional
})

data = response.json()
print(data)

# Download screenshot
if data['screenshot_exists']:
    screenshot = requests.get('http://localhost:5000/screenshot/download')
    with open('screenshot.png', 'wb') as f:
        f.write(screenshot.content)
```

### Using JavaScript/Fetch

```javascript
// Search
fetch('http://localhost:5000/search', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: 'best hotels',
    proxy: 'user:pass@proxy-host:port'  // Optional
  })
})
.then(res => res.json())
.then(data => console.log(data));

// View screenshot in browser
window.open('http://localhost:5000/screenshot');
```

## Proxy Format

- **Without authentication:** `host:port`
  - Example: `192.168.1.1:8080`

- **With authentication:** `username:password@host:port`
  - Example: `myuser:mypass@proxy.example.com:8080`

## Command Line Usage

You can also run the script directly:

```bash
# Without proxy
python raw_cdp_google.py "best hotels"

# With proxy (no auth)
python raw_cdp_google.py "best hotels" --proxy "192.168.1.1:8080"

# With proxy (with auth)
python raw_cdp_google.py "best hotels" --proxy "user:pass@proxy.example.com:8080"
```

## Features

- ✅ CDP Mode (No WebDriver footprint)
- ✅ Proxy support with authentication
- ✅ Full-page screenshots
- ✅ Cookie consent handling
- ✅ Popup dismissal
- ✅ Ad blocking
- ✅ Command line and API interfaces

## Notes

- Screenshots are saved as `google_search_full_page.png` in the script directory
- The API has a 2-minute timeout for searches
- Proxy authentication is supported for Chrome/Edge browsers

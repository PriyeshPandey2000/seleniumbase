"""
Simple Flask API for CDP Mode Web Scraping
Run locally: python api_google_search.py
"""
from flask import Flask, request, jsonify
import subprocess
import os
import sys
import json

app = Flask(__name__)

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRAPER_SCRIPT = os.path.join(SCRIPT_DIR, "raw_cdp_google.py")

@app.route('/', methods=['GET'])
def root():
    """Root endpoint with API information"""
    return jsonify({
        "service": "CDP Mode Web Scraping API",
        "status": "running",
        "endpoints": {
            "GET /": "API information (this page)",
            "GET /health": "Health check",
            "POST /search": "Scrape URL or search Google"
        },
        "example_request": {
            "method": "POST",
            "url": "/search",
            "body": {
                "query": "best hotels",           # Search Google (optional)
                "url": "https://example.com",     # OR direct URL (optional)
                "proxy": "user:pass@host:port",   # Optional
                "screenshot": True                # Optional (default: true)
            }
        },
        "example_response": {
            "success": True,
            "screenshot_base64": "iVBORw0KGg...",  # If screenshot=true
            "html": "<html>...</html>",
            "url": "https://...",
            "query": "best hotels"
        }
    })

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "cdp-scraping-api"})

@app.route('/search', methods=['POST'])
def search():
    """
    Scrape URL or search Google with CDP Mode

    Request body (JSON):
    {
        "query": "search term",    # Optional: searches Google
        "url": "https://...",      # Optional: scrape direct URL
        "proxy": "host:port",      # Optional
        "screenshot": true         # Optional (default: true)
    }

    Returns:
    {
        "success": true/false,
        "screenshot_base64": "...",  # If screenshot=true
        "html": "<html>...</html>",
        "url": "final URL",
        "query": "search query" (if used)
    }
    """
    try:
        data = request.get_json() or {}

        # Get query or URL (one must be provided)
        query = data.get('query')
        url = data.get('url')

        if not query and not url:
            return jsonify({
                "success": False,
                "error": "Either 'query' or 'url' parameter is required"
            }), 400

        if query and url:
            return jsonify({
                "success": False,
                "error": "Provide either 'query' OR 'url', not both"
            }), 400

        # Get optional parameters
        proxy = data.get('proxy')
        screenshot = data.get('screenshot', True)  # Default to True

        # Build command
        cmd = [sys.executable, SCRAPER_SCRIPT]

        # Add query or URL
        if query:
            cmd.append(query)
        elif url:
            cmd.extend(['--url', url])

        # Add optional parameters
        if proxy:
            cmd.extend(['--proxy', proxy])
        if not screenshot:
            cmd.append('--no-screenshot')

        print(f"[API] Executing: {' '.join(cmd)}")

        # Run the scraper script
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout
            env=os.environ.copy()
        )

        # Parse JSON output from script
        if result.returncode == 0:
            try:
                # Script outputs JSON on last line
                output_lines = result.stdout.strip().split('\n')
                json_output = output_lines[-1]
                response_data = json.loads(json_output)
                return jsonify(response_data), 200
            except json.JSONDecodeError as e:
                return jsonify({
                    "success": False,
                    "error": f"Failed to parse script output: {e}",
                    "stdout": result.stdout[-500:],
                    "stderr": result.stderr[-500:]
                }), 500
        else:
            return jsonify({
                "success": False,
                "error": "Scraping failed",
                "stderr": result.stderr[-500:] if result.stderr else "Unknown error",
                "stdout": result.stdout[-500:] if result.stdout else None
            }), 500

    except subprocess.TimeoutExpired:
        return jsonify({
            "success": False,
            "error": "Request timed out after 2 minutes"
        }), 504

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

if __name__ == '__main__':
    print("=" * 60)
    print("CDP Mode Web Scraping API")
    print("=" * 60)
    print(f"Scraper script: {SCRAPER_SCRIPT}")
    print("\nEndpoints:")
    print("  GET  /health - Health check")
    print("  POST /search - Scrape URL or search Google")
    print("\nExample POST /search:")
    print('  {"query": "best hotels", "screenshot": true}')
    print('  {"url": "https://example.com", "screenshot": false}')
    print("\nStarting server on http://localhost:5000")
    print("=" * 60)

    app.run(host='0.0.0.0', port=5000, debug=True)

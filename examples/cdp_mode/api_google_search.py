"""
Simple Flask API for Google Search with CDP Mode
Run locally: python api_google_search.py
"""
from flask import Flask, request, jsonify, send_file
import subprocess
import os
import sys
import time
from pathlib import Path

app = Flask(__name__)

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent
SEARCH_SCRIPT = SCRIPT_DIR / "raw_cdp_google.py"
OUTPUT_DIR = SCRIPT_DIR
SCREENSHOT_NAME = "google_search_full_page.png"

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "google-search-cdp-api"})

@app.route('/search', methods=['POST'])
def search():
    """
    Search Google with CDP Mode
    
    Request body (JSON):
    {
        "query": "search term",  # Required
        "proxy": "host:port" or "username:password@host:port"  # Optional
    }
    
    Returns:
    {
        "success": true/false,
        "message": "status message",
        "screenshot_path": "path to screenshot",
        "query": "search query used",
        "proxy": "proxy used (if any)"
    }
    """
    try:
        data = request.get_json() or {}
        
        # Get search query
        search_query = data.get('query', 'best hotels')
        if not search_query:
            return jsonify({
                "success": False,
                "error": "Query parameter is required"
            }), 400
        
        # Get proxy (optional)
        proxy = data.get('proxy', None)
        
        # Build command
        cmd = [sys.executable, str(SEARCH_SCRIPT), search_query]
        if proxy:
            cmd.extend(['--proxy', proxy])
        
        print(f"[API] Executing: {' '.join(cmd)}")
        
        # Run the search script
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout
        )
        
        # Check if screenshot was created
        screenshot_path = OUTPUT_DIR / SCREENSHOT_NAME
        screenshot_exists = screenshot_path.exists()
        
        response = {
            "success": result.returncode == 0 and screenshot_exists,
            "message": "Search completed successfully" if result.returncode == 0 else "Search failed",
            "query": search_query,
            "proxy": proxy if proxy else None,
            "screenshot_path": str(screenshot_path) if screenshot_exists else None,
            "screenshot_exists": screenshot_exists,
            "return_code": result.returncode,
            "stdout": result.stdout[-500:] if result.stdout else None,  # Last 500 chars
            "stderr": result.stderr[-500:] if result.stderr else None,  # Last 500 chars
        }
        
        if result.returncode != 0:
            response["error"] = result.stderr[-500:] if result.stderr else "Unknown error"
            return jsonify(response), 500
        
        return jsonify(response), 200
        
    except subprocess.TimeoutExpired:
        return jsonify({
            "success": False,
            "error": "Search timed out after 2 minutes"
        }), 504
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/screenshot', methods=['GET'])
def get_screenshot():
    """
    Get the latest screenshot
    
    Returns the screenshot file if it exists
    """
    screenshot_path = OUTPUT_DIR / SCREENSHOT_NAME
    
    if not screenshot_path.exists():
        return jsonify({
            "error": "Screenshot not found. Run a search first."
        }), 404
    
    return send_file(
        str(screenshot_path),
        mimetype='image/png',
        as_attachment=False
    )

@app.route('/screenshot/download', methods=['GET'])
def download_screenshot():
    """
    Download the latest screenshot
    
    Returns the screenshot file as download
    """
    screenshot_path = OUTPUT_DIR / SCREENSHOT_NAME
    
    if not screenshot_path.exists():
        return jsonify({
            "error": "Screenshot not found. Run a search first."
        }), 404
    
    return send_file(
        str(screenshot_path),
        mimetype='image/png',
        as_attachment=True,
        download_name=SCREENSHOT_NAME
    )

if __name__ == '__main__':
    print("=" * 60)
    print("Google Search CDP Mode API")
    print("=" * 60)
    print(f"Script: {SEARCH_SCRIPT}")
    print(f"Output directory: {OUTPUT_DIR}")
    print("\nEndpoints:")
    print("  GET  /health - Health check")
    print("  POST /search - Search Google")
    print("  GET  /screenshot - View latest screenshot")
    print("  GET  /screenshot/download - Download latest screenshot")
    print("\nExample POST /search:")
    print('  {"query": "best hotels", "proxy": "user:pass@host:port"}')
    print("\nStarting server on http://localhost:5000")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=True)

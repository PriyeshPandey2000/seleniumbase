"""
SeleniumBase CDP Mode — Session-aware scraping API

One pod = one Chrome instance = one active session at a time.
Profile and cache dirs live on Filestore (NFS), mounted at /mnt/sessions.

Endpoints:
  GET  /health          Health check (liveness/readiness probe)
  GET  /status          Current session state (for Crawler pod-assignment logic)
  POST /search          Scrape a URL (requires session_id, profile_dir, cache_dir)
  POST /stop            Stop Chrome and clear session (called by Crawler on retirement)
"""

from flask import Flask, request, jsonify
import subprocess
import os
import sys
import json
import threading
import queue
import shutil
import time

app = Flask(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRAPER_SCRIPT = os.path.join(SCRIPT_DIR, "raw_cdp_google.py")
sys.path.insert(0, SCRIPT_DIR)

from chrome_desktop import ChromeDesktop

# ── Pod-level state ───────────────────────────────────────────────────────────
# Protected by _state_lock for reads/writes.
# _scrape_lock ensures only one scrape runs at a time (non-blocking acquire).

_state_lock   = threading.Lock()
_scrape_lock  = threading.Lock()

_current_session_id: str | None     = None
_current_chrome: ChromeDesktop | None = None
_is_busy: bool                       = False


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "service": "selenium-scraper"})


@app.route('/status', methods=['GET'])
def status():
    """
    Return current pod state. Crawler uses this to decide whether a pod
    is available for a new session assignment.

    Response:
      {
        "session_id": "uuid or null",
        "chrome_running": true/false,
        "busy": true/false          # true while a scrape is in progress
      }
    """
    with _state_lock:
        chrome_running = _current_chrome is not None and _current_chrome._sb is not None
        return jsonify({
            "session_id": _current_session_id,
            "chrome_running": chrome_running,
            "busy": _is_busy,
        })


@app.route('/search', methods=['POST'])
def search():
    """
    Scrape a URL using the given session.

    Request body (JSON):
    {
        "session_id":  "uuid",                        # required
        "profile_dir": "/mnt/sessions/{session_id}",  # required — Filestore path for this session
        "proxy":       "user:pass@host:port",          # optional (proxy_full with session ID)
        "url":         "https://example.com",          # one of url/query required
        "query":       "hotels in new york",           # one of url/query required
        "screenshot":  true                            # optional, default true
    }

    Chrome stores its HTTP cache inside profile_dir automatically (at
    {profile_dir}/Default/Cache/). The cache is updated on every request
    and persists on Filestore across pod restarts — no warmup needed.

    Returns:
    {
        "success": true/false,
        "captcha": true,            # only on CAPTCHA detection
        "url": "final URL",
        "html": "<html>...</html>",
        "screenshot_base64": "...", # if screenshot=true and success=true
        "query": "...",             # if query was used
        "debug_info": { ... }
    }

    HTTP 503 → pod is currently busy (Crawler should not send concurrent requests)
    HTTP 400 → missing required params
    HTTP 500 → scrape failed
    """
    global _current_session_id, _current_chrome, _is_busy

    data = request.get_json() or {}

    session_id  = data.get('session_id')
    profile_dir = data.get('profile_dir')
    proxy       = data.get('proxy')
    url         = data.get('url')
    query       = data.get('query')
    screenshot  = data.get('screenshot', True)

    if not session_id or not profile_dir:
        return jsonify({
            "success": False,
            "error": "session_id and profile_dir are required"
        }), 400

    if not url and not query:
        return jsonify({
            "success": False,
            "error": "Either 'url' or 'query' is required"
        }), 400

    if url and query:
        return jsonify({
            "success": False,
            "error": "Provide either 'url' OR 'query', not both"
        }), 400

    # Reject concurrent requests immediately — Crawler tracks in_use
    if not _scrape_lock.acquire(blocking=False):
        return jsonify({
            "success": False,
            "error": "Pod is busy with another request"
        }), 503

    try:
        # Briefly hold state lock to swap session if needed
        with _state_lock:
            _is_busy = True

            if _current_session_id != session_id:
                # Different session: stop existing Chrome before starting new one
                if _current_chrome is not None:
                    _current_chrome.stop()
                _current_chrome = ChromeDesktop(
                    session_id=session_id,
                    profile_dir=profile_dir,
                )
                _current_session_id = session_id

            chrome = _current_chrome  # local ref so /stop can't pull it away mid-scrape

        # Build target URL
        if url:
            target_url   = url
            query_string = None
        else:
            query_string = query
            target_url   = f"https://www.google.com/search?q={query}&sourceid=chrome&ie=UTF-8"

        print(f"[API] Scraping session={session_id[:8]} url={target_url}", flush=True)

        # Scrape — no lock held here so /stop can still update state
        result = chrome.scrape(target_url, proxy, query_string, screenshot)

        return jsonify(result), 200 if result.get('success') else 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    finally:
        with _state_lock:
            _is_busy = False
        _scrape_lock.release()


@app.route('/stop', methods=['POST'])
def stop():
    """
    Stop Chrome and clear session state.
    Called by Crawler when it retires a session (CAPTCHA, max_requests, TTL, etc.).
    Optionally deletes the profile dir if 'profile_dir' is provided in the body.
    Pod is immediately available for a new session assignment after this returns.
    """
    global _current_session_id, _current_chrome

    data = request.get_json() or {}
    profile_dir = data.get('profile_dir')

    with _state_lock:
        chrome              = _current_chrome
        _current_chrome     = None
        _current_session_id = None

    if chrome is not None:
        chrome.stop()

    if profile_dir and os.path.isdir(profile_dir):
        try:
            shutil.rmtree(profile_dir)
            print(f"[API] Deleted profile dir: {profile_dir}", flush=True)
        except Exception as e:
            print(f"[API] Warning: could not delete profile dir {profile_dir}: {e}", flush=True)

    return jsonify({"status": "stopped"})


@app.route('/cleanup-profiles', methods=['POST'])
def cleanup_profiles():
    """
    Scan /mnt/sessions and delete profile dirs not modified within max_age_seconds.
    Called hourly by the Crawler's cron job. All pods share the same Filestore mount
    so only one pod needs to run this.
    """
    data = request.get_json() or {}
    max_age_seconds = data.get('max_age_seconds', 7200)
    sessions_dir = '/mnt/sessions'

    if not os.path.isdir(sessions_dir):
        return jsonify({"deleted": [], "errors": ["Sessions dir not found: " + sessions_dir]})

    now = time.time()
    deleted = []
    errors = []

    for entry in os.scandir(sessions_dir):
        if not entry.is_dir():
            continue
        try:
            age = now - entry.stat().st_mtime
            if age > max_age_seconds:
                shutil.rmtree(entry.path)
                deleted.append(entry.name)
                print(f"[API] Cleanup: deleted orphaned profile {entry.name} (age={int(age)}s)", flush=True)
        except Exception as e:
            errors.append(f"{entry.name}: {e}")

    print(f"[API] Cleanup complete: {len(deleted)} deleted, {len(errors)} errors", flush=True)
    return jsonify({"deleted": deleted, "errors": errors})


# ── Mobile fallback path (unchanged — subprocess per request, no session) ─────

@app.route('/search/mobile', methods=['POST'])
def search_mobile():
    """
    Mobile scrape via subprocess. No session management — stateless.
    Kept separate from /search to avoid polluting session-aware logic.
    """
    try:
        data       = request.get_json() or {}
        query      = data.get('query')
        url        = data.get('url')
        proxy      = data.get('proxy')
        user_agent = data.get('user_agent')
        screenshot = data.get('screenshot', True)

        if not query and not url:
            return jsonify({"success": False, "error": "Either 'query' or 'url' is required"}), 400

        cmd = [sys.executable, SCRAPER_SCRIPT]
        if query:
            cmd.append(query)
        elif url:
            cmd.extend(['--url', url])
        if proxy:
            cmd.extend(['--proxy', proxy])
        if user_agent:
            cmd.extend(['--user-agent', user_agent])
        cmd.append('--mobile')
        if not screenshot:
            cmd.append('--no-screenshot')

        print(f"[API] Mobile: {' '.join(cmd)}", flush=True)

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, env=os.environ.copy()
        )

        if result.stderr:
            print("[API] Mobile stderr:")
            print(result.stderr)

        if result.returncode == 0:
            try:
                json_output = result.stdout.strip().split('\n')[-1]
                return jsonify(json.loads(json_output)), 200
            except json.JSONDecodeError as e:
                return jsonify({
                    "success": False,
                    "error": f"Failed to parse script output: {e}",
                    "stdout": result.stdout[-500:],
                }), 500
        else:
            return jsonify({
                "success": False,
                "error": "Scraping failed",
                "stderr": result.stderr[-500:] if result.stderr else "Unknown error",
            }), 500

    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "Request timed out after 2 minutes"}), 504
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("=" * 60)
    print("SeleniumBase Session-Aware Scraping API")
    print("=" * 60)
    print("Endpoints:")
    print("  GET  /health        — liveness/readiness probe")
    print("  GET  /status        — pod session state")
    print("  POST /search        — scrape (session-aware)")
    print("  POST /stop          — stop Chrome, free pod")
    print("  POST /search/mobile — mobile scrape (stateless)")
    print("\nFilestore mount expected at: /mnt/sessions")
    print("Starting server on http://0.0.0.0:5000")
    print("=" * 60)

    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)

"""Persistent Chrome Desktop pool for CDP-mode scraping.

Keeps N Chrome processes alive across requests so Google JS/CSS
(~1 MB) stays in the disk cache. Subsequent requests only fetch fresh
HTML + hotel data (~300–500 KB) instead of ~1.5 MB per request.

Pool size is controlled by the CHROME_POOL_SIZE env var (default: 1).
Set to 2 or 3 for concurrent requests.

Restart conditions (per worker):
  - First request         → start Chrome
  - Proxy changed         → stop old, start new
  - Idle > IDLE_TIMEOUT   → stop, restart on next request
  - Chrome unresponsive   → stop, restart
  - Scrape exception      → stop (restart on next request)
"""

import os
import platform
import time
import json
import base64
import queue
import tempfile
import random
import subprocess
import threading
import urllib.request
import urllib.error

from seleniumbase import sb_cdp

IDLE_TIMEOUT = 180  # 3 minutes

BLOCKED_URLS = [
    # CSS — pure styling, not needed for data extraction
    "*.css", "*.css?*",
    # Image extensions
    "*.jpg", "*.jpg?*", "*.jpeg", "*.jpeg?*",
    "*.png", "*.png?*", "*.gif", "*.gif?*",
    "*.webp", "*.webp?*", "*.svg", "*.svg?*",
    "*.ico", "*.ico?*", "*.bmp", "*.bmp?*",
    "*.avif", "*.avif?*", "*.tiff", "*.tiff?*",
    # Font extensions
    "*.woff", "*.woff?*", "*.woff2", "*.woff2?*",
    "*.ttf", "*.ttf?*", "*.otf", "*.otf?*", "*.eot", "*.eot?*",
    # Media extensions
    "*.mp4", "*.mp4?*", "*.webm", "*.webm?*",
    "*.mp3", "*.mp3?*", "*.wav", "*.wav?*",
    "*.avi", "*.avi?*", "*.mov", "*.mov?*",
    # Google image CDNs that serve extensionless images
    "*encrypted-tbn0.gstatic.com*",
    "*encrypted-tbn1.gstatic.com*",
    "*encrypted-tbn2.gstatic.com*",
    "*encrypted-tbn3.gstatic.com*",
    "*googleusercontent.com*",
    "*ggpht.com*",
    # Google Fonts (not needed for scraping)
    "*fonts.gstatic.com*",
    "*fonts.googleapis.com*",
    # Ad/tracking domains
    "*doubleclick.net*",
    "*googlesyndication.com*",
    "*googletagmanager.com*",
    "*google-analytics.com*",
    "*amazon-adsystem.com*",
    "*adsafeprotected.com*",
    "*fastclick.net*",
    "*snigelweb.com*",
    "*2mdn.net*",
    "*outbrain.com*",
    "*taboola.com*",
    "*criteo.com*",
    "*pubmatic.com*",
    "*rubiconproject.com*",
    "*moatads.com*",
    "*scorecardresearch.com*",
    "*quantserve.com*",
    "*facebook.com/tr*",
    # Google post-load tracking & logging (fires after page load, not needed)
    "*google.com/gen_204*",
    "*google.com/client_204*",
    "*google.com/log*",
    "*google.com/complete/search*",
    "*google.com/searchbyimage*",
    "*google.com/async/*",
    "*google.com/s?*",
    # Google Maps tiles (hotel search loads maps)
    "*maps.googleapis.com*",
    "*maps.gstatic.com*",
    "*/maps/vt*",
    "*/maps/api*",
]

# Module-level cache-warmup coordination — only one worker should warm
# the shared cache; others skip if warmup is already done or in progress.
_cache_warm_lock = threading.Lock()
_cache_warmed = False


def detect_proxy_timezone(proxy_string, log_fn, max_retries=3):
    """
    Detect timezone and geolocation from proxy using ip-api.com.
    Uses Python urllib (built-in, no extra dependencies).
    Returns dict with timezone, coords, country, city, ip — or None on failure.
    """
    log_fn("Detecting proxy timezone and location...")

    proxy_handler = None
    if proxy_string:
        proxy_handler = urllib.request.ProxyHandler({
            'http': f'http://{proxy_string}',
            'https': f'http://{proxy_string}',
        })

    for attempt in range(1, max_retries + 1):
        try:
            opener = (
                urllib.request.build_opener(proxy_handler)
                if proxy_handler
                else urllib.request.build_opener()
            )
            req = urllib.request.Request(
                'http://ip-api.com/json/?fields=status,query,timezone,lat,lon,country,city'
            )
            with opener.open(req, timeout=8) as response:
                if response.status == 200:
                    result = json.loads(response.read().decode('utf-8'))
                    if result and result.get('status') == 'success' and result.get('timezone'):
                        log_fn(f"✅ Proxy location detected (attempt {attempt}):")
                        log_fn(f"   IP: {result.get('query')}")
                        log_fn(f"   Country: {result.get('country')}")
                        log_fn(f"   City: {result.get('city')}")
                        log_fn(f"   Timezone: {result.get('timezone')}")
                        log_fn(f"   Coords: {result.get('lat')}, {result.get('lon')}")
                        return {
                            'timezone': result.get('timezone'),
                            'coords': {
                                'latitude': result.get('lat'),
                                'longitude': result.get('lon'),
                            } if result.get('lat') and result.get('lon') else None,
                            'country': result.get('country'),
                            'city': result.get('city'),
                            'ip': result.get('query'),
                        }
                    else:
                        log_fn(f"⚠️  IP-API attempt {attempt} failed: Invalid response")
                else:
                    log_fn(f"⚠️  IP-API attempt {attempt} failed: HTTP {response.status}")

        except urllib.error.URLError as e:
            log_fn(f"⚠️  IP-API attempt {attempt} URLError: {str(e)}")
        except Exception as e:
            log_fn(f"⚠️  IP-API attempt {attempt} error: {str(e)}")

        if attempt < max_retries:
            time.sleep(1)

    log_fn("❌ Failed to detect proxy timezone after all retries")
    return None


class ChromeDesktop:
    """One persistent Chrome worker within the pool."""

    def __init__(self, index=0, shared_cache_dir=None):
        self._index = index
        self._sb = None
        self._tab = None
        self._loop = None
        self._current_proxy = None
        self._last_request_time = 0
        self._is_linux = platform.system() == "Linux"

        if self._is_linux:
            self._profile_dir = f"/tmp/chrome-profile-desktop-{index}"
            self._warmup_profile_dir = f"/tmp/chrome-profile-desktop-warmup-{index}"
            # All workers share one cache dir so warmup only needs to run once
            self._cache_dir = shared_cache_dir or "/tmp/chrome-cache-desktop"
        else:
            base = os.path.expanduser("~")
            self._profile_dir = f"{base}/.chrome-profile-desktop-{index}"
            self._warmup_profile_dir = f"{base}/.chrome-profile-desktop-warmup-{index}"
            self._cache_dir = shared_cache_dir or os.path.expanduser("~/.chrome-cache-desktop")

        os.makedirs(self._profile_dir, exist_ok=True)
        os.makedirs(self._warmup_profile_dir, exist_ok=True)
        os.makedirs(self._cache_dir, exist_ok=True)

        # Lock serialises scrape() vs watchdog for THIS worker only.
        self._lock = threading.Lock()

        # Bandwidth tracking per request (encoded_data_length = actual wire bytes)
        self._bytes_lock = threading.Lock()
        self._request_bytes = 0

        # Per-worker watchdog: stops Chrome after IDLE_TIMEOUT seconds.
        t = threading.Thread(target=self._watchdog, daemon=True)
        t.start()

    def _log_prefix(self):
        return f"[Worker-{self._index}]"

    def _watchdog(self):
        """Polls every 30s and stops Chrome if it has been idle too long."""
        while True:
            time.sleep(30)
            if (
                self._sb is not None
                and self._last_request_time > 0
                and (time.time() - self._last_request_time) > IDLE_TIMEOUT
            ):
                with self._lock:
                    if (
                        self._sb is not None
                        and self._last_request_time > 0
                        and (time.time() - self._last_request_time) > IDLE_TIMEOUT
                    ):
                        print(f"{self._log_prefix()} Idle timeout — stopping Chrome", flush=True)
                        self._stop()

    def _build_kwargs(self, proxy):
        kwargs = {
            "ad_block": False if proxy else True,
            "headless": False,
            "headless2": False,
            "user_data_dir": self._profile_dir,
        }

        if self._is_linux:
            kwargs["binary_location"] = "/usr/bin/google-chrome-stable"

        kwargs["chromium_arg"] = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--disable-sync",
            "--disable-background-networking",
            "--disable-default-apps",
            "--disable-component-update",
            f"--disk-cache-dir={self._cache_dir}",
            "--disk-cache-size=209715200",  # 200 MB
            "--host-resolver-rules="
            "MAP *.gvt1.com 0.0.0.0,"
            "MAP update.googleapis.com 0.0.0.0,"
            "MAP dl.google.com 0.0.0.0,"
            "MAP edgedl.me.gvt1.com 0.0.0.0",
            "--disable-features=OptimizationHints,MediaRouter,CertificateTransparencyComponentUpdater",
        ]

        if proxy:
            kwargs["proxy"] = proxy

        return kwargs

    def _cache_is_cold(self):
        return not os.path.exists(os.path.join(self._cache_dir, "index"))

    def _remove_lock_files(self):
        for lock_file in ["SingletonLock", "SingletonCookie", "SingletonSocket"]:
            try:
                os.remove(os.path.join(self._profile_dir, lock_file))
            except OSError:
                pass

    def _remove_warmup_lock_files(self):
        for lock_file in ["SingletonLock", "SingletonCookie", "SingletonSocket"]:
            try:
                os.remove(os.path.join(self._warmup_profile_dir, lock_file))
            except OSError:
                pass

    def _populate_cache(self, log_fn):
        """Pre-warm shared disk cache without proxy. Only one worker does this;
        others skip if warmup is already done or in progress."""
        global _cache_warmed

        with _cache_warm_lock:
            if _cache_warmed:
                log_fn(f"{self._log_prefix()} Cache already warmed by another worker — skipping warmup")
                return
            # Mark as warmed immediately so concurrent workers don't double-warm
            _cache_warmed = True

        import mycdp
        log_fn(f"{self._log_prefix()} Pre-warming cache without proxy (saves proxy bandwidth on first real request)...")
        try:
            self._remove_warmup_lock_files()
            kwargs = self._build_kwargs(proxy=None)
            kwargs["user_data_dir"] = self._warmup_profile_dir
            sb = sb_cdp.Chrome(**kwargs)
            tab = sb.get_active_tab()
            loop = sb.get_event_loop()
            loop.run_until_complete(tab.send(mycdp.network.enable()))
            loop.run_until_complete(tab.send(mycdp.network.set_blocked_urls(urls=BLOCKED_URLS)))
            sb.open("https://www.google.com/search?q=test")
            time.sleep(5)
            sb.driver.stop()
            log_fn(f"{self._log_prefix()} ✅ Cache pre-warmed — Google JS/CSS now on disk")
        except Exception as e:
            log_fn(f"{self._log_prefix()} ⚠️  Cache pre-warm failed (non-fatal): {e}")
        finally:
            self._remove_warmup_lock_files()

    def _start(self, proxy, log_fn):
        import mycdp

        if proxy:
            self._populate_cache(log_fn)

        self._remove_lock_files()

        if self._is_linux:
            try:
                subprocess.run(
                    ["/usr/bin/google-chrome-stable",
                     "--headless=new", "--no-sandbox", "--disable-dev-shm-usage",
                     "--dump-dom", "about:blank"],
                    capture_output=True, text=True, timeout=10
                )
            except Exception:
                pass

        self._sb = sb_cdp.Chrome(**self._build_kwargs(proxy))
        self._tab = self._sb.get_active_tab()
        self._loop = self._sb.get_event_loop()
        self._current_proxy = proxy

        self._loop.run_until_complete(self._tab.send(mycdp.network.enable()))
        self._loop.run_until_complete(
            self._tab.send(mycdp.network.set_blocked_urls(urls=BLOCKED_URLS))
        )

        def _on_loading_finished(event):
            with self._bytes_lock:
                self._request_bytes += int(event.encoded_data_length or 0)

        self._tab.add_handler(mycdp.network.LoadingFinished, _on_loading_finished)
        log_fn(f"{self._log_prefix()} ✅ Chrome started, URL blocking enabled ({len(BLOCKED_URLS)} patterns)")

    def _stop(self):
        try:
            if self._sb is not None:
                self._sb.driver.stop()
        except Exception:
            pass
        finally:
            self._sb = None
            self._tab = None
            self._loop = None
            self._current_proxy = None

    def _is_alive(self):
        if self._sb is None:
            return False
        import mycdp
        try:
            self._loop.run_until_complete(
                self._tab.send(mycdp.runtime.evaluate(expression="1+1"))
            )
            return True
        except Exception:
            return False

    def _ensure_ready(self, proxy, log_fn):
        idle_too_long = (
            self._last_request_time > 0
            and (time.time() - self._last_request_time) > IDLE_TIMEOUT
        )
        proxy_changed = self._sb is not None and self._current_proxy != proxy

        if self._sb is None:
            reason = "first start"
        elif proxy_changed:
            reason = "proxy changed"
        elif idle_too_long:
            reason = "idle timeout"
        elif not self._is_alive():
            reason = "Chrome unresponsive"
        else:
            log_fn(f"{self._log_prefix()} ✅ Reusing existing Chrome instance")
            return

        log_fn(f"{self._log_prefix()} Starting Chrome ({reason})")
        self._stop()
        self._start(proxy, log_fn)

    def _handle_cookie_consent(self):
        reject_selector = '#L2AGLb'
        accept_selector = '#WOwltc'
        if random.choice([True, False]):
            if self._sb.click_if_visible(reject_selector):
                self._sb.sleep(1)
                return True
            elif self._sb.click_if_visible(accept_selector):
                self._sb.sleep(1)
                return True
        else:
            if self._sb.click_if_visible(accept_selector):
                self._sb.sleep(1)
                return True
            elif self._sb.click_if_visible(reject_selector):
                self._sb.sleep(1)
                return True
        return False

    def _dismiss_popups(self):
        selectors = [
            'g-raised-button[jsaction="click:O6N1Pb"]',
            '.mpQYc g-raised-button',
            '[role="dialog"] .mpQYc [role="button"]',
            'button[aria-label*="Block"]',
            'button[aria-label*="Don\'t allow"]',
            'button[data-value="Block"]',
            '[data-value="Decline"]',
            'button[aria-label="No thanks"]',
            '.modal button[aria-label="Close"]',
            '.close-button',
        ]
        for selector in selectors:
            try:
                if self._sb.click_if_visible(selector):
                    self._sb.sleep(0.5)
            except Exception:
                continue

    def scrape(self, target_url, proxy=None, query_string=None, take_screenshot=True):
        """
        Scrape target_url using this Chrome worker.
        Returns a dict with success, url, html, debug_info, and optionally
        screenshot_base64, query, proxy.
        """
        import mycdp

        debug_log = []

        def log_fn(msg):
            debug_log.append(msg)

        with self._lock:
            try:
                self._ensure_ready(proxy, log_fn)
                self._last_request_time = time.time()

                with self._bytes_lock:
                    self._request_bytes = 0

                self._loop.run_until_complete(
                    self._tab.send(mycdp.network.clear_browser_cookies())
                )
                log_fn(f"{self._log_prefix()} ✅ Cookies cleared (disk cache preserved)")

                log_fn(f"{self._log_prefix()} Navigating to: {target_url}")
                self._sb.open(target_url)
                self._sb.sleep(2)

                if proxy:
                    proxy_data = detect_proxy_timezone(proxy, log_fn, max_retries=3)
                    if proxy_data and proxy_data.get('timezone'):
                        try:
                            log_fn(f"{self._log_prefix()} Applying dynamic timezone: {proxy_data['timezone']}")
                            self._loop.run_until_complete(
                                self._tab.send(mycdp.emulation.set_timezone_override(
                                    timezone_id=proxy_data['timezone']
                                ))
                            )
                            log_fn(f"{self._log_prefix()} ✅ Dynamic timezone applied")
                        except Exception as e:
                            log_fn(f"{self._log_prefix()} ⚠️  Could not apply timezone: {e}")
                    else:
                        log_fn(f"{self._log_prefix()} ⚠️  Skipping timezone override (detection failed)")
                else:
                    log_fn(f"{self._log_prefix()} No proxy - skipping timezone detection")

                self._sb.sleep(1)

                self._handle_cookie_consent()
                self._dismiss_popups()

                self._sb.scroll_to_bottom()
                self._sb.sleep(1)
                self._sb.scroll_to_top()
                self._sb.sleep(1)

                final_url = self._sb.get_current_url()
                log_fn(f"{self._log_prefix()} Final URL: {final_url}")

                page_html = self._sb.get_page_source()
                html_length = len(page_html)
                log_fn(f"{self._log_prefix()} HTML length: {html_length:,} chars")

                is_captcha = (
                    '/sorry/' in final_url
                    or 'sorry.google.com' in final_url
                    or html_length < 500_000
                    or 'detected unusual traffic' in page_html.lower()
                )
                if is_captcha:
                    with self._bytes_lock:
                        bytes_used = self._request_bytes
                    bandwidth_kb = round(bytes_used / 1024, 1)
                    bandwidth_mb = round(bytes_used / (1024 * 1024), 3)
                    log_fn(f"{self._log_prefix()} ⚠️  CAPTCHA detected (html={html_length:,}, url={final_url}) — stopping Chrome")
                    log_fn(f"{self._log_prefix()} Bandwidth this request: {bandwidth_kb} KB ({bandwidth_mb} MB)")
                    self._stop()
                    return {
                        "success": False,
                        "captcha": True,
                        "error": "CAPTCHA detected",
                        "url": final_url,
                        "debug_info": {
                            "mode": "desktop",
                            "worker": self._index,
                            "implementation": "ChromePool",
                            "logs": debug_log,
                            "html_length": html_length,
                            "bandwidth_bytes": bytes_used,
                            "bandwidth_kb": bandwidth_kb,
                            "bandwidth_mb": bandwidth_mb,
                        },
                    }

                screenshot_base64 = None
                if take_screenshot:
                    log_fn(f"{self._log_prefix()} Capturing screenshot...")
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                        tmp_path = tmp.name

                    self._sb.loop.run_until_complete(
                        self._sb.page.save_screenshot(tmp_path, full_page=True)
                    )

                    with open(tmp_path, 'rb') as f:
                        screenshot_base64 = base64.b64encode(f.read()).decode('utf-8')

                    os.remove(tmp_path)

                    screenshot_len = len(screenshot_base64)
                    log_fn(f"{self._log_prefix()} Screenshot size: {screenshot_len:,} chars")
                    if screenshot_len < 100000:
                        log_fn(f"{self._log_prefix()} ⚠️  Small screenshot (<100k) - possible CAPTCHA")
                    elif screenshot_len > 500000:
                        log_fn(f"{self._log_prefix()} ✅ Large screenshot (>500k) - likely real content")

                self._last_request_time = time.time()

                with self._bytes_lock:
                    bytes_used = self._request_bytes
                bandwidth_kb = round(bytes_used / 1024, 1)
                bandwidth_mb = round(bytes_used / (1024 * 1024), 3)
                log_fn(f"{self._log_prefix()} Bandwidth this request: {bandwidth_kb} KB ({bandwidth_mb} MB)")

                response = {
                    "success": True,
                    "url": final_url,
                    "html": page_html,
                    "debug_info": {
                        "mode": "desktop",
                        "worker": self._index,
                        "implementation": "ChromePool",
                        "logs": debug_log,
                        "html_length": html_length,
                        "bandwidth_bytes": bytes_used,
                        "bandwidth_kb": bandwidth_kb,
                        "bandwidth_mb": bandwidth_mb,
                    },
                }

                if screenshot_base64:
                    response["screenshot_base64"] = screenshot_base64
                    response["debug_info"]["screenshot_length"] = len(screenshot_base64)

                if query_string:
                    response["query"] = query_string

                if proxy:
                    response["proxy"] = proxy

                log_fn(f"{self._log_prefix()} ✅ Desktop scraping completed")
                return response

            except Exception as e:
                log_fn(f"{self._log_prefix()} ❌ Desktop scrape error: {str(e)}")
                self._stop()
                return {
                    "success": False,
                    "error": str(e),
                    "url": target_url,
                    "debug_info": {
                        "mode": "desktop",
                        "worker": self._index,
                        "implementation": "ChromePool",
                        "logs": debug_log,
                    },
                }


class ChromePool:
    """Pool of N persistent Chrome workers. Concurrent requests are dispatched
    to any available worker; callers block (up to timeout) if all are busy."""

    def __init__(self, size=1):
        self._size = size
        is_linux = platform.system() == "Linux"
        shared_cache = (
            "/tmp/chrome-cache-desktop"
            if is_linux
            else os.path.expanduser("~/.chrome-cache-desktop")
        )
        self._workers = [
            ChromeDesktop(index=i, shared_cache_dir=shared_cache)
            for i in range(size)
        ]
        # Queue holds indices of currently available workers
        self._available: queue.Queue = queue.Queue()
        for i in range(size):
            self._available.put(i)

        print(f"[ChromePool] Initialized with {size} worker(s)", flush=True)

    def scrape(self, target_url, proxy=None, query_string=None, take_screenshot=True):
        """Acquire a free worker, run the scrape, then release the worker."""
        try:
            worker_idx = self._available.get(timeout=120)
        except queue.Empty:
            return {
                "success": False,
                "error": f"All {self._size} Chrome worker(s) busy — request timed out waiting for a free worker",
            }

        try:
            return self._workers[worker_idx].scrape(target_url, proxy, query_string, take_screenshot)
        finally:
            self._available.put(worker_idx)

    def status(self):
        """Return status of all workers (for /chrome-status endpoint)."""
        import time
        statuses = []
        for w in self._workers:
            running = w._sb is not None
            proxy = w._current_proxy
            if proxy and '@' in proxy:
                proxy = '***@' + proxy.split('@', 1)[1]
            idle_seconds = round(time.time() - w._last_request_time) if w._last_request_time else None
            statuses.append({
                "worker": w._index,
                "running": running,
                "current_proxy": proxy,
                "idle_seconds": idle_seconds,
            })
        return statuses


# ---------------------------------------------------------------------------
# Module-level pool — size controlled by CHROME_POOL_SIZE env var (default 1)
# ---------------------------------------------------------------------------
_pool_size = int(os.environ.get("CHROME_POOL_SIZE", "1"))
_pool = ChromePool(size=_pool_size)


def scrape_desktop(target_url, proxy=None, query_string=None, take_screenshot=True):
    """Convenience wrapper — dispatches to the module-level ChromePool."""
    return _pool.scrape(target_url, proxy, query_string, take_screenshot)


def get_pool_status():
    """Return pool status (used by /chrome-status endpoint)."""
    return _pool.status()

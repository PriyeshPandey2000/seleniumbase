"""Persistent Chrome instance for a single CDP-mode session.

One ChromeDesktop per pod. The session (profile dir + cache dir) lives on
Google Cloud Filestore so it survives pod restarts and is visible to all pods.

Lifecycle:
  - First request (or after pod restart) → start Chrome, warm cache if cold
  - Subsequent requests (same session) → reuse Chrome, clear cookies only
  - CAPTCHA or exception → stop Chrome (Crawler retires the session)
  - /stop called by Crawler → stop Chrome, pod is free for next session

Cache warmup:
  - Runs without proxy on first use of a cache dir (cold = no index file)
  - Skipped if cache dir already has content (warm, e.g. pod restart recovery)
  - Warmup profile is ephemeral (/tmp) — only the cache dir is on Filestore
"""

import os
import platform
import time
import json
import base64
import tempfile
import random
import subprocess
import threading
import urllib.request
import urllib.error

from seleniumbase import sb_cdp

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
    # Google post-load tracking & logging
    "*google.com/gen_204*",
    "*google.com/client_204*",
    "*google.com/log*",
    "*google.com/complete/search*",
    "*google.com/searchbyimage*",
    "*google.com/async/*",
    "*google.com/s?*",
    # Google Maps tiles
    "*maps.googleapis.com*",
    "*maps.gstatic.com*",
    "*/maps/vt*",
    "*/maps/api*",
]


def detect_proxy_timezone(proxy_string, log_fn, max_retries=3):
    """
    Detect timezone and geolocation from proxy using ip-api.com.
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
    """
    One persistent Chrome instance tied to a single session.

    profile_dir lives on Filestore — it persists across pod restarts.
    Chrome stores its HTTP cache inside the profile automatically
    (at {profile_dir}/Default/Cache/). No separate cache_dir needed.

    On pod restart with the same profile_dir:
      - Chrome finds the existing profile + HTTP cache on Filestore
      - First request is warm (no re-downloading of Google assets)
      - Cookies and session state are preserved
    """

    def __init__(self, session_id: str, profile_dir: str):
        self._session_id = session_id
        self._profile_dir = profile_dir
        self._is_linux = platform.system() == "Linux"

        os.makedirs(self._profile_dir, exist_ok=True)

        self._sb = None
        self._tab = None
        self._loop = None
        self._current_proxy = None

        # Serialises scrape vs stop calls on this instance
        self._lock = threading.Lock()

        # Bandwidth tracking
        self._bytes_lock = threading.Lock()
        self._request_bytes = 0

    def _log(self, msg):
        print(f"[Session-{self._session_id[:8]}] {msg}", flush=True)

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
            "--disk-cache-size=209715200",  # 200 MB cap (Chrome manages location inside profile)
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

    def _remove_lock_files(self):
        for lock_file in ["SingletonLock", "SingletonCookie", "SingletonSocket"]:
            try:
                os.remove(os.path.join(self._profile_dir, lock_file))
            except OSError:
                pass

    def _start(self, proxy, log_fn):
        import mycdp

        self._remove_lock_files()

        if self._is_linux:
            # Touch Chrome once to avoid the "first run" slowness
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
        log_fn(f"✅ Chrome started, URL blocking enabled ({len(BLOCKED_URLS)} patterns)")

    def stop(self):
        """Stop Chrome. Safe to call from any thread."""
        with self._lock:
            self._stop_unlocked()

    def _stop_unlocked(self):
        """Stop Chrome — must be called with self._lock held."""
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

    def is_alive(self):
        """Return True if Chrome is running and responsive."""
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
        """Start Chrome if not running or if unresponsive."""
        if self._sb is None:
            reason = "first start"
        elif not self.is_alive():
            reason = "Chrome unresponsive"
        else:
            log_fn("✅ Reusing existing Chrome instance (warm cache)")
            return

        log_fn(f"Starting Chrome ({reason})")
        self._stop_unlocked()
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
        Scrape target_url using this Chrome instance.
        Returns a dict with success, url, html, debug_info, and optionally screenshot_base64.
        On CAPTCHA or exception, stops Chrome (Crawler should retire this session).
        """
        import mycdp

        debug_log = []

        def log_fn(msg):
            debug_log.append(msg)
            self._log(msg)

        with self._lock:
            try:
                self._ensure_ready(proxy, log_fn)

                with self._bytes_lock:
                    self._request_bytes = 0

                # self._loop.run_until_complete(
                #     self._tab.send(mycdp.network.clear_browser_cookies())
                # )
                # log_fn("✅ Cookies cleared (disk cache preserved)")

                log_fn(f"Navigating to: {target_url}")
                self._sb.open(target_url)
                self._sb.sleep(2)

                if proxy:
                    proxy_data = detect_proxy_timezone(proxy, log_fn, max_retries=3)
                    if proxy_data and proxy_data.get('timezone'):
                        try:
                            log_fn(f"Applying dynamic timezone: {proxy_data['timezone']}")
                            self._loop.run_until_complete(
                                self._tab.send(mycdp.emulation.set_timezone_override(
                                    timezone_id=proxy_data['timezone']
                                ))
                            )
                            log_fn("✅ Dynamic timezone applied")
                        except Exception as e:
                            log_fn(f"⚠️  Could not apply timezone: {e}")
                    else:
                        log_fn("⚠️  Skipping timezone override (detection failed)")
                else:
                    log_fn("No proxy — skipping timezone detection")

                self._sb.sleep(1)

                self._handle_cookie_consent()
                self._dismiss_popups()

                final_url = self._sb.get_current_url()
                log_fn(f"Final URL: {final_url}")

                page_html = self._sb.get_page_source()
                html_length = len(page_html)
                log_fn(f"HTML length: {html_length:,} chars")

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
                    log_fn(f"⚠️  CAPTCHA detected (html={html_length:,}) — stopping Chrome")
                    self._stop_unlocked()
                    return {
                        "success": False,
                        "captcha": True,
                        "error": "CAPTCHA detected",
                        "url": final_url,
                        "debug_info": {
                            "session_id": self._session_id,
                            "logs": debug_log,
                            "html_length": html_length,
                            "bandwidth_kb": bandwidth_kb,
                            "bandwidth_mb": bandwidth_mb,
                        },
                    }

                screenshot_base64 = None
                if take_screenshot:
                    log_fn("Capturing screenshot...")
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                        tmp_path = tmp.name

                    self._sb.loop.run_until_complete(
                        self._sb.page.save_screenshot(tmp_path, full_page=True)
                    )

                    with open(tmp_path, 'rb') as f:
                        screenshot_base64 = base64.b64encode(f.read()).decode('utf-8')

                    os.remove(tmp_path)

                    screenshot_len = len(screenshot_base64)
                    log_fn(f"Screenshot size: {screenshot_len:,} chars")
                    if screenshot_len < 100000:
                        log_fn("⚠️  Small screenshot (<100k) - possible CAPTCHA")
                    elif screenshot_len > 500000:
                        log_fn("✅ Large screenshot (>500k) - likely real content")

                with self._bytes_lock:
                    bytes_used = self._request_bytes
                bandwidth_kb = round(bytes_used / 1024, 1)
                bandwidth_mb = round(bytes_used / (1024 * 1024), 3)
                log_fn(f"Bandwidth this request: {bandwidth_kb} KB ({bandwidth_mb} MB)")

                response = {
                    "success": True,
                    "url": final_url,
                    "html": page_html,
                    "debug_info": {
                        "session_id": self._session_id,
                        "logs": debug_log,
                        "html_length": html_length,
                        "bandwidth_kb": bandwidth_kb,
                        "bandwidth_mb": bandwidth_mb,
                    },
                }

                if screenshot_base64:
                    response["screenshot_base64"] = screenshot_base64
                    response["debug_info"]["screenshot_length"] = len(screenshot_base64)

                if query_string:
                    response["query"] = query_string

                log_fn("✅ Scrape completed")
                return response

            except Exception as e:
                log_fn(f"❌ Scrape error: {str(e)}")
                self._stop_unlocked()
                return {
                    "success": False,
                    "error": str(e),
                    "url": target_url,
                    "debug_info": {
                        "session_id": self._session_id,
                        "logs": debug_log,
                    },
                }

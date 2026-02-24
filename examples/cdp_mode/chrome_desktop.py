"""Persistent Chrome Desktop singleton for CDP-mode scraping.

Keeps a single Chrome process alive across requests so Google JS/CSS
(~1 MB) stays in the disk cache. Subsequent requests only fetch fresh
HTML + hotel data (~300–500 KB) instead of ~1.5 MB per request.

Restart conditions:
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
import tempfile
import random
import subprocess
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
]


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
    """Persistent singleton Chrome instance for desktop CDP scraping."""

    def __init__(self):
        self._sb = None
        self._tab = None
        self._loop = None
        self._current_proxy = None
        self._last_request_time = 0
        self._is_linux = platform.system() == "Linux"

        if self._is_linux:
            self._profile_dir = "/tmp/chrome-profile-desktop"
            self._cache_dir = "/tmp/chrome-cache-desktop"
        else:
            self._profile_dir = os.path.expanduser("~/.chrome-profile-desktop")
            self._cache_dir = os.path.expanduser("~/.chrome-cache-desktop")

        os.makedirs(self._profile_dir, exist_ok=True)
        os.makedirs(self._cache_dir, exist_ok=True)

        # Background watchdog: actively kills Chrome after IDLE_TIMEOUT seconds.
        import threading
        t = threading.Thread(target=self._watchdog, daemon=True)
        t.start()

    def _watchdog(self):
        """Polls every 30s and stops Chrome if it has been idle too long."""
        while True:
            time.sleep(30)
            if (
                self._sb is not None
                and self._last_request_time > 0
                and (time.time() - self._last_request_time) > IDLE_TIMEOUT
            ):
                print("[ChromeDesktop] Idle timeout reached — stopping Chrome", flush=True)
                self._stop()

    def _build_kwargs(self, proxy):
        kwargs = {
            "ad_block": False if proxy else True,
            "headless": False,
            "headless2": False,
            # user_data_dir must be a direct kwarg — SeleniumBase adds
            # --user-data-dir automatically from this value.
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
            "--disable-component-update",   # Stop Chrome auto-update downloads through proxy
            # Explicit disk cache dir — forces Chrome to use disk cache even when
            # a proxy is active (proxy mode can silently switch to memory-only cache)
            f"--disk-cache-dir={self._cache_dir}",
            "--disk-cache-size=209715200",  # 200 MB
            # Null-route Chrome telemetry/update domains at DNS level so they
            # never reach the proxy at all
            "--host-resolver-rules="
            "MAP *.gvt1.com 0.0.0.0,"
            "MAP update.googleapis.com 0.0.0.0,"
            "MAP dl.google.com 0.0.0.0,"
            "MAP edgedl.me.gvt1.com 0.0.0.0",
            # Kill remaining background callers
            "--disable-features=OptimizationHints,MediaRouter,CertificateTransparencyComponentUpdater",
        ]

        if proxy:
            kwargs["proxy"] = proxy

        return kwargs

    def _start(self, proxy, log_fn):
        import mycdp

        # Remove stale lock files left by crashed/killed Chrome sessions.
        for lock_file in ["SingletonLock", "SingletonCookie", "SingletonSocket"]:
            try:
                os.remove(os.path.join(self._profile_dir, lock_file))
                log_fn(f"Removed stale lock: {lock_file}")
            except OSError:
                pass  # Doesn't exist — fine

        # Warm up Chrome binary before launching CDP session.
        # On first deploy this prevents "Failed to connect to the browser"
        # by ensuring the binary is ready and any one-time init is done.
        if self._is_linux:
            try:
                subprocess.run(
                    ["/usr/bin/google-chrome-stable",
                     "--headless=new", "--no-sandbox", "--disable-dev-shm-usage",
                     "--dump-dom", "about:blank"],
                    capture_output=True, text=True, timeout=10
                )
                log_fn("Chrome warmup done")
            except Exception:
                pass  # Non-fatal — continue regardless

        self._sb = sb_cdp.Chrome(**self._build_kwargs(proxy))
        self._tab = self._sb.get_active_tab()
        self._loop = self._sb.get_event_loop()
        self._current_proxy = proxy

        self._loop.run_until_complete(self._tab.send(mycdp.network.enable()))
        self._loop.run_until_complete(
            self._tab.send(mycdp.network.set_blocked_urls(urls=BLOCKED_URLS))
        )
        log_fn(f"✅ Chrome started, URL blocking enabled ({len(BLOCKED_URLS)} patterns)")

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
            log_fn("✅ Reusing existing Chrome instance")
            return

        log_fn(f"Starting Chrome ({reason})")
        self._stop()
        self._start(proxy, log_fn)

    def _handle_cookie_consent(self):
        reject_selector = '#L2AGLb'  # "Reject all"
        accept_selector = '#WOwltc'  # "Accept all"
        # 50/50 random to appear more human
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
        Scrape target_url using the persistent Chrome instance.
        Returns a dict with success, url, html, debug_info, and optionally
        screenshot_base64, query, proxy.
        """
        import mycdp

        debug_log = []

        def log_fn(msg):
            debug_log.append(msg)

        try:
            self._ensure_ready(proxy, log_fn)
            self._last_request_time = time.time()

            # Clear cookies before navigation — same privacy as incognito,
            # but disk cache is preserved (that's the whole point).
            self._loop.run_until_complete(
                self._tab.send(mycdp.network.clear_browser_cookies())
            )
            log_fn("✅ Cookies cleared (disk cache preserved)")

            log_fn(f"Navigating to: {target_url}")
            self._sb.open(target_url)
            self._sb.sleep(2)

            # Detect and apply timezone from proxy location
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
                log_fn("No proxy - skipping timezone detection")

            self._sb.sleep(1)

            self._handle_cookie_consent()
            self._dismiss_popups()

            self._sb.scroll_to_bottom()
            self._sb.sleep(1)
            self._sb.scroll_to_top()
            self._sb.sleep(1)

            final_url = self._sb.get_current_url()
            log_fn(f"Final URL: {final_url}")

            page_html = self._sb.get_page_source()
            log_fn(f"HTML length: {len(page_html):,} chars")

            # Screenshot
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

            self._last_request_time = time.time()

            response = {
                "success": True,
                "url": final_url,
                "html": page_html,
                "debug_info": {
                    "mode": "desktop",
                    "implementation": "Persistent Chrome (ChromeDesktop)",
                    "logs": debug_log,
                    "html_length": len(page_html),
                },
            }

            if screenshot_base64:
                response["screenshot_base64"] = screenshot_base64
                response["debug_info"]["screenshot_length"] = len(screenshot_base64)

            if query_string:
                response["query"] = query_string

            if proxy:
                response["proxy"] = proxy

            log_fn("✅ Desktop scraping completed")
            return response

        except Exception as e:
            log_fn(f"❌ Desktop scrape error: {str(e)}")
            self._stop()
            return {
                "success": False,
                "error": str(e),
                "url": target_url,
                "debug_info": {
                    "mode": "desktop",
                    "implementation": "Persistent Chrome (ChromeDesktop)",
                    "logs": debug_log,
                },
            }


# Module-level singleton — one Chrome process shared across all requests.
_desktop = ChromeDesktop()


def scrape_desktop(target_url, proxy=None, query_string=None, take_screenshot=True):
    """Convenience wrapper around the module-level ChromeDesktop singleton."""
    return _desktop.scrape(target_url, proxy, query_string, take_screenshot)

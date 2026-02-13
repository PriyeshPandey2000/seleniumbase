"""CDP Mode Web Scraper - Returns JSON output"""
from seleniumbase import sb_cdp, SB
import sys
import argparse
import os
import json
import base64
import subprocess
import platform
import time
import urllib.request
import urllib.error
import random

# Initialize debug log for troubleshooting
debug_log = []

def log_debug(message):
    """Log debug information for output"""
    debug_log.append(message)
    print(f"[DEBUG] {message}", file=sys.stderr)

# Real mobile device profiles (2-3 most popular, accurate devices)
MOBILE_DEVICES = [
    {
        "name": "iPhone 13",
        "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
        "viewport": {"width": 390, "height": 844, "device_scale_factor": 3},
        "platform": "iPhone",
    },
    {
        "name": "Samsung Galaxy S21",
        "user_agent": "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "viewport": {"width": 360, "height": 800, "device_scale_factor": 3},
        "platform": "Linux armv8l",
    },
]

def detect_proxy_timezone(proxy_string, max_retries=3):
    """
    Detect timezone and geolocation from proxy using ip-api.com
    Uses Python urllib (built-in, no dependencies)
    Returns: dict with timezone, coords, country, city, ip (or None if failed)
    """
    log_debug("Detecting proxy timezone and location...")

    # Setup proxy handler
    proxy_handler = None
    if proxy_string:
        if '@' in proxy_string:
            # Authenticated proxy: user:pass@host:port
            proxy_handler = urllib.request.ProxyHandler({
                'http': f'http://{proxy_string}',
                'https': f'http://{proxy_string}'
            })
        else:
            # Unauthenticated proxy: host:port
            proxy_handler = urllib.request.ProxyHandler({
                'http': f'http://{proxy_string}',
                'https': f'http://{proxy_string}'
            })

    for attempt in range(1, max_retries + 1):
        try:
            # Build opener with proxy
            if proxy_handler:
                opener = urllib.request.build_opener(proxy_handler)
            else:
                opener = urllib.request.build_opener()

            # Make request
            req = urllib.request.Request(
                'http://ip-api.com/json/?fields=status,query,timezone,lat,lon,country,city'
            )

            with opener.open(req, timeout=8) as response:
                if response.status == 200:
                    result = json.loads(response.read().decode('utf-8'))

                    if result and result.get('status') == 'success' and result.get('timezone'):
                        log_debug(f"✅ Proxy location detected (attempt {attempt}):")
                        log_debug(f"   IP: {result.get('query')}")
                        log_debug(f"   Country: {result.get('country')}")
                        log_debug(f"   City: {result.get('city')}")
                        log_debug(f"   Timezone: {result.get('timezone')}")
                        log_debug(f"   Coords: {result.get('lat')}, {result.get('lon')}")

                        return {
                            'timezone': result.get('timezone'),
                            'coords': {
                                'latitude': result.get('lat'),
                                'longitude': result.get('lon')
                            } if result.get('lat') and result.get('lon') else None,
                            'country': result.get('country'),
                            'city': result.get('city'),
                            'ip': result.get('query')
                        }
                    else:
                        log_debug(f"⚠️  IP-API attempt {attempt} failed: Invalid response")
                else:
                    log_debug(f"⚠️  IP-API attempt {attempt} failed: HTTP {response.status}")

        except urllib.error.URLError as e:
            log_debug(f"⚠️  IP-API attempt {attempt} URLError: {str(e)}")
        except Exception as e:
            log_debug(f"⚠️  IP-API attempt {attempt} error: {str(e)}")

        # Wait before retry (except on last attempt)
        if attempt < max_retries:
            time.sleep(1)

    log_debug("❌ Failed to detect proxy timezone after all retries")
    return None

# Parse command line arguments
parser = argparse.ArgumentParser(description='CDP Mode Web Scraper')
parser.add_argument('query', nargs='?', default=None,
                    help='Search query for Google')
parser.add_argument('--url', type=str, default=None,
                    help='Direct URL to scrape')
parser.add_argument('--proxy', type=str, default=None,
                    help='Proxy server. Format: "host:port" or "username:password@host:port"')
parser.add_argument('--user-agent', type=str, default=None,
                    help='Custom user agent string')
parser.add_argument('--mobile', action='store_true',
                    help='Enable mobile device emulation')
parser.add_argument('--no-screenshot', action='store_true',
                    help='Skip screenshot capture')
args = parser.parse_args()

# Determine target URL
if args.url:
    target_url = args.url
    query_string = None
elif args.query:
    # Build Google search URL
    query_string = args.query
    target_url = f"https://www.google.com/search?q={query_string}&sourceid=chrome&ie=UTF-8"
else:
    print(json.dumps({
        "success": False,
        "error": "Either query or --url must be provided"
    }))
    sys.exit(1)

# ================================================================
# MOBILE MODE: Use high-level UC Mode (proper mobile emulation)
# ================================================================
if args.mobile:
    log_debug("=" * 60)
    log_debug("MOBILE MODE - Using UC Mode with proper device metrics")
    log_debug("=" * 60)
    log_debug(f"Platform: {platform.system()}")
    log_debug(f"Target URL: {target_url}")

    # Detect platform
    is_linux = platform.system() == "Linux"

    # Configure UC Mode for mobile (WITHOUT mobile=True - we'll set manually)
    sb_kwargs = {
        "uc": True,           # Undetected Chrome mode (most stealthy)
        "incognito": True,
        "ad_block": False if args.proxy else True,
        "headless": False,
        "test": False,
    }

    # Platform-specific: Set Chrome binary on Linux
    if is_linux:
        sb_kwargs["chromium_arg"] = "--binary-location=/usr/bin/google-chrome-stable"
        log_debug("Linux detected: Setting Chrome binary")

    # Add proxy if provided
    if args.proxy:
        sb_kwargs["proxy"] = args.proxy
        log_debug(f"Proxy: {args.proxy[:50]}...")

    # Select random real device profile
    device = random.choice(MOBILE_DEVICES)
    log_debug(f"Selected device: {device['name']}")

    mobile_agent = args.user_agent if args.user_agent else device['user_agent']
    log_debug(f"Mobile UA: {mobile_agent[:80]}...")

    try:
        log_debug("Launching Chrome with UC Mode...")

        with SB(**sb_kwargs) as sb:
            # CRITICAL: Set device metrics BEFORE activating CDP mode
            # to avoid viewport leak (desktop -> mobile detection)
            import mycdp

            log_debug("Opening blank page...")
            sb.open("about:blank")

            log_debug("Activating CDP mode...")
            sb.activate_cdp_mode()  # Don't pass agent here - set via CDP later

            # Get CDP tab and event loop for emulation overrides
            tab = sb.cdp.get_active_tab()
            loop = sb.cdp.get_event_loop()

            # Apply device settings FIRST (before any real page loads)
            log_debug(f"Applying {device['name']} settings BEFORE page load...")

            # Set User-Agent with real platform
            loop.run_until_complete(
                tab.send(
                    mycdp.emulation.set_user_agent_override(
                        user_agent=mobile_agent,
                        platform=device['platform']
                    )
                )
            )
            log_debug(f"UA set: {device['platform']}")

            # Set real device viewport
            vp = device['viewport']
            loop.run_until_complete(
                tab.send(
                    mycdp.emulation.set_device_metrics_override(
                        width=vp['width'],
                        height=vp['height'],
                        device_scale_factor=vp['device_scale_factor'],
                        mobile=True
                    )
                )
            )
            log_debug(f"Viewport: {vp['width']}x{vp['height']} @{vp['device_scale_factor']}x")

            # Enable touch emulation
            loop.run_until_complete(
                tab.send(
                    mycdp.emulation.set_touch_emulation_enabled(
                        enabled=True,
                        max_touch_points=5
                    )
                )
            )
            log_debug("Touch emulation enabled")

            # Block heavy resources to save proxy bandwidth
            log_debug("Blocking images, fonts, videos to save bandwidth...")
            loop.run_until_complete(tab.send(mycdp.network.enable()))
            loop.run_until_complete(
                tab.send(
                    mycdp.network.set_blocked_urls(
                        urls=[
                            # Images (biggest bandwidth consumers)
                            "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp",
                            "*.svg", "*.ico", "*.bmp",
                            # Fonts
                            "*.woff", "*.woff2", "*.ttf", "*.otf", "*.eot",
                            # Videos and media
                            "*.mp4", "*.webm", "*.avi", "*.mov", "*.flv",
                            # Other heavy resources
                            "*.pdf", "*.zip", "*.rar",
                            # Google CDN domains (images, thumbnails)
                            "*googleusercontent.com*",
                            "*gstatic.com*",
                            "*encrypted-tbn*",
                            "*yt3.ggpht.com*",  # YouTube profile pics
                            "*ytimg.com*",  # YouTube images
                            # YouTube video thumbnails
                            "*img.youtube.com*",
                            "*i.ytimg.com*",
                            # Ad networks
                            "*.googlesyndication.com*",
                            "*.googletagmanager.com*",
                            "*.google-analytics.com*",
                            "*.doubleclick.net*",
                        ]
                    )
                )
            )
            log_debug("✅ Resource blocking enabled (images, fonts, videos, ads, Google CDN)")

            # Device settings already applied before page load (see above)
            # Now open target URL with mobile fingerprint already set
            log_debug("Opening URL...")
            sb.open(target_url)
            sb.sleep(2)  # Wait for page to load

            # TESTING: Timezone override disabled - might be detection signal!
            # Yesterday got some success without it, today 100% CAPTCHA with it
            log_debug("⚠️  TESTING: Timezone override DISABLED for mobile mode")

            # if args.proxy:
            #     proxy_data = detect_proxy_timezone(args.proxy, max_retries=3)
            #     if proxy_data and proxy_data.get('timezone'):
            #         try:
            #             log_debug(f"Applying dynamic timezone: {proxy_data['timezone']}")
            #             loop.run_until_complete(
            #                 tab.send(mycdp.emulation.set_timezone_override(
            #                     timezone_id=proxy_data['timezone']
            #                 ))
            #             )
            #             log_debug("✅ Dynamic timezone applied")
            #         except Exception as e:
            #             log_debug(f"⚠️  Could not apply timezone/geo: {e}")
            #     else:
            #         log_debug("⚠️  Skipping timezone override (detection failed)")
            # else:
            #     log_debug("No proxy - skipping timezone detection")

            # Log actual user agent being used
            try:
                actual_ua = sb.execute_script("return navigator.userAgent;")
                log_debug(f"Actual UA: {actual_ua[:80]}...")

                is_mobile_ua = any(x in actual_ua.lower() for x in ['mobile', 'android', 'iphone'])
                log_debug(f"Mobile UA detected: {is_mobile_ua}")
            except Exception as e:
                log_debug(f"Could not retrieve UA: {e}")

            # Log viewport dimensions
            try:
                vw = sb.execute_script("return window.innerWidth;")
                vh = sb.execute_script("return window.innerHeight;")
                log_debug(f"Viewport: {vw}x{vh}")

                if vw > 500:
                    log_debug("⚠️  WARNING: Viewport > 500px (should be mobile size ~412px)")
            except Exception as e:
                log_debug(f"Could not get viewport: {e}")

            # Log device capabilities
            try:
                has_touch = sb.execute_script("return 'ontouchstart' in window;")
                platform_val = sb.execute_script("return navigator.platform;")
                log_debug(f"Touch events: {has_touch}")
                log_debug(f"Navigator.platform: {platform_val}")
            except Exception as e:
                log_debug(f"Could not get device props: {e}")

            # Wait for page load
            sb.sleep(3)
            log_debug("Page loaded, waiting 3s...")

            # Handle cookie consent (inline function)
            def handle_cookie_consent():
                import random
                selectors = ['#L2AGLb', '#WOwltc']  # Reject, Accept
                random.shuffle(selectors)
                for sel in selectors:
                    if sb.click_if_visible(sel, timeout=1):
                        sb.sleep(1)
                        return True
                return False

            log_debug("Handling cookie consent...")
            handle_cookie_consent()

            # Dismiss popups
            popup_selectors = [
                'g-raised-button[jsaction="click:O6N1Pb"]',
                'button[aria-label*="Block"]',
                'button[data-value="Block"]',
            ]
            for sel in popup_selectors:
                try:
                    sb.click_if_visible(sel, timeout=0.5)
                except:
                    pass

            # Scroll (human-like behavior)
            log_debug("Scrolling page...")
            sb.scroll_to_bottom()
            sb.sleep(1)
            sb.scroll_to_top()
            sb.sleep(1)

            # Get final URL
            final_url = sb.get_current_url()
            log_debug(f"Final URL: {final_url}")

            # Check if mobile version
            if "/m." in final_url or "m.google" in final_url:
                log_debug("✅ Google mobile version detected")
            else:
                log_debug("⚠️  Desktop URL (Google may not detect mobile)")

            # Get HTML
            page_html = sb.get_page_source()
            log_debug(f"HTML length: {len(page_html):,} chars")

            # Screenshot
            screenshot_base64 = None
            if not args.no_screenshot:
                log_debug("Capturing screenshot...")
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                    tmp_path = tmp.name

                sb.save_screenshot(tmp_path)

                with open(tmp_path, 'rb') as f:
                    screenshot_bytes = f.read()
                    screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')

                log_debug(f"Screenshot size: {len(screenshot_base64):,} chars")

                if len(screenshot_base64) < 100000:
                    log_debug("⚠️  Small screenshot (<100k) - possible CAPTCHA")
                elif len(screenshot_base64) > 500000:
                    log_debug("✅ Large screenshot (>500k) - likely real content")

                os.remove(tmp_path)

            # Build response
            response = {
                "success": True,
                "url": final_url,
                "html": page_html,
                "debug_info": {
                    "mode": "mobile",
                    "implementation": "UC Mode (SB)",
                    "logs": debug_log,
                    "html_length": len(page_html),
                }
            }

            if screenshot_base64:
                response["screenshot_base64"] = screenshot_base64
                response["debug_info"]["screenshot_length"] = len(screenshot_base64)

            if query_string:
                response["query"] = query_string

            if args.proxy:
                response["proxy"] = args.proxy

            log_debug("✅ Mobile scraping completed")

            # Output JSON
            print(json.dumps(response))
            sys.exit(0)

    except Exception as e:
        log_debug(f"❌ Mobile mode error: {str(e)}")
        error_response = {
            "success": False,
            "error": str(e),
            "url": args.url if args.url else f"Google search: {args.query}",
            "debug_info": {
                "mode": "mobile",
                "implementation": "UC Mode (SB)",
                "logs": debug_log,
            }
        }
        print(json.dumps(error_response))
        sys.exit(1)

# ================================================================
# DESKTOP MODE: Keep existing working implementation (raw CDP)
# ================================================================
else:
    log_debug("=" * 60)
    log_debug("DESKTOP MODE - Using existing raw CDP implementation")
    log_debug("=" * 60)

# Detect platform for desktop mode
is_linux_desktop = platform.system() == "Linux"

# Chrome configuration
chrome_kwargs = {
    "incognito": True,
    "ad_block": False if args.proxy else True,  # Disable ad_block with proxy
    "headless": False,  # Full headful mode with Xvfb (20-40% CAPTCHA vs 50-70%)
    "headless2": False,  # Disabled - using true headful mode
}

# Platform-specific: Set Chrome binary on Linux only
if is_linux_desktop:
    chrome_kwargs["binary_location"] = "/usr/bin/google-chrome-stable"
    log_debug("Linux detected: Setting Chrome binary for desktop mode")

# Add essential Chrome flags for cloud environments
chrome_kwargs["chromium_arg"] = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
]

# Add proxy if provided
if args.proxy:
    chrome_kwargs["proxy"] = args.proxy

# Add user agent if provided (or set mobile user agent if mobile mode)
if args.mobile and not args.user_agent:
    # Use iOS User-Agent (iPhone - might be less detectable than Android)
    chrome_kwargs["user_agent"] = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/15.0 Mobile/15E148 Safari/604.1"
    )
elif args.user_agent:
    chrome_kwargs["user_agent"] = args.user_agent

# Add mobile mode if requested (stealthy mobile emulation)
if args.mobile:
    chrome_kwargs["mobile"] = True

try:
    log_debug(f"Target URL: {target_url}")
    if args.proxy:
        log_debug(f"Proxy: {args.proxy[:50]}...")

    # Try to warm up Chrome (non-fatal if it fails)
    chrome_path = "/usr/bin/google-chrome-stable"
    try:
        subprocess.run(
            [chrome_path, '--headless=new', '--no-sandbox', '--disable-dev-shm-usage',
             '--dump-dom', 'about:blank'],
            capture_output=True,
            text=True,
            timeout=10
        )
    except:
        pass  # Continue even if warmup fails

    # Launch Chrome with CDP
    log_debug("Launching Chrome with raw CDP...")
    sb = sb_cdp.Chrome(target_url, **chrome_kwargs)
    log_debug("Chrome launched successfully")

    # Block heavy resources to save proxy bandwidth
    try:
        import mycdp
        tab = sb.get_active_tab()
        loop = sb.get_event_loop()

        log_debug("Blocking images, fonts, videos to save bandwidth...")
        loop.run_until_complete(tab.send(mycdp.network.enable()))
        loop.run_until_complete(
            tab.send(
                mycdp.network.set_blocked_urls(
                    urls=[
                        # Images (biggest bandwidth consumers)
                        "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp",
                        "*.svg", "*.ico", "*.bmp",
                        # Fonts
                        "*.woff", "*.woff2", "*.ttf", "*.otf", "*.eot",
                        # Videos and media
                        "*.mp4", "*.webm", "*.avi", "*.mov", "*.flv",
                        # Other heavy resources
                        "*.pdf", "*.zip", "*.rar",
                        # Google CDN domains (images, thumbnails)
                        "*googleusercontent.com*",
                        "*gstatic.com*",
                        "*encrypted-tbn*",
                        "*yt3.ggpht.com*",  # YouTube profile pics
                        "*ytimg.com*",  # YouTube images
                        # YouTube video thumbnails
                        "*img.youtube.com*",
                        "*i.ytimg.com*",
                        # Ad networks
                        "*.googlesyndication.com*",
                        "*.googletagmanager.com*",
                        "*.google-analytics.com*",
                        "*.doubleclick.net*",
                        "*.amazon-adsystem.com*",
                        "*.adsafeprotected.com*",
                        "*.fastclick.net*",
                        "*.snigelweb.com*",
                        "*.2mdn.net*",
                    ]
                )
            )
        )
        log_debug("✅ Resource blocking enabled (images, fonts, videos, ads, Google CDN)")
    except Exception as e:
        log_debug(f"⚠️  Could not enable resource blocking: {e}")

    # Wait for page to load
    sb.sleep(2)

    # Detect and set timezone dynamically based on proxy location
    if args.proxy:
        proxy_data = detect_proxy_timezone(args.proxy, max_retries=3)
        if proxy_data and proxy_data.get('timezone'):
            try:
                log_debug(f"Applying dynamic timezone: {proxy_data['timezone']}")
                loop.run_until_complete(
                    tab.send(mycdp.emulation.set_timezone_override(
                        timezone_id=proxy_data['timezone']
                    ))
                )
                log_debug("✅ Dynamic timezone applied")
            except Exception as e:
                log_debug(f"⚠️  Could not apply timezone/geo: {e}")
        else:
            log_debug("⚠️  Skipping timezone override (detection failed)")
    else:
        log_debug("No proxy - skipping timezone detection")

    # Additional wait after timezone/geo setup
    sb.sleep(1)

    # ============================================
    # Handle Google Cookie Consent
    # ============================================
    def handle_google_cookie_consent():
        """Handle Google cookie consent banner"""
        reject_selector = '#L2AGLb'  # "Reject all" button
        accept_selector = '#WOwltc'  # "Accept all" button

        # Randomly accept or reject (50/50 chance) to appear more human
        import random
        if random.choice([True, False]):
            if sb.click_if_visible(reject_selector, timeout=1):
                sb.sleep(1)
                return True
            elif sb.click_if_visible(accept_selector, timeout=1):
                sb.sleep(1)
                return True
        else:
            if sb.click_if_visible(accept_selector, timeout=1):
                sb.sleep(1)
                return True
            elif sb.click_if_visible(reject_selector, timeout=1):
                sb.sleep(1)
                return True
        return False

    # ============================================
    # Dismiss Popups and Dialogs
    # ============================================
    def dismiss_popups_and_dialogs():
        """Dismiss all popups, dialogs, and permission prompts"""
        selectors = [
            # Google-specific
            'g-raised-button[jsaction="click:O6N1Pb"]',
            '.mpQYc g-raised-button',
            '[role="dialog"] .mpQYc [role="button"]',
            # Permission buttons
            'button[aria-label*="Block"]',
            'button[aria-label*="Don\'t allow"]',
            'button[data-value="Block"]',
            # Generic close buttons
            '[data-value="Decline"]',
            'button[aria-label="No thanks"]',
            '.modal button[aria-label="Close"]',
            '.close-button',
        ]

        for selector in selectors:
            try:
                if sb.click_if_visible(selector, timeout=0.5):
                    sb.sleep(0.5)
            except:
                continue

    # Handle cookie consent and popups
    handle_google_cookie_consent()
    dismiss_popups_and_dialogs()

    # Scroll page (appears more human)
    sb.scroll_to_bottom()
    sb.sleep(1)
    sb.scroll_to_top()
    sb.sleep(1)

    # Get final URL (after redirects)
    final_url = sb.get_current_url()
    log_debug(f"Final URL: {final_url}")

    # Get page HTML
    page_html = sb.get_page_source()
    log_debug(f"HTML length: {len(page_html):,} chars")

    # Take screenshot if requested
    screenshot_base64 = None
    if not args.no_screenshot:
        log_debug("Capturing screenshot...")
        # Save screenshot to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp_path = tmp.name

        # Capture full page screenshot
        sb.loop.run_until_complete(
            sb.page.save_screenshot(tmp_path, full_page=True)
        )

        # Read and convert to base64
        with open(tmp_path, 'rb') as f:
            screenshot_bytes = f.read()
            screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')

        # Clean up temp file
        os.remove(tmp_path)

        screenshot_len = len(screenshot_base64) if screenshot_base64 else 0
        log_debug(f"Screenshot size: {screenshot_len:,} chars")

        if screenshot_len > 0:
            if screenshot_len < 100000:
                log_debug("⚠️  Small screenshot (<100k) - possible CAPTCHA")
            elif screenshot_len > 500000:
                log_debug("✅ Large screenshot (>500k) - likely real content")

    # Build response
    response = {
        "success": True,
        "url": final_url,
        "html": page_html,
        "debug_info": {
            "mode": "desktop",
            "implementation": "Raw CDP (sb_cdp.Chrome)",
            "logs": debug_log,
            "html_length": len(page_html),
        }
    }

    # Add optional fields
    if screenshot_base64:
        response["screenshot_base64"] = screenshot_base64
        response["debug_info"]["screenshot_length"] = len(screenshot_base64)

    if query_string:
        response["query"] = query_string

    if args.proxy:
        response["proxy"] = args.proxy

    log_debug("✅ Desktop scraping completed")

    # Output JSON (API will parse this)
    print(json.dumps(response))

    # Clean up
    sb.driver.stop()
    sys.exit(0)

except Exception as e:
    # Output error as JSON
    log_debug(f"❌ Desktop mode error: {str(e)}")
    error_response = {
        "success": False,
        "error": str(e),
        "url": args.url if args.url else f"Google search: {args.query}",
        "debug_info": {
            "mode": "desktop",
            "implementation": "Raw CDP (sb_cdp.Chrome)",
            "logs": debug_log,
        }
    }
    print(json.dumps(error_response))
    sys.exit(1)

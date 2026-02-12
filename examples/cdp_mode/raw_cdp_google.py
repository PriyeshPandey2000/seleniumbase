"""CDP Mode Web Scraper - Returns JSON output"""
from seleniumbase import sb_cdp, SB
import sys
import argparse
import os
import json
import base64
import subprocess
import platform

# Initialize debug log for troubleshooting
debug_log = []

def log_debug(message):
    """Log debug information for output"""
    debug_log.append(message)
    print(f"[DEBUG] {message}", file=sys.stderr)

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

    # Configure UC Mode for mobile
    sb_kwargs = {
        "uc": True,           # Undetected Chrome mode (most stealthy)
        "mobile": True,       # Enable proper mobile emulation with device metrics
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

    # Custom user agent (optional - mobile=True auto-generates one)
    if args.user_agent:
        sb_kwargs["agent"] = args.user_agent
        log_debug(f"Custom UA: {args.user_agent[:60]}...")
    else:
        log_debug("Using auto-generated mobile User-Agent")

    try:
        log_debug("Launching Chrome with UC Mode...")

        with SB(**sb_kwargs) as sb:
            # Open target URL
            log_debug("Opening URL...")
            sb.open(target_url)

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

# Chrome configuration
chrome_kwargs = {
    "incognito": True,
    "ad_block": False if args.proxy else True,  # Disable ad_block with proxy
    "headless": False,  # Full headful mode with Xvfb (20-40% CAPTCHA vs 50-70%)
    "headless2": False,  # Disabled - using true headful mode
    "binary_location": "/usr/bin/google-chrome-stable",
}

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

# Timezone mapping for US cities (improves fingerprint consistency)
TIMEZONE_MAP = {
    "newyork": "America/New_York",      # EST/EDT
    "losangeles": "America/Los_Angeles", # PST/PDT
    "chicago": "America/Chicago",        # CST/CDT
    "houston": "America/Chicago",        # CST/CDT (Texas is Central)
    "lasvegas": "America/Los_Angeles",   # PST/PDT (Nevada is Pacific)
}

# Extract city from proxy and set timezone if available
proxy_timezone = None
if args.proxy and "_city-" in args.proxy:
    try:
        city = args.proxy.split("_city-")[1].split("@")[0].lower()
        proxy_timezone = TIMEZONE_MAP.get(city)
    except:
        pass  # If parsing fails, continue without timezone

try:
    log_debug(f"Target URL: {target_url}")
    if args.proxy:
        log_debug(f"Proxy: {args.proxy[:50]}...")
    if proxy_timezone:
        log_debug(f"Proxy timezone: {proxy_timezone}")

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

    # Set timezone to match proxy location (if available)
    if proxy_timezone:
        try:
            import mycdp
            tab = sb.get_active_tab()
            loop = sb.get_event_loop()
            loop.run_until_complete(
                tab.send(mycdp.emulation.set_timezone_override(timezone_id=proxy_timezone))
            )
        except Exception as e:
            pass  # Continue even if timezone setting fails

    # Wait for page to load
    sb.sleep(3)

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

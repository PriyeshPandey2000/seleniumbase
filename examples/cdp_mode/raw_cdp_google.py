"""CDP Mode Web Scraper - Returns JSON output"""
from seleniumbase import sb_cdp
import sys
import argparse
import os
import json
import base64
import subprocess

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
                    help='Enable mobile mode emulation')
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

# Chrome configuration (SAME for desktop and mobile)
# Using headless=False with Xvfb reduces CAPTCHA by 40-60%!
chrome_kwargs = {
    "incognito": True,
    "ad_block": False if args.proxy else True,  # Disable ad_block with proxy
    "headless": False,  # Headful mode with Xvfb (fewer CAPTCHAs!)
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

# Add user agent if provided
if args.user_agent:
    chrome_kwargs["user_agent"] = args.user_agent

# Add mobile mode if requested - ONLY DIFFERENCE
if args.mobile:
    chrome_kwargs["mobile"] = True

try:
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

    # Launch Chrome with CDP (SAME for both desktop and mobile)
    sb = sb_cdp.Chrome(target_url, **chrome_kwargs)

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

    # Get page HTML
    page_html = sb.get_page_source()

    # Take screenshot if requested
    screenshot_base64 = None
    if not args.no_screenshot:
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

    # Build response
    response = {
        "success": True,
        "url": final_url,
        "html": page_html,
    }

    # Add optional fields
    if screenshot_base64:
        response["screenshot_base64"] = screenshot_base64

    if query_string:
        response["query"] = query_string

    if args.proxy:
        response["proxy"] = args.proxy

    # Output JSON (API will parse this)
    print(json.dumps(response))

    # Clean up
    sb.driver.stop()
    sys.exit(0)

except Exception as e:
    # Output error as JSON
    error_response = {
        "success": False,
        "error": str(e),
        "url": args.url if args.url else f"Google search: {args.query}"
    }
    print(json.dumps(error_response))
    sys.exit(1)

"""Pure CDP Mode Google Search - Maximum Bot Evasion"""
from seleniumbase import sb_cdp
import sys
import random
import argparse
import os
import time

# Parse command line arguments
parser = argparse.ArgumentParser(description='Google Search with CDP Mode')
parser.add_argument('search_query', nargs='?', default='best hotels', 
                    help='Search query (default: "best hotels")')
parser.add_argument('--proxy', type=str, default=None,
                    help='Proxy server. Format: "host:port" or "username:password@host:port"')
args = parser.parse_args()

search_query = args.search_query
proxy_string = args.proxy

# Use your full search URL directly
search_url = f"https://www.google.com/search?q={search_query}&oq={search_query}&sourceid=chrome&ie=UTF-8"

# ============================================
# Xvfb Setup (COMMENTED OUT - Using headless2 instead)
# ============================================
# Uncomment this section if you need headful mode (headless=False) with Xvfb
#
# # Check DISPLAY environment variable
# display = os.environ.get('DISPLAY', ':100')
# print(f"[*] DISPLAY environment variable: {display}")
#
# # Try to start Xvfb if it's not running (for docker-compose run scenarios)
# import subprocess
# xvfb_running = False
# try:
#     result = subprocess.run(
#         ['pgrep', '-f', f'Xvfb {display}'],
#         capture_output=True,
#         timeout=1
#     )
#     if result.returncode == 0:
#         xvfb_running = True
#         print(f"[+] Xvfb is already running on display {display}")
# except Exception:
#     pass
#
# if not xvfb_running:
#     print(f"[*] Xvfb not running, attempting to start it on {display}...")
#     try:
#         # Start Xvfb in background
#         subprocess.Popen(
#             ['Xvfb', display, '-screen', '0', '1920x1080x24', '-ac', '+extension', 'GLX', '+render', '-noreset'],
#             stdout=subprocess.DEVNULL,
#             stderr=subprocess.DEVNULL
#         )
#         print(f"[+] Started Xvfb on {display}")
#         time.sleep(5)  # Wait longer for Xvfb to fully initialize
#         print(f"[+] Xvfb initialization wait complete")
#     except Exception as e:
#         print(f"[!] Could not start Xvfb: {e}")
#         print("[!] WARNING: Continuing without Xvfb verification...")
# ============================================

# Start Pure CDP Mode (No WebDriver footprint!)
print(f"[*] Opening Google search with Pure CDP Mode...")
print(f"[*] Searching for: {search_query}")
if proxy_string:
    print(f"[*] Using proxy: {proxy_string.split('@')[-1] if '@' in proxy_string else proxy_string}")

# Build Chrome options
# Use headless2 (new headless mode) - harder to detect, no Xvfb needed
chrome_kwargs = {
    "incognito": True,
    "ad_block": True,
    "headless": False,
    "headless2": True,  # New headless mode - harder to detect than old headless
}
print("[*] Using headless2 mode (new headless - harder to detect, no Xvfb needed)")

# Add proxy if provided
if proxy_string:
    chrome_kwargs["proxy"] = proxy_string

# Enable built-in SeleniumBase features:
# - ad_block=True: Automatically blocks ads and some popups
# - incognito=True: Private browsing mode
# - proxy: Optional proxy with authentication support
# - Popup blocking: Enabled by default in Chrome settings

print(f"[*] Launching Chrome with kwargs: {chrome_kwargs}")
try:
    sb = sb_cdp.Chrome(search_url, **chrome_kwargs)
except Exception as e:
    print(f"[!] ERROR launching Chrome: {e}")
    print(f"[!] Error type: {type(e).__name__}")
    import traceback
    traceback.print_exc()
    raise

# Wait for page to fully load
sb.sleep(3)

# ============================================
# Handle Google Cookie Consent
# ============================================
def handle_google_cookie_consent():
    """Handle Google cookie consent banner - randomly accepts or rejects (50/50)"""
    print("[*] Checking for Google cookie consent...")
    
    # Google Cookie Consent Selectors
    reject_selector = '#L2AGLb'  # "Reject all" button
    accept_selector = '#WOwltc'  # "Accept all" button
    
    # Randomly accept or reject (50/50 chance) to appear more human
    if random.choice([True, False]):
        # Try to reject first
        if sb.click_if_visible(reject_selector, timeout=1):
            print("[+] Clicked 'Reject all' on cookie consent")
            sb.sleep(1)
            return True
        elif sb.click_if_visible(accept_selector, timeout=1):
            print("[+] Clicked 'Accept all' on cookie consent")
            sb.sleep(1)
            return True
    else:
        # Try to accept first
        if sb.click_if_visible(accept_selector, timeout=1):
            print("[+] Clicked 'Accept all' on cookie consent")
            sb.sleep(1)
            return True
        elif sb.click_if_visible(reject_selector, timeout=1):
            print("[+] Clicked 'Reject all' on cookie consent")
            sb.sleep(1)
            return True
    
    return False

# ============================================
# Dismiss Popups and Dialogs
# ============================================
def dismiss_popups_and_dialogs():
    """Dismiss all popups, dialogs, and permission prompts"""
    print("[*] Dismissing popups and dialogs...")
    
    # Google-Specific Dialogs (Location/permissions prompts)
    google_selectors = [
        'g-raised-button[jsaction="click:O6N1Pb"]',
        '.mpQYc g-raised-button',
        '[role="dialog"] .mpQYc [role="button"]',
    ]
    
    # Permission blocking buttons
    permission_selectors = [
        'button[aria-label*="Block"]',
        'button[aria-label*="Don\'t allow"]',
        'button[aria-label*="Deny"]',
        'button[data-value="Block"]',
        'button[data-value="Deny"]',
    ]
    
    # Generic Decline/Dismiss Buttons
    decline_selectors = [
        '[data-value="Decline"]',
        '[data-value="Not now"]',
        'button[aria-label="No thanks"]',
        'button[aria-label="Decline"]',
    ]
    
    # Generic Modal/Popup Close Buttons
    close_selectors = [
        '.modal button[aria-label="Close"]',
        '.popup button[aria-label="Close"]',
        '.close-button',
        '.dismiss-button',
    ]
    
    # Combine all selectors
    all_selectors = google_selectors + permission_selectors + decline_selectors + close_selectors
    
    dismissed = False
    for selector in all_selectors:
        try:
            if sb.click_if_visible(selector, timeout=0.5):
                print(f"[+] Dismissed popup: {selector}")
                sb.sleep(0.5)
                dismissed = True
        except:
            continue
    
    # Fallback: Press ESC key using page keyboard API
    if not dismissed:
        try:
            sb.loop.run_until_complete(sb.page.keyboard.press('Escape'))
            print("[+] Pressed ESC key as fallback")
            sb.sleep(0.5)
        except:
            pass
    
    return dismissed

# Handle cookie consent first
handle_google_cookie_consent()

# Get page title and URL
current_url = sb.get_current_url()
print(f"[*] Page Title: {sb.get_title()}")
print(f"[*] Current URL: {current_url}")

# Verify we're on search results page
if "/search?q=" in current_url:
    print("[+] Successfully loaded search results!")
    # Dismiss any popups/dialogs after results load
    dismiss_popups_and_dialogs()
else:
    print("[!] WARNING: Not on search results page!")

# Scroll to bottom to load all results
print("[*] Scrolling page to load all results...")
sb.scroll_to_bottom()
sb.sleep(1)
sb.scroll_to_top()
sb.sleep(1)

# Highlight first result
print("[*] Highlighting first search result...")
try:
    if sb.is_element_visible("h3"):
        sb.highlight("h3")
        first_result = sb.get_text("h3")
        print(f"[*] First result: {first_result}")
except Exception as e:
    print(f"[!] Could not find h3 elements: {e}")

# Take FULL PAGE screenshot using the async method directly
print("[*] Taking FULL PAGE screenshot (entire scrollable page)...")
# Use the async method to get true full page screenshot
# Save to /app/ directory (works in both Docker and Fly.io)
screenshot_path = "/app/google_search_full_page.png"
sb.loop.run_until_complete(
    sb.page.save_screenshot(screenshot_path, full_page=True)
)

# Regular viewport screenshot only (commented out)
# sb.save_screenshot("google_search_full_page.png")

# Save as PDF too
# print("[*] Saving as PDF...")
# sb.save_as_pdf("google_search_results.pdf")

# Save HTML source
# print("[*] Saving page HTML...")
# sb.save_page_source("google_search_source.html")

# Get all search result titles
print("\n[*] All search results:")
try:
    results = sb.find_elements("h3")
    for i, result in enumerate(results[:10], 1):
        try:
            text = result.text.strip()
            if text:
                print(f"  {i}. {text}")
        except:
            pass
except Exception as e:
    print(f"[!] Could not get search results: {e}")

print("\n[*] Bot evasion test complete!")
print(f"[*] Screenshot saved: {screenshot_path}")
# print("    - google_search_results.pdf (PDF)")
# print("    - google_search_source.html (HTML)")

# Keep browser open for 5 seconds so you can see it
sb.sleep(5)
sb.driver.stop()

"""Pure CDP Mode Google Search with SUBMIT method - Maximum Bot Evasion"""
from seleniumbase import sb_cdp

# ============================================
# CONFIGURATION
# ============================================
# Your search query
search_query = "hotels near me"

# Proxy configuration (set to None to disable)
# Examples:
#   None                                      # No proxy (default)
#   "proxy-server:port"                       # Basic proxy
#   "username:password@proxy-server:port"     # Authenticated proxy
proxy = None  # Change this to use a proxy

# Browser settings
headless = False  # False = headful mode (works with Xvfb in Docker!)
incognito = True  # Private browsing mode

# ============================================

# Build Chrome options with built-in SeleniumBase features:
# - ad_block=True: Automatically blocks ads and some popups
# - incognito: Private browsing mode
# - Popup blocking: Enabled by default in Chrome settings
chrome_kwargs = {
    "incognito": incognito,
    "headless": headless,
    "ad_block": True,  # Enable built-in ad blocking
}

# Add proxy if configured
if proxy:
    chrome_kwargs["proxy"] = proxy
    print(f"[*] Using proxy: {proxy}")

# Start Pure CDP Mode (No WebDriver footprint!)
print(f"[*] Opening Google with Pure CDP Mode...")
print(f"[*] Headless: {headless}, Incognito: {incognito}")
sb = sb_cdp.Chrome("https://www.google.com/ncr", **chrome_kwargs)

# Wait for page to load
sb.sleep(2)

# Handle cookie consent popups (manual backup - ad_block doesn't handle cookie consent)
print("[*] Checking for cookie consent popups (manual backup)...")
cookie_selectors = [
    'button:contains("Accept all")',
    'button:contains("Accept")',
    'button:contains("I agree")',
    'button:contains("Agree")',
    'button:contains("OK")',
    'button:contains("Got it")',
    'button[id*="accept"]',
    'button[class*="accept"]',
    '[id*="accept"] button',
    '[class*="accept"] button',
    'button[aria-label*="Accept"]',
    'button[aria-label*="Cookie"]',
]

cookie_clicked = False
for selector in cookie_selectors:
    try:
        if sb.click_if_visible(selector, timeout=0.5):
            print(f"[+] Clicked cookie consent: {selector}")
            sb.sleep(1)
            cookie_clicked = True
            break
    except:
        continue

if not cookie_clicked:
    print("[*] No cookie consent popup found (or already handled)")

# Type search query
print(f"[*] Typing search query: {search_query}")
sb.type('textarea[name="q"]', search_query)
sb.sleep(1)

# PROPER WAY TO SUBMIT - Use submit() method!
print("[*] Submitting search using submit() method...")
sb.submit('textarea[name="q"]')
sb.sleep(3)

# Get page title and URL
current_url = sb.get_current_url()
print(f"[*] Page Title: {sb.get_title()}")
print(f"[*] Current URL: {current_url}")

# Verify we're on search results page
if "/search?q=" in current_url:
    print("[+] Successfully loaded search results!")
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

# Take FULL PAGE screenshot (entire scrollable page)
print("[*] Taking FULL PAGE screenshot (entire scrollable page)...")
sb.loop.run_until_complete(
    sb.page.save_screenshot("google_search_submit_full_page.png", full_page=True)
)

# Save as PDF
# print("[*] Saving as PDF...")
# sb.save_as_pdf("google_search_submit_results.pdf")

# Save HTML source
# print("[*] Saving page HTML...")
# sb.save_page_source("google_search_submit_source.html")

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
print("[*] Screenshot saved: google_search_submit_full_page.png")
# print("    - google_search_submit_results.pdf (PDF)")
# print("    - google_search_submit_source.html (HTML)")

# Keep browser open for 5 seconds so you can see it
sb.sleep(5)
sb.driver.stop()

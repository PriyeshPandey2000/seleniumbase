"""Pure CDP Mode Google Search with SUBMIT method - Docker/Chromium Compatible"""
from seleniumbase import sb_cdp
import os

# ============================================
# CONFIGURATION
# ============================================
# Your search query
search_query = "hotels near me"

# Proxy configuration (set to None to disable)
proxy = None  # Change this to use a proxy

# Browser settings
headless = False  # False = headful mode (works with Xvfb in Docker!)
incognito = True  # Private browsing mode

# ============================================

# Build Chrome options with explicit binary path for Chromium
chrome_kwargs = {
    "incognito": incognito,
    "headless": headless,
}

# Chromium binary path for Docker/ARM64
chromium_path = "/usr/bin/chromium-browser"
if os.path.exists(chromium_path):
    chrome_kwargs["binary_location"] = chromium_path
    print(f"[*] Using Chromium binary: {chromium_path}")

# Add proxy if configured
if proxy:
    chrome_kwargs["proxy"] = proxy
    print(f"[*] Using proxy: {proxy}")

# Start Pure CDP Mode (No WebDriver footprint!)
print(f"[*] Opening Google with Pure CDP Mode...")
print(f"[*] Headless: {headless}, Incognito: {incognito}")

try:
    sb = sb_cdp.Chrome("https://www.google.com/ncr", **chrome_kwargs)
    
    # Wait for page to load
    sb.sleep(2)
    
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
    
    # Keep browser open for 5 seconds so you can see it
    sb.sleep(5)
    sb.driver.stop()

except Exception as e:
    print(f"[!] ERROR: {e}")
    print("\n[*] Trying to get more debug information...")
    import traceback
    traceback.print_exc()
    exit(1)


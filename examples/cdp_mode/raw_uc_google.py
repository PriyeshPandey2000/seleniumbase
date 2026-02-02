"""UC Mode + CDP Mode Google Search - Advanced Bot Evasion"""
from seleniumbase import SB

# Your search query - just go directly to the search results URL!
search_query = "12831000A01803"

# Use your full search URL directly
search_url = f"https://www.google.com/search?q={search_query}&oq={search_query}&sourceid=chrome&ie=UTF-8"

with SB(uc=True, test=True, locale="en") as sb:
    print(f"[*] Opening Google search with UC Mode + CDP Mode...")
    print(f"[*] Searching for: {search_query}")
    sb.activate_cdp_mode(search_url)
    sb.sleep(3)

    # Print page title and URL
    current_url = sb.get_current_url()
    print(f"[*] Page Title: {sb.get_page_title()}")
    print(f"[*] Current URL: {current_url}")

    # Verify we're on search results page
    if "/search?q=" in current_url:
        print("[+] Successfully loaded search results!")
    else:
        print("[!] WARNING: Not on search results page!")

    # Wait for AI Overview if it appears
    sb.sleep(1)
    if sb.is_text_visible("Generating"):
        print("[*] Waiting for AI Overview to generate...")
        try:
            sb.wait_for_text("AI Overview", timeout=10)
        except:
            print("[*] AI Overview didn't appear or timed out")

    # Highlight and get first result
    print("[*] Getting search results...")
    sb.sleep(1)
    try:
        if sb.is_element_visible("h3"):
            sb.cdp.highlight("h3")
            first_result = sb.get_text("h3")
            print(f"[*] First result: {first_result}")
    except Exception as e:
        print(f"[!] Could not find h3 elements: {e}")

    # Get all search result titles
    print("\n[*] Top search results:")
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

    # Save outputs
    print("\n[*] Saving results...")
    sb.save_as_pdf_to_logs()  # Saved to ./latest_logs/
    sb.save_page_source_to_logs()
    sb.save_screenshot_to_logs()

    print("[*] Results saved to ./latest_logs/")
    print("[*] Bot evasion test complete!")

    # Keep browser open for 5 seconds
    sb.sleep(5)

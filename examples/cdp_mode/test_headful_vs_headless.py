"""
Test script to compare CAPTCHA rates between headful and headless modes

Usage:
    # On Mac/Windows (with display):
    python test_headful_vs_headless.py

    # On Linux server with Xvfb:
    export DISPLAY=:99
    Xvfb :99 -screen 0 1920x1080x24 &
    sleep 2
    python test_headful_vs_headless.py
"""

from seleniumbase import sb_cdp
import time
import sys

# Configuration
NUM_TESTS = 5  # Number of tests per mode
SEARCH_QUERY = "hotels near me"

def test_with_mode(headless_mode, test_num):
    """Test a single search with given headless mode"""
    mode_name = "HEADLESS" if headless_mode else "HEADFUL"
    print(f"\n[{mode_name}] Test {test_num}/{NUM_TESTS}...")

    try:
        # Build search URL
        search_url = f"https://www.google.com/search?q={SEARCH_QUERY}"

        # Start Chrome
        sb = sb_cdp.Chrome(
            search_url,
            incognito=True,
            headless=headless_mode
        )

        # Wait for page load
        time.sleep(3)

        # Check current URL
        url = sb.get_current_url()

        # Determine result
        if "/sorry/" in url:
            result = "CAPTCHA"
            print(f"[{mode_name}] ❌ CAPTCHA detected!")
        else:
            result = "SUCCESS"
            print(f"[{mode_name}] ✅ No CAPTCHA - Search succeeded!")

        # Cleanup
        sb.driver.stop()

        # Wait between tests to avoid rate limiting
        time.sleep(5)

        return result

    except Exception as e:
        print(f"[{mode_name}] ⚠️  Error: {e}")
        try:
            sb.driver.stop()
        except:
            pass
        return "ERROR"


def run_tests():
    """Run comparison tests"""
    print("=" * 70)
    print("HEADFUL vs HEADLESS MODE - CAPTCHA COMPARISON TEST")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  - Tests per mode: {NUM_TESTS}")
    print(f"  - Search query: {SEARCH_QUERY}")
    print(f"  - Delay between tests: 5 seconds")

    # Check if running on Linux with Xvfb
    import os
    if sys.platform == "linux" and not os.environ.get("DISPLAY"):
        print("\n⚠️  WARNING: Running on Linux without DISPLAY variable!")
        print("   Headful mode will fail. Please start Xvfb first:")
        print("   export DISPLAY=:99")
        print("   Xvfb :99 -screen 0 1920x1080x24 &")
        print("")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            return

    # Test Headless Mode
    print("\n" + "=" * 70)
    print("PHASE 1: Testing HEADLESS Mode (headless=True)")
    print("=" * 70)
    headless_results = []
    for i in range(NUM_TESTS):
        result = test_with_mode(headless_mode=True, test_num=i+1)
        headless_results.append(result)

    # Wait between phases
    print("\n⏳ Waiting 10 seconds before Phase 2...")
    time.sleep(10)

    # Test Headful Mode
    print("\n" + "=" * 70)
    print("PHASE 2: Testing HEADFUL Mode (headless=False)")
    print("=" * 70)
    headful_results = []
    for i in range(NUM_TESTS):
        result = test_with_mode(headless_mode=False, test_num=i+1)
        headful_results.append(result)

    # Calculate statistics
    headless_captchas = headless_results.count("CAPTCHA")
    headless_success = headless_results.count("SUCCESS")
    headless_errors = headless_results.count("ERROR")

    headful_captchas = headful_results.count("CAPTCHA")
    headful_success = headful_results.count("SUCCESS")
    headful_errors = headful_results.count("ERROR")

    # Print results
    print("\n" + "=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)

    print(f"\n📊 HEADLESS Mode (headless=True):")
    print(f"   ✅ Success: {headless_success}/{NUM_TESTS} ({headless_success/NUM_TESTS*100:.0f}%)")
    print(f"   ❌ CAPTCHA: {headless_captchas}/{NUM_TESTS} ({headless_captchas/NUM_TESTS*100:.0f}%)")
    if headless_errors:
        print(f"   ⚠️  Errors:  {headless_errors}/{NUM_TESTS} ({headless_errors/NUM_TESTS*100:.0f}%)")

    print(f"\n📊 HEADFUL Mode (headless=False + Xvfb):")
    print(f"   ✅ Success: {headful_success}/{NUM_TESTS} ({headful_success/NUM_TESTS*100:.0f}%)")
    print(f"   ❌ CAPTCHA: {headful_captchas}/{NUM_TESTS} ({headful_captchas/NUM_TESTS*100:.0f}%)")
    if headful_errors:
        print(f"   ⚠️  Errors:  {headful_errors}/{NUM_TESTS} ({headful_errors/NUM_TESTS*100:.0f}%)")

    # Calculate improvement
    if headless_captchas > 0:
        improvement = ((headless_captchas - headful_captchas) / headless_captchas) * 100
        print(f"\n🎯 IMPROVEMENT: {improvement:.0f}% fewer CAPTCHAs with headful mode!")
    else:
        print(f"\n✨ LUCKY! No CAPTCHAs in either mode during testing!")

    # Recommendation
    print("\n" + "=" * 70)
    print("RECOMMENDATION")
    print("=" * 70)

    if headful_captchas < headless_captchas:
        print("✅ Headful mode is BETTER! Deploy with Xvfb in production.")
        print("   Use: docker-compose -f docker-compose-xvfb.yml up -d")
    elif headful_captchas == headless_captchas and headful_captchas > 0:
        print("⚠️  Both modes getting CAPTCHAs. You need:")
        print("   1. Residential proxies")
        print("   2. 2Captcha API")
        print("   3. Longer delays between requests")
    else:
        print("✅ Both modes working well! Consider headless for lower resources.")

    print("=" * 70)


if __name__ == "__main__":
    try:
        run_tests()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user!")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()

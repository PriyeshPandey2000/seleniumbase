"""Simple test to verify Chromium works in Docker"""
import subprocess
import os

print("=" * 50)
print("CHROMIUM INSTALLATION TEST")
print("=" * 50)

# Check if chromium binary exists
chromium_paths = [
    "/usr/bin/chromium-browser",
    "/usr/bin/chromium",
    "/snap/bin/chromium"
]

found_chromium = None
for path in chromium_paths:
    if os.path.exists(path):
        print(f"✓ Found Chromium at: {path}")
        found_chromium = path
        break

if not found_chromium:
    print("✗ Chromium binary not found!")
    exit(1)

# Try to get Chromium version
try:
    result = subprocess.run(
        [found_chromium, "--version"],
        capture_output=True,
        text=True,
        timeout=5
    )
    print(f"✓ Chromium version: {result.stdout.strip()}")
except Exception as e:
    print(f"✗ Could not get Chromium version: {e}")

# Check chromedriver
chromedriver_paths = [
    "/usr/bin/chromedriver",
    "/usr/lib/chromium-browser/chromedriver"
]

found_driver = None
for path in chromedriver_paths:
    if os.path.exists(path):
        print(f"✓ Found ChromeDriver at: {path}")
        found_driver = path
        break

if not found_driver:
    print("⚠ ChromeDriver not found in expected locations")

# Test basic SeleniumBase import
try:
    from seleniumbase import sb_cdp
    print("✓ SeleniumBase CDP imported successfully")
except Exception as e:
    print(f"✗ Failed to import SeleniumBase: {e}")
    exit(1)

print("\n" + "=" * 50)
print("Now testing simple Chromium launch...")
print("=" * 50)

# Try launching Chromium with CDP
try:
    print("[*] Attempting to launch Chromium in headless mode...")
    sb = sb_cdp.Chrome(
        "about:blank",
        headless=True,
        binary_location=found_chromium
    )
    print("✓ Successfully launched Chromium!")
    print(f"✓ Page title: {sb.get_title()}")
    sb.driver.stop()
    print("✓ Test PASSED!")
except Exception as e:
    print(f"✗ Failed to launch Chromium: {e}")
    import traceback
    traceback.print_exc()
    exit(1)


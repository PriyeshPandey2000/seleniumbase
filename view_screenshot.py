#!/usr/bin/env python3
"""
Script to make a screenshot API call and view the result.
Configure parameters at the top of the script and run.
"""

import requests
import base64
import tempfile
import subprocess
import platform
import json
from pathlib import Path

# ============================================
# CONFIGURATION - Edit these parameters
# ============================================
API_URL = "https://seleniumbase-api.fly.dev/search"

# API Parameters
QUERY = "tokyo hotels"
PROXY = "customer-sphota_eJA6T-sessid-1_us_texas_houston_1770628433855-st-us_texas-city-houston:ogdh_3UNGk7u@pr.oxylabs.io:7777"
SCREENSHOT = True

# Optional: Save screenshot to specific location (None = temp file)
SAVE_PATH = None  # e.g., "screenshot.png" or None for temp file

# ============================================
# Script Logic
# ============================================

def make_api_request():
    """Make the API request with configured parameters."""
    payload = {
        "query": QUERY,
        "proxy": PROXY,
        "screenshot": SCREENSHOT
    }

    headers = {
        "Content-Type": "application/json"
    }

    print(f"Making API request to {API_URL}...")
    print(f"Query: {QUERY}")
    print(f"Proxy: {PROXY[:50]}..." if len(PROXY) > 50 else f"Proxy: {PROXY}")
    print(f"Screenshot: {SCREENSHOT}")
    print("-" * 60)

    try:
        response = requests.post(API_URL, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error making API request: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text[:500]}")
        return None


def save_and_open_screenshot(base64_data):
    """Decode base64 screenshot and open it."""
    if not base64_data:
        print("No screenshot data found in response!")
        return False

    try:
        # Decode base64 to image bytes
        image_data = base64.b64decode(base64_data)

        # Determine save location
        if SAVE_PATH:
            image_path = Path(SAVE_PATH)
        else:
            # Create temp file
            temp_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix='.png',
                prefix='screenshot_'
            )
            image_path = Path(temp_file.name)

        # Write image to file
        with open(image_path, 'wb') as f:
            f.write(image_data)

        print(f"Screenshot saved to: {image_path}")

        # Open the image based on OS
        system = platform.system()
        try:
            if system == "Darwin":  # macOS
                subprocess.run(["open", str(image_path)], check=True)
            elif system == "Windows":
                subprocess.run(["start", str(image_path)], shell=True, check=True)
            elif system == "Linux":
                subprocess.run(["xdg-open", str(image_path)], check=True)
            else:
                print(f"Unknown OS: {system}. Please open the file manually.")
                return True

            print("Screenshot opened successfully!")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Could not open image automatically: {e}")
            print(f"Please open it manually: {image_path}")
            return True

    except Exception as e:
        print(f"Error processing screenshot: {e}")
        return False


def main():
    """Main execution function."""
    print("=" * 60)
    print("Screenshot API Viewer")
    print("=" * 60)

    # Make API request
    response_data = make_api_request()

    if not response_data:
        print("Failed to get API response.")
        return

    print("\nAPI Response received!")

    # Pretty print the response (excluding base64 data)
    response_copy = response_data.copy()
    if 'screenshot_base64' in response_copy:
        base64_preview = response_copy['screenshot_base64'][:100] + "..."
        response_copy['screenshot_base64'] = f"<base64 data, length: {len(response_data.get('screenshot_base64', ''))} chars>"

    print("\nResponse data:")
    print(json.dumps(response_copy, indent=2))
    print("-" * 60)

    # Extract and process screenshot
    screenshot_base64 = response_data.get('screenshot_base64')

    if screenshot_base64:
        print(f"\nScreenshot data found ({len(screenshot_base64)} characters)")
        save_and_open_screenshot(screenshot_base64)
    else:
        print("\nNo 'screenshot_base64' field in response!")
        print("Available fields:", list(response_data.keys()))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Process test results and save screenshots"""
import json
import base64
import sys
import os

def process_result(json_file, output_prefix):
    """Extract screenshot from JSON and save it"""
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)

        if not data.get('success'):
            print(f"❌ {output_prefix}: FAILED - {data.get('error', 'Unknown error')}")
            return False

        html = data.get('html', '')
        screenshot_b64 = data.get('screenshot_base64', '')

        html_len = len(html)
        screenshot_len = len(screenshot_b64)

        # Save HTML
        html_file = f"{output_prefix}.html"
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html)

        # Save screenshot if available
        if screenshot_b64:
            screenshot_file = f"{output_prefix}.png"
            screenshot_data = base64.b64decode(screenshot_b64)
            with open(screenshot_file, 'wb') as f:
                f.write(screenshot_data)

            # Determine if CAPTCHA or real results
            if screenshot_len > 500000:
                status = "✅ REAL RESULTS"
            else:
                status = "❌ CAPTCHA"

            print(f"{status} {output_prefix}: HTML={html_len:,} chars, Screenshot={screenshot_len:,} chars")
            return screenshot_len > 500000
        else:
            print(f"⚠️  {output_prefix}: No screenshot")
            return False

    except Exception as e:
        print(f"❌ {output_prefix}: ERROR - {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: process_results.py <json_file> <output_prefix>")
        sys.exit(1)

    json_file = sys.argv[1]
    output_prefix = sys.argv[2]

    success = process_result(json_file, output_prefix)
    sys.exit(0 if success else 1)

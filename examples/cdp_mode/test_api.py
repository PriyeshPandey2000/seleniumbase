"""
Test script for the Google Search API
Run this to verify the API is working correctly
"""

import requests
import json
import time

# API endpoint
API_URL = "http://localhost:8000"


def test_health_check():
    """Test the health check endpoint"""
    print("=" * 60)
    print("Testing Health Check Endpoint...")
    print("=" * 60)

    response = requests.get(f"{API_URL}/health")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    assert response.status_code == 200, "Health check failed!"
    print("✅ Health check passed!\n")


def test_search():
    """Test the search endpoint"""
    print("=" * 60)
    print("Testing Search Endpoint...")
    print("=" * 60)

    search_data = {
        "query": "12831000A01803",
        "max_results": 5,
        "save_screenshot": True,
        "incognito": True
    }

    print(f"Request: {json.dumps(search_data, indent=2)}\n")
    print("⏳ Performing search (this may take 5-10 seconds)...\n")

    start_time = time.time()
    response = requests.post(
        f"{API_URL}/search",
        json=search_data,
        timeout=60  # 60 second timeout
    )
    elapsed_time = time.time() - start_time

    print(f"Status Code: {response.status_code}")
    print(f"Response Time: {elapsed_time:.2f} seconds\n")

    if response.status_code == 200:
        result = response.json()
        print("Response:")
        print(f"  Query: {result['query']}")
        print(f"  Title: {result['title']}")
        print(f"  URL: {result['url']}")
        print(f"  Timestamp: {result['timestamp']}")
        print(f"  Screenshot: {result['screenshot_path']}")
        print(f"\n  Search Results ({len(result['results'])} found):")
        for i, res in enumerate(result['results'], 1):
            print(f"    {i}. {res}")

        print("\n✅ Search test passed!")
        return result
    else:
        print(f"❌ Search failed!")
        print(f"Error: {response.text}")
        return None


def test_concurrent_searches():
    """Test multiple concurrent searches"""
    print("\n" + "=" * 60)
    print("Testing Concurrent Searches...")
    print("=" * 60)

    import concurrent.futures

    queries = [
        "SeleniumBase",
        "Python automation",
        "Bot detection bypass"
    ]

    def perform_search(query):
        try:
            response = requests.post(
                f"{API_URL}/search",
                json={
                    "query": query,
                    "max_results": 3,
                    "save_screenshot": False,
                    "incognito": True
                },
                timeout=60
            )
            return query, response.status_code, len(response.json().get('results', []))
        except Exception as e:
            return query, "error", str(e)

    print(f"Running {len(queries)} searches concurrently...\n")

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(perform_search, q) for q in queries]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    print("Results:")
    for query, status, result_count in results:
        print(f"  {query}: Status={status}, Results={result_count}")

    print("\n✅ Concurrent search test completed!")


if __name__ == "__main__":
    print("\n" + "🧪" * 30)
    print("Google Search API Test Suite")
    print("🧪" * 30 + "\n")

    try:
        # Test 1: Health Check
        test_health_check()

        # Test 2: Single Search
        time.sleep(1)
        test_search()

        # Test 3: Concurrent Searches (optional - comment out if you don't want to test)
        # time.sleep(2)
        # test_concurrent_searches()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)

    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Could not connect to the API")
        print("Make sure the API is running:")
        print("  python api_google_search.py")
        print("  OR")
        print("  docker-compose up")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

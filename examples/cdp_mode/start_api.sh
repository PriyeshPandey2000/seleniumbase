#!/bin/bash

# Quick start script for Google Search API
# Makes it easy to deploy in production

set -e  # Exit on error

echo "================================================"
echo "  SeleniumBase Google Search API - Startup"
echo "================================================"

# Check if Docker is available
if command -v docker &> /dev/null; then
    echo "✅ Docker found"
    DOCKER_AVAILABLE=true
else
    echo "⚠️  Docker not found"
    DOCKER_AVAILABLE=false
fi

# Function to start with Docker
start_docker() {
    echo ""
    echo "Starting with Docker Compose..."
    echo ""

    # Build if needed
    if [ ! "$(docker images -q google-search-api 2> /dev/null)" ]; then
        echo "Building Docker image..."
        docker-compose build
    fi

    # Start services
    docker-compose up -d

    echo ""
    echo "✅ API started successfully!"
    echo ""
    echo "API URL: http://localhost:8000"
    echo "API Docs: http://localhost:8000/docs"
    echo ""
    echo "View logs: docker-compose logs -f"
    echo "Stop API: docker-compose down"
    echo ""
}

# Function to start locally
start_local() {
    echo ""
    echo "Starting locally with Python..."
    echo ""

    # Check if virtual environment exists
    if [ ! -d "venv" ]; then
        echo "Creating virtual environment..."
        python3 -m venv venv
    fi

    # Activate virtual environment
    source venv/bin/activate

    # Install dependencies
    echo "Installing dependencies..."
    pip install -q -r requirements-api.txt

    # Download chromedriver if needed
    echo "Verifying ChromeDriver..."
    seleniumbase get chromedriver --path

    # Start the API
    echo ""
    echo "✅ Starting API server..."
    echo ""
    python api_google_search.py
}

# Main menu
echo ""
echo "Choose deployment method:"
echo "  1) Docker (Recommended for production)"
echo "  2) Local Python (For development)"
echo "  3) Exit"
echo ""
read -p "Enter choice [1-3]: " choice

case $choice in
    1)
        if [ "$DOCKER_AVAILABLE" = true ]; then
            start_docker
        else
            echo "❌ Docker is not installed. Please install Docker first."
            exit 1
        fi
        ;;
    2)
        start_local
        ;;
    3)
        echo "Exiting..."
        exit 0
        ;;
    *)
        echo "Invalid choice. Exiting..."
        exit 1
        ;;
esac

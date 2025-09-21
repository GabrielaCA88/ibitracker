#!/bin/bash

# IBI Tracker - Test Script

echo "🧪 Running IBI Tracker Tests..."

# Check if virtual environment exists
if [ ! -d "ibitracker" ]; then
    echo "❌ Virtual environment not found. Run ./setup-venv.sh first!"
    exit 1
fi

# Activate virtual environment
source ibitracker/bin/activate

# Check if pytest is installed
if ! pip list | grep -q "pytest"; then
    echo "📦 Installing test dependencies..."
    pip install -r requirements.txt
fi

echo "🔍 Running tests..."
pytest backend/ -v

echo ""
echo "✅ Tests completed!"

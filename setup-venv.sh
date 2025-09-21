#!/bin/bash

# IBI Tracker - Virtual Environment Management Script

echo "🐍 IBI Tracker Virtual Environment Manager"
echo "========================================"

# Check if virtual environment exists
if [ ! -d "ibitracker" ]; then
    echo "❌ Virtual environment not found. Creating one..."
    python3 -m venv ibitracker
    echo "✅ Virtual environment created!"
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source ibitracker/bin/activate

# Check if packages are installed
if ! pip list | grep -q "fastapi"; then
    echo "📦 Installing dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    echo "✅ Dependencies installed!"
else
    echo "✅ Dependencies already installed!"
fi

echo ""
echo "🎉 Virtual environment is ready!"
echo ""
echo "📋 Available commands:"
echo "  • source ibitracker/bin/activate    - Activate the environment"
echo "  • deactivate                        - Deactivate the environment"
echo "  • ./start-dev.sh                    - Start the application"
echo "  • ./test.sh                         - Run tests"
echo ""
echo "🔧 Current Python version: $(python --version)"
echo "📍 Virtual environment path: $(which python)"

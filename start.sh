#!/bin/bash

echo "🚀 Starting IBI Tracker..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is not installed. Please install Python3 first."
    exit 1
fi

# Install dependencies
echo "📦 Installing Python dependencies..."
pip3 install -r requirements.txt

# Start the backend server
echo "🔧 Starting FastAPI backend server..."
cd backend
python3 main.py &
BACKEND_PID=$!

# Wait a moment for the server to start
sleep 3

echo "✅ Backend server started on http://localhost:8000"
echo "🌐 Open frontend/index.html in your browser to use the application"
echo ""
echo "📊 API Documentation available at: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"

# Keep the script running
wait $BACKEND_PID
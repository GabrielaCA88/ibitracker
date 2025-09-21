#!/bin/bash

# IBI Tracker - Development Startup Script

echo "🚀 Starting IBI Tracker in Development Mode..."

# Check if virtual environment exists
if [ ! -d "ibitracker" ]; then
    echo "❌ Virtual environment not found. Run ./setup-venv.sh first!"
    exit 1
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source ibitracker/bin/activate

# Check if dependencies are installed
if ! pip list | grep -q "fastapi"; then
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
fi

# Start the backend server
echo "🔧 Starting FastAPI backend server..."
cd backend
python main.py &
BACKEND_PID=$!

# Wait for server to start
sleep 3

echo ""
echo "✅ Backend server started on http://localhost:8000"
echo "🌐 Frontend: Open frontend/index.html in your browser"
echo "📊 API Docs: http://localhost:8000/docs"
echo ""
echo "🛑 Press Ctrl+C to stop the server"

# Keep the script running and handle cleanup
trap "echo ''; echo '🛑 Stopping server...'; kill $BACKEND_PID; exit" INT
wait $BACKEND_PID

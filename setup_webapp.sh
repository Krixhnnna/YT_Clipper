#!/bin/bash

echo "🎬 YouTube to Script Web App - Setup (Gemini AI)"
echo "================================================"

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed. Please install Python 3.6+ first."
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "❌ Error: pip3 is not installed. Please install pip first."
    exit 1
fi

echo "📦 Installing dependencies..."
pip3 install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "✅ Dependencies installed successfully!"
    
    # Create output directory
    mkdir -p output
    
    echo ""
    echo "🚀 Setup completed!"
    echo ""
    echo "📋 Next steps:"
    echo "1. The Gemini API key is already configured in the app"
    echo "2. (Optional) For Hinglish translation, set up Google Cloud credentials:"
    echo "   export GOOGLE_APPLICATION_CREDENTIALS='path/to/your/credentials.json'"
    echo ""
    echo "3. Start the web app:"
    echo "   python3 webapp.py"
    echo ""
    echo "4. Open your browser to: http://localhost:8080"
    echo ""
    echo "💡 The app is ready to use with Gemini AI!"
    echo ""
else
    echo "❌ Error: Failed to install dependencies."
    exit 1
fi 
#!/bin/bash

echo "🎬 Installing FFmpeg for video processing..."

# Detect operating system
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    echo "📱 Detected macOS"
    if command -v brew &> /dev/null; then
        echo "🍺 Installing FFmpeg using Homebrew..."
        brew install ffmpeg
    else
        echo "❌ Homebrew not found. Please install Homebrew first:"
        echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        exit 1
    fi
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    echo "🐧 Detected Linux"
    if command -v apt-get &> /dev/null; then
        echo "📦 Installing FFmpeg using apt..."
        sudo apt update
        sudo apt install -y ffmpeg
    elif command -v yum &> /dev/null; then
        echo "📦 Installing FFmpeg using yum..."
        sudo yum install -y ffmpeg
    else
        echo "❌ Package manager not found. Please install FFmpeg manually:"
        echo "   Visit: https://ffmpeg.org/download.html"
        exit 1
    fi
else
    echo "❌ Unsupported operating system: $OSTYPE"
    echo "   Please install FFmpeg manually:"
    echo "   Visit: https://ffmpeg.org/download.html"
    exit 1
fi

# Verify installation
if command -v ffmpeg &> /dev/null; then
    echo "✅ FFmpeg installed successfully!"
    ffmpeg -version | head -n 1
else
    echo "❌ FFmpeg installation failed. Please install manually."
    exit 1
fi

echo "🚀 You can now run the YouTube to Script app!" 
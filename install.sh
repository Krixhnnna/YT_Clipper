#!/bin/bash

echo "YouTube Video Downloader - Installation Script"
echo "=============================================="

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed. Please install Python 3.6+ first."
    exit 1
fi

echo "Python 3 found: $(python3 --version)"

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "Error: pip3 is not installed. Please install pip first."
    exit 1
fi

echo "Installing dependencies..."
pip3 install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "Dependencies installed successfully!"
    
    # Make scripts executable
    chmod +x video_downloader.py
    chmod +x video_downloader_gui.py
    chmod +x launcher.py
    
    echo ""
    echo "Installation completed!"
    echo ""
    echo "Usage:"
    echo "  python3 launcher.py          # Choose interface"
    echo "  python3 video_downloader.py  # Command line version"
    echo "  python3 video_downloader_gui.py  # GUI version"
    echo ""
    echo "For more information, see README.md"
else
    echo "Error: Failed to install dependencies."
    exit 1
fi 
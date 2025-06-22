#!/usr/bin/env python3
"""
Demo script for YouTube to Script Web App (Gemini AI)
Shows how to use the web app programmatically
"""

import os
import sys
from pathlib import Path

def check_setup():
    """Check if the web app is properly set up."""
    print("🔍 Checking setup...")
    
    # Check if required files exist
    required_files = ['webapp.py', 'templates/index.html', 'requirements.txt']
    for file in required_files:
        if not Path(file).exists():
            print(f"❌ Missing: {file}")
            return False
        else:
            print(f"✅ Found: {file}")
    
    # Check if output directory exists
    if not Path('output').exists():
        print("📁 Creating output directory...")
        Path('output').mkdir(exist_ok=True)
    
    # Check if templates directory exists
    if not Path('templates').exists():
        print("❌ Missing templates directory")
        return False
    
    print("✅ Setup looks good!")
    return True

def show_usage():
    """Show usage instructions."""
    print("\n🎬 YouTube to Script Web App - Usage (Gemini AI)")
    print("=" * 50)
    
    print("\n1️⃣  The Gemini API key is already configured!")
    print("   No additional setup needed for transcription.")
    
    print("\n2️⃣  Start the web app:")
    print("   python3 webapp.py")
    
    print("\n3️⃣  Open your browser:")
    print("   http://localhost:8080")
    
    print("\n4️⃣  Paste a YouTube URL and click 'Convert to Script'")
    
    print("\n💡 Optional: For Hinglish translation")
    print("   export GOOGLE_APPLICATION_CREDENTIALS='path/to/credentials.json'")

def show_example():
    """Show an example of what the app does."""
    print("\n📝 Example Output:")
    print("-" * 30)
    print("Input: https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    print("\nEnglish Transcript:")
    print("We're no strangers to love...")
    print("\nHinglish Transcript:")
    print("Hum pyaar ke ajnabi nahi hain...")

def main():
    """Main demo function."""
    print("🎬 YouTube to Script Web App - Demo (Gemini AI)")
    print("=" * 50)
    
    if not check_setup():
        print("\n❌ Setup incomplete. Please run setup_webapp.sh first.")
        return
    
    show_usage()
    show_example()
    
    print("\n🚀 Ready to start? Run:")
    print("   python3 webapp.py")
    print("\n✨ Powered by Google Gemini AI!")

if __name__ == "__main__":
    main() 
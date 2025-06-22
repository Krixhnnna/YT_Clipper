#!/usr/bin/env python3
"""
YouTube Video Downloader Launcher
Choose between command-line and GUI versions
"""

import sys
import subprocess
import os

def main():
    print("YouTube Video Downloader")
    print("=" * 30)
    print("Choose your preferred interface:")
    print("1. Command Line Interface (CLI)")
    print("2. Graphical User Interface (GUI)")
    print("3. Exit")
    
    while True:
        try:
            choice = input("\nEnter your choice (1-3): ").strip()
            
            if choice == "1":
                print("\nStarting Command Line Interface...")
                subprocess.run([sys.executable, "video_downloader.py"] + sys.argv[1:])
                break
            elif choice == "2":
                print("\nStarting Graphical User Interface...")
                subprocess.run([sys.executable, "video_downloader_gui.py"])
                break
            elif choice == "3":
                print("Goodbye!")
                break
            else:
                print("Invalid choice. Please enter 1, 2, or 3.")
                
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")
            break

if __name__ == "__main__":
    main() 
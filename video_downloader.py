#!/usr/bin/env python3
"""
YouTube Video Downloader
Downloads videos from YouTube links to the /video folder
"""

import os
import sys
import yt_dlp
from pathlib import Path
import argparse

def create_video_folder():
    """Create the video folder if it doesn't exist"""
    video_folder = Path("video")
    video_folder.mkdir(exist_ok=True)
    return video_folder

def get_available_formats(url):
    """Get available formats for a video"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])
            return formats, info
    except Exception as e:
        print(f"Error getting video info: {e}")
        return [], None

def download_video(url, video_folder, quality='best', audio_only=False):
    """Download video from YouTube URL to the video folder"""
    
    # Configure yt-dlp options
    if audio_only:
        format_spec = 'bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio'
        outtmpl = str(video_folder / '%(title)s.%(ext)s')
    else:
        if quality == 'best':
            format_spec = 'best[ext=mp4]/best'
        elif quality == 'worst':
            format_spec = 'worst[ext=mp4]/worst'
        elif quality == '720p':
            format_spec = 'best[height<=720][ext=mp4]/best[height<=720]'
        elif quality == '480p':
            format_spec = 'best[height<=480][ext=mp4]/best[height<=480]'
        else:
            format_spec = 'best[ext=mp4]/best'
        
        outtmpl = str(video_folder / '%(title)s.%(ext)s')
    
    ydl_opts = {
        'outtmpl': outtmpl,
        'format': format_spec,
        'writeinfojson': True,
        'writethumbnail': True,
        'progress_hooks': [progress_hook],
        'ignoreerrors': False,
        'no_warnings': False,
        'extractaudio': audio_only,
        'audioformat': 'mp3' if audio_only else None,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}] if audio_only else [],
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"Starting download: {url}")
            print(f"Quality: {quality}")
            print(f"Audio only: {audio_only}")
            ydl.download([url])
            print("Download completed successfully!")
            
    except yt_dlp.DownloadError as e:
        print(f"Error downloading video: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False
    
    return True

def progress_hook(d):
    """Progress hook to show download progress"""
    if d['status'] == 'downloading':
        total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
        downloaded = d.get('downloaded_bytes', 0)
        
        if total > 0:
            percentage = (downloaded / total) * 100
            speed = d.get('speed', 0)
            if speed:
                speed_mb = speed / 1024 / 1024
                print(f"\rDownloading... {percentage:.1f}% ({speed_mb:.1f} MB/s)", end='', flush=True)
            else:
                print(f"\rDownloading... {percentage:.1f}%", end='', flush=True)
    
    elif d['status'] == 'finished':
        print(f"\nDownload finished: {d['filename']}")

def list_formats(url):
    """List available formats for a video"""
    formats, info = get_available_formats(url)
    
    if not formats:
        print("Could not retrieve video formats.")
        return
    
    print(f"\nVideo: {info.get('title', 'Unknown')}")
    print(f"Duration: {info.get('duration', 0)} seconds")
    print("\nAvailable formats:")
    print("-" * 80)
    print(f"{'Format ID':<10} {'Extension':<8} {'Resolution':<12} {'Filesize':<10} {'Note'}")
    print("-" * 80)
    
    for f in formats:
        format_id = f.get('format_id', 'N/A')
        ext = f.get('ext', 'N/A')
        resolution = f.get('resolution', 'N/A')
        filesize = f.get('filesize', 0)
        if filesize:
            filesize_mb = filesize / 1024 / 1024
            filesize_str = f"{filesize_mb:.1f}MB"
        else:
            filesize_str = 'N/A'
        note = f.get('format_note', '')
        
        print(f"{format_id:<10} {ext:<8} {resolution:<12} {filesize_str:<10} {note}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Download YouTube videos to local video folder')
    parser.add_argument('url', nargs='?', help='YouTube URL to download')
    parser.add_argument('-q', '--quality', choices=['best', 'worst', '720p', '480p'], 
                       default='best', help='Video quality (default: best)')
    parser.add_argument('-a', '--audio-only', action='store_true', 
                       help='Download audio only (MP3)')
    parser.add_argument('-l', '--list-formats', action='store_true', 
                       help='List available formats for the video')
    parser.add_argument('-i', '--interactive', action='store_true', 
                       help='Interactive mode')
    
    args = parser.parse_args()
    
    print("YouTube Video Downloader")
    print("=" * 30)
    
    # Create video folder
    video_folder = create_video_folder()
    print(f"Video folder: {video_folder.absolute()}")
    
    # Get YouTube URL
    url = args.url
    if not url and not args.interactive:
        print("Error: No URL provided. Use -i for interactive mode or provide a URL.")
        return
    
    if args.interactive and not url:
        url = input("Enter YouTube URL: ").strip()
    
    if not url:
        print("No URL provided. Exiting.")
        return
    
    # Validate URL (basic check)
    if 'youtube.com' not in url and 'youtu.be' not in url:
        print("Warning: This doesn't look like a YouTube URL.")
        response = input("Continue anyway? (y/N): ").strip().lower()
        if response != 'y':
            return
    
    # List formats if requested
    if args.list_formats:
        list_formats(url)
        return
    
    # Download the video
    success = download_video(url, video_folder, args.quality, args.audio_only)
    
    if success:
        print(f"\nVideo downloaded to: {video_folder.absolute()}")
    else:
        print("\nDownload failed. Please check the URL and try again.")

if __name__ == "__main__":
    main() 
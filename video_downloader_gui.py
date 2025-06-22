#!/usr/bin/env python3
"""
YouTube Video Downloader GUI
Graphical interface for downloading YouTube videos
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import yt_dlp
from pathlib import Path
import sys
import os

class VideoDownloaderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Video Downloader")
        self.root.geometry("600x500")
        self.root.resizable(True, True)
        
        # Variables
        self.url_var = tk.StringVar()
        self.quality_var = tk.StringVar(value="best")
        self.audio_only_var = tk.BooleanVar()
        self.output_folder_var = tk.StringVar(value="video")
        
        self.setup_ui()
        
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # URL input
        ttk.Label(main_frame, text="YouTube URL:").grid(row=0, column=0, sticky=tk.W, pady=5)
        url_entry = ttk.Entry(main_frame, textvariable=self.url_var, width=50)
        url_entry.grid(row=0, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Output folder
        ttk.Label(main_frame, text="Output Folder:").grid(row=1, column=0, sticky=tk.W, pady=5)
        folder_entry = ttk.Entry(main_frame, textvariable=self.output_folder_var, width=40)
        folder_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)
        ttk.Button(main_frame, text="Browse", command=self.browse_folder).grid(row=1, column=2, padx=(5, 0), pady=5)
        
        # Quality selection
        ttk.Label(main_frame, text="Quality:").grid(row=2, column=0, sticky=tk.W, pady=5)
        quality_combo = ttk.Combobox(main_frame, textvariable=self.quality_var, 
                                   values=["best", "720p", "480p", "worst"], state="readonly")
        quality_combo.grid(row=2, column=1, sticky=tk.W, pady=5)
        
        # Audio only checkbox
        audio_check = ttk.Checkbutton(main_frame, text="Audio Only (MP3)", variable=self.audio_only_var)
        audio_check.grid(row=2, column=2, sticky=tk.W, pady=5)
        
        # Buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=10)
        
        ttk.Button(button_frame, text="List Formats", command=self.list_formats).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Download", command=self.start_download).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear", command=self.clear_output).pack(side=tk.LEFT, padx=5)
        
        # Progress bar
        self.progress_var = tk.StringVar(value="Ready")
        ttk.Label(main_frame, textvariable=self.progress_var).grid(row=4, column=0, columnspan=3, pady=5)
        
        self.progress_bar = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress_bar.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        # Output text area
        ttk.Label(main_frame, text="Output:").grid(row=6, column=0, sticky=tk.W, pady=(10, 5))
        
        self.output_text = scrolledtext.ScrolledText(main_frame, height=15, width=70)
        self.output_text.grid(row=7, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # Configure text area to expand
        main_frame.rowconfigure(7, weight=1)
        
    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_folder_var.set(folder)
    
    def log_message(self, message):
        self.output_text.insert(tk.END, message + "\n")
        self.output_text.see(tk.END)
        self.root.update_idletasks()
    
    def clear_output(self):
        self.output_text.delete(1.0, tk.END)
        self.progress_var.set("Ready")
        self.progress_bar.stop()
    
    def progress_hook(self, d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            
            if total > 0:
                percentage = (downloaded / total) * 100
                speed = d.get('speed', 0)
                if speed:
                    speed_mb = speed / 1024 / 1024
                    self.progress_var.set(f"Downloading... {percentage:.1f}% ({speed_mb:.1f} MB/s)")
                else:
                    self.progress_var.set(f"Downloading... {percentage:.1f}%")
        
        elif d['status'] == 'finished':
            self.progress_var.set(f"Download finished: {d['filename']}")
            self.log_message(f"Download finished: {d['filename']}")
    
    def get_available_formats(self, url):
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
            self.log_message(f"Error getting video info: {e}")
            return [], None
    
    def list_formats(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a YouTube URL")
            return
        
        self.progress_var.set("Getting video formats...")
        self.progress_bar.start()
        
        def list_formats_thread():
            try:
                formats, info = self.get_available_formats(url)
                
                if not formats:
                    self.log_message("Could not retrieve video formats.")
                    return
                
                self.log_message(f"\nVideo: {info.get('title', 'Unknown')}")
                self.log_message(f"Duration: {info.get('duration', 0)} seconds")
                self.log_message("\nAvailable formats:")
                self.log_message("-" * 80)
                self.log_message(f"{'Format ID':<10} {'Extension':<8} {'Resolution':<12} {'Filesize':<10} {'Note'}")
                self.log_message("-" * 80)
                
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
                    
                    self.log_message(f"{format_id:<10} {ext:<8} {resolution:<12} {filesize_str:<10} {note}")
                
            except Exception as e:
                self.log_message(f"Error: {e}")
            finally:
                self.progress_var.set("Ready")
                self.progress_bar.stop()
        
        threading.Thread(target=list_formats_thread, daemon=True).start()
    
    def download_video(self, url, output_folder, quality, audio_only):
        # Create output folder
        output_path = Path(output_folder)
        output_path.mkdir(exist_ok=True)
        
        # Configure yt-dlp options
        if audio_only:
            format_spec = 'bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio'
            outtmpl = str(output_path / '%(title)s.%(ext)s')
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
            
            outtmpl = str(output_path / '%(title)s.%(ext)s')
        
        ydl_opts = {
            'outtmpl': outtmpl,
            'format': format_spec,
            'writeinfojson': True,
            'writethumbnail': True,
            'progress_hooks': [self.progress_hook],
            'ignoreerrors': False,
            'no_warnings': False,
            'extractaudio': audio_only,
            'audioformat': 'mp3' if audio_only else None,
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}] if audio_only else [],
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self.log_message(f"Starting download: {url}")
                self.log_message(f"Quality: {quality}")
                self.log_message(f"Audio only: {audio_only}")
                ydl.download([url])
                self.log_message("Download completed successfully!")
                return True
                
        except yt_dlp.DownloadError as e:
            self.log_message(f"Error downloading video: {e}")
            return False
        except Exception as e:
            self.log_message(f"Unexpected error: {e}")
            return False
    
    def start_download(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a YouTube URL")
            return
        
        output_folder = self.output_folder_var.get().strip()
        if not output_folder:
            messagebox.showerror("Error", "Please specify an output folder")
            return
        
        quality = self.quality_var.get()
        audio_only = self.audio_only_var.get()
        
        self.progress_var.set("Starting download...")
        self.progress_bar.start()
        
        def download_thread():
            try:
                success = self.download_video(url, output_folder, quality, audio_only)
                
                if success:
                    self.progress_var.set("Download completed!")
                    messagebox.showinfo("Success", f"Video downloaded to: {output_folder}")
                else:
                    self.progress_var.set("Download failed")
                    messagebox.showerror("Error", "Download failed. Please check the URL and try again.")
                    
            except Exception as e:
                self.log_message(f"Error: {e}")
                self.progress_var.set("Download failed")
                messagebox.showerror("Error", f"Download failed: {e}")
            finally:
                self.progress_bar.stop()
        
        threading.Thread(target=download_thread, daemon=True).start()

def main():
    root = tk.Tk()
    app = VideoDownloaderGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main() 
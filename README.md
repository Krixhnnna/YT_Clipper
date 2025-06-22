# YouTube Video Downloader

A Python application to download videos from YouTube links to a local `/video` folder. Available in both command-line and graphical interface versions.

## Features

- Downloads YouTube videos in the best available quality (prefers MP4 format)
- Saves videos to a dedicated `/video` folder
- Shows download progress in real-time with speed information
- Saves video metadata and thumbnails
- Supports both youtube.com and youtu.be URLs
- Multiple quality options (best, 720p, 480p, worst)
- Audio-only download option (MP3 format)
- List available video formats before downloading
- Command-line interface with interactive mode
- Graphical user interface (GUI) for easy use

## Installation

1. Make sure you have Python 3.6+ installed
2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Command-Line Version (`video_downloader.py`)

#### Method 1: Interactive Mode
Run the script without arguments and enter the URL when prompted:

```bash
python3 video_downloader.py
```

#### Method 2: Command Line Mode
Pass the YouTube URL as a command line argument:

```bash
python3 video_downloader.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

#### Method 3: With Options
```bash
# Download with specific quality
python3 video_downloader.py "URL" -q 720p

# Download audio only (MP3)
python3 video_downloader.py "URL" -a

# List available formats
python3 video_downloader.py "URL" -l

# Interactive mode
python3 video_downloader.py -i
```

#### Command-Line Options
- `-q, --quality`: Video quality (best, 720p, 480p, worst)
- `-a, --audio-only`: Download audio only (MP3)
- `-l, --list-formats`: List available formats for the video
- `-i, --interactive`: Interactive mode

### GUI Version (`video_downloader_gui.py`)

Launch the graphical interface:

```bash
python3 video_downloader_gui.py
```

The GUI provides:
- URL input field
- Output folder selection with browse button
- Quality dropdown (best, 720p, 480p, worst)
- Audio-only checkbox
- List formats button
- Download button with progress bar
- Real-time output log

## Output

- Videos are saved to the `/video` folder (or custom folder in GUI)
- Filenames include the video title and extension
- Additional files created:
  - `.info.json` - Video metadata
  - `.webp` or `.jpg` - Video thumbnail

## Examples

### Command-Line Examples

```bash
# Basic download
$ python3 video_downloader.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
YouTube Video Downloader
==============================
Video folder: /path/to/YT_Clipper/video
Starting download: https://www.youtube.com/watch?v=dQw4w9WgXcQ
Quality: best
Audio only: False
Downloading... 45.2% (2.1 MB/s)
Download finished: /path/to/YT_Clipper/video/Rick Astley - Never Gonna Give You Up (Official Music Video).mp4
Download completed successfully!

Video downloaded to: /path/to/YT_Clipper/video

# Download audio only
$ python3 video_downloader.py "https://www.youtube.com/watch?v=VIDEO_ID" -a

# Download 720p quality
$ python3 video_downloader.py "https://www.youtube.com/watch?v=VIDEO_ID" -q 720p

# List available formats
$ python3 video_downloader.py "https://www.youtube.com/watch?v=VIDEO_ID" -l
```

### GUI Example

1. Run `python3 video_downloader_gui.py`
2. Enter YouTube URL in the URL field
3. Select output folder (default: "video")
4. Choose quality from dropdown
5. Check "Audio Only" if you want MP3
6. Click "Download" to start
7. Monitor progress in the output area

## Requirements

- Python 3.6+
- yt-dlp (latest version)
- requests
- tkinter (for GUI - usually included with Python)

## Notes

- The script automatically creates the `/video` folder if it doesn't exist
- Downloads are saved in the best available quality for the selected option
- The script validates URLs to ensure they're from YouTube
- Progress is shown during download with speed information
- Error handling is included for failed downloads
- GUI version runs downloads in background threads to keep interface responsive

## Troubleshooting

### Common Issues

1. **"No module named 'yt_dlp'"**: Install dependencies with `pip install -r requirements.txt`
2. **Download fails**: Try updating yt-dlp with `pip install --upgrade yt-dlp`
3. **GUI doesn't start**: Ensure tkinter is installed (usually included with Python)
4. **Permission errors**: Make sure you have write permissions in the output directory

### Updating yt-dlp

YouTube frequently changes their systems, so keep yt-dlp updated:

```bash
pip install --upgrade yt-dlp
```

## Legal Notice

This tool is for personal use only. Please respect YouTube's Terms of Service and only download videos you have permission to download. # YT_Clipper

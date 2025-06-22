# YouTube to Script Web App

A modern web application that downloads YouTube videos and converts them to text scripts using Google Gemini AI. The app intelligently detects the video's language and generates appropriate scripts - Hinglish for Hindi videos, English for others.

## 🌟 Features

- **Smart Language Detection**: Automatically detects if a video is in Hindi or other languages
- **Intelligent Script Generation**: 
  - Hindi videos → Hinglish script (Hindi in Latin script)
  - Other languages → English script
- **One-Click Download**: Download YouTube videos with a single click
- **Auto-Save Scripts**: Scripts are automatically saved as text files in the `/output` folder
- **Modern Web Interface**: Beautiful, responsive UI with real-time feedback
- **Powered by Gemini AI**: Uses Google's latest AI model for accurate transcription

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- Google Gemini API key

### Installation

1. **Clone or download the project files**

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up your Gemini API key:**
   - Get your API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
   - The API key is already configured in the app

4. **Run the web app:**
   ```bash
   python3 webapp.py
   ```

5. **Open your browser and go to:**
   ```
   http://localhost:8080
   ```

## 📖 How to Use

1. **Enter YouTube URL**: Paste any YouTube video link in the input field
2. **Click Generate**: The app will download the video and analyze its language
3. **Get Your Script**: 
   - Hindi videos will generate Hinglish scripts
   - Other languages will generate English scripts
4. **Download**: Click the download button to save the script as a text file

## 🎯 How It Works

### Language Detection
The app uses Gemini AI to analyze the video content and determine the primary spoken language:
- If Hindi is detected → Generates Hinglish script
- If other languages are detected → Generates English script

### Script Generation
- **Hinglish Scripts**: Hindi speech converted to Latin script (e.g., "Namaste, kaise ho aap?")
- **English Scripts**: Direct English transcription of the video content

### File Naming
Scripts are saved with descriptive filenames:
- Hindi videos: `{video_id}_{title}_script_hinglish.txt`
- Other videos: `{video_id}_{title}_script.txt`

## 📁 Project Structure

```
YT_Clipper/
├── webapp.py              # Main Flask application
├── templates/
│   └── index.html         # Web interface
├── output/                # Downloaded videos and scripts
├── requirements.txt       # Python dependencies
└── README_WEBAPP.md       # This file
```

## 🔧 Configuration

### API Keys
The app is pre-configured with a Gemini API key. If you need to use your own:

1. Get your API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Replace the `GEMINI_API_KEY` in `webapp.py`

### Output Directory
Scripts and videos are saved to the `/output` folder by default. You can modify the `OUTPUT_DIR` variable in `webapp.py` to change this location.

## 📋 Requirements

```
flask==2.3.3
yt-dlp==2023.7.6
google-generativeai==0.3.1
google-cloud-translate==3.11.1
```

## 🌐 Web Interface

The web app provides a modern, user-friendly interface with:

- **Clean Design**: Modern gradient background and card-based layout
- **Real-time Feedback**: Progress indicators and status messages
- **Language Badges**: Visual indicators showing script language
- **Download Links**: Direct download buttons for generated scripts
- **Responsive Design**: Works on desktop and mobile devices

## 🎨 Features Overview

### Smart Detection
- Automatically analyzes video content
- Determines primary spoken language
- Routes to appropriate transcription method

### Hindi → Hinglish
- Detects Hindi speech in videos
- Converts to Hinglish (Hindi in Latin script)
- Maintains natural language flow

### English Transcription
- Handles all other languages
- Provides accurate English transcriptions
- Clean, readable output format

### Auto-Save
- Scripts automatically saved to `/output` folder
- Descriptive filenames with video metadata
- Easy download links in web interface

## 🔍 Troubleshooting

### Common Issues

1. **"Transcription error" message**
   - Check your internet connection
   - Verify the YouTube URL is valid
   - Ensure the video is not private or age-restricted

2. **Port 8080 already in use**
   - Change the port in `webapp.py` (line with `app.run()`)
   - Or kill the process using port 8080

3. **Video download fails**
   - Some videos may be restricted or unavailable
   - Try a different YouTube video

### Performance Tips

- The app works best with videos under 10 minutes
- Longer videos may take more time to process
- Ensure stable internet connection for video downloads

## 🚀 Advanced Usage

### Custom Language Detection
You can modify the language detection logic in the `detect_language_and_transcribe()` function to support additional languages.

### Batch Processing
For processing multiple videos, you can extend the app to accept multiple URLs or create a batch processing script.

### Custom Output Formats
Modify the `save_transcript_to_file()` function to save scripts in different formats (JSON, CSV, etc.).

## 📝 License

This project is open source and available under the MIT License.

## 🤝 Contributing

Feel free to submit issues, feature requests, or pull requests to improve the application.

---

**Happy Scripting! 🎬📝** 
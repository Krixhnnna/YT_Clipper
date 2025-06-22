import os
from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify
from pathlib import Path
import yt_dlp
import google.generativeai as genai
from google.cloud import translate_v2 as translate
import tempfile
import json
import base64
from datetime import datetime
import time
import subprocess
import re
import threading
import uuid

app = Flask(__name__)
OUTPUT_DIR = Path('output')
OUTPUT_DIR.mkdir(exist_ok=True)

# Configure Gemini AI
GEMINI_API_KEY = "AIzaSyDT0VLpFKwJvhcmiBNYzQhnm2Ohmzg4e-U"
genai.configure(api_key=GEMINI_API_KEY)

# Initialize Gemini model
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

# Initialize Google Translate client (you'll need to set GOOGLE_APPLICATION_CREDENTIALS)
try:
    translate_client = translate.Client()
except:
    translate_client = None

# Global progress tracking
progress_tracker = {}

def download_youtube_video(url, output_dir, task_id):
    """Download YouTube video as mp4 to output_dir, return file path."""
    progress_tracker[task_id] = {'status': 'downloading', 'progress': 0, 'message': 'Starting download...'}
    
    ydl_opts = {
        'outtmpl': str(output_dir / '%(id)s.%(ext)s'),
        'format': 'best[ext=mp4]/best',
        'quiet': True,
        'progress_hooks': [lambda d: update_progress(task_id, d)],
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_id = info['id']
        ext = info['ext']
        progress_tracker[task_id]['progress'] = 25
        progress_tracker[task_id]['message'] = 'Download completed'
        return output_dir / f"{video_id}.{ext}"

def update_progress(task_id, d):
    """Update progress for download."""
    if task_id in progress_tracker:
        if d['status'] == 'downloading':
            try:
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
                if total > 0:
                    progress = min(25, (downloaded / total) * 25)
                    progress_tracker[task_id]['progress'] = progress
                    progress_tracker[task_id]['message'] = f'Downloading... {progress:.1f}%'
            except:
                pass

def detect_language_and_transcribe_with_timestamps(video_path, task_id, max_retries=3):
    """Detect if video is in Hindi and transcribe with timestamps."""
    progress_tracker[task_id]['status'] = 'transcribing'
    progress_tracker[task_id]['progress'] = 30
    progress_tracker[task_id]['message'] = 'Detecting language...'
    
    for attempt in range(max_retries):
        try:
            # Read video file and encode to base64
            progress_tracker[task_id]['message'] = 'Reading video file...'
            with open(video_path, "rb") as video_file:
                video_data = video_file.read()
                video_base64 = base64.b64encode(video_data).decode('utf-8')
            
            # First, detect the language
            progress_tracker[task_id]['message'] = 'Detecting language with AI...'
            detection_prompt = """
            Please analyze this video and determine if the primary spoken language is Hindi.
            Respond with only 'HINDI' if Hindi is the main language, or 'ENGLISH' if it's English or any other language.
            """
            
            detection_response = gemini_model.generate_content([
                detection_prompt,
                {
                    "mime_type": "video/mp4",
                    "data": video_base64
                }
            ])
            
            is_hindi = 'HINDI' in detection_response.text.upper()
            progress_tracker[task_id]['progress'] = 45
            progress_tracker[task_id]['message'] = 'Transcribing with AI...'
            
            # Now transcribe with timestamps based on detected language
            if is_hindi:
                transcribe_prompt = """
                This video is in Hindi. Please transcribe the Hindi speech and convert it to Hinglish (Hindi written in Latin script).
                Include timestamps for each segment in format [MM:SS] or [MM:SS.MS].
                Provide a clear, accurate transcription with timestamps.
                Format example:
                [00:05] Namaste, aaj hum baat karenge...
                [00:12] Ye bahut important topic hai...
                """
                language = "Hinglish"
            else:
                transcribe_prompt = """
                Please transcribe this video to English text with timestamps.
                Include timestamps for each segment in format [MM:SS] or [MM:SS.MS].
                Provide a clear, accurate transcription of all spoken content with timestamps.
                Format example:
                [00:05] Hello everyone, today we will discuss...
                [00:12] This is a very important topic...
                """
                language = "English"
            
            transcription_response = gemini_model.generate_content([
                transcribe_prompt,
                {
                    "mime_type": "video/mp4",
                    "data": video_base64
                }
            ])
            
            progress_tracker[task_id]['progress'] = 60
            progress_tracker[task_id]['message'] = 'Transcription completed'
            
            return transcription_response.text, language, is_hindi
            
        except Exception as e:
            error_str = str(e)
            
            # Check for rate limit/quota exceeded errors
            if "429" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower():
                if attempt < max_retries - 1:
                    # Wait before retrying (exponential backoff)
                    wait_time = (2 ** attempt) * 10  # 10s, 20s, 40s
                    progress_tracker[task_id]['message'] = f'Rate limit hit, waiting {wait_time}s...'
                    time.sleep(wait_time)
                    continue
                else:
                    progress_tracker[task_id]['status'] = 'error'
                    progress_tracker[task_id]['message'] = f'API rate limit exceeded'
                    return f"API rate limit exceeded. Please wait a few minutes and try again. Error: {error_str}", "Error", False
            
            # For other errors, return immediately
            progress_tracker[task_id]['status'] = 'error'
            progress_tracker[task_id]['message'] = f'Transcription error: {error_str}'
            return f"Transcription error: {error_str}", "Error", False
    
    progress_tracker[task_id]['status'] = 'error'
    progress_tracker[task_id]['message'] = 'Transcription failed after multiple attempts'
    return "Transcription failed after multiple attempts", "Error", False

def analyze_script_and_find_three_clips(transcript, video_duration, task_id):
    """Analyze the transcript and find the 3 best clips with viral scores."""
    progress_tracker[task_id]['status'] = 'analyzing'
    progress_tracker[task_id]['progress'] = 70
    progress_tracker[task_id]['message'] = 'Analyzing transcript for best clips...'
    
    try:
        analysis_prompt = f"""
        Analyze this transcript and find the 3 best clips that would be most engaging for social media.
        
        Transcript:
        {transcript}
        
        For each clip, identify:
        1. Start timestamp (MM:SS format)
        2. End timestamp (MM:SS format)
        3. Viral score out of 100 (based on engagement potential)
        4. Brief reason why this clip is viral-worthy
        
        Choose clips that:
        - Are between 15-45 seconds long
        - Have high engagement potential
        - Are self-contained and make sense on their own
        - Have clear, impactful speech
        - Would work well for social media sharing
        
        Respond in this exact format:
        CLIP1_START: [MM:SS]
        CLIP1_END: [MM:SS]
        CLIP1_SCORE: [number 0-100]
        CLIP1_REASON: [brief explanation]
        
        CLIP2_START: [MM:SS]
        CLIP2_END: [MM:SS]
        CLIP2_SCORE: [number 0-100]
        CLIP2_REASON: [brief explanation]
        
        CLIP3_START: [MM:SS]
        CLIP3_END: [MM:SS]
        CLIP3_SCORE: [number 0-100]
        CLIP3_REASON: [brief explanation]
        """
        
        response = gemini_model.generate_content(analysis_prompt)
        response_text = response.text
        
        # Parse the response for 3 clips
        clips = []
        for i in range(1, 4):
            start_match = re.search(f'CLIP{i}_START:\\s*\\[(\\d{{2}}:\\d{{2}})\\]', response_text)
            end_match = re.search(f'CLIP{i}_END:\\s*\\[(\\d{{2}}:\\d{{2}})\\]', response_text)
            score_match = re.search(f'CLIP{i}_SCORE:\\s*\\[(\\d+)\\]', response_text)
            reason_match = re.search(f'CLIP{i}_REASON:\\s*(.+)', response_text)
            
            if start_match and end_match and score_match:
                start_time = start_match.group(1)
                end_time = end_match.group(1)
                score = int(score_match.group(1))
                reason = reason_match.group(1) if reason_match else f"Clip {i} selected for engagement"
                
                clips.append({
                    'start_time': start_time,
                    'end_time': end_time,
                    'score': score,
                    'reason': reason
                })
        
        # If we don't get 3 clips, create fallback clips
        while len(clips) < 3:
            fallback_start = f"00:{30 + len(clips) * 15:02d}"
            fallback_end = f"00:{45 + len(clips) * 15:02d}"
            clips.append({
                'start_time': fallback_start,
                'end_time': fallback_end,
                'score': 70 - len(clips) * 10,
                'reason': f"Fallback clip {len(clips) + 1}"
            })
        
        progress_tracker[task_id]['progress'] = 80
        progress_tracker[task_id]['message'] = 'Clip analysis completed'
        
        return clips[:3]  # Ensure we return exactly 3 clips
            
    except Exception as e:
        print(f"Error analyzing script: {e}")
        progress_tracker[task_id]['message'] = 'Analysis failed, using fallback clips'
        # Fallback: create 3 clips
        return [
            {'start_time': '00:30', 'end_time': '00:45', 'score': 75, 'reason': 'Fallback clip 1'},
            {'start_time': '00:45', 'end_time': '01:00', 'score': 70, 'reason': 'Fallback clip 2'},
            {'start_time': '01:00', 'end_time': '01:15', 'score': 65, 'reason': 'Fallback clip 3'}
        ]

def create_vertical_clip(input_video_path, start_time, end_time, output_filename, task_id):
    """Create a 9:16 vertical clip from the original video."""
    try:
        output_path = OUTPUT_DIR / output_filename
        
        # FFmpeg command to create 9:16 vertical clip
        # Crop to center and resize to 9:16 aspect ratio
        cmd = [
            'ffmpeg', '-i', str(input_video_path),
            '-ss', start_time,
            '-to', end_time,
            '-vf', 'crop=ih*9/16:ih,scale=1080:1920',  # Crop to 9:16 and scale to 1080x1920
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-preset', 'fast',
            '-crf', '23',
            '-y',  # Overwrite output file
            str(output_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return output_path
        else:
            print(f"FFmpeg error: {result.stderr}")
            return None
            
    except Exception as e:
        print(f"Error creating vertical clip: {e}")
        return None

def process_video_task(url, task_id):
    """Process video in background thread."""
    try:
        # Download video
        video_path = download_youtube_video(url, OUTPUT_DIR, task_id)
        
        # Get video info for title and ID
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            video_title = info.get('title', 'Unknown Video')
            video_id = info.get('id', 'unknown')
            video_duration = info.get('duration', 0)
        
        # Detect language and transcribe with timestamps
        transcript, language, is_hindi = detect_language_and_transcribe_with_timestamps(video_path, task_id)
        
        # Analyze script and find 3 best clips
        if transcript and not transcript.startswith("Transcription error") and not transcript.startswith("API rate limit"):
            clips = analyze_script_and_find_three_clips(transcript, video_duration, task_id)
            
            progress_tracker[task_id]['status'] = 'clipping'
            progress_tracker[task_id]['progress'] = 85
            progress_tracker[task_id]['message'] = 'Creating vertical clips...'
            
            # Create vertical clips
            safe_title = "".join(c for c in video_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_title = safe_title.replace(' ', '_')[:20]
            
            created_clips = []
            for i, clip in enumerate(clips):
                clip_filename = f"{video_id}_{safe_title}_clip{i+1}_9x16.mp4"
                clip_path = create_vertical_clip(video_path, clip['start_time'], clip['end_time'], clip_filename, task_id)
                
                if clip_path:
                    created_clips.append({
                        'start_time': clip['start_time'],
                        'end_time': clip['end_time'],
                        'score': clip['score'],
                        'reason': clip['reason'],
                        'filename': clip_filename
                    })
                
                # Update progress for each clip
                progress_tracker[task_id]['progress'] = 85 + ((i + 1) * 5)
                progress_tracker[task_id]['message'] = f'Created clip {i + 1}/3...'
            
            if created_clips:
                progress_tracker[task_id]['progress'] = 100
                progress_tracker[task_id]['status'] = 'completed'
                progress_tracker[task_id]['message'] = 'All clips created successfully!'
                progress_tracker[task_id]['result'] = {
                    'clips': created_clips,
                    'video_title': video_title
                }
            else:
                progress_tracker[task_id]['status'] = 'error'
                progress_tracker[task_id]['message'] = 'Failed to create clips'
        else:
            progress_tracker[task_id]['status'] = 'error'
            progress_tracker[task_id]['message'] = transcript if transcript else 'Transcription failed'
            
    except Exception as e:
        progress_tracker[task_id]['status'] = 'error'
        progress_tracker[task_id]['message'] = f'Error: {str(e)}'

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        url = request.form.get('youtube_url')
        if not url:
            return jsonify({'error': 'Please provide a YouTube link.'})
        
        # Generate unique task ID
        task_id = str(uuid.uuid4())
        progress_tracker[task_id] = {
            'status': 'starting',
            'progress': 0,
            'message': 'Initializing...',
            'result': None
        }
        
        # Start background processing
        thread = threading.Thread(target=process_video_task, args=(url, task_id))
        thread.daemon = True
        thread.start()
        
        return jsonify({'task_id': task_id})
    
    return render_template('index.html')

@app.route('/progress/<task_id>')
def get_progress(task_id):
    """Get progress for a specific task."""
    if task_id in progress_tracker:
        return jsonify(progress_tracker[task_id])
    else:
        return jsonify({'error': 'Task not found'})

@app.route('/download/<filename>')
def download_file(filename):
    """Download a file from the output directory."""
    try:
        file_path = OUTPUT_DIR / filename
        if file_path.exists() and file_path.is_file():
            return send_file(file_path, as_attachment=True)
        else:
            return "File not found", 404
    except Exception as e:
        return f"Error downloading file: {e}", 500

@app.route('/video/<filename>')
def serve_video(filename):
    """Serve video files for preview."""
    try:
        file_path = OUTPUT_DIR / filename
        if file_path.exists() and file_path.is_file():
            return send_file(file_path, mimetype='video/mp4')
        else:
            return "Video not found", 404
    except Exception as e:
        return f"Error serving video: {e}", 500

@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy", 
        "gemini_key": bool(GEMINI_API_KEY),
        "translate_available": bool(translate_client)
    })

if __name__ == '__main__':
    # Check for required environment variables
    if not GEMINI_API_KEY:
        print("⚠️  Warning: GEMINI_API_KEY not set. Please set it to use transcription.")
        print("   Get your API key from: https://makersuite.google.com/app/apikey")
    
    if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
        print("⚠️  Warning: GOOGLE_APPLICATION_CREDENTIALS not set. Hinglish translation may not work.")
        print("   Set up Google Cloud credentials for translation features.")
    
    print("🚀 Starting Clipper.ai - AI Video Clipper...")
    print(f"📝 Using Gemini API Key: {GEMINI_API_KEY[:10]}...")
    print("🌐 Web app will be available at: http://localhost:8080")
    print("💾 Videos will be saved to: /output folder")
    print("🎯 Smart language detection: Hindi → Hinglish, Others → English")
    print("📱 Auto-creates 3 viral clips with scores")
    print("⚠️  Note: Free tier has rate limits. If you hit limits, wait a few minutes and try again.")
    
    app.run(debug=True, host='0.0.0.0', port=8080) 
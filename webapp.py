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

# Helper functions for timestamp normalization
def _to_seconds(time_str):
    """Converts HH:MM:SS or MM:SS into total seconds, robustly."""
    try:
        time_str = time_str.split('.')[0]  # Remove milliseconds
        parts = [int(p) for p in time_str.split(':')]
        seconds = 0
        if len(parts) == 3:  # HH:MM:SS
            seconds = parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 2:  # MM:SS
            seconds = parts[0] * 60 + parts[1]
        return seconds
    except (ValueError, IndexError):
        return 0 # Return 0 if format is unexpected

def _from_seconds_to_hhmmss(seconds):
    """Converts total seconds into HH:MM:SS format for FFmpeg."""
    s = int(seconds)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

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

def extract_audio(video_path, task_id):
    """Extracts audio from video and returns the path to the audio file."""
    progress_tracker[task_id]['message'] = 'Extracting audio...'
    progress_tracker[task_id]['progress'] = 26 # After download (25%)
    try:
        audio_path = video_path.with_suffix('.mp3')
        cmd = [
            'ffmpeg', '-i', str(video_path),
            '-q:a', '0', # best quality
            '-map', 'a',
            '-y', # overwrite
            str(audio_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            print(f"FFmpeg audio extraction error: {result.stderr}")
            return None
        progress_tracker[task_id]['message'] = 'Audio extracted.'
        progress_tracker[task_id]['progress'] = 30
        return audio_path
    except Exception as e:
        print(f"Error extracting audio: {e}")
        return None

def transcribe_audio_with_timestamps(audio_path, task_id, max_retries=3):
    """Transcribes audio using Gemini, handling language detection implicitly."""
    progress_tracker[task_id]['status'] = 'transcribing'
    progress_tracker[task_id]['progress'] = 35
    progress_tracker[task_id]['message'] = 'Preparing for transcription...'

    if not audio_path:
        progress_tracker[task_id]['status'] = 'error'
        progress_tracker[task_id]['message'] = 'Audio extraction failed.'
        return "Audio extraction failed.", "Error", False
    
    for attempt in range(max_retries):
        try:
            progress_tracker[task_id]['message'] = f'Uploading audio for transcription (Attempt {attempt+1}/{max_retries})...'
            with open(audio_path, "rb") as audio_file:
                audio_data = audio_file.read()
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')

            progress_tracker[task_id]['message'] = 'Transcribing with AI...'
            progress_tracker[task_id]['progress'] = 45

            prompt = """
            Transcribe the following audio. Include timestamps for each segment in [MM:SS] or [MM:SS.MS] format.
            If the spoken language is primarily Hindi, you MUST provide the transcription in Hinglish (Hindi written in the Roman/Latin alphabet).
            For all other languages, provide the transcription in English.
            At the very beginning of your response, you MUST indicate the detected language on a single line, like this:
            LANGUAGE: [Hinglish/English]

            Then, provide the full transcript. For example:

            LANGUAGE: Hinglish
            [00:05] Namaste, aaj hum baat karenge...
            [00:12] Ye bahut important topic hai...
            """

            response = gemini_model.generate_content([
                prompt,
                {
                    "mime_type": "audio/mp3",
                    "data": audio_base64
                }
            ])

            response_text = response.text
            
            # Determine language from response
            language = "English"
            is_hindi = False
            if response_text.lower().startswith("language: hinglish"):
                language = "Hinglish"
                is_hindi = True

            # Clean up the response to only include the transcript
            transcript = re.sub(r'LANGUAGE:.*?\n', '', response_text, count=1).strip()

            progress_tracker[task_id]['progress'] = 60
            progress_tracker[task_id]['message'] = 'Transcription completed'
            
            return transcript, language, is_hindi

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
        Analyze this transcript to find the 3 most viral-worthy clips for social media.

        Transcript:
        {transcript}

        For each clip, you must identify:
        1. A start timestamp (in MM:SS format)
        2. An end timestamp (in MM:SS format)
        3. A viral score (from 0-100) based on its potential to be engaging.
        4. A brief, compelling reason why the clip is viral-worthy.

        CRITICAL REQUIREMENTS:
        - Each clip's duration MUST be between 16 and 60 seconds.
        - Each clip MUST end at a natural stopping point (end of a sentence or a complete thought). Do NOT cut off a speaker mid-sentence.
        - Prioritize moments with strong emotional cues, surprising statements, or valuable insights.

        Respond in this exact format, with each field on a new line:
        CLIP1_START: [MM:SS]
        CLIP1_END: [MM:SS]
        CLIP1_SCORE: [score]
        CLIP1_REASON: [reason]

        CLIP2_START: [MM:SS]
        CLIP2_END: [MM:SS]
        CLIP2_SCORE: [score]
        CLIP2_REASON: [reason]

        CLIP3_START: [MM:SS]
        CLIP3_END: [MM:SS]
        CLIP3_SCORE: [score]
        CLIP3_REASON: [reason]
        """
        
        response = gemini_model.generate_content(analysis_prompt)
        response_text = response.text
        print(f"Gemini Analysis Response:\n---\n{response_text}\n---") # DEBUG
        
        clips = []
        for i in range(1, 4):
            start_match = re.search(f'CLIP{i}_START:\\s*\\[(.*?)\\]', response_text)
            end_match = re.search(f'CLIP{i}_END:\\s*\\[(.*?)\\]', response_text)
            score_match = re.search(f'CLIP{i}_SCORE:\\s*\\[(\\d+)\\]', response_text)
            # Use a non-greedy match that stops at the next CLIP or end of string
            reason_match = re.search(f'CLIP{i}_REASON:\\s*(.*?)(?=\\nCLIP|\\Z)', response_text, re.DOTALL)
            
            if start_match and end_match and score_match:
                start_s = _to_seconds(start_match.group(1).strip())
                end_s = _to_seconds(end_match.group(1).strip())

                if start_s < end_s and 16 <= (end_s - start_s) <= 60:
                    score = int(score_match.group(1))
                    reason = reason_match.group(1).strip() if reason_match else f"Clip {i} selected for engagement"
                    clips.append({
                        'start_time': _from_seconds_to_hhmmss(start_s),
                        'end_time': _from_seconds_to_hhmmss(end_s),
                        'score': score,
                        'reason': reason
                    })

        # If AI fails, use the new intelligent fallback
        if len(clips) < 3:
            print(f"AI returned only {len(clips)} valid clips. Using intelligent fallback.")
            fallback_clips = find_best_segments_from_transcript(transcript, video_duration, num_clips=3 - len(clips))
            clips.extend(fallback_clips)

        progress_tracker[task_id]['progress'] = 80
        progress_tracker[task_id]['message'] = 'Clip analysis completed'
        
        return clips[:3]
            
    except Exception as e:
        print(f"Error analyzing script: {e}. Using intelligent fallback.")
        progress_tracker[task_id]['message'] = 'Analysis failed, using intelligent fallback'
        return find_best_segments_from_transcript(transcript, video_duration, num_clips=3)

def find_best_segments_from_transcript(transcript, video_duration, num_clips=3):
    """A smarter fallback that finds good segments from the transcript."""
    lines = transcript.strip().split('\n')
    
    segments = []
    for line in lines:
        match = re.match(r'\[(.*?)\]\s*(.*)', line)
        if match:
            timestamp_str, text = match.groups()
            start_s = _to_seconds(timestamp_str)
            segments.append({'start': start_s, 'text': text.strip()})
    
    if not segments:
        return []

    # Calculate end times based on the next segment's start
    for i in range(len(segments) - 1):
        segments[i]['end'] = segments[i+1]['start']
    if segments:
        segments[-1]['end'] = min(segments[-1]['start'] + 10, video_duration) # End of last segment

    # Group segments into coherent passages based on punctuation
    passages = []
    current_passage = []
    for seg in segments:
        current_passage.append(seg)
        if seg['text'].endswith(('.', '?', '!')) and len(current_passage) > 0:
            passage_text = ' '.join([p['text'] for p in current_passage])
            start_time = current_passage[0]['start']
            end_time = current_passage[-1]['end']
            duration = end_time - start_time
            
            if 16 <= duration <= 60:
                passages.append({
                    'text': passage_text,
                    'start': start_time,
                    'end': end_time,
                    'duration': duration
                })
            current_passage = []

    # Score passages to find the best ones
    scored_passages = []
    for passage in passages:
        score = 50  # Base score for any valid fallback
        # Add points for ideal duration (25-45s)
        if 25 <= passage['duration'] <= 45:
            score += 15
        # Add points for length of text
        score += min(10, len(passage['text']) // 20) # 1 point per 20 chars, max 10
        # Add points for questions
        if '?' in passage['text']:
            score += 5
        scored_passages.append({'passage': passage, 'score': score})
    
    # Sort by score and pick top non-overlapping clips
    scored_passages.sort(key=lambda x: x['score'], reverse=True)
    
    final_clips = []
    used_times = []

    for item in scored_passages:
        if len(final_clips) >= num_clips:
            break
        
        start_t = item['passage']['start']
        end_t = item['passage']['end']
        
        is_overlapping = any(max(start_t, s) < min(end_t, e) for s, e in used_times)
        
        if not is_overlapping:
            final_clips.append({
                'start_time': _from_seconds_to_hhmmss(start_t),
                'end_time': _from_seconds_to_hhmmss(end_t),
                'score': item['score'],
                'reason': 'Intelligent fallback: A coherent segment was selected from the transcript.'
            })
            used_times.append((start_t, end_t))
            
    return final_clips

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
            '-vf', 'crop=ih*9/16:ih,scale=1080:1920,setsar=1',  # Crop, scale, and set SAR
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-preset', 'fast',
            '-crf', '23',
            '-y',  # Overwrite output file
            str(output_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        
        if result.returncode == 0:
            return output_path
        else:
            print(f"FFmpeg error for {output_filename}: {result.stderr}")
            return None
            
    except Exception as e:
        print(f"Error creating vertical clip for {output_filename}: {e}")
        return None

def process_video_task(url, task_id):
    """Process video in background thread."""
    video_path = None
    audio_path = None
    try:
        # Download video
        video_path = download_youtube_video(url, OUTPUT_DIR, task_id)
        if not video_path:
             progress_tracker[task_id]['status'] = 'error'
             progress_tracker[task_id]['message'] = 'Failed to download video.'
             return

        # Extract audio
        audio_path = extract_audio(video_path, task_id)
        if not audio_path:
            progress_tracker[task_id]['status'] = 'error'
            progress_tracker[task_id]['message'] = 'Failed to extract audio.'
            return

        # Get video info for title and ID
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            video_title = info.get('title', 'Unknown Video')
            video_id = info.get('id', 'unknown')
            video_duration = info.get('duration', 0)
        
        # Detect language and transcribe with timestamps
        transcript, language, is_hindi = transcribe_audio_with_timestamps(audio_path, task_id)
        
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
                        'filename': clip_filename,
                        'processed': True
                    })
                else:
                    # If clip creation failed, add a placeholder.
                    print(f"Warning: Failed to create clip {i+1}, adding placeholder.")
                    created_clips.append({
                        'start_time': clip['start_time'],
                        'end_time': clip['end_time'],
                        'score': clip['score'],
                        'reason': clip['reason'] + " (Processing failed)",
                        'filename': None,
                        'processed': False
                    })
                
                # Update progress for each clip
                progress = 85 + ((i + 1) / 3) * 15
                progress_tracker[task_id]['progress'] = min(99, progress)
                progress_tracker[task_id]['message'] = f'Created clip {i + 1}/3...'
            
            print(f"Final clips generated: {len(created_clips)}")
            progress_tracker[task_id]['progress'] = 100
            progress_tracker[task_id]['status'] = 'completed'
            progress_tracker[task_id]['message'] = 'All clips created successfully!'
            progress_tracker[task_id]['result'] = {
                'clips': created_clips,
                'video_title': video_title
            }
        else:
            progress_tracker[task_id]['status'] = 'error'
            progress_tracker[task_id]['message'] = transcript if transcript else 'Transcription failed'
            
    except Exception as e:
        progress_tracker[task_id]['status'] = 'error'
        progress_tracker[task_id]['message'] = f'An unexpected error occurred: {str(e)}'
        print(f"Error in process_video_task: {e}")
    finally:
        # Clean up the original downloaded video and audio files
        if video_path and video_path.exists():
            try:
                os.remove(video_path)
                print(f"Cleaned up original video: {video_path}")
            except OSError as e:
                print(f"Error removing original video file {video_path}: {e}")
        if audio_path and audio_path.exists():
            try:
                os.remove(audio_path)
                print(f"Cleaned up temporary audio file: {audio_path}")
            except OSError as e:
                print(f"Error removing audio file {audio_path}: {e}")

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
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
        Your task is to act as an expert social media video editor. Analyze the following transcript and identify the 3 best clips that have the highest potential to go viral.

        Transcript:
        {transcript}

        For each clip, provide:
        1. Start Timestamp (MM:SS)
        2. End Timestamp (MM:SS)
        3. Viral Score (0-100): An estimate of its viral potential.
        4. Reason: A compelling, one-sentence explanation of why this clip is viral-worthy.

        --- CRITICAL SELECTION CRITERIA ---
        1.  **Duration:** Each clip MUST be between 15 and 70 seconds.
        2.  **Narrative Arc:** Each clip must feel like a complete story or a self-contained thought. It should have a clear beginning (a hook), a middle (the substance), and an end (a conclusion or punchline).
        3.  **DO NOT CUT OFF SENTENCES:** Clips must end at a natural pause or the end of a thought. A clip ending mid-sentence is an automatic failure.
        4.  **Content Quality:** Prioritize moments of high emotion, humor, controversy, strong opinions, or "aha!" moments. Look for the core message or the most impactful statement in the video.

        Respond in this exact format:
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
            reason_match = re.search(f'CLIP{i}_REASON:\\s*(.*?)(?=\\nCLIP|\\Z)', response_text, re.DOTALL)
            if start_match and end_match and score_match:
                start_s = _to_seconds(start_match.group(1).strip())
                end_s = _to_seconds(end_match.group(1).strip())
                if start_s < end_s and 15 <= (end_s - start_s) <= 70:
                    score = int(score_match.group(1))
                    reason = reason_match.group(1).strip() if reason_match else f"Clip {i} selected for engagement"
                    clips.append({
                        'start_time': _from_seconds_to_hhmmss(start_s),
                        'end_time': _from_seconds_to_hhmmss(end_s),
                        'score': score,
                        'reason': reason
                    })
        print(f"AI returned {len(clips)} valid clips.")
        if len(clips) < 3:
            print(f"Falling back to transcript-based segmenting. Need {3-len(clips)} more.")
            fallback_clips = find_best_segments_from_transcript(transcript, video_duration, num_clips=3 - len(clips))
            print(f"Fallback produced {len(fallback_clips)} clips.")
            # For fallback, do not assign a static score, mark as 'AI unavailable'
            for fc in fallback_clips:
                fc['score'] = 'AI unavailable'
                fc['reason'] = fc.get('reason', '') + ' (AI viral score unavailable)'
            clips.extend(fallback_clips)
        print(f"Total clips returned: {len(clips)}")
        progress_tracker[task_id]['progress'] = 80
        progress_tracker[task_id]['message'] = 'Clip analysis completed'
        # Always return 3 clips, fill with placeholders if needed
        while len(clips) < 3:
            clips.append({
                'start_time': '--:--',
                'end_time': '--:--',
                'score': 'No score',
                'reason': 'No clip found',
                'filename': None,
                'processed': False
            })
        return clips[:3]
    except Exception as e:
        print(f"Error analyzing script: {e}. Using intelligent fallback.")
        progress_tracker[task_id]['message'] = 'Analysis failed, using intelligent fallback'
        fallback_clips = find_best_segments_from_transcript(transcript, video_duration, num_clips=3)
        print(f"Fallback produced {len(fallback_clips)} clips.")
        for fc in fallback_clips:
            fc['score'] = 'AI unavailable'
            fc['reason'] = fc.get('reason', '') + ' (AI viral score unavailable)'
        # Always return 3 clips, fill with placeholders if needed
        while len(fallback_clips) < 3:
            fallback_clips.append({
                'start_time': '--:--',
                'end_time': '--:--',
                'score': 'No score',
                'reason': 'No clip found',
                'filename': None,
                'processed': False
            })
        return fallback_clips[:3]

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
    for i in range(len(segments) - 1):
        segments[i]['end'] = segments[i+1]['start']
    if segments:
        segments[-1]['end'] = min(segments[-1]['start'] + 10, video_duration)
    passages = []
    current_passage = []
    for seg in segments:
        current_passage.append(seg)
        if seg['text'].endswith(('.', '?', '!')) and len(current_passage) > 0:
            passage_text = ' '.join([p['text'] for p in current_passage])
            start_time = current_passage[0]['start']
            end_time = current_passage[-1]['end']
            duration = end_time - start_time
            if 15 <= duration <= 70:
                passages.append({
                    'text': passage_text,
                    'start': start_time,
                    'end': end_time,
                    'duration': duration
                })
            current_passage = []
    if not passages:
        print("No punctuation-based passages found, creating time-based fallback chunks.")
        for i in range(5):
            start_s = (i * (video_duration / 5)) + 5
            end_s = start_s + 30
            if end_s < video_duration:
                 passages.append({
                    'text': "Segment selected by time.",
                    'start': start_s,
                    'end': end_s,
                    'duration': end_s - start_s
                })
    scored_passages = []
    for passage in passages:
        score = 40
        duration = passage['duration']
        if 25 <= duration <= 60:
            score += 20
        elif 15 <= duration < 25:
            score += 5
        score += min(15, len(passage['text']) // 20)
        if '?' in passage['text']: score += 10
        if any(keyword in passage['text'].lower() for keyword in ['because', 'secret', 'finally', 'imagine']): score += 5
        scored_passages.append({'passage': passage, 'score': score})
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
                'score': min(item['score'], 99),
                'reason': 'Intelligent fallback: A coherent segment was selected from the transcript.'
            })
            used_times.append((start_t, end_t))
    # If not enough, relax duration requirement for last clips
    if len(final_clips) < num_clips:
        print(f"Relaxing duration requirement to fill {num_clips - len(final_clips)} more clips.")
        # Try to add shorter or longer passages
        for passage in passages:
            if len(final_clips) >= num_clips:
                break
            start_t = passage['start']
            end_t = passage['end']
            is_overlapping = any(max(start_t, s) < min(end_t, e) for s, e in used_times)
            if not is_overlapping:
                final_clips.append({
                    'start_time': _from_seconds_to_hhmmss(start_t),
                    'end_time': _from_seconds_to_hhmmss(end_t),
                    'score': 30,
                    'reason': 'Relaxed fallback: Segment from transcript.'
                })
                used_times.append((start_t, end_t))
    print(f"Fallback returning {len(final_clips)} clips.")
    return final_clips

def create_vertical_clip(input_video_path, start_time, end_time, output_filename, task_id):
    """Create a 9:16 vertical clip from the original video. If FFmpeg fails, try a shorter fallback segment."""
    try:
        output_path = OUTPUT_DIR / output_filename
        # FFmpeg command to create 9:16 vertical clip
        cmd = [
            'ffmpeg', '-i', str(input_video_path),
            '-ss', start_time,
            '-to', end_time,
            '-vf', 'crop=ih*9/16:ih,scale=1080:1920,setsar=1',
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-preset', 'fast',
            '-crf', '23',
            '-y',
            str(output_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return output_path, None
        else:
            # Try fallback: 20s segment from start_time
            start_sec = _to_seconds(start_time)
            end_sec = _to_seconds(end_time)
            fallback_end = start_sec + 20
            if fallback_end < end_sec:
                fallback_end_str = _from_seconds_to_hhmmss(fallback_end)
                fallback_cmd = [
                    'ffmpeg', '-i', str(input_video_path),
                    '-ss', start_time,
                    '-to', fallback_end_str,
                    '-vf', 'crop=ih*9/16:ih,scale=1080:1920,setsar=1',
                    '-c:v', 'libx264',
                    '-c:a', 'aac',
                    '-preset', 'fast',
                    '-crf', '23',
                    '-y',
                    str(output_path)
                ]
                fallback_result = subprocess.run(fallback_cmd, capture_output=True, text=True, check=False)
                if fallback_result.returncode == 0:
                    return output_path, f"FFmpeg failed for full segment, fallback 20s segment used. FFmpeg error: {result.stderr.strip()}"
            return None, f"FFmpeg error: {result.stderr.strip()}"
    except Exception as e:
        return None, f"Error creating vertical clip: {e}"

def process_video_task(url, task_id, clip_mode, start_time=None, end_time=None):
    """Process video in background thread for either AI or manual clipping."""
    video_path = None
    audio_path = None
    try:
        # Step 1: Get video info first to check duration
        progress_tracker[task_id]['status'] = 'validating'
        progress_tracker[task_id]['progress'] = 0 # Start at 0 to prevent flicker
        progress_tracker[task_id]['message'] = 'Analyzing video link...'
        
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            video_duration = info.get('duration', 0)
            video_title = info.get('title', 'Unknown Video')
            video_id = info.get('id', 'unknown')

        if video_duration > 3600: # 1 hour limit
            progress_tracker[task_id]['status'] = 'error'
            progress_tracker[task_id]['message'] = 'Error: Video is longer than 1 hour and cannot be processed.'
            return

        # Step 2: Download the video
        video_path = download_youtube_video(url, OUTPUT_DIR, task_id)
        if not video_path:
             progress_tracker[task_id]['status'] = 'error'
             progress_tracker[task_id]['message'] = 'Failed to download video.'
             return

        # --- AI Clipping Logic ---
        if clip_mode == 'ai':
            # Extract audio
            audio_path = extract_audio(video_path, task_id)
            if not audio_path:
                progress_tracker[task_id]['status'] = 'error'
                progress_tracker[task_id]['message'] = 'Failed to extract audio.'
                return
            
            # Transcribe
            transcript, language, is_hindi = transcribe_audio_with_timestamps(audio_path, task_id)
            
            # Analyze and get clips
            if transcript and not transcript.startswith("Transcription error"):
                clips = analyze_script_and_find_three_clips(transcript, video_duration, task_id)
                
                progress_tracker[task_id]['status'] = 'clipping'
                progress_tracker[task_id]['progress'] = 85
                progress_tracker[task_id]['message'] = 'Creating AI-powered clips...'
                
                created_clips = []
                for i, clip in enumerate(clips):
                    clip_filename = f"{video_id}_{i+1}_AI_clip.mp4"
                    clip_path, ffmpeg_error = create_vertical_clip(video_path, clip['start_time'], clip['end_time'], clip_filename, task_id)
                    if clip_path:
                        clip['filename'] = clip_filename
                        clip['processed'] = True
                        if ffmpeg_error:
                            clip['reason'] += f" (Partial fallback: {ffmpeg_error})"
                        created_clips.append(clip)
                    else:
                        clip['filename'] = None
                        clip['processed'] = False
                        clip['reason'] += f" (Clip failed: {ffmpeg_error})"
                        created_clips.append(clip)
                
                progress_tracker[task_id]['result'] = {'clips': created_clips, 'video_title': video_title, 'original_video': video_path.name}
            else:
                progress_tracker[task_id]['status'] = 'error'
                progress_tracker[task_id]['message'] = transcript if transcript else 'Transcription failed'
                return

        # --- Manual Clipping Logic ---
        elif clip_mode == 'manual':
            progress_tracker[task_id]['status'] = 'clipping'
            progress_tracker[task_id]['progress'] = 50
            progress_tracker[task_id]['message'] = 'Creating your manual clip...'
            
            # Normalize timestamps
            start_s = _from_seconds_to_hhmmss(_to_seconds(start_time))
            end_s = _from_seconds_to_hhmmss(_to_seconds(end_time))
            
            clip_filename = f"{video_id}_manual_clip.mp4"
            clip_path, ffmpeg_error = create_vertical_clip(video_path, start_s, end_s, clip_filename, task_id)
            
            if clip_path:
                manual_clip = {
                    'start_time': start_s,
                    'end_time': end_s,
                    'score': 'Manual',
                    'reason': 'Manually selected time range.',
                    'filename': clip_filename,
                    'processed': True,
                }
                if ffmpeg_error:
                    manual_clip['reason'] += f" (Clip failed: {ffmpeg_error})"
                progress_tracker[task_id]['result'] = {'clips': [manual_clip], 'video_title': video_title}
            else:
                progress_tracker[task_id]['status'] = 'error'
                progress_tracker[task_id]['message'] = 'Failed to create manual clip.'
                return

        progress_tracker[task_id]['progress'] = 100
        progress_tracker[task_id]['status'] = 'completed'
        progress_tracker[task_id]['message'] = 'Your clips are ready!'

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
        clip_mode = request.form.get('clip_mode', 'ai')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')

        if not url:
            return jsonify({'error': 'Please provide a YouTube link.'})
        
        # Generate unique task ID
        task_id = str(uuid.uuid4())
        progress_tracker[task_id] = {
            'status': 'starting',
            'progress': 0,
            'message': 'Initializing...',
            'result': None,
            'start_time': time.time()
        }
        
        # Start background processing
        thread = threading.Thread(target=process_video_task, args=(url, task_id, clip_mode, start_time, end_time))
        thread.daemon = True
        thread.start()
        
        return jsonify({'task_id': task_id})
    
    return render_template('index.html')

@app.route('/progress/<task_id>')
def get_progress(task_id):
    """Get progress for a specific task."""
    if task_id in progress_tracker:
        progress_data = progress_tracker[task_id]
        
        # Calculate ETA
        progress = progress_data.get('progress', 0)
        start_time = progress_data.get('start_time')
        eta_seconds = None
        
        if start_time and progress > 5 and progress < 99: # Only show between 5% and 99%
            elapsed = time.time() - start_time
            # Avoid division by zero
            if progress > 0:
                total_time = (elapsed / progress) * 100
                eta_seconds = total_time - elapsed
        
        response_data = progress_data.copy()
        response_data['eta'] = eta_seconds
        return jsonify(response_data)
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
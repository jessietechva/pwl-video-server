from flask import Flask, request, jsonify
import subprocess
import os
import requests
import tempfile
import uuid

app = Flask(__name__)

def download_file(url, dest_path):
    """Download a file from URL to dest_path."""
    r = requests.get(url, stream=True, timeout=60)
    r.raise_for_status()
    with open(dest_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)

@app.route('/assemble', methods=['POST'])
def assemble_video():
    """
    Expects JSON body:
    {
        "audio_url": "https://...",        # URL to MP3 audio file from Google Drive
        "video_urls": ["https://...", ...], # List of Pexels video clip URLs
        "topic": "How to invest your first $100"
    }
    Returns:
    {
        "success": true,
        "video_url": "https://..."         # Public URL to assembled MP4
    }
    """
    data = request.json
    audio_url = data.get('audio_url')
    video_urls = data.get('video_urls', [])
    topic = data.get('topic', 'video')

    if not audio_url or not video_urls:
        return jsonify({"success": False, "error": "Missing audio_url or video_urls"}), 400

    # Create temp working directory
    work_dir = tempfile.mkdtemp()
    job_id = str(uuid.uuid4())[:8]

    try:
        # Download audio file
        audio_path = os.path.join(work_dir, 'audio.mp3')
        download_file(audio_url, audio_path)

        # Get audio duration
        result = subprocess.run([
            'ffprobe', '-v', 'error', '-show_entries',
            'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1',
            audio_path
        ], capture_output=True, text=True)
        audio_duration = float(result.stdout.strip())

        # Download video clips
        clip_paths = []
        for i, url in enumerate(video_urls[:5]):  # max 5 clips
            clip_path = os.path.join(work_dir, f'clip_{i}.mp4')
            try:
                download_file(url, clip_path)
                clip_paths.append(clip_path)
            except Exception:
                continue

        if not clip_paths:
            return jsonify({"success": False, "error": "Could not download any video clips"}), 400

        # Create concat file — loop clips to fill audio duration
        concat_file = os.path.join(work_dir, 'concat.txt')
        clip_duration_each = audio_duration / len(clip_paths)

        with open(concat_file, 'w') as f:
            for clip_path in clip_paths:
                f.write(f"file '{clip_path}'\n")

        # Concatenate video clips
        concat_output = os.path.join(work_dir, 'concat_video.mp4')
        subprocess.run([
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-i', concat_file,
            '-c', 'copy',
            concat_output
        ], check=True, capture_output=True)

        # Combine concatenated video with audio
        output_path = os.path.join(work_dir, f'pwl_{job_id}.mp4')
        subprocess.run([
            'ffmpeg', '-y',
            '-stream_loop', '-1', '-i', concat_output,  # loop video
            '-i', audio_path,
            '-map', '0:v:0',
            '-map', '1:a:0',
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-shortest',                                  # stop at audio end
            '-vf', 'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2',
            '-r', '30',
            output_path
        ], check=True, capture_output=True)

        # Upload to file.io for temporary public URL (free, no signup)
        with open(output_path, 'rb') as f:
            upload_response = requests.post(
                'https://file.io/?expires=1d',
                files={'file': (f'pwl_{job_id}.mp4', f, 'video/mp4')}
            )

        upload_data = upload_response.json()
        if upload_data.get('success'):
            return jsonify({
                "success": True,
                "video_url": upload_data['link'],
                "topic": topic,
                "job_id": job_id
            })
        else:
            return jsonify({"success": False, "error": "Upload failed"}), 500

    except subprocess.CalledProcessError as e:
        return jsonify({"success": False, "error": f"FFmpeg error: {e.stderr.decode()}"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "Passive Wealth Lab Video Server"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

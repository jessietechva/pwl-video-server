from flask import Flask, request, jsonify
import subprocess, os, requests, tempfile, uuid

app = Flask(__name__)

def download_file(url, dest_path):
    r = requests.get(url, stream=True, timeout=60)
    r.raise_for_status()
    with open(dest_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)

@app.route('/')
def index():
    return 'PWL Video Server running!'

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/assemble', methods=['POST'])
def assemble_video():
    data = request.json
    voicerss_key = data.get('voicerss_key')
    voicerss_text = data.get('voicerss_text', '')
    video_urls = data.get('video_urls', [])
    topic = data.get('topic', 'video')

    if not voicerss_key or not voicerss_text or not video_urls:
        return jsonify({"success": False, "error": "Missing required fields"}), 400

    work_dir = tempfile.mkdtemp()
    job_id = str(uuid.uuid4())[:8]

    try:
        audio_path = os.path.join(work_dir, 'audio.mp3')
        tts = requests.post('https://api.voicerss.org/', data={
            'key': voicerss_key,
            'hl': 'en-us',
            'v': 'John',
            'src': voicerss_text[:3000],
            'f': '44khz_16bit_stereo',
            'c': 'MP3'
        }, timeout=60)
        with open(audio_path, 'wb') as f:
            f.write(tts.content)

        probe = subprocess.run([
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', audio_path
        ], capture_output=True, text=True)
        audio_duration = float(probe.stdout.strip())

        clip_paths = []
        for i, url in enumerate(video_urls[:5]):
            cp = os.path.join(work_dir, 'clip' + str(i) + '.mp4')
            try:
                download_file(url, cp)
                clip_paths.append(cp)
            except Exception:
                continue

        if not clip_paths:
            return jsonify({"success": False, "error": "No clips downloaded"}), 400

        concat_file = os.path.join(work_dir, 'concat.txt')
        with open(concat_file, 'w') as f:
            for cp in clip_paths:
                f.write("file '" + cp + "'\n")

        concat_out = os.path.join(work_dir, 'concat.mp4')
        subprocess.run([
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-i', concat_file, '-c', 'copy', concat_out
        ], check=True, capture_output=True)

        output_path = os.path.join(work_dir, 'pwl' + job_id + '.mp4')
        subprocess.run([
            'ffmpeg', '-y',
            '-stream_loop', '-1', '-i', concat_out,
            '-i', audio_path,
            '-map', '0:v:0', '-map', '1:a:0',
            '-c:v', 'libx264', '-c:a', 'aac',
            '-shortest', '-r', '30', output_path
        ], check=True, capture_output=True)

        with open(output_path, 'rb') as f:
            up = requests.post('https://file.io/?expires=1d',
                files={'file': ('video.mp4', f, 'video/mp4')})

        ud = up.json()
        if ud.get('success'):
            return jsonify({"success": True, "video_url": ud['link'], "topic": topic})
        else:
            return jsonify({"success": False, "error": "Upload failed"}), 500

    except subprocess.CalledProcessError as e:
        return jsonify({"success": False, "error": "FFmpeg error"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

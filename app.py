from flask import Flask, request, jsonify
import subprocess, os, requests, tempfile, uuid

app = Flask(__name__)

def download_file(url, dest_path):
    r = requests.get(url, stream=True, timeout=120)
    r.raise_for_status()
    with open(dest_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)

@app.route('/')
def index():
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        return 'FFmpeg OK: ' + result.stdout[:100]
    except Exception as e:
        return 'FFmpeg not found: ' + str(e)

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

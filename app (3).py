from flask import Flask, request, jsonify
import subprocess
import os
import requests
import tempfile
import uuid

app = Flask(__name__)


@app.route('/')
def index():
    return 'PWL Video Server running!'


@app.route('/health')
def health():
    return jsonify({"status": "ok"})


@app.route('/assemble', methods=['POST'])
def assemble_video():
    data = request.json
    voicerss_key = data.get('voicerss_key', '')
    voicerss_text = data.get('voicerss_text', '')
    video_urls = data.get('video_urls', [])
    topic = data.get('topic', 'video')

    if not voicerss_key or not voicerss_text or not video_urls:
        return jsonify({"success": False, "error": "Missing required fields"}), 400

    work_dir = tempfile.mkdtemp()
    job_id = str(uuid.uuid4())[:8]
    audio_path = os.path.join(work_dir, 'audio.mp3')
    output_path = os.path.join(work_dir, 'output.mp4')
    concat_file = os.path.join(work_dir, 'concat.txt')
    concat_out = os.path.join(work_dir, 'concat.mp4')

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
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        audio_path
    ], capture_output=True, text=True)

    if not probe.stdout.strip():
        return jsonify({"success": False, "error": "Audio failed: " + tts.text[:100]}), 400

    clips_downloaded = []
    for idx in range(len(video_urls)):
        url = video_urls[idx]
        cp = os.path.join(work_dir, 'clip' + str(idx) + '.mp4')
        r = requests.get(url, stream=True, timeout=120, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 200:
            with open(cp, 'wb') as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            if os.path.getsize(cp) > 10000:
                clips_downloaded.append(cp)

    if not clips_downloaded:
        return jsonify({"success": False, "error": "No clips downloaded"}), 400

    with open(concat_file, 'w') as f:
        for cp in clips_downloaded:
            f.write("file '" + cp + "'\n")

    subprocess.run([
        'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
        '-i', concat_file, '-c', 'copy', concat_out
    ], capture_output=True)

    subprocess.run([
        'ffmpeg', '-y',
        '-stream_loop', '-1', '-i', concat_out,
        '-i', audio_path,
        '-map', '0:v:0',
        '-map', '1:a:0',
        '-c:v', 'libx264',
        '-c:a', 'aac',
        '-shortest',
        '-r', '30',
        output_path
    ], capture_output=True)

    with open(output_path, 'rb') as f:
        up = requests.post(
            'https://file.io/?expires=1d',
            files={'file': ('video.mp4', f, 'video/mp4')}
        )

    ud = up.json()
    if ud.get('success'):
        return jsonify({"success": True, "video_url": ud['link'], "topic": topic})

    return jsonify({"success": False, "error": "Upload failed"}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

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


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})


@app.route('/test-ffmpeg', methods=['GET'])
def test_ffmpeg():
    result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
    return result.stdout[:200]


@app.route('/assemble', methods=['POST'])
def assemble_video():
    data = request.json
    if not data:
        return jsonify({"success": False, "error": "No data received"}), 400
    return jsonify({"success": True, "received": list(data.keys())})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

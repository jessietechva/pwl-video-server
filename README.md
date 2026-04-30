# PWL Video Server — Deployment Guide

## What this does
This server receives audio + video clip URLs from Make.com,
stitches them together using FFmpeg, and returns a public MP4 URL
that Make.com can upload to YouTube.

## Deploy to Render.com (Free)

### Step 1 — Upload to GitHub
1. Create a free account at github.com
2. Create a new repository called "pwl-video-server"
3. Upload all 3 files: app.py, requirements.txt, render.yaml

### Step 2 — Deploy on Render.com
1. Go to render.com and sign up free
2. Click "New" → "Web Service"
3. Connect your GitHub account
4. Select the "pwl-video-server" repository
5. Render will auto-detect the render.yaml config
6. Click "Create Web Service"
7. Wait ~5 minutes for deployment

### Step 3 — Get your server URL
After deployment, Render gives you a URL like:
https://pwl-video-server.onrender.com

### Step 4 — Add to Make.com
Add a new HTTP module BEFORE the YouTube upload module:
- URL: https://pwl-video-server.onrender.com/assemble
- Method: POST
- Body:
{
  "audio_url": "{{6.webViewLink}}",
  "video_urls": ["{{7.videos[0].video_files[0].link}}", "{{7.videos[1].video_files[0].link}}"],
  "topic": "{{1.Topic}}"
}

Then update the YouTube module to use the returned video_url
instead of the MP3 file.

## API Endpoints
- GET /health — Check if server is running
- POST /assemble — Assemble video from audio + clips

# 👻 Subtitle Generator

Upload a video, pick a language, and get auto-generated, translated subtitles (SRT + WebVTT) — with an in-browser player that shows them live.

## Features
- Extracts audio from any uploaded video using **ffmpeg**
- Transcribes speech with **OpenAI Whisper** (`tiny` model)
- Translates each subtitle segment into 100+ languages via **deep-translator** (Google Translate backend)
- Outputs both `.srt` (downloadable) and `.vtt` (for in-browser playback)
- Watch the video with live subtitles burned in via the HTML5 `<track>` element

## Tech Stack
- **Backend:** Flask (Python)
- **Speech-to-text:** OpenAI Whisper
- **Translation:** deep-translator
- **Audio extraction:** ffmpeg
- **Frontend:** vanilla HTML/CSS/JS

## Setup

```bash
# clone the repo
git clone <your-repo-url>
cd <repo-folder>

# create and activate a virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# install dependencies
pip install -r requirements.txt

# make sure ffmpeg is installed and on your PATH
# macOS: brew install ffmpeg
# Ubuntu: sudo apt install ffmpeg
# Windows: download from ffmpeg.org and add to PATH

# run the app
python app.py
```

Visit `http://127.0.0.1:5000` in your browser.

## How it works
1. Upload a video and select a target language
2. Server extracts audio (`ffmpeg`) → transcribes it (`Whisper`) → translates each segment (`deep-translator`)
3. Subtitles are written as both `.srt` and `.vtt`
4. Download the `.srt`, or watch the video in-browser with subtitles overlaid

## Note
- Whisper's `tiny` model is used for speed; swap to `base`/`small`/`medium` in `app.py` for better accuracy at the cost of speed
- Uploaded videos and generated subtitle files are stored locally in `uploads/` and `outputs/` (not committed to git)
- Transcription runs on CPU by default, so processing can take a few minutes depending on video length — this is expected, not a bug. For faster testing, try a short clip (under 30 seconds).
  
## Possible improvements
- Progress indicator during transcription (currently just a loading animation)
- Support for multiple concurrent users (currently single global video state)
- Batch translation instead of per-segment API calls for speed

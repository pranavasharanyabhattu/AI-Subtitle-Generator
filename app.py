from flask import Flask, render_template, request, send_file
from werkzeug.utils import secure_filename
from deep_translator import GoogleTranslator
import whisper
import os
import subprocess
 
app = Flask(__name__)
 
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
OUTPUT_FOLDER = os.path.join(BASE_DIR, "outputs")
 
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
 
model = whisper.load_model("tiny")
 
LANGUAGE_MAP = {
    # A
    "Afrikaans":            "af",
    "Albanian":             "sq",
    "Amharic":              "am",
    "Arabic":               "ar",
    "Armenian":             "hy",
    "Azerbaijani":          "az",
    # B
    "Basque":               "eu",
    "Belarusian":           "be",
    "Bengali":              "bn",
    "Bosnian":              "bs",
    "Bulgarian":            "bg",
    # C
    "Catalan":              "ca",
    "Cebuano":              "ceb",
    "Chinese (Simplified)": "zh-CN",
    "Chinese (Traditional)":"zh-TW",
    "Corsican":             "co",
    "Croatian":             "hr",
    "Czech":                "cs",
    # D
    "Danish":               "da",
    "Dutch":                "nl",
    # E
    "English":              "en",
    "Esperanto":            "eo",
    "Estonian":             "et",
    # F
    "Finnish":              "fi",
    "French":               "fr",
    "Frisian":              "fy",
    # G
    "Galician":             "gl",
    "Georgian":             "ka",
    "German":               "de",
    "Greek":                "el",
    "Gujarati":             "gu",
    # H
    "Haitian Creole":       "ht",
    "Hausa":                "ha",
    "Hawaiian":             "haw",
    "Hebrew":               "iw",
    "Hindi":                "hi",
    "Hmong":                "hmn",
    "Hungarian":            "hu",
    # I
    "Icelandic":            "is",
    "Igbo":                 "ig",
    "Indonesian":           "id",
    "Irish":                "ga",
    "Italian":              "it",
    # J
    "Japanese":             "ja",
    "Javanese":             "jw",
    # K
    "Kannada":              "kn",
    "Kazakh":               "kk",
    "Khmer":                "km",
    "Kinyarwanda":          "rw",
    "Korean":               "ko",
    "Kurdish (Kurmanji)":   "ku",
    "Kyrgyz":               "ky",
    # L
    "Lao":                  "lo",
    "Latin":                "la",
    "Latvian":              "lv",
    "Lithuanian":           "lt",
    "Luxembourgish":        "lb",
    # M
    "Macedonian":           "mk",
    "Malagasy":             "mg",
    "Malay":                "ms",
    "Malayalam":            "ml",
    "Maltese":              "mt",
    "Maori":                "mi",
    "Marathi":              "mr",
    "Mongolian":            "mn",
    "Myanmar (Burmese)":    "my",
    # N
    "Nepali":               "ne",
    "Norwegian":            "no",
    # O
    "Odia (Oriya)":         "or",
    # P
    "Pashto":               "ps",
    "Persian":              "fa",
    "Polish":               "pl",
    "Portuguese":           "pt",
    "Punjabi":              "pa",
    # R
    "Romanian":             "ro",
    "Russian":              "ru",
    # S
    "Samoan":               "sm",
    "Scots Gaelic":         "gd",
    "Serbian":              "sr",
    "Sesotho":              "st",
    "Shona":                "sn",
    "Sindhi":               "sd",
    "Sinhala":              "si",
    "Slovak":               "sk",
    "Slovenian":            "sl",
    "Somali":               "so",
    "Spanish":              "es",
    "Sundanese":            "su",
    "Swahili":              "sw",
    "Swedish":              "sv",
    # T
    "Tajik":                "tg",
    "Tamil":                "ta",
    "Tatar":                "tt",
    "Telugu":               "te",
    "Thai":                 "th",
    "Turkish":              "tr",
    "Turkmen":              "tk",
    # U
    "Ukrainian":            "uk",
    "Urdu":                 "ur",
    "Uyghur":               "ug",
    "Uzbek":                "uz",
    # V
    "Vietnamese":           "vi",
    # W
    "Welsh":                "cy",
    # X
    "Xhosa":                "xh",
    # Y
    "Yiddish":              "yi",
    "Yoruba":               "yo",
    # Z
    "Zulu":                 "zu",
}
 
current_video_filename = None
 
 
def format_time(seconds):
    h  = int(seconds // 3600)
    m  = int((seconds % 3600) // 60)
    s  = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"
 
 
def translate_text(text, target_language_code):
    try:
        translated = GoogleTranslator(
            source="auto",
            target=target_language_code
        ).translate(text)
        return translated if translated else text
    except Exception:
        # if translation fails, return original text
        return text
 
 
@app.route('/')
def home():
    return render_template('index.html')
 
 
@app.route('/upload', methods=['POST'])
def upload():
    global current_video_filename
 
    if 'video' not in request.files:
        return "No video uploaded", 400
 
    video = request.files['video']
 
    if video.filename == "":
        return "No file selected", 400
 
    filename = secure_filename(video.filename)
    current_video_filename = filename
 
    video_path = os.path.join(UPLOAD_FOLDER, filename)
    video.save(video_path)
 
    audio_path = os.path.join(OUTPUT_FOLDER, "audio.wav")
 
    command = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-ar", "16000",
        "-ac", "1",
        audio_path
    ]
 
    result_ffmpeg = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
 
    if result_ffmpeg.returncode != 0 or not os.path.exists(audio_path):
        error_msg = result_ffmpeg.stderr.decode("utf-8", errors="ignore")
        return f"Audio extraction failed: {error_msg}", 500
 
    language_name = request.form.get("language", "English")
    language_code = LANGUAGE_MAP.get(language_name, "en")
 
    try:
        # always transcribe first in original spoken language
        result = model.transcribe(audio_path)
 
    except Exception as e:
        return f"Transcription error: {str(e)}", 500
 
    segments = result["segments"]
 
    if len(segments) == 0:
        return "No speech detected in video", 400
 
    srt_content = ""
    vtt_content = "WEBVTT\n\n"
 
    for i, segment in enumerate(segments):
        start = segment['start']
        end   = segment['end']
        text  = segment['text'].strip()
     
        translated_text = translate_text(text, language_code)
 
        
        srt_content += f"{i+1}\n"
        srt_content += f"{format_time(start)} --> {format_time(end)}\n"
        srt_content += f"{translated_text}\n\n"
 
        
        vtt_content += f"{format_time(start).replace(',', '.')} --> {format_time(end).replace(',', '.')}\n"
        vtt_content += f"{translated_text}\n\n"
 
    srt_path = os.path.join(OUTPUT_FOLDER, "subtitles.srt")
    vtt_path = os.path.join(OUTPUT_FOLDER, "subtitles.vtt")
 
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)
 
    with open(vtt_path, "w", encoding="utf-8") as f:
        f.write(vtt_content)
 
    if os.path.getsize(srt_path) == 0:
        return "Subtitle file is empty", 500
 
    return "success", 200
 
 
@app.route('/download')
def download():
    srt_path = os.path.join(OUTPUT_FOLDER, "subtitles.srt")
 
    if not os.path.exists(srt_path):
        return "No subtitles found. Please generate them first.", 404
 
    return send_file(srt_path, as_attachment=True)
 
 
@app.route('/video/<filename>')
def serve_video(filename):
    filename = secure_filename(filename)
    video_path = os.path.join(UPLOAD_FOLDER, filename)
 
    if not os.path.exists(video_path):
        return "Video not found", 404
 
    return send_file(video_path)
 
 
@app.route('/subtitles.vtt')
def serve_vtt():
    vtt_path = os.path.join(OUTPUT_FOLDER, "subtitles.vtt")
 
    if not os.path.exists(vtt_path):
        return "Subtitles not found", 404
 
    return send_file(vtt_path, mimetype="text/vtt")
 
 
@app.route('/watch')
def watch():
    if not current_video_filename:
        return "No video available. Please upload and generate subtitles first.", 404
 
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Watch Video</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                background: #0a0a0a;
                color: white;
                font-family: 'Courier New', monospace;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                padding: 40px 20px;
            }}
            h1 {{
                color: #ff7300;
                margin-bottom: 24px;
                font-size: 1.6rem;
            }}
            video {{
                width: 100%;
                max-width: 860px;
                border-radius: 16px;
                border: 2px solid #ff7300;
                box-shadow: 0 0 30px rgba(255,115,0,0.3);
            }}
            a {{
                margin-top: 24px;
                color: #ff7300;
                border: 2px solid #ff7300;
                padding: 10px 22px;
                border-radius: 10px;
                text-decoration: none;
                transition: 0.3s;
            }}
            a:hover {{
                background: #ff7300;
                color: black;
            }}
        </style>
    </head>
    <body>
        <h1>Watch Video 👻</h1>
        <video controls>
            <source src="/video/{current_video_filename}">
            <track
                kind="subtitles"
                src="/subtitles.vtt"
                srclang="en"
                label="Subtitles"
                default
            >
            Your browser does not support the video tag.
        </video>
        <a href="/">← Back to Generator</a>
    </body>
    </html>
    """
 
 
if __name__ == '__main__':
    app.run(debug=True)
 

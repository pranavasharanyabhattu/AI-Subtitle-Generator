import os
import re
import glob
import time
import uuid
import shutil
import threading
import subprocess

from flask import (
    Flask,
    jsonify,
    render_template,
    render_template_string,
    request,
    send_file,
)
from deep_translator import GoogleTranslator, MyMemoryTranslator
from deep_translator.constants import MY_MEMORY_LANGUAGES_TO_CODES
import whisper

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB upload limit

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
OUTPUT_FOLDER = os.path.join(BASE_DIR, "outputs")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
JOB_ID_RE = re.compile(r"^[0-9a-f]{32}$")
LANG_CODE_RE = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z]{2,4})?$")
JOB_MAX_AGE_SECONDS = 24 * 60 * 60  # old jobs are deleted after 24 hours

model = None
transcribe_lock = threading.Lock()  # one transcription at a time on the shared model

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


def format_time(seconds):
    total_ms = int(round(seconds * 1000))
    h, rest = divmod(total_ms, 3_600_000)
    m, rest = divmod(rest, 60_000)
    s, ms = divmod(rest, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def base_language(code):
    base = code.split("-")[0].lower()
    return "he" if base == "iw" else base


def mymemory_language_code(code, allow_auto=False):
    if allow_auto and (not code or code.lower() == "auto"):
        return "auto"

    normalized = base_language(code).lower()
    aliases = {"jw": "jv", "in": "id", "no": "nb"}
    normalized = aliases.get(normalized, normalized)
    supported_codes = list(MY_MEMORY_LANGUAGES_TO_CODES.values())
    if code in supported_codes:
        return code
    for supported_code in supported_codes:
        if supported_code.split("-")[0].lower() == normalized:
            return supported_code
    if allow_auto:
        return "auto"
    raise ValueError(f"MyMemory does not support language code {code!r}")


def translate_segments(texts, target_language_code, source_language_code="auto", max_batch_chars=4000):
    marker = "ZXQSUBTITLEBREAKZXQ"
    translated_texts = list(texts)
    failed = 0
    chunks = []
    fallback_indexes = []
    current_chunk = []
    current_size = 0

    for index, text in enumerate(texts):
        text = text.strip()
        extra_size = len(text) + (len(marker) if current_chunk else 0)
        if current_chunk and current_size + extra_size > max_batch_chars:
            chunks.append(current_chunk)
            current_chunk = []
            current_size = 0
            extra_size = len(text)
        current_chunk.append((index, text))
        current_size += extra_size
    if current_chunk:
        chunks.append(current_chunk)

    try:
        translator = GoogleTranslator(source="auto", target=target_language_code)
    except Exception as e:
        app.logger.warning("Could not initialize translator: %s", e)
        return translated_texts, len(texts)
    for chunk_number, chunk in enumerate(chunks):
        if chunk_number:
            time.sleep(1.1)
        indexes, lines = zip(*chunk)
        try:
            payload = f"\n{marker}\n".join(lines)
            result = translator.translate(payload)
            parts = result.split(marker) if result else []
            if len(parts) != len(lines):
                raise ValueError("The translation response did not preserve subtitle boundaries")
            for index, translated in zip(indexes, parts):
                translated_texts[index] = translated.strip() or texts[index].strip()
        except Exception as e:
            app.logger.warning("Translation batch failed: %s", e)
            fallback_indexes.extend(indexes)

    if fallback_indexes:
        try:
            fallback_translator = MyMemoryTranslator(
                source=mymemory_language_code(source_language_code, allow_auto=True),
                target=mymemory_language_code(target_language_code),
                email=os.environ.get("MYMEMORY_EMAIL"),
            )
        except Exception as e:
            app.logger.warning("Could not initialize MyMemory fallback: %s", e)
            fallback_translator = None

        consecutive_failures = 0
        quota_used_up = False
        for position, index in enumerate(fallback_indexes):
            original = texts[index].strip()
            if quota_used_up or consecutive_failures >= 5:
                failed += 1  # MyMemory is out of quota or down: don't keep hammering it
                continue
            if position:
                time.sleep(0.3)
            try:
                if len(original.encode("utf-8")) > 500:
                    raise ValueError("MyMemory accepts at most 500 bytes per subtitle line")
                result = fallback_translator.translate(original) if fallback_translator else None
                if result and "MYMEMORY WARNING" in result.upper():
                    quota_used_up = True  # it returns this text as if it were the translation
                    raise ValueError("MyMemory free quota used up")
                if result:
                    translated_texts[index] = result
                    consecutive_failures = 0
                else:
                    failed += 1
                    consecutive_failures += 1
            except Exception as e:
                failed += 1
                consecutive_failures += 1
                app.logger.warning("MyMemory fallback failed for subtitle line %d: %s", index + 1, e)

    return translated_texts, failed


def error_response(message, status):
    return jsonify({"error": message}), status


def job_paths(job_id):
    job_dir = os.path.join(OUTPUT_FOLDER, job_id)
    return {
        "dir": job_dir,
        "audio": os.path.join(job_dir, "audio.wav"),
        "srt": os.path.join(job_dir, "subtitles.srt"),
        "vtt": os.path.join(job_dir, "subtitles.vtt"),
        "lang": os.path.join(job_dir, "lang.txt"),
    }


def find_video(job_id):
    matches = glob.glob(os.path.join(UPLOAD_FOLDER, job_id + ".*"))
    return matches[0] if matches else None


def discard_job(job_id):
    shutil.rmtree(os.path.join(OUTPUT_FOLDER, job_id), ignore_errors=True)
    for path in glob.glob(os.path.join(UPLOAD_FOLDER, job_id + ".*")):
        try:
            os.remove(path)
        except OSError:
            pass


def cleanup_old_jobs():
    cutoff = time.time() - JOB_MAX_AGE_SECONDS
    try:
        for name in os.listdir(OUTPUT_FOLDER):
            path = os.path.join(OUTPUT_FOLDER, name)
            if JOB_ID_RE.match(name) and os.path.isdir(path) and os.path.getmtime(path) < cutoff:
                discard_job(name)
    except OSError as e:
        app.logger.warning("Cleanup failed: %s", e)


def valid_job_or_404(job_id):
    if not JOB_ID_RE.match(job_id):
        return None
    paths = job_paths(job_id)
    return paths if os.path.isdir(paths["dir"]) else None


@app.errorhandler(413)
def too_large(_e):
    return error_response("File is too large (maximum 500 MB).", 413)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    video = request.files.get("video")
    if video is None:
        return error_response("No video uploaded.", 400)
    if not video.filename:
        return error_response("No file selected.", 400)

    ext = os.path.splitext(video.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        return error_response(f"Unsupported file type. Please upload one of: {allowed}", 400)

    language_name = request.form.get("language", "English")
    language_code = LANGUAGE_MAP.get(language_name, "en")

    cleanup_old_jobs()

    job_id = uuid.uuid4().hex
    paths = job_paths(job_id)
    os.makedirs(paths["dir"])
    video_path = os.path.join(UPLOAD_FOLDER, job_id + ext)

    try:
        video.save(video_path)
        return run_job(job_id, video_path, paths, language_code)
    except Exception:
        app.logger.exception("Unexpected error while processing job %s", job_id)
        discard_job(job_id)
        return error_response("Something went wrong on the server. Please try again.", 500)


def run_job(job_id, video_path, paths, language_code):
    command = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",
        "-ar", "16000",
        "-ac", "1",
        paths["audio"],
    ]
    try:
        proc = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600
        )
    except FileNotFoundError:
        discard_job(job_id)
        return error_response("ffmpeg is not installed on the server.", 500)
    except subprocess.TimeoutExpired:
        discard_job(job_id)
        return error_response("Audio extraction took too long. Try a shorter video.", 400)

    if proc.returncode != 0 or not os.path.exists(paths["audio"]):
        app.logger.warning(
            "ffmpeg failed for job %s: %s",
            job_id,
            proc.stderr.decode("utf-8", errors="ignore")[-500:],
        )
        discard_job(job_id)
        return error_response(
            "Could not read audio from this file. Make sure it is a valid video that has an audio track.",
            400,
        )

    try:
        with transcribe_lock:
            global model
            if model is None:
                model = whisper.load_model(os.environ.get("WHISPER_MODEL", "tiny"))
            result = model.transcribe(paths["audio"], fp16=False)
    except Exception:
        app.logger.exception("Transcription failed for job %s", job_id)
        discard_job(job_id)
        return error_response("Transcription failed. Please try again with a different file.", 500)
    finally:
        try:
            os.remove(paths["audio"])  # the wav is large and no longer needed
        except OSError:
            pass

    segments = result.get("segments", [])
    if not segments:
        discard_job(job_id)
        return error_response("No speech detected in video.", 400)

    detected_language = result.get("language", "")

    target_base = base_language(language_code)
    needs_translation = not (target_base == detected_language and target_base != "zh")

    texts = [segment["text"].strip() for segment in segments]
    failed = 0
    if needs_translation:
        texts, failed = translate_segments(
            texts, language_code, source_language_code=detected_language or "auto"
        )

    warnings = []
    if failed:
        if needs_translation and failed == len(segments):
            warnings.append(
                "Translation is unavailable. Subtitles were created in the original "
                f"language ({detected_language or 'unknown'}). Check your internet "
                "connection and try again to translate them."
            )
        else:
            warnings.append(
                f"{failed} of {len(segments)} subtitle lines could not be translated "
                f"and were left in the original language ({detected_language or 'unknown'})."
            )

    srt_blocks = []
    vtt_blocks = ["WEBVTT\n"]
    for i, (segment, text) in enumerate(zip(segments, texts), start=1):
        start = format_time(segment["start"])
        end = format_time(segment["end"])
        srt_blocks.append(f"{i}\n{start} --> {end}\n{text}\n")
        vtt_blocks.append(f"{start.replace(',', '.')} --> {end.replace(',', '.')}\n{text}\n")

    with open(paths["srt"], "w", encoding="utf-8") as f:
        f.write("\n".join(srt_blocks))
    with open(paths["vtt"], "w", encoding="utf-8") as f:
        f.write("\n".join(vtt_blocks))
    with open(paths["lang"], "w", encoding="utf-8") as f:
        f.write(language_code)

    return jsonify(
        {
            "job_id": job_id,
            "language": language_code,
            "detected_language": detected_language,
            "translated": needs_translation,
            "warnings": warnings,
        }
    )


@app.route("/download/<job_id>")
def download(job_id):
    paths = valid_job_or_404(job_id)
    if paths is None or not os.path.exists(paths["srt"]):
        return error_response("No subtitles found. Please generate them first.", 404)
    return send_file(paths["srt"], as_attachment=True, download_name="subtitles.srt")


@app.route("/video/<job_id>")
def serve_video(job_id):
    if valid_job_or_404(job_id) is None:
        return error_response("Video not found.", 404)
    video_path = find_video(job_id)
    if not video_path:
        return error_response("Video not found.", 404)
    return send_file(video_path)


@app.route("/subtitles/<job_id>.vtt")
def serve_vtt(job_id):
    paths = valid_job_or_404(job_id)
    if paths is None or not os.path.exists(paths["vtt"]):
        return error_response("Subtitles not found.", 404)
    return send_file(paths["vtt"], mimetype="text/vtt")


WATCH_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Watch Video</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: #0a0a0a;
            color: white;
            font-family: 'Courier New', monospace;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 40px 20px;
        }
        h1 {
            color: #ff7300;
            margin-bottom: 24px;
            font-size: 1.6rem;
        }
        video {
            width: 100%;
            max-width: 860px;
            border-radius: 16px;
            border: 2px solid #ff7300;
            box-shadow: 0 0 30px rgba(255,115,0,0.3);
        }
        a {
            margin-top: 24px;
            color: #ff7300;
            border: 2px solid #ff7300;
            padding: 10px 22px;
            border-radius: 10px;
            text-decoration: none;
            transition: 0.3s;
        }
        a:hover {
            background: #ff7300;
            color: black;
        }
    </style>
</head>
<body>
    <h1>Watch Video 👻</h1>
    <video controls>
        <source src="/video/{{ job_id }}">
        <track
            kind="subtitles"
            src="/subtitles/{{ job_id }}.vtt"
            srclang="{{ lang }}"
            label="Subtitles"
            default
        >
        Your browser does not support the video tag.
    </video>
    <a href="/">← Back to Generator</a>
</body>
</html>
"""


@app.route("/watch/<job_id>")
def watch(job_id):
    paths = valid_job_or_404(job_id)
    if paths is None or not find_video(job_id) or not os.path.exists(paths["vtt"]):
        return error_response(
            "No video available. Please upload and generate subtitles first.", 404
        )

    lang = "en"
    try:
        with open(paths["lang"], encoding="utf-8") as f:
            candidate = f.read().strip()
        if LANG_CODE_RE.match(candidate):
            lang = candidate
    except OSError:
        pass

    return render_template_string(WATCH_TEMPLATE, job_id=job_id, lang=lang)


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
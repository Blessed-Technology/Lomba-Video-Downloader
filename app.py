"""
VideoGrab - a small self-hosted video downloader built on Flask + yt-dlp.

Use it for videos you own, have permission to download, or that are
licensed for reuse (e.g. Creative Commons). Downloading other people's
content may violate the platform's Terms of Service or copyright law.

Requires ffmpeg on PATH (merging video+audio, MP3 conversion).
"""
import hashlib
import ipaddress
import os
import re
import shutil
import tempfile
import threading
import time
from urllib.parse import urlparse

from flask import Flask, jsonify, render_template, request, send_file
import yt_dlp

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)

# Allowed hosts: "*" allows any site supported by yt-dlp (YouTube, TikTok, Twitter/X, Instagram, Vimeo, etc.).
# You can restrict to specific domains via ALLOWED_HOSTS="youtube.com,vimeo.com".
ALLOWED_HOSTS_RAW = os.environ.get("ALLOWED_HOSTS", "*").strip()
ALLOWED_HOSTS = (
    set(h.strip().lower() for h in ALLOWED_HOSTS_RAW.split(",") if h.strip())
    if ALLOWED_HOSTS_RAW != "*"
    else "*"
)
MAX_DURATION_SECONDS = int(os.environ.get("MAX_DURATION_SECONDS", 0))  # 0 = no limit

PROXY = os.environ.get("PROXY") or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")

COOKIE_FILE = os.environ.get("COOKIE_FILE")
COOKIES_CONTENT = os.environ.get("YOUTUBE_COOKIES") or os.environ.get("COOKIES_TEXT")

if COOKIES_CONTENT and not COOKIE_FILE:
    cookie_path = os.path.join(tempfile.gettempdir(), "youtube_cookies.txt")
    try:
        with open(cookie_path, "w", encoding="utf-8") as f:
            f.write(COOKIES_CONTENT.strip())
        COOKIE_FILE = cookie_path
    except Exception as e:
        print(f"Warning: could not write cookies file: {e}")

if not COOKIE_FILE:
    local_cookie_path = os.path.join(BASE_DIR, "cookies.txt")
    if os.path.isfile(local_cookie_path):
        COOKIE_FILE = local_cookie_path


# Partial and finished files live here so interrupted downloads can resume.
# In serverless environments (e.g. Vercel), the filesystem is read-only except /tmp
def get_cache_dir():
    custom = os.environ.get("CACHE_DIR")
    if custom:
        return os.path.abspath(custom)
    if os.environ.get("VERCEL"):
        return os.path.join(tempfile.gettempdir(), "downloads")
    try:
        target = os.path.join(BASE_DIR, "downloads")
        os.makedirs(target, exist_ok=True)
        return target
    except (PermissionError, OSError):
        return os.path.join(tempfile.gettempdir(), "downloads")


CACHE_DIR = get_cache_dir()
KEEP_HOURS = int(os.environ.get("KEEP_HOURS", 24))
os.makedirs(CACHE_DIR, exist_ok=True)

jobs = {}  # job_id -> state dict (in memory; files on disk survive restarts)
jobs_lock = threading.Lock()


def is_private_host(hostname: str) -> bool:
    hostname = hostname.lower().strip()
    if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
        return True
    if hostname.endswith(".local") or hostname.endswith(".internal") or hostname.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(hostname)
        return ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local
    except ValueError:
        pass
    return False


def is_allowed(url: str) -> bool:
    try:
        p = urlparse(url)
    except ValueError:
        return False
    if p.scheme not in ("https", "http") or not p.hostname:
        return False
    host = p.hostname.lower().strip()
    if is_private_host(host):
        return False
    if ALLOWED_HOSTS == "*":
        return True
    return any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS)


def fmt_size(n):
    if not n:
        return None
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.get("/api/health")
def health():
    return jsonify(
        status="ok",
        app="Lomba Video Downloader",
        version="1.0.0",
        ffmpeg=bool(shutil.which("ffmpeg")),
        node=bool(shutil.which("node")),
        cookies_loaded=bool(COOKIE_FILE and os.path.isfile(COOKIE_FILE)),
        proxy_configured=bool(PROXY),
    )


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/info")
def info():
    url = (request.get_json(silent=True) or {}).get("url", "").strip()
    if not is_allowed(url):
        return jsonify(error="Paste a valid video link."), 400

    opts = {
        "quiet": True,
        "noplaylist": True,
        "skip_download": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["tv_samsung", "tv", "mweb", "web", "android", "ios"]
            }
        },
        "js_runtimes": {"node": {}},
    }
    if PROXY:
        opts["proxy"] = PROXY
    if COOKIE_FILE and os.path.isfile(COOKIE_FILE):
        opts["cookiefile"] = COOKIE_FILE
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            data = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        clean_err = re.sub(r"\x1b\[[0-9;]*m", "", str(e)).strip()
        if "UNEXPECTED_EOF_WHILE_READING" in clean_err or "EOF occurred in violation of protocol" in clean_err:
            clean_err = "Connection blocked by your ISP (SSL EOF error). YouTube is restricted on your network. Please click 'Connect' in your VPN (e.g. MEGA VPN or ProtonVPN) and try again."
        elif "Failed to extract any player response" in clean_err or "Sign in to confirm you’re not a bot" in clean_err:
            clean_err = "YouTube is rate-limiting this server IP. Try another video, or configure YOUTUBE_COOKIES / PROXY in your server environment."
        elif "Unsupported URL" in clean_err:
            clean_err += ". That link is a home page or feed. Please open or copy the link to a specific video (e.g. tiktok.com/@user/video/... or youtube.com/watch?v=...)."
        return jsonify(error=clean_err[:300]), 422

    formats = data.get("formats", [])
    audio_best = max(
        (f for f in formats if f.get("vcodec") == "none" and f.get("acodec") != "none"),
        key=lambda f: f.get("abr") or 0,
        default=None,
    )
    audio_size = (audio_best or {}).get("filesize") or (audio_best or {}).get("filesize_approx") or 0

    by_height = {}
    for f in formats:
        h = f.get("height")
        if not h or f.get("vcodec") in (None, "none"):
            continue
        size = (f.get("filesize") or f.get("filesize_approx") or 0)
        direct_url = f.get("url") if (f.get("acodec") not in (None, "none") and f.get("url")) else None
        if h not in by_height or size > (by_height[h].get("size") or 0):
            by_height[h] = {"size": size, "direct_url": direct_url}

    options = [
        {
            "kind": "video",
            "height": h,
            "label": f"MP4 {h}p",
            "size": fmt_size(info["size"] + audio_size) if info["size"] else None,
            "direct_url": info.get("direct_url"),
        }
        for h, info in sorted(by_height.items(), reverse=True)
    ]

    # Fallback for platforms with single stream or where height isn't declared
    if not options:
        video_formats = [f for f in formats if f.get("vcodec") not in (None, "none")] or formats
        if video_formats:
            best_v = video_formats[-1]
            size = (best_v.get("filesize") or best_v.get("filesize_approx") or 0)
            options.append({
                "kind": "video",
                "height": None,
                "label": "Best Video (MP4)",
                "size": fmt_size(size) if size else None,
                "direct_url": best_v.get("url"),
            })

    options.append(
        {
            "kind": "audio",
            "height": None,
            "label": "MP3 audio",
            "size": fmt_size(audio_size),
            "direct_url": (audio_best or {}).get("url"),
        }
    )

    return jsonify(
        title=data.get("title"),
        thumbnail=data.get("thumbnail"),
        duration=data.get("duration"),
        uploader=data.get("uploader"),
        options=options,
    )


def job_id_for(url, kind, height):
    return hashlib.sha1(f"{url}|{kind}|{height}".encode()).hexdigest()[:16]


def find_final_file(job_dir):
    """Return the finished file in a job dir (ignores .part and per-stream temp files)."""
    if not os.path.isdir(job_dir):
        return None
    for name in os.listdir(job_dir):
        if (
            name.endswith((".mp4", ".mp3", ".webm", ".mkv", ".mov", ".m4a"))
            and not re.search(r"\.f\d+\.", name)
            and not name.endswith(".part")
        ):
            return name
    return None


def cleanup_old():
    cutoff = time.time() - KEEP_HOURS * 3600
    for name in os.listdir(CACHE_DIR):
        p = os.path.join(CACHE_DIR, name)
        if os.path.isdir(p) and os.path.getmtime(p) < cutoff and name not in jobs_running():
            shutil.rmtree(p, ignore_errors=True)


def jobs_running():
    return {j for j, st in jobs.items() if st["status"] == "downloading"}


def run_job(job_id, url, kind, height):
    job_dir = os.path.join(CACHE_DIR, job_id)
    state = jobs[job_id]

    def hook(d):
        if state.get("status") == "cancelled":
            raise ValueError("Download cancelled by user")
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            if total:
                state["progress"] = round(d["downloaded_bytes"] / total * 100, 1)
            state["speed"] = d.get("speed")
            state["eta"] = d.get("eta")
        elif d["status"] == "finished":
            state["progress"] = 100.0

    opts = {
        "quiet": True,
        "noplaylist": True,
        "outtmpl": os.path.join(job_dir, "%(title).150B.%(ext)s"),
        "continuedl": True,          # resume from .part files
        "retries": 50,               # retry dropped connections
        "fragment_retries": 50,
        "file_access_retries": 5,
        "socket_timeout": 30,
        "progress_hooks": [hook],
        "extractor_args": {
            "youtube": {
                "player_client": ["tv_samsung", "tv", "mweb", "web", "android", "ios"]
            }
        },
        "js_runtimes": {"node": {}},
    }
    if PROXY:
        opts["proxy"] = PROXY
    if COOKIE_FILE and os.path.isfile(COOKIE_FILE):
        opts["cookiefile"] = COOKIE_FILE
    if MAX_DURATION_SECONDS > 0:
        opts["match_filter"] = yt_dlp.utils.match_filter_func(
            f"duration <= {MAX_DURATION_SECONDS}"
        )
    if kind == "audio":
        opts.update(
            format="bestaudio/best",
            postprocessors=[
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
            ],
        )
    else:
        if height:
            opts.update(
                format=f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best",
                merge_output_format="mp4",
            )
        else:
            opts.update(
                format="bestvideo+bestaudio/best",
                merge_output_format="mp4",
            )

    try:
        os.makedirs(job_dir, exist_ok=True)
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        name = find_final_file(job_dir)
        if not name:
            raise RuntimeError("Nothing was downloaded (video may exceed the length limit).")
        state.update(status="done", file=name, progress=100.0)
    except Exception as e:  # partial files are kept so a retry resumes
        if state.get("status") == "cancelled":
            return # Cancelled properly
        msg = re.sub(r"\x1b\[[0-9;]*m", "", str(e))[:300]
        if "UNEXPECTED_EOF_WHILE_READING" in msg or "EOF occurred in violation of protocol" in msg:
            msg = "Connection blocked by your ISP (SSL EOF error). Please turn on your VPN (MEGA VPN or ProtonVPN) and retry."
        state.update(status="error", error=msg)


@app.post("/api/cancel/<job_id>")
def cancel(job_id):
    if not re.fullmatch(r"[0-9a-f]{16}", job_id):
        return jsonify(error="Bad job"), 400
    with jobs_lock:
        state = jobs.get(job_id)
        if state and state["status"] == "downloading":
            state["status"] = "cancelled"
            return jsonify(status="cancelled")
    return jsonify(error="Not running"), 404


@app.post("/api/prepare")
def prepare():
    body = request.get_json(silent=True) or {}
    url = body.get("url", "").strip()
    kind = body.get("kind", "video")
    height = body.get("height")
    if not is_allowed(url) or kind not in ("video", "audio") or not isinstance(height, (int, type(None))):
        return jsonify(error="Bad request"), 400

    cleanup_old()
    job_id = job_id_for(url, kind, height)
    job_dir = os.path.join(CACHE_DIR, job_id)

    with jobs_lock:
        state = jobs.get(job_id)
        if state and state["status"] == "downloading":
            return jsonify(job=job_id)  # already running
        done_file = find_final_file(job_dir)
        if done_file:  # already finished earlier
            jobs[job_id] = {"status": "done", "file": done_file, "progress": 100.0}
            return jsonify(job=job_id)
        # start (or restart/resume: .part files in job_dir are picked up)
        jobs[job_id] = {"status": "downloading", "progress": 0.0, "speed": None, "eta": None}
        threading.Thread(target=run_job, args=(job_id, url, kind, height), daemon=True).start()
    return jsonify(job=job_id)


@app.get("/api/status/<job_id>")
def status(job_id):
    if not re.fullmatch(r"[0-9a-f]{16}", job_id):
        return jsonify(error="Bad job"), 400
    state = jobs.get(job_id)
    if state is None:
        done_file = find_final_file(os.path.join(CACHE_DIR, job_id))
        if done_file:
            return jsonify(status="done", progress=100.0)
        return jsonify(status="unknown"), 404
    return jsonify({k: v for k, v in state.items() if k != "file"})


@app.get("/api/file/<job_id>")
def get_file(job_id):
    if not re.fullmatch(r"[0-9a-f]{16}", job_id):
        return "Bad job", 400
    job_dir = os.path.join(CACHE_DIR, job_id)
    name = find_final_file(job_dir)
    if not name:
        return "File not ready", 404
    # conditional=True enables HTTP Range + ETag, so browsers can resume
    return send_file(
        os.path.join(job_dir, name), as_attachment=True, download_name=name, conditional=True
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    app.run(host=host, port=port, debug=False, threaded=True)

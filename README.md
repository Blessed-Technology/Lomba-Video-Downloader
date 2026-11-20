# <img src="static/logo.png" alt="Lomba Logo" width="38" height="38" align="center" style="vertical-align: middle; margin-right: 8px;" /> Lomba Video Downloader

**A fast, self-hosted, cloud-ready universal media downloader powered by Flask and yt-dlp.**

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Render%20Online-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://lomba-video-downloader.onrender.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-FED063?style=for-the-badge)](#license)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Docker Ready](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)

> 🌐 **Live Demo:** [https://lomba-video-downloader.onrender.com](https://lomba-video-downloader.onrender.com)

---

## 🌟 Overview

**Lomba Video Downloader** is a self-hosted, lightweight web application and browser extension that lets you download video and audio content from YouTube, TikTok, Instagram, Twitter/X, Vimeo, Facebook, and over 1,000+ supported sites.

It includes automated `ffmpeg` media merging, client-side "Save As" file location picker, resumable downloads, and a bundled Manifest V3 browser extension.

---

## ✨ Features

- 🌍 **1,000+ Platforms Supported**: YouTube, TikTok, Instagram, Twitter/X, Vimeo, Facebook, Reddit, and any site supported by `yt-dlp`.
- 📁 **Save As Location Prompt**: Prompts you to pick your preferred destination folder and filename directly in your browser.
- ⚡ **Full Quality & Formats**: Multiple MP4 video resolutions (1080p, 720p, 480p, 360p) and MP3 audio extraction with automatic `ffmpeg` merging.
- 🧩 **Manifest V3 Browser Extension**: Download directly while browsing without leaving the tab.
- 🐳 **Docker & Production Ready**: One-command setup with Docker Compose, preconfigured health checks, and Render cloud support.
- 🛡️ **Built-in Security**: Localhost SSRF protection, strict HTTP security headers, and safe file cleanup.

---

## 🚀 Live Demo

You can try the live hosted deployment here:  
👉 **[https://lomba-video-downloader.onrender.com](https://lomba-video-downloader.onrender.com)**

---

## 🛠️ Deployment

### Option 1: Deploy to Render (Recommended - 100% Free)

Render's free tier provides Docker support, full `ffmpeg` installation, free SSL, and a public HTTPS URL:

1. Fork or push this repository to your **GitHub** account.
2. Sign in to [Render.com](https://render.com).
3. Click **New +** &rarr; **Blueprint**.
4. Connect this repository — Render will automatically read [`render.yaml`](render.yaml).
5. Click **Apply**. Render will build the container and provide your live URL:  
   `https://lomba-video-downloader.onrender.com`

---

### Option 2: Docker & Docker Compose

Run with Docker in a single command (`ffmpeg` and Python dependencies are automatically installed):

```bash
docker compose up -d --build
```

Access the application at `http://localhost:5000`.

---

### Option 3: Local Installation

1. **Install `ffmpeg`** on your system:
   - **Windows**: `winget install ffmpeg`
   - **macOS**: `brew install ffmpeg`
   - **Linux (Ubuntu/Debian)**: `sudo apt install ffmpeg`

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the server**:
   ```bash
   python app.py
   ```
   Open [http://localhost:5000](http://localhost:5000) in your web browser.

---

### Option 4: Deploy to Vercel (Serverless)

```bash
npm install -g vercel
vercel
```
*Note: Vercel serverless functions have a 10s-60s execution timeout and lack `ffmpeg`. For production background conversions, Render or Docker is recommended.*

---

## 🧩 Browser Extension Setup (Chrome & Edge)

Lomba includes a Manifest V3 browser extension located in the `extension/` folder:

1. Open `chrome://extensions` (or `edge://extensions`) in your browser.
2. Turn on **Developer mode** in the top right.
3. Click **Load unpacked** and choose the [`extension/`](extension/) directory.
4. Pin the **Lomba** extension to your toolbar.
5. *(Optional)* If your server is hosted remotely (e.g. on Render), open the extension popup, expand **Server**, enter `https://lomba-video-downloader.onrender.com`, and click **Save**.

---

## ⚙️ Configuration (.env)

| Variable | Default | Description |
| :--- | :--- | :--- |
| `ALLOWED_HOSTS` | `*` | Comma-separated domains allowed, or `*` for all platforms |
| `MAX_DURATION_SECONDS` | `0` | Max video duration in seconds (`0` = no duration limit) |
| `CACHE_DIR` | `downloads` | Local temporary folder for video caching & merging |
| `KEEP_HOURS` | `24` | Hours to keep cached downloads before auto-cleanup |
| `PORT` | `5000` | Port for the web server to bind to |
| `PROXY` | *(None)* | Optional HTTP/SOCKS5 proxy URL (`http://127.0.0.1:7890`) |

---

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).

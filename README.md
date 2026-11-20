# Lomba Video Downloader

Self-hosted and cloud-ready universal video downloader (Flask + yt-dlp).

## Run Locally
1. Install ffmpeg (`sudo apt install ffmpeg` / `brew install ffmpeg` / `winget install ffmpeg`)
2. `pip install -r requirements.txt`
3. `python app.py` then open http://localhost:5000

## Deploy on Render (100% Free)
Render is the **recommended free hosting platform** for Lomba Video Downloader because its free tier supports Docker and full `ffmpeg` processing without serverless timeouts.

1. Push this repository to your **GitHub** account.
2. Sign in to [Render.com](https://render.com) (free account, no credit card required).
3. Click **New +** &rarr; **Blueprint**.
4. Select your GitHub repository.
5. Render will detect [`render.yaml`](render.yaml) automatically. Click **Apply**.
6. Render builds the Docker container, installs `ffmpeg`, and provides you a free, permanent HTTPS URL (e.g., `https://lomba-video-downloader.onrender.com`).

*(You can also use this free Render URL in your Lomba Chrome Extension so it downloads from anywhere!)*

## Deploy to Vercel
1. Install the Vercel CLI: `npm i -g vercel` (or connect your GitHub repository directly to Vercel).
2. Inside this project folder, run:
   ```bash
   vercel
   ```
3. Follow the CLI prompts. `vercel.json` and `api/index.py` are already pre-configured!

> [!NOTE]
> Vercel is a serverless platform with a 10s-60s function execution timeout, a 4.5MB payload limit, and no preinstalled `ffmpeg`. It is great for testing and fetching video details/direct links. For heavy multi-gigabyte video conversions requiring `ffmpeg` and long background processing, a dedicated container service (such as Render, Railway, Fly.io, or VPS) is recommended for production.

## Config (env vars)
- `ALLOWED_HOSTS` - comma list or `*` for all platforms supported by yt-dlp (default `*`)
- `CACHE_DIR` - where partial/finished files are kept, default `./downloads`
- `KEEP_HOURS` - delete cached files after this many hours, default 24
- `MAX_DURATION_SECONDS` - default 14400 (4h); set to 0 for no limit

## Notes
- Supports YouTube, TikTok, Instagram, Twitter/X, Vimeo, Facebook, and 1,000+ sites.
- Keep yt-dlp updated (`pip install -U yt-dlp`); sites change often and old versions break.
- Only download content you own, have permission for, or that is licensed for reuse.

## Resuming & Saving
- When clicking Download in Chrome/Edge, a native "Save As" file picker opens so you can choose the destination folder and filename.
- Interrupted server transfers resume from `.part` files in `CACHE_DIR`.
- The finished file is served with HTTP Range support, so interrupted browser downloads can be resumed.

## Chrome extension
The `extension/` folder is a Manifest V3 extension that uses your running server.

1. Start the server (`python app.py`).
2. Open `chrome://extensions`, turn on **Developer mode**, click **Load unpacked**, and pick the `extension/` folder.
3. Open any supported video page, click the VideoGrab icon, choose a quality, and click Download.

- When download completes, Chrome prompts you with a "Save As" dialog to choose where to save the file.
- Downloads run in the background, so you can close the popup. The icon badge shows progress.
- Using a server on another machine: open the popup, expand **Server**, enter its address (e.g. https://my-server.example) and Save. Chrome will ask permission for that address. Exposing the server publicly without a login is not recommended.

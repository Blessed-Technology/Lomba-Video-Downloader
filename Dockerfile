FROM python:3.12-slim

# Install system dependencies (ffmpeg is required for audio/video processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -U -r requirements.txt

# Copy application source code
COPY . .

# Create cache directory
RUN mkdir -p downloads

ENV PYTHONUNBUFFERED=1
ENV PORT=5000

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD sh -c "curl -f http://localhost:${PORT:-5000}/api/health || exit 1"

CMD ["python", "app.py"]

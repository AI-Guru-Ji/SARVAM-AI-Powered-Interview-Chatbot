# Dockerfile for deploying the ShramSaathi AI FastAPI backend on Render.
#
# Render auto-detects this file and uses it instead of the default
# Python buildpack. The Docker route is required because WeasyPrint
# needs cairo/pango/gdk-pixbuf system libraries that the buildpack
# does not install.
#
# Build locally for testing:
#   docker build -t shramsaathi-backend .
#   docker run --rm -p 8000:8000 \
#       -e SARVAM_API_KEY=xxx -e DEMO_MODE=1 shramsaathi-backend

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# WeasyPrint native dependencies — cairo, pango, gdk-pixbuf.
# Also need libpq for any future Postgres adapter; cheap to include.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        shared-mime-info \
        fonts-noto-core \
        fonts-noto-cjk \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for better Docker-layer caching.
COPY requirements.txt ./
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy the rest of the source tree. The Streamlit UI is included for
# the recruiter dashboard but Render only invokes the FastAPI app.
COPY . .

# Render injects $PORT — default to 8000 for local docker runs.
ENV PORT=8000
EXPOSE 8000

# Healthcheck so Render dashboards show "Live" once the app responds.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fs http://127.0.0.1:${PORT}/v1/health || exit 1

CMD uvicorn ui.fastapi.app:app --host 0.0.0.0 --port ${PORT}

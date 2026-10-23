# API image: FastAPI service with the threat detection pipeline.
# Build context is the repo root (see docker-compose.yml).
ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first: this layer is cached until requirements-api.txt changes
COPY requirements-api.txt .
RUN pip install -r requirements-api.txt

# Application code only. Trained models are mounted at run time, not baked in,
# so retraining never needs an image rebuild.
COPY src ./src

# Run as a normal user. /app/evidence holds the SQLite evidence log (a volume).
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/evidence /app/models \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Docker marks the container unhealthy if /health stops answering
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

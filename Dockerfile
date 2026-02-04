# ========================================
# Multi-stage Dockerfile for LearnPulse AI Instructor Assistant
# Optimized for Google Cloud Run deployment
# ========================================

# ----------------------------------------
# Stage 1: Builder - Compile dependencies
# ----------------------------------------
FROM python:3.11-slim as builder

# Prevent Python from writing .pyc files and buffering stdout/stderr
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies for Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy requirements and install in virtual environment
COPY requirements.txt .
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# ----------------------------------------
# Stage 2: Runtime - Minimal production image
# ----------------------------------------
FROM python:3.11-slim

# Cloud Run sets PORT environment variable
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8080 \
    ENVIRONMENT=production

LABEL maintainer="LearnPulse AI <dev@learnpulse.ai>"
LABEL description="Production LearnPulse AI Instructor Assistant API"
LABEL version="1.0.0"

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Create non-root user for security
RUN groupadd -r appuser && \
    useradd -r -g appuser -u 1000 -m -s /sbin/nologin appuser && \
    mkdir -p /app /app/mock_data /app/knowledge && \
    chown -R appuser:appuser /app

WORKDIR /app

# Copy application code
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser main.py .
COPY --chown=appuser:appuser mock_data/ ./mock_data/
COPY --chown=appuser:appuser knowledge/ ./knowledge/

# Switch to non-root user
USER appuser

# Expose port (Cloud Run uses PORT env var, default 8080)
EXPOSE $PORT

# Cloud Run startup command
# Single worker recommended for Cloud Run (scales via instances)
CMD exec uvicorn main:app \
    --host 0.0.0.0 \
    --port $PORT \
    --workers 1 \
    --log-level info \
    --proxy-headers \
    --forwarded-allow-ips='*'

# ----------------------------------------
# Deployment Instructions:
# ----------------------------------------
# Build and push to Google Container Registry:
#   gcloud builds submit --tag gcr.io/PROJECT_ID/learnpulse-assistant
#
# Deploy to Cloud Run:
#   gcloud run deploy learnpulse-assistant \
#     --image gcr.io/PROJECT_ID/learnpulse-assistant \
#     --platform managed \
#     --region us-central1 \
#     --service-account SA_EMAIL \
#     --set-env-vars "PROJECT_ID=xxx,REGION=us-central1" \
#     --allow-unauthenticated
# ----------------------------------------

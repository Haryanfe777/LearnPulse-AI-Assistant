"""FastAPI application entrypoint for LearnPulse AI Instructor Assistant.

Production-ready configuration for Google Cloud Run deployment.
"""
import sys
import os

# Ensure UTF-8 encoding
if sys.stdout:
    sys.stdout.reconfigure(encoding='utf-8')

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import time
import uuid

from app.api.routes import router
from app.core.logging import get_logger, setup_logging
from app.core.config import settings

# Initialize structured logging
log_format = settings.environment == "production"
setup_logging(level=settings.log_level, json_format=log_format)
logger = get_logger(__name__)

# Application metadata
APP_VERSION = "1.0.0"
APP_NAME = "LearnPulse AI Instructor Assistant"

app = FastAPI(
    title=APP_NAME,
    description="AI-powered insights for LearnPulse AI K-12 instructors",
    version=APP_VERSION,
    docs_url="/docs" if settings.environment != "production" else None,  # Disable in prod
    redoc_url="/redoc" if settings.environment != "production" else None,
)

# CORS middleware - configure for production
cors_origins = settings.cors_origins.copy()
if settings.environment == "production":
    # Add your production domains here
    cors_origins.extend([
        "https://*.run.app",  # Cloud Run domains
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware to log all requests with timing and status code."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    start_time = time.time()
    
    logger.info(
        f"Request started: {request.method} {request.url.path}",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "client": request.client.host if request.client else None,
        }
    )
    
    try:
        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000
        
        logger.info(
            f"Request completed: {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            }
        )
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        return response
    
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Request failed: {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "duration_ms": round(duration_ms, 2),
                "error": str(e),
            },
            exc_info=True
        )
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "request_id": request_id}
        )


@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    logger.info("Application starting up", extra={"version": "1.0.0"})


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    logger.info("Application shutting down")


app.include_router(router)


@app.get("/")
def root():
    """Root endpoint with basic service info."""
    return {
        "service": APP_NAME,
        "version": APP_VERSION,
        "status": "running",
        "environment": settings.environment
    }


@app.get("/health")
def health_check():
    """Health check endpoint for Cloud Run liveness/readiness probes.
    
    Returns 200 if the service is healthy.
    Cloud Run uses this to determine if the instance should receive traffic.
    """
    return {
        "status": "healthy",
        "version": APP_VERSION,
        "checks": {
            "api": "ok",
            "config": "ok" if settings.project_id else "missing"
        }
    }


@app.get("/ready")
async def readiness_check():
    """Readiness check - verifies external dependencies are accessible.
    
    More comprehensive than health check, validates:
    - Configuration is valid
    - External services are reachable (if applicable)
    """
    checks = {
        "config": "ok" if settings.project_id else "error",
        "region": settings.region or "not_set",
    }
    
    # Check Redis if configured
    try:
        from app.infrastructure.redis import get_redis_client
        redis = get_redis_client()
        if redis:
            redis.ping()
            checks["redis"] = "ok"
        else:
            checks["redis"] = "fallback_memory"
    except Exception:
        checks["redis"] = "fallback_memory"
    
    all_ok = checks.get("config") == "ok"
    
    return {
        "status": "ready" if all_ok else "degraded",
        "checks": checks
    }
"""GCP-specific configuration extensions for production deployment.

This module extends src/config.py with GCP Secret Manager integration
and Cloud SQL connection handling.
"""
import os
from pathlib import Path
from google.cloud import secretmanager

from src.logging_config import get_logger

logger = get_logger(__name__)

# Detect environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")  # development, staging, production
IS_PRODUCTION = ENVIRONMENT == "production"
IS_GCP = os.getenv("K_SERVICE") is not None  # Cloud Run sets K_SERVICE env var

# GCP Configuration
PROJECT_ID = os.getenv("PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
REGION = os.getenv("REGION", "europe-west1")


def get_secret_from_manager(secret_id: str, project_id: str = None) -> str:
    """Fetch secret from Google Cloud Secret Manager.
    
    Args:
        secret_id: Secret name (e.g., 'jwt-secret-key')
        project_id: GCP project ID (defaults to PROJECT_ID env var)
        
    Returns:
        Secret value as string
        
    Raises:
        Exception: If secret cannot be accessed
        
    Example:
        >>> jwt_key = get_secret_from_manager('jwt-secret-key')
    """
    try:
        project_id = project_id or PROJECT_ID
        if not project_id:
            raise ValueError("PROJECT_ID must be set")
        
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
        
        logger.info(f"Fetching secret: {secret_id}")
        response = client.access_secret_version(request={"name": name})
        secret_value = response.payload.data.decode("UTF-8")
        
        logger.info(f"Successfully retrieved secret: {secret_id}")
        return secret_value
    
    except Exception as e:
        logger.error(f"Failed to fetch secret {secret_id}: {e}", exc_info=True)
        raise


def get_jwt_secret() -> str:
    """Get JWT secret key from Secret Manager (production) or env var (dev).
    
    Returns:
        JWT secret key string
    """
    if IS_PRODUCTION or IS_GCP:
        try:
            return get_secret_from_manager("jwt-secret-key")
        except Exception as e:
            logger.warning(f"Failed to get JWT secret from Secret Manager: {e}")
            # Fallback to env var
            return os.getenv("JWT_SECRET_KEY", "fallback-insecure-key")
    else:
        return os.getenv("JWT_SECRET_KEY", "development-secret-key")


def get_db_password() -> str:
    """Get database password from Secret Manager (production) or env var (dev).
    
    Returns:
        Database password string
    """
    if IS_PRODUCTION or IS_GCP:
        try:
            return get_secret_from_manager("db-password")
        except Exception as e:
            logger.warning(f"Failed to get DB password from Secret Manager: {e}")
            return os.getenv("DB_PASSWORD", "")
    else:
        return os.getenv("DB_PASSWORD", "postgres")


def get_database_url() -> str:
    """Construct database URL for Cloud SQL or local PostgreSQL.
    
    Returns:
        SQLAlchemy-compatible database URL
        
    Example:
        >>> url = get_database_url()
        >>> # Production: postgresql+psycopg2://user:pass@/dbname?host=/cloudsql/project:region:instance
        >>> # Development: postgresql://user:pass@localhost:5432/dbname
    """
    db_user = os.getenv("DB_USER", "appuser")
    db_password = get_db_password()
    db_name = os.getenv("DB_NAME", "teacher_assistant")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    
    if IS_GCP and db_host.startswith("/cloudsql/"):
        # Cloud SQL Unix socket connection
        return f"postgresql+psycopg2://{db_user}:{db_password}@/{db_name}?host={db_host}"
    else:
        # TCP connection (local or external)
        return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


def get_redis_config() -> dict:
    """Get Redis configuration for Memorystore or local Redis.
    
    Returns:
        Dict with Redis connection parameters
        
    Example:
        >>> config = get_redis_config()
        >>> redis_client = redis.Redis(**config)
    """
    return {
        "host": os.getenv("REDIS_HOST", "localhost"),
        "port": int(os.getenv("REDIS_PORT", "6379")),
        "decode_responses": True,
        "socket_connect_timeout": 5,
        "socket_timeout": 5,
        # Memorystore doesn't use password (VPC-secured)
        # Only set password if explicitly provided
        "password": os.getenv("REDIS_PASSWORD") or None,
    }


def setup_cloud_logging():
    """Set up Google Cloud Logging in production.
    
    In production, this connects Python logging to Cloud Logging.
    In development, logs go to stdout (already configured in logging_config.py).
    """
    if IS_PRODUCTION or IS_GCP:
        try:
            import google.cloud.logging
            client = google.cloud.logging.Client()
            client.setup_logging()
            logger.info("Cloud Logging initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Cloud Logging: {e}")
            logger.info("Using local logging instead")


def get_vertex_credentials_source() -> str | None:
    """Get local service account JSON path if provided.

    Returns:
        Path to service account JSON file (or None to use ADC).
    """
    credentials_file = (
        os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        or os.getenv("SERVICE_ACCOUNT_FILE")
    )
    if credentials_file:
        return credentials_file

    if IS_GCP:
        logger.info("Using default compute service account for Vertex AI")
    return None


# Export configuration
GCP_CONFIG = {
    "environment": ENVIRONMENT,
    "is_production": IS_PRODUCTION,
    "is_gcp": IS_GCP,
    "project_id": PROJECT_ID,
    "region": REGION,
    "jwt_secret": get_jwt_secret,  # Function, call to get value
    "db_url": get_database_url,    # Function, call to get value
    "redis_config": get_redis_config,  # Function, call to get value
}


# Log configuration on import
logger.info(f"Configuration loaded: environment={ENVIRONMENT}, is_gcp={IS_GCP}")
if IS_GCP:
    logger.info(f"Running on Google Cloud Platform: project={PROJECT_ID}, region={REGION}")
else:
    logger.info("Running in local development mode")


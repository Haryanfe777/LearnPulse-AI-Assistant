"""Core application configuration and settings.

Handles environment variables, GCP credentials, and application settings.
"""
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from google.auth import default
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from pydantic import Field
from pydantic_settings import BaseSettings


# Load environment variables
ROOT = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=ROOT / ".env", override=True)
load_dotenv(override=True)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Google Cloud Platform
    project_id: str = Field(
        default_factory=lambda: (
            os.getenv("PROJECT_ID") 
            or os.getenv("GOOGLE_CLOUD_PROJECT") 
            or os.getenv("GCP_PROJECT")
            or ""
        ),
        alias="PROJECT_ID"
    )
    region: str = Field(
        default_factory=lambda: (
            os.getenv("REGION") 
            or os.getenv("GOOGLE_CLOUD_REGION") 
            or os.getenv("LOCATION")
            or "us-central1"
        ),
        alias="REGION"
    )
    service_account_file: str = Field(
        default_factory=lambda: (
            os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            or os.getenv("SERVICE_ACCOUNT_FILE")
            or ""
        ),
        alias="GOOGLE_APPLICATION_CREDENTIALS"
    )
    
    # Database Schema Configuration
    student_col: str = Field(default="student_name", alias="STUDENT_COL")
    class_col: str = Field(default="class_id", alias="CLASS_COL")
    score_col: str = Field(default="score", alias="SCORE_COL")
    date_col: str = Field(default="date", alias="DATE_COL")
    
    # Redis Configuration
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_password: Optional[str] = Field(default=None, alias="REDIS_PASSWORD")
    redis_db: int = Field(default=0, alias="REDIS_DB")
    
    # JWT Authentication
    jwt_secret_key: str = Field(
        default="development-secret-key-change-in-production",
        alias="JWT_SECRET_KEY"
    )
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=1440, alias="ACCESS_TOKEN_EXPIRE_MINUTES")  # 24 hours
    
    # Application Settings
    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    
    # API Settings
    api_prefix: str = Field(default="/api/v1", alias="API_PREFIX")
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:8501",
            "http://127.0.0.1:8501"
        ],
        alias="CORS_ORIGINS"
    )
    
    class Config:
        case_sensitive = False
        env_file = ".env"
        populate_by_name = True
    
    def validate_required_settings(self):
        """Validate that required settings are present."""
        if not self.project_id:
            raise ValueError(
                "PROJECT_ID not set. Define PROJECT_ID in .env "
                "(or GOOGLE_CLOUD_PROJECT/GCP_PROJECT)."
            )
        if not self.region:
            raise ValueError(
                "REGION not set. Define REGION in .env "
                "(e.g., us-central1 or europe-west1)."
            )
        if self.environment == "production" and self.jwt_secret_key == "development-secret-key-change-in-production":
            raise ValueError(
                "JWT_SECRET_KEY must be set to a secure value in production."
            )


# Global settings instance
settings = Settings()

# Legacy exports for backward compatibility
PROJECT_ID = settings.project_id
REGION = settings.region
SERVICE_ACCOUNT_FILE = settings.service_account_file
STUDENT_COL = settings.student_col
CLASS_COL = settings.class_col
SCORE_COL = settings.score_col
DATE_COL = settings.date_col


def get_vertex_credentials():
    """Get credentials for Vertex AI (service account file or ADC).

    Returns a credential that works across environments
    (local, FastAPI, Streamlit, GCP).

    Returns:
        Credentials object

    Raises:
        Exception: If credential creation fails

    Example:
        >>> creds = get_vertex_credentials()
        >>> init(project=PROJECT_ID, location=REGION, credentials=creds)
    """
    try:
        scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        if settings.service_account_file:
            return service_account.Credentials.from_service_account_file(
                settings.service_account_file,
                scopes=scopes
            )

        credentials, _ = default(scopes=scopes)
        credentials.refresh(Request())
        return credentials
    
    except Exception as e:
        print(f"⚠️ Error creating credentials: {e}")
        raise


# Validate settings on module import (only in non-test environments)
if settings.environment != "test":
    try:
        settings.validate_required_settings()
    except ValueError as e:
        print(f"Configuration Error: {e}")
        # Don't raise in development to allow partial setup
        if settings.environment == "production":
            raise

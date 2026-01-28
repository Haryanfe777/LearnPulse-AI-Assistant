"""Configuration and credentials for the LearnPulse AI Instructor Assistant service."""
import os
from pathlib import Path
from dotenv import load_dotenv
from google.auth import default
from google.auth.transport.requests import Request
from google.oauth2 import service_account

# Load .env 
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=ROOT / ".env", override=True)
load_dotenv(override=True)

PROJECT_ID = (
    os.getenv("PROJECT_ID")
    or os.getenv("GOOGLE_CLOUD_PROJECT")
    or os.getenv("GCP_PROJECT")
)
REGION = (
    os.getenv("REGION")
    or os.getenv("GOOGLE_CLOUD_REGION")
    or os.getenv("LOCATION")
)
SERVICE_ACCOUNT_FILE = (
    os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    or os.getenv("SERVICE_ACCOUNT_FILE")
)

# Dataset schema (override via .env to fit real data)
STUDENT_COL = os.getenv("STUDENT_COL", "student_name")
CLASS_COL = os.getenv("CLASS_COL", "class_id")
SCORE_COL = os.getenv("SCORE_COL", "score")
DATE_COL = os.getenv("DATE_COL", "date")

if not PROJECT_ID:
    raise ValueError("PROJECT_ID not set. Define PROJECT_ID in .env (or GOOGLE_CLOUD_PROJECT/GCP_PROJECT).")
if not REGION:
    raise ValueError("REGION not set. Define REGION in .env (e.g., us-central1 or europe-west1).")

def get_vertex_credentials():
    """
    Returns credentials for Vertex AI (service account file or ADC).
    Works across environments (local, FastAPI, Streamlit, GCP).
    """
    try:
        scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        if SERVICE_ACCOUNT_FILE:
            return service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE,
                scopes=scopes
            )

        credentials, _ = default(scopes=scopes)
        credentials.refresh(Request())
        return credentials

    except Exception as e:
        print("⚠️ Error creating credentials:", e)
        raise

# LearnPulse AI Instructor Assistant

An AI-powered teaching assistant that helps K-12 instructors analyze student learning data, track progress, generate personalized feedback, and make data-driven classroom decisions.

## Features

- **Conversational AI Interface**: Natural language queries about student/class performance
- **Student Analytics**: Track individual student progress, identify struggling areas
- **Class Insights**: Aggregate class trends, compare performance across concepts
- **Personalized Feedback**: AI-generated, instructor-friendly feedback for students
- **Visual Reports**: Interactive charts and PDF reports
- **Multi-language Support**: English and French

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Streamlit UI  │────>│   FastAPI API    │────>│  Vertex AI      │
│   (Frontend)    │     │   (Backend)      │     │  (Gemini 2.0)   │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
               ┌────▼────┐          ┌─────▼─────┐
               │  Redis  │          │ Mock Data │
               │ (Cache) │          │   (CSV)   │
               └─────────┘          └───────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Google Cloud account with Vertex AI enabled
- (Optional) Redis for caching

### Local Development

1. **Clone and setup**:
   ```bash
   git clone https://github.com/Haryanfe777/learnpulse-ai-assistant.git
   cd learnpulse-ai-assistant
   python -m venv venv
   source venv/bin/activate  # Windows: .\venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

3. **GCP Authentication** (choose one):
   ```bash
   # Option A: Service Account Key (local dev)
   # Download key from GCP Console, save to credentials/
   # Set GOOGLE_APPLICATION_CREDENTIALS in .env
   
   # Option B: Application Default Credentials
   gcloud auth application-default login
   ```

4. **Start the services**:
   ```bash
   # Terminal 1: FastAPI backend
   uvicorn main:app --reload --port 8000
   
   # Terminal 2: Streamlit frontend
   streamlit run app_streamlit.py --server.port 8501
   ```

5. **Access**:
   - API: http://localhost:8000
   - Streamlit UI: http://localhost:8501
   - API Docs: http://localhost:8000/docs

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check for Cloud Run |
| `/ready` | GET | Readiness check with dependency status |
| `/meta` | GET | List available students and classes |
| `/chat` | POST | Conversational AI endpoint |
| `/student/{name}` | GET | Individual student analytics |
| `/class/{class_id}` | GET | Class-level analytics |
| `/feedback/student/{name}` | GET | Generate personalized feedback |
| `/report/student/{name}/html` | GET | Student HTML report |
| `/report/student/{name}/pdf` | GET | Student PDF report |
| `/auth/login` | POST | JWT authentication |

## Production Deployment (Cloud Run)

### Prerequisites

1. GCP Project with billing enabled
2. APIs enabled: Vertex AI, Cloud Run, Cloud Build
3. Service account with `Vertex AI User` role

### Deploy

```bash
# Set project
export PROJECT_ID=your-project-id
export REGION=us-central1
export SA_EMAIL=your-sa@$PROJECT_ID.iam.gserviceaccount.com

# Build and push image
gcloud builds submit --tag gcr.io/$PROJECT_ID/learnpulse-assistant

# Create secrets (first time only)
echo -n "your-secure-jwt-secret-64-chars" | \
  gcloud secrets create jwt-secret --data-file=-

# Deploy to Cloud Run
gcloud run deploy learnpulse-assistant \
  --image gcr.io/$PROJECT_ID/learnpulse-assistant \
  --platform managed \
  --region $REGION \
  --service-account $SA_EMAIL \
  --set-env-vars "PROJECT_ID=$PROJECT_ID,REGION=$REGION,ENVIRONMENT=production" \
  --set-secrets "JWT_SECRET_KEY=jwt-secret:latest" \
  --allow-unauthenticated \
  --memory 2Gi \
  --min-instances 0 \
  --max-instances 10
```

### With Memorystore Redis (Optional)

```bash
# Create Memorystore instance
gcloud redis instances create learnpulse-redis \
  --region=$REGION \
  --tier=basic \
  --size=1

# Get Redis IP
REDIS_IP=$(gcloud redis instances describe learnpulse-redis \
  --region=$REGION --format='value(host)')

# Create VPC connector
gcloud compute networks vpc-access connectors create learnpulse-vpc \
  --region=$REGION \
  --range=10.8.0.0/28

# Deploy with Redis
gcloud run deploy learnpulse-assistant \
  --image gcr.io/$PROJECT_ID/learnpulse-assistant \
  --set-env-vars "REDIS_HOST=$REDIS_IP" \
  --vpc-connector learnpulse-vpc \
  ... (other flags)
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PROJECT_ID` | Yes | - | GCP project ID |
| `REGION` | Yes | us-central1 | GCP region |
| `ENVIRONMENT` | No | development | Environment (development/production) |
| `JWT_SECRET_KEY` | Yes (prod) | - | JWT signing key (64+ chars recommended) |
| `REDIS_HOST` | No | localhost | Redis host |
| `REDIS_PORT` | No | 6379 | Redis port |
| `LOG_LEVEL` | No | INFO | Logging level |

## Project Structure

```
learnpulse-ai-assistant/
├── app/
│   ├── api/
│   │   └── routes.py          # FastAPI endpoints
│   ├── core/
│   │   ├── auth.py            # JWT authentication
│   │   ├── config.py          # Settings management
│   │   └── logging.py         # Structured logging
│   ├── domain/
│   │   ├── student.py         # Student models
│   │   └── user.py            # User models
│   ├── infrastructure/
│   │   ├── data_loader.py     # Data access layer
│   │   ├── redis.py           # Redis client
│   │   ├── vertex.py          # Vertex AI client
│   │   └── vertex_async.py    # Async Vertex AI
│   ├── services/
│   │   ├── analytics.py       # Analytics logic
│   │   ├── assistant.py       # AI conversation
│   │   ├── reports.py         # Report generation
│   │   └── support.py         # Support escalation
│   └── utils/
│       └── text.py            # Text utilities
├── knowledge/                  # Knowledge base docs
├── mock_data/                  # Sample data
├── tests/                      # Test suite
├── main.py                     # Application entrypoint
├── app_streamlit.py           # Streamlit frontend
├── Dockerfile                  # Production container
├── requirements.txt            # Dependencies
└── .env.example               # Environment template
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_routes_integration.py -v
```

## Security Considerations

- **JWT Tokens**: Use a strong, random secret key in production (64+ characters)
- **Service Accounts**: Use dedicated service accounts with minimal permissions
- **Credentials**: Never commit `.env` or credential files to version control
- **Cloud Run**: Credentials are injected automatically - never set `GOOGLE_APPLICATION_CREDENTIALS`

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

---

Built with FastAPI, Vertex AI (Gemini 2.0), and Streamlit.

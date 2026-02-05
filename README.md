# LearnPulse AI Instructor Assistant

A smart teaching assistant platform that helps K-12 instructors analyze student learning data, track progress, generate personalized feedback, and make data-driven classroom decisions.

## Live Demo

- **Web Application**: https://learnpulse-frontend-kgbnk6qtsa-uc.a.run.app
- **API Documentation**: https://learnpulse-assistant-kgbnk6qtsa-uc.a.run.app/docs

### Demo Credentials
- **Username**: `Habeeb HAMMED`
- **Password**: `Haryanfe7`

## Features

- **Conversational Interface**: Natural language queries about student/class performance
- **Student Analytics**: Track individual progress, identify areas needing attention
- **Class Insights**: Aggregate trends, compare performance across concepts
- **Personalized Feedback**: Generate actionable, instructor-friendly feedback
- **Visual Reports**: Interactive charts and downloadable PDF reports
- **Multi-language Support**: English and French

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Streamlit UI  │────>│   FastAPI API    │────>│   Vertex AI     │
│   (Frontend)    │     │   (Backend)      │     │   (Gemini 2.0)  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
               ┌────▼────┐          ┌─────▼─────┐
               │  Redis  │          │ BigQuery  │
               │ (Cache) │          │  (Data)   │
               └─────────┘          └───────────┘
```

## Technology Stack

- **Backend**: FastAPI (Python 3.11)
- **Frontend**: Streamlit
- **LLM**: Google Vertex AI (Gemini 2.0 Flash)
- **Database**: BigQuery
- **Caching**: Redis (Memorystore)
- **Deployment**: Google Cloud Run
- **CI/CD**: Cloud Build

## Quick Start

### Prerequisites

- Python 3.11+
- Google Cloud account with Vertex AI enabled
- (Optional) Redis for caching

### Local Development

1. **Clone and setup**:
   ```bash
   git clone https://github.com/Haryanfe777/LearnPulse-AI-Assistant.git
   cd LearnPulse-AI-Assistant
   python -m venv venv
   source venv/bin/activate  # Windows: .\venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your GCP project settings
   ```

3. **GCP Authentication**:
   ```bash
   gcloud auth application-default login
   ```

4. **Start the services**:
   ```bash
   # Terminal 1: Backend API
   uvicorn main:app --reload --port 8000
   
   # Terminal 2: Frontend UI
   streamlit run app_streamlit.py --server.port 8501
   ```

5. **Access**:
   - Frontend: http://localhost:8501
   - API Docs: http://localhost:8000/docs

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Service health check |
| `/ready` | GET | Readiness check with dependencies |
| `/meta` | GET | List available students and classes |
| `/chat` | POST | Conversational query endpoint |
| `/student/{name}` | GET | Individual student analytics |
| `/class/{class_id}` | GET | Class-level analytics |
| `/feedback/student/{name}` | GET | Personalized feedback generation |
| `/report/student/{name}/html` | GET | Student HTML report |
| `/report/student/{name}/pdf` | GET | Student PDF download |
| `/auth/login` | POST | JWT authentication |

## Project Structure

```
LearnPulse-AI-Assistant/
├── app/
│   ├── api/routes.py           # API endpoints
│   ├── core/
│   │   ├── auth.py             # JWT authentication
│   │   ├── config.py           # Configuration
│   │   └── logging.py          # Structured logging
│   ├── domain/                 # Domain models
│   ├── infrastructure/
│   │   ├── data_loader.py      # Data access
│   │   ├── redis.py            # Cache client
│   │   └── vertex.py           # LLM client
│   └── services/
│       ├── analytics.py        # Analytics logic
│       ├── assistant.py        # Conversation handler
│       └── reports.py          # Report generation
├── mock_data/                  # Sample data
├── main.py                     # Application entry
├── app_streamlit.py            # Frontend
├── Dockerfile                  # Backend container
├── Dockerfile.streamlit        # Frontend container
└── requirements.txt            # Dependencies
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `PROJECT_ID` | Yes | GCP project ID |
| `REGION` | Yes | GCP region (e.g., us-central1) |
| `ENVIRONMENT` | No | development/production |
| `JWT_SECRET_KEY` | Yes (prod) | JWT signing key |
| `REDIS_HOST` | No | Redis host for caching |
| `REDIS_PORT` | No | Redis port (default: 6379) |

## Deployment

The application is deployed on Google Cloud Run with automatic scaling.

### Manual Deployment

```bash
# Build and push images
docker build -t gcr.io/PROJECT_ID/learnpulse-assistant .
docker push gcr.io/PROJECT_ID/learnpulse-assistant

# Deploy to Cloud Run
gcloud run deploy learnpulse-assistant \
  --image gcr.io/PROJECT_ID/learnpulse-assistant \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

### CI/CD

Push to `main` branch triggers automatic deployment via Cloud Build.

## Testing

```bash
# Run tests
pytest

# With coverage
pytest --cov=app --cov-report=html
```

## Security

- JWT-based authentication for protected endpoints
- Service accounts with minimal permissions
- Secrets stored in GCP Secret Manager
- No credentials in version control

## License

MIT License

## Author

Habeeb HAMMED

---

Built with FastAPI, Vertex AI, and Streamlit.

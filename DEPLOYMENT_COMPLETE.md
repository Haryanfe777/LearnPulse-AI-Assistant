# LearnPulse AI Teaching Assistant - Complete Deployment Documentation

## Overview

This document details the complete production deployment of the LearnPulse AI Teaching Assistant on Google Cloud Platform (GCP). The deployment includes both backend API and frontend UI, with enterprise-grade infrastructure for caching, monitoring, and CI/CD.

---

## Deployment Summary

| Component | Status | Details |
|-----------|--------|---------|
| Backend API | Deployed | Cloud Run service with Vertex AI integration |
| Frontend UI | Deployed | Streamlit app on Cloud Run |
| Database | Active | BigQuery for game logs analytics |
| Caching | Active | Memorystore Redis for session/response caching |
| CI/CD | Configured | Cloud Build pipeline for automatic deployments |
| Monitoring | Active | Uptime checks and alerting configured |
| Custom Domain | Pending | Instructions provided below |

---

## Service URLs

### Production Endpoints

| Service | URL |
|---------|-----|
| **Frontend (Web UI)** | https://learnpulse-frontend-kgbnk6qtsa-uc.a.run.app |
| **Backend API** | https://learnpulse-assistant-kgbnk6qtsa-uc.a.run.app |
| **API Documentation** | https://learnpulse-assistant-kgbnk6qtsa-uc.a.run.app/docs |
| **Health Check** | https://learnpulse-assistant-kgbnk6qtsa-uc.a.run.app/health |

---

## GCP Resources Created

### 1. Cloud Run Services

#### Backend API (`learnpulse-assistant`)
- **Image**: `us-central1-docker.pkg.dev/learnpulse-ai-assistant/learnpulse-repo/learnpulse-assistant:v1.1`
- **Memory**: 512Mi
- **CPU**: 1
- **Region**: us-central1
- **Service Account**: `learnpulse-ai@learnpulse-ai-assistant.iam.gserviceaccount.com`
- **VPC Connector**: `learnpulse-connector` (for Redis access)

#### Frontend UI (`learnpulse-frontend`)
- **Image**: `us-central1-docker.pkg.dev/learnpulse-ai-assistant/learnpulse-repo/learnpulse-frontend:v1.0`
- **Memory**: 512Mi
- **CPU**: 1
- **Region**: us-central1
- **Environment Variables**:
  - `API_URL`: Points to backend API URL

### 2. Artifact Registry

- **Repository**: `learnpulse-repo`
- **Location**: `us-central1-docker.pkg.dev/learnpulse-ai-assistant/learnpulse-repo`
- **Images**:
  - `learnpulse-assistant:v1.0`, `v1.1`, `latest`
  - `learnpulse-frontend:v1.0`, `latest`

### 3. BigQuery

- **Dataset**: `learnpulse_data`
- **Table**: `game_logs`
- **Schema**:
  - `student_id` (INTEGER)
  - `student_name` (STRING)
  - `class_id` (STRING)
  - `challenge_name` (STRING)
  - `concept` (STRING)
  - `attempts` (INTEGER)
  - `success_rate` (FLOAT)
  - `interaction_accuracy` (FLOAT)
  - `avg_time_spent_min` (FLOAT)
  - `streak_days` (INTEGER)
  - `language_preference` (STRING)
  - `motivation_score` (FLOAT)
  - `feedback_notes` (STRING)
  - `difficulty_level` (STRING)
  - `retry_rate` (FLOAT)
  - `peer_rank` (INTEGER)
  - `week_number` (INTEGER)
- **Records**: 200 rows of mock data

### 4. Memorystore Redis

- **Instance Name**: `learnpulse-cache`
- **Tier**: Basic
- **Size**: 1 GB
- **Region**: us-central1
- **Host**: `10.182.54.211`
- **Port**: `6379`
- **Purpose**: Session management and response caching
- **Status**: Instance created, VPC connector ready

**Note**: The backend currently uses fallback in-memory caching. To enable Memorystore Redis:

```bash
gcloud run services update learnpulse-assistant \
  --vpc-connector=learnpulse-connector \
  --update-env-vars="REDIS_HOST=10.182.54.211,REDIS_PORT=6379" \
  --region=us-central1
```

If you encounter startup timeouts, increase the startup probe timeout or check container health.

### 5. VPC Connector

- **Name**: `learnpulse-connector`
- **Region**: us-central1
- **IP Range**: `10.8.0.0/28`
- **Purpose**: Allows Cloud Run to access Memorystore Redis

### 6. Secret Manager

- **Secret**: `jwt-secret-key`
- **Purpose**: Secure storage for JWT authentication secret
- **Access**: `learnpulse-ai` service account

### 7. Cloud Storage Buckets

- **Build Staging**: `learnpulse-build-staging-2026`
- **Purpose**: Cloud Build source staging

---

## CI/CD Pipeline

### Cloud Build Configuration

The `cloudbuild.yaml` file configures automatic deployment on code push:

```yaml
Steps:
1. Build Backend Docker Image
2. Build Frontend Docker Image
3. Push Backend to Artifact Registry
4. Push Frontend to Artifact Registry
5. Deploy Backend to Cloud Run
6. Get Backend URL
7. Deploy Frontend to Cloud Run (with backend URL)
```

### Setting Up GitHub Trigger

To enable automatic deployments on GitHub push:

1. Go to [Cloud Build Triggers](https://console.cloud.google.com/cloud-build/triggers?project=learnpulse-ai-assistant)

2. Click "Connect Repository"

3. Select "GitHub" and authenticate

4. Select repository: `Haryanfe777/LearnPulse-AI-Assistant`

5. Create trigger with these settings:
   - **Name**: `deploy-on-push`
   - **Event**: Push to branch
   - **Branch**: `^main$`
   - **Configuration**: Cloud Build configuration file
   - **Location**: `/cloudbuild.yaml`

### Manual Deployment

To manually deploy changes:

```bash
# Build and push backend
docker build -t us-central1-docker.pkg.dev/learnpulse-ai-assistant/learnpulse-repo/learnpulse-assistant:v1.2 .
docker push us-central1-docker.pkg.dev/learnpulse-ai-assistant/learnpulse-repo/learnpulse-assistant:v1.2

# Deploy backend
gcloud run deploy learnpulse-assistant \
  --image=us-central1-docker.pkg.dev/learnpulse-ai-assistant/learnpulse-repo/learnpulse-assistant:v1.2 \
  --region=us-central1

# Build and push frontend
docker build -f Dockerfile.streamlit -t us-central1-docker.pkg.dev/learnpulse-ai-assistant/learnpulse-repo/learnpulse-frontend:v1.1 .
docker push us-central1-docker.pkg.dev/learnpulse-ai-assistant/learnpulse-repo/learnpulse-frontend:v1.1

# Deploy frontend
gcloud run deploy learnpulse-frontend \
  --image=us-central1-docker.pkg.dev/learnpulse-ai-assistant/learnpulse-repo/learnpulse-frontend:v1.1 \
  --region=us-central1
```

---

## Monitoring & Alerting

### Uptime Checks

| Check Name | Target | Frequency |
|------------|--------|-----------|
| `LearnPulse-Backend-Health` | `/health` endpoint | Every 1 minute |
| `LearnPulse-Frontend-Health` | `/_stcore/health` endpoint | Every 1 minute |

### Viewing Dashboards

1. Go to [Cloud Monitoring](https://console.cloud.google.com/monitoring?project=learnpulse-ai-assistant)
2. Navigate to "Dashboards" > "Cloud Run"
3. View metrics for both services

### Key Metrics to Monitor

- **Request Count**: Total requests per service
- **Latency**: P50, P95, P99 response times
- **Error Rate**: 4xx and 5xx responses
- **Instance Count**: Auto-scaling behavior
- **Memory/CPU Utilization**: Resource consumption

### Setting Up Email Alerts

1. Go to [Alerting](https://console.cloud.google.com/monitoring/alerting?project=learnpulse-ai-assistant)
2. Click "Edit Notification Channels"
3. Add email address(es) for alerts
4. Create alert policy linking to uptime checks

---

## Custom Domain Configuration

To add a custom domain (e.g., `app.learnpulse.ai`):

### Step 1: Verify Domain Ownership

```bash
gcloud domains verify YOUR_DOMAIN.com
```

### Step 2: Map Domain to Frontend

```bash
gcloud run domain-mappings create \
  --service=learnpulse-frontend \
  --domain=app.YOUR_DOMAIN.com \
  --region=us-central1
```

### Step 3: Map Domain to API (optional)

```bash
gcloud run domain-mappings create \
  --service=learnpulse-assistant \
  --domain=api.YOUR_DOMAIN.com \
  --region=us-central1
```

### Step 4: Update DNS Records

Add the following DNS records at your domain registrar:

| Type | Name | Value |
|------|------|-------|
| CNAME | app | ghs.googlehosted.com |
| CNAME | api | ghs.googlehosted.com |

**Note**: SSL certificates are automatically provisioned by Google.

---

## Environment Variables

### Backend Service

| Variable | Description | Value |
|----------|-------------|-------|
| `ENVIRONMENT` | Deployment environment | `production` |
| `PROJECT_ID` | GCP project ID | `learnpulse-ai-assistant` |
| `REGION` | GCP region | `us-central1` |
| `BQ_DATASET` | BigQuery dataset | `learnpulse_data` |
| `BQ_TABLE` | BigQuery table | `game_logs` |
| `DEBUG` | Debug mode | `false` |
| `REDIS_HOST` | Redis IP address | `10.182.54.211` |
| `REDIS_PORT` | Redis port | `6379` |
| `JWT_SECRET_KEY` | JWT secret (from Secret Manager) | (auto-injected) |

### Frontend Service

| Variable | Description | Value |
|----------|-------------|-------|
| `API_URL` | Backend API URL | `https://learnpulse-assistant-kgbnk6qtsa-uc.a.run.app` |

---

## Security Configuration

### Service Account Permissions

The `learnpulse-ai` service account has:
- `roles/bigquery.admin` - BigQuery access
- `roles/secretmanager.secretAccessor` - Secret Manager access
- `roles/serviceusage.serviceUsageConsumer` - API access
- `roles/aiplatform.user` - Vertex AI access (implicit)

### Cloud Build Service Account Permissions

The Cloud Build service account (`517662876246@cloudbuild.gserviceaccount.com`) has:
- `roles/run.admin` - Deploy to Cloud Run
- `roles/secretmanager.secretAccessor` - Access secrets
- `roles/storage.admin` - Artifact Registry access
- `roles/iam.serviceAccountUser` - Act as learnpulse-ai SA

### Authentication

- JWT-based authentication for protected endpoints
- Demo mode enabled for unauthenticated access to data endpoints
- Production endpoints require valid JWT tokens

---

## Updating Data

### Update BigQuery Data

To update the game logs data:

```python
# Run the load script with new data
python scripts/load_to_bigquery.py

# Or use bq command line
bq load --replace --source_format=CSV \
  learnpulse_data.game_logs \
  mock_data/mock_game_logs.csv \
  student_id:INTEGER,student_name:STRING,...
```

### Schema Modifications

1. Update the CSV file with new columns
2. Update `scripts/load_to_bigquery.py` with new schema
3. Run the load script with `--replace` flag

---

## Troubleshooting

### Common Issues

#### 1. Service Not Responding
```bash
# Check service logs
gcloud run services logs read learnpulse-assistant --region=us-central1

# Check service status
gcloud run services describe learnpulse-assistant --region=us-central1
```

#### 2. Redis Connection Failed
- Verify VPC connector is attached to service
- Check Redis instance is in `READY` state
- Verify IP address is correct

#### 3. BigQuery Errors
```bash
# Verify table exists
bq show learnpulse_data.game_logs

# Check service account permissions
gcloud projects get-iam-policy learnpulse-ai-assistant
```

#### 4. Build Failures
```bash
# Check Cloud Build history
gcloud builds list --project=learnpulse-ai-assistant

# View specific build logs
gcloud builds log BUILD_ID
```

---

## Cost Estimation

### Monthly Costs (Estimated)

| Service | Estimated Cost |
|---------|----------------|
| Cloud Run (2 services) | $5-20/month (depends on traffic) |
| Memorystore Redis (1GB) | ~$35/month |
| BigQuery | <$1/month (small dataset) |
| Artifact Registry | <$1/month |
| Secret Manager | <$1/month |
| Monitoring | Free tier |
| **Total** | **~$45-60/month** |

### Cost Optimization Tips

1. Set `min-instances=0` for Cloud Run (already configured)
2. Use Basic tier Redis (already configured)
3. Enable BigQuery slot reservations if queries increase
4. Delete unused images from Artifact Registry periodically

---

## Next Steps

1. **Custom Domain**: Register and configure your domain following the instructions above
2. **Email Alerts**: Set up notification channels in Cloud Monitoring
3. **Load Testing**: Test with realistic traffic before public launch
4. **Backup Strategy**: Consider BigQuery export schedules
5. **Staging Environment**: Create a staging Cloud Run service for testing

---

## Files Created/Modified

### New Files
- `Dockerfile.streamlit` - Frontend container configuration
- `requirements-streamlit.txt` - Frontend Python dependencies
- `monitoring/uptime-check-backend.json` - Monitoring configuration
- `monitoring/alert-policy.json` - Alert configuration
- `DEPLOYMENT_COMPLETE.md` - This documentation

### Modified Files
- `app_streamlit.py` - Added env var for API URL
- `.dockerignore` - Added streamlit requirements exclusion
- `cloudbuild.yaml` - Updated for dual-service CI/CD

---

## Contact & Support

For issues with this deployment:
1. Check Cloud Run logs first
2. Review monitoring dashboards
3. Consult GCP documentation

---

*Documentation generated: February 5, 2026*
*Deployment Region: us-central1*
*Project ID: learnpulse-ai-assistant*

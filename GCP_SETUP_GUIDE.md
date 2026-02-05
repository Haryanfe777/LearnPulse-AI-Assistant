# GCP Setup Guide for LearnPulse AI Instructor Assistant

Complete step-by-step guide to configure Google Cloud Platform for production deployment.

---

## Table of Contents
1. [Prerequisites](#1-prerequisites)
2. [GCP Project Setup](#2-gcp-project-setup)
3. [Enable Required APIs](#3-enable-required-apis)
4. [Service Account Creation](#4-service-account-creation)
5. [Local Development Credentials](#5-local-development-credentials)
6. [Data Loading to GCP](#6-data-loading-to-gcp)
7. [Cloud Run Deployment](#7-cloud-run-deployment)
8. [Verification & Testing](#8-verification--testing)

---

## 1. Prerequisites

### Install Required Tools

```bash
# Install Google Cloud SDK
# Download from: https://cloud.google.com/sdk/docs/install

# Verify installation
gcloud --version

# Install Docker (for Cloud Run)
# Download from: https://www.docker.com/products/docker-desktop
```

### Create a Google Cloud Account
1. Go to https://console.cloud.google.com/
2. Sign in with your Google account
3. Accept terms of service

---

## 2. GCP Project Setup

### Step 2.1: Create a New Project

```bash
# Set your project ID (must be globally unique)
PROJECT_ID="learnpulse-ai-assistant"

# Create the project
gcloud projects create $PROJECT_ID --name="LearnPulse AI Assistant"

# Set as default project
gcloud config set project $PROJECT_ID
```

**Or via Console:**
1. Go to https://console.cloud.google.com/projectcreate
2. Enter project name: `LearnPulse AI Assistant`
3. Note the Project ID (e.g., `learnpulse-ai-assistant`)
4. Click "Create"

### Step 2.2: Enable Billing

1. Go to https://console.cloud.google.com/billing
2. Link a billing account to your project
3. **Note:** Vertex AI requires billing enabled

### Step 2.3: Set Default Region

```bash
# Set your preferred region (europe-west9 for France, us-central1 for US)
gcloud config set compute/region europe-west9
```

---

## 3. Enable Required APIs

### Step 3.1: Enable All Required APIs

```bash
# Enable APIs (run all commands)
gcloud services enable aiplatform.googleapis.com          # Vertex AI
gcloud services enable bigquery.googleapis.com            # BigQuery (data storage)
gcloud services enable storage.googleapis.com             # Cloud Storage
gcloud services enable run.googleapis.com                 # Cloud Run
gcloud services enable cloudbuild.googleapis.com          # Cloud Build
gcloud services enable secretmanager.googleapis.com       # Secret Manager
gcloud services enable logging.googleapis.com             # Cloud Logging
gcloud services enable monitoring.googleapis.com          # Cloud Monitoring
gcloud services enable redis.googleapis.com               # Memorystore Redis
```

**Or enable via Console:**
1. Go to https://console.cloud.google.com/apis/library
2. Search and enable each API:
   - Vertex AI API
   - BigQuery API
   - Cloud Storage API
   - Cloud Run Admin API
   - Cloud Build API
   - Secret Manager API
   - Cloud Logging API
   - Cloud Monitoring API

---

## 4. Service Account Creation

### Step 4.1: Create Service Account

```bash
# Create service account
gcloud iam service-accounts create learnpulse-ai \
    --display-name="LearnPulse AI Service Account" \
    --description="Service account for LearnPulse AI Instructor Assistant"

# Get the service account email
SA_EMAIL="learnpulse-ai@${PROJECT_ID}.iam.gserviceaccount.com"
echo "Service Account: $SA_EMAIL"
```

### Step 4.2: Grant Required Roles

```bash
PROJECT_ID="learnpulse-ai-assistant"
SA_EMAIL="learnpulse-ai@${PROJECT_ID}.iam.gserviceaccount.com"

# Vertex AI User (for Gemini API)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/aiplatform.user"

# BigQuery Data Viewer (read game logs)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/bigquery.dataViewer"

# BigQuery Job User (run queries)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/bigquery.jobUser"

# Cloud Storage Object Viewer (read files)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/storage.objectViewer"

# Secret Manager Accessor (read secrets)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/secretmanager.secretAccessor"

# Logging Writer (write logs)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/logging.logWriter"
```

### Step 4.3: Create Service Account Key (Local Development Only)

```bash
# Create key file for local development
gcloud iam service-accounts keys create ./credentials/service-account.json \
    --iam-account=$SA_EMAIL

# IMPORTANT: Never commit this file to git!
# Add to .gitignore: credentials/
```

---

## 5. Local Development Credentials

### Option A: Application Default Credentials (Recommended for Development)

```bash
# Login with your Google account
gcloud auth application-default login

# This opens a browser for authentication
# Credentials are saved to: ~/.config/gcloud/application_default_credentials.json
```

### Option B: Service Account Key File

```bash
# Set environment variable pointing to key file
export GOOGLE_APPLICATION_CREDENTIALS="./credentials/service-account.json"

# Or add to .env file:
# GOOGLE_APPLICATION_CREDENTIALS=./credentials/service-account.json
```

### Update .env File

```env
# .env file for local development
PROJECT_ID=learnpulse-ai-assistant
REGION=europe-west9
JWT_SECRET_KEY=your-secure-secret-key-here

# For local dev with service account file (optional)
# GOOGLE_APPLICATION_CREDENTIALS=./credentials/service-account.json

# Database columns
STUDENT_COL=student_name
CLASS_COL=class_id
SCORE_COL=score
DATE_COL=date
```

---

## 6. Data Loading to GCP

### Option A: BigQuery (Recommended for Production)

#### Step 6.1: Create BigQuery Dataset

```bash
# Create dataset
bq mk --dataset \
    --description "LearnPulse AI game logs and analytics" \
    --location europe-west9 \
    ${PROJECT_ID}:learnpulse_data
```

#### Step 6.2: Create Table Schema

```bash
# Create table with schema
bq mk --table \
    ${PROJECT_ID}:learnpulse_data.game_logs \
    student_id:INTEGER,student_name:STRING,class_id:STRING,challenge_name:STRING,score:FLOAT,interaction_accuracy:FLOAT,time_spent_seconds:INTEGER,attempts:INTEGER,completed:BOOLEAN,date:DATE,language_preference:STRING
```

#### Step 6.3: Load CSV Data

```bash
# Upload local CSV to BigQuery
bq load \
    --source_format=CSV \
    --skip_leading_rows=1 \
    ${PROJECT_ID}:learnpulse_data.game_logs \
    ./mock_data/mock_game_logs.csv \
    student_id:INTEGER,student_name:STRING,class_id:STRING,challenge_name:STRING,score:FLOAT,interaction_accuracy:FLOAT,time_spent_seconds:INTEGER,attempts:INTEGER,completed:BOOLEAN,date:DATE,language_preference:STRING
```

#### Step 6.4: Verify Data

```bash
# Query to verify data loaded
bq query --use_legacy_sql=false \
    "SELECT COUNT(*) as total_records, COUNT(DISTINCT student_name) as unique_students 
     FROM \`${PROJECT_ID}.learnpulse_data.game_logs\`"
```

### Option B: Cloud Storage (For Raw Files)

#### Step 6.1: Create Storage Bucket

```bash
# Create bucket (name must be globally unique)
BUCKET_NAME="${PROJECT_ID}-data"
gcloud storage buckets create gs://$BUCKET_NAME \
    --location=europe-west9 \
    --uniform-bucket-level-access
```

#### Step 6.2: Upload Data Files

```bash
# Upload CSV files
gcloud storage cp ./mock_data/mock_game_logs.csv gs://$BUCKET_NAME/game_logs/

# Upload knowledge base
gcloud storage cp ./knowledge/*.md gs://$BUCKET_NAME/knowledge/
```

#### Step 6.3: Verify Upload

```bash
# List uploaded files
gcloud storage ls gs://$BUCKET_NAME/
```

---

## 7. Cloud Run Deployment

> **IMPORTANT: Credentials on Cloud Run**
> 
> Cloud Run **automatically injects credentials** from the service account you assign to the service.
> 
> - **DO NOT** set `GOOGLE_APPLICATION_CREDENTIALS` in Cloud Run
> - **DO NOT** include service account JSON files in your Docker image
> - Simply assign the service account with `--service-account` flag
> 
> This is the GCP best practice for production deployments.

### Step 7.1: Build Docker Image

```bash
# Build and push to Google Container Registry
PROJECT_ID="learnpulse-ai-assistant"

# Build image
gcloud builds submit --tag gcr.io/$PROJECT_ID/learnpulse-assistant

# Or build locally and push
docker build -t gcr.io/$PROJECT_ID/learnpulse-assistant .
docker push gcr.io/$PROJECT_ID/learnpulse-assistant
```

### Step 7.2: Create Secrets in Secret Manager

```bash
# Store JWT secret
echo -n "your-production-jwt-secret-key" | \
    gcloud secrets create jwt-secret --data-file=-

# Grant service account access to secret
gcloud secrets add-iam-policy-binding jwt-secret \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/secretmanager.secretAccessor"
```

### Step 7.3: Deploy to Cloud Run

```bash
# Deploy with environment variables
gcloud run deploy learnpulse-assistant \
    --image gcr.io/$PROJECT_ID/learnpulse-assistant \
    --platform managed \
    --region europe-west9 \
    --service-account $SA_EMAIL \
    --set-env-vars "PROJECT_ID=$PROJECT_ID,REGION=europe-west9,ENVIRONMENT=production" \
    --set-secrets "JWT_SECRET_KEY=jwt-secret:latest" \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --min-instances 0 \
    --max-instances 10 \
    --timeout 300
```

### Step 7.4: Get Service URL

```bash
# Get the deployed URL
gcloud run services describe learnpulse-assistant \
    --platform managed \
    --region europe-west9 \
    --format 'value(status.url)'
```

---

## 8. Verification & Testing

### Step 8.1: Test Vertex AI Access

```bash
# Test that Vertex AI is accessible
gcloud ai models list --region=europe-west9
```

### Step 8.2: Test API Endpoints

```bash
# Get your Cloud Run URL
SERVICE_URL=$(gcloud run services describe learnpulse-assistant \
    --platform managed --region europe-west9 --format 'value(status.url)')

# Test health endpoint
curl $SERVICE_URL/health

# Test meta endpoint
curl $SERVICE_URL/meta

# Test chat endpoint
curl -X POST $SERVICE_URL/chat \
    -H "Content-Type: application/json" \
    -d '{"message": "Hello, how can you help me?", "session_id": null}'
```

### Step 8.3: Monitor Logs

```bash
# View Cloud Run logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=learnpulse-assistant" \
    --limit 50 \
    --format "table(timestamp, textPayload)"

# Or use Cloud Console
# https://console.cloud.google.com/logs
```

---

## Quick Reference: Environment Variables

| Variable | Local Dev | Cloud Run | Notes |
|----------|-----------|-----------|-------|
| `PROJECT_ID` | `.env` file | `--set-env-vars` | Required |
| `REGION` | `.env` file | `--set-env-vars` | Required |
| `JWT_SECRET_KEY` | `.env` file | Secret Manager | Use Secret Manager in prod |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to JSON | **DO NOT SET** | Cloud Run auto-injects |
| `ENVIRONMENT` | `development` | `production` | Optional |

### Credentials Best Practice Summary

| Environment | How Credentials Work |
|-------------|---------------------|
| **Local Development** | Use service account JSON file via `GOOGLE_APPLICATION_CREDENTIALS` |
| **Cloud Run (Production)** | Automatic injection via `--service-account` flag. **Never set GOOGLE_APPLICATION_CREDENTIALS** |
| **Cloud Functions** | Same as Cloud Run - automatic injection |
| **GKE** | Use Workload Identity |

---

## Troubleshooting

### Permission Denied Errors

```bash
# Check current authentication
gcloud auth list

# Re-authenticate
gcloud auth application-default login

# Verify service account roles
gcloud projects get-iam-policy $PROJECT_ID \
    --flatten="bindings[].members" \
    --filter="bindings.members:$SA_EMAIL" \
    --format="table(bindings.role)"
```

### API Not Enabled Errors

```bash
# List enabled APIs
gcloud services list --enabled

# Enable specific API
gcloud services enable aiplatform.googleapis.com
```

### Quota Exceeded Errors

1. Go to https://console.cloud.google.com/iam-admin/quotas
2. Filter by the API showing errors
3. Request quota increase if needed

---

## Cost Optimization Tips

1. **Use Preemptible/Spot instances** for non-production workloads
2. **Set min-instances to 0** in Cloud Run to scale to zero when idle
3. **Use BigQuery on-demand pricing** for development (pay per query)
4. **Enable budget alerts** at https://console.cloud.google.com/billing/budgets

---

## Security Checklist

- [ ] Never commit service account keys to git
- [ ] Use Secret Manager for sensitive values in production
- [ ] Enable VPC Service Controls for sensitive data
- [ ] Set up Cloud Audit Logs
- [ ] Use least-privilege IAM roles
- [ ] Enable Cloud Armor for DDoS protection (if public)
- [ ] Set up Identity-Aware Proxy (IAP) for admin access

---

## Next Steps

1. Set up CI/CD with Cloud Build triggers
2. Configure custom domain with Cloud DNS
3. Set up monitoring dashboards in Cloud Monitoring
4. Implement backup strategy for BigQuery data
5. Set up Redis (Memorystore) for production caching

---

*Generated for LearnPulse AI Instructor Assistant*

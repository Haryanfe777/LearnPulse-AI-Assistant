#!/bin/bash
# Deployment script for LearnPulse AI Instructor Assistant on Google Cloud Platform
# Usage: ./deploy.sh [environment]
# Environments: staging, production

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-staging}
PROJECT_ID=$(gcloud config get-value project)
REGION="europe-west1"
SERVICE_NAME="teacher-assistant-${ENVIRONMENT}"
IMAGE_NAME="europe-west1-docker.pkg.dev/${PROJECT_ID}/teacher-assistant/api"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}LearnPulse AI Instructor Assistant - GCP Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Environment: ${ENVIRONMENT}"
echo "Project ID: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo ""

# Validate environment
if [[ "$ENVIRONMENT" != "staging" && "$ENVIRONMENT" != "production" ]]; then
    echo -e "${RED}Error: Environment must be 'staging' or 'production'${NC}"
    exit 1
fi

# Confirm production deployment
if [[ "$ENVIRONMENT" == "production" ]]; then
    echo -e "${YELLOW}⚠️  WARNING: You are deploying to PRODUCTION${NC}"
    read -p "Are you sure you want to continue? (yes/no): " confirm
    if [[ "$confirm" != "yes" ]]; then
        echo "Deployment cancelled"
        exit 0
    fi
fi

echo -e "${GREEN}Step 1: Running tests...${NC}"
pytest tests/ -v --cov=src --cov-report=term-missing --cov-fail-under=80
if [ $? -ne 0 ]; then
    echo -e "${RED}Tests failed! Deployment aborted.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Tests passed${NC}"
echo ""

echo -e "${GREEN}Step 2: Building Docker image...${NC}"
docker build -t ${IMAGE_NAME}:latest -t ${IMAGE_NAME}:$(git rev-parse --short HEAD) .
if [ $? -ne 0 ]; then
    echo -e "${RED}Docker build failed! Deployment aborted.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker image built${NC}"
echo ""

echo -e "${GREEN}Step 3: Pushing image to Artifact Registry...${NC}"
docker push ${IMAGE_NAME}:latest
docker push ${IMAGE_NAME}:$(git rev-parse --short HEAD)
echo -e "${GREEN}✓ Image pushed${NC}"
echo ""

echo -e "${GREEN}Step 4: Deploying to Cloud Run (${ENVIRONMENT})...${NC}"

# Get Redis IP from Memorystore
REDIS_HOST=$(gcloud redis instances describe teacher-assistant-redis \
    --region=${REGION} \
    --format="value(host)" 2>/dev/null || echo "localhost")

# Get Cloud SQL connection name
CLOUDSQL_CONNECTION=$(gcloud sql instances describe teacher-assistant-db \
    --format="value(connectionName)" 2>/dev/null || echo "")

# Deploy based on environment
if [[ "$ENVIRONMENT" == "staging" ]]; then
    # Staging: smaller resources, allow unauthenticated
    gcloud run deploy ${SERVICE_NAME} \
        --image=${IMAGE_NAME}:latest \
        --region=${REGION} \
        --platform=managed \
        --allow-unauthenticated \
        --memory=1Gi \
        --cpu=1 \
        --min-instances=0 \
        --max-instances=10 \
        --timeout=300 \
        --set-env-vars="ENVIRONMENT=staging,PROJECT_ID=${PROJECT_ID},REGION=${REGION},REDIS_HOST=${REDIS_HOST}" \
        --set-cloudsql-instances=${CLOUDSQL_CONNECTION} \
        --service-account=teacher-assistant-sa@${PROJECT_ID}.iam.gserviceaccount.com
else
    # Production: larger resources, require authentication
    gcloud run deploy ${SERVICE_NAME} \
        --image=${IMAGE_NAME}:$(git rev-parse --short HEAD) \
        --region=${REGION} \
        --platform=managed \
        --no-allow-unauthenticated \
        --memory=2Gi \
        --cpu=2 \
        --min-instances=1 \
        --max-instances=100 \
        --timeout=300 \
        --set-env-vars="ENVIRONMENT=production,PROJECT_ID=${PROJECT_ID},REGION=${REGION},REDIS_HOST=${REDIS_HOST}" \
        --set-cloudsql-instances=${CLOUDSQL_CONNECTION} \
        --service-account=teacher-assistant-sa@${PROJECT_ID}.iam.gserviceaccount.com
fi

if [ $? -ne 0 ]; then
    echo -e "${RED}Deployment failed!${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Deployed successfully${NC}"
echo ""

# Get service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --region=${REGION} \
    --format="value(status.url)")

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Service URL: ${SERVICE_URL}"
echo "Environment: ${ENVIRONMENT}"
echo "Git commit: $(git rev-parse --short HEAD)"
echo ""
echo "Next steps:"
echo "1. Test the health endpoint: curl ${SERVICE_URL}/health"
echo "2. View logs: gcloud run services logs read ${SERVICE_NAME} --region=${REGION}"
echo "3. Monitor: https://console.cloud.google.com/run/detail/${REGION}/${SERVICE_NAME}/metrics"
echo ""

if [[ "$ENVIRONMENT" == "production" ]]; then
    echo -e "${GREEN}✓ Production deployment successful!${NC}"
    echo -e "${YELLOW}Remember to:${NC}"
    echo "- Monitor error rates and latency"
    echo "- Check Cloud Logging for any issues"
    echo "- Notify team of deployment"
fi


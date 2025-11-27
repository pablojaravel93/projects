

# 0) Set project/region & enable APIs
gcloud config set project acqscale
REGION=us-central1

gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  bigquery.googleapis.com \
  storage.googleapis.com \
  cloudscheduler.googleapis.com

# 1) Create the project folder and app files
mkdir etl-job-details && cd etl-job-details

# main.py (one-shot ETL that exits cleanly)
cat > main.py << 'EOF'

    # Code goes here

EOF

# requirements.txt
cat > requirements.txt << 'EOF'
requests
google-cloud-storage
google-cloud-bigquery
pytz
EOF


# Dockerfile (runs once and exits)

cat > Dockerfile << 'EOF'
FROM python:3.11-slim

RUN pip install --no-cache-dir --upgrade pip
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["python", "main.py"] # Run the batch and exit (no web server)
EOF

# 2) Build and push the container (Artifact Registry)

PROJECT_ID=$(gcloud config get-value project)
gcloud artifacts repositories create cloud-run \
  --repository-format=docker \
  --location="$REGION" \
  --description="Containers for Cloud Run" \
  || true

# 2.1) Build and push with Cloud Build:

IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run/etl-job-details:latest"
gcloud builds submit --tag "$IMAGE"


# 3) Create (or update) the Cloud Run Job

gcloud run jobs create etl-hourly-leads-job \
  --image "$IMAGE" \
  --region "$REGION" \
  --tasks 1 \
  --max-retries 0 \
  --task-timeout 3600s \
  --memory 1Gi \
  --cpu 1 \
  --set-env-vars=GCS_BUCKET=my-etl-bucket \
  --set-env-vars=GCS_PREFIX=api_dumps \
  --set-env-vars=BQ_DATASET=phonexia_reports \
  --set-env-vars=BQ_TABLE=phonexa_summary_reports \
  --set-env-vars=BQ_LOCATION=US \
  || gcloud run jobs update etl-hourly-leads-job \
  --image "$IMAGE" \
  --region "$REGION" \
  --tasks 1 \
  --max-retries 0 \
  --task-timeout 3600s \
  --memory 1Gi \
  --cpu 1 \
  --set-env-vars=GCS_BUCKET=my-etl-bucket,GCS_PREFIX=api_dumps,BQ_DATASET=phonexia_reports,BQ_TABLE=stg_summarydate,BQ_LOCATION=US


# 4) IAM for the Job’s service account
SA_EMAIL=$(gcloud run jobs describe etl-daily-job --region "$REGION" --format="value(template.template.serviceAccount)")
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" --role="roles/storage.objectCreator"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" --role="roles/storage.objectViewer"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" --role="roles/bigquery.jobUser"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" --role="roles/bigquery.dataEditor"

# 5) Execute the job now (manual test) & read logs
gcloud run jobs execute etl-daily-job --region "$REGION" --wait
gcloud logs read "run.googleapis.com%2Fjob%2Fetl-daily-job" --limit 100

# 6) Schedule it daily with Cloud Scheduler (America/Bogota)
SCHED_SA="scheduler-invoker@$PROJECT_ID.iam.gserviceaccount.com"
gcloud iam service-accounts create scheduler-invoker --display-name="Scheduler Invoker" || true

API_URI="https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT_ID/jobs/etl-daily-job:run"
gcloud scheduler jobs create http etl-daily-schedule \
  --location "$REGION" \
  --schedule "0 6 * * *" \
  --time-zone "America/Bogota" \
  --http-method POST \
  --uri "$API_URI" \
  --oauth-service-account-email "$SCHED_SA" \
  --oauth-token-audience "https://$REGION-run.googleapis.com/"


# Run it ad-hoc
gcloud scheduler jobs run etl-daily-schedule --location "$REGION"




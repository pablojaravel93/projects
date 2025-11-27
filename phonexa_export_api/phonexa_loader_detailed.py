
cat > main.py << 'EOF'

import os
import io
import requests
from google.cloud import storage, bigquery
import hashlib
import datetime
import json
import sys
import pytz
from concurrent.futures import TimeoutError as FuturesTimeout

# ---- Config (use env vars in Cloud Run) ----
# Example values shown in the deploy step; keep these names to match your code.
# GCS_BUCKET = os.environ["GCS_BUCKET"]                  # e.g., my-staging-bucket
# GCS_PREFIX = os.environ.get("GCS_PREFIX", "api_dumps")           # folder/prefix
# BQ_DATASET = os.environ["BQ_DATASET"]                      # e.g., raw_zone
# BQ_TABLE = os.environ["BQ_TABLE"]                         # e.g., api_events
# BQ_LOCATION = os.environ.get("BQ_LOCATION", "US")

GCS_BUCKET = "phonexia_csv_reports"
GCS_PREFIX = ""           
BQ_DATASET = "staging"
BQ_TABLE = "stg_lead_details"
BQ_LOCATION = "US"

def get_report_url():
    signData = {
        'date': datetime.datetime.now().strftime('%d.%m.%Y'), # Current Date in format d.m.Y
        'userId': '1014', # Id of user assigned to API ID
        'component': 'lms', # One of Component list
        'menuItemId': 'report::lead::index', # one of menuItemId
        'category': '1' # one of Category List
    }

    signDataSorted = dict(sorted(signData.items()))

    signature = hashlib.md5(
        (hashlib.md5('|'.join(signDataSorted.values()).encode('utf-8')).hexdigest() + '|82272d81f6dc0caaa1830025cf').encode('utf-8')
    ).hexdigest()

    #set date parameter
    timezone = pytz.timezone('America/Los_Angeles')
    today = datetime.datetime.now(timezone).strftime("%m/%d/%Y")
    date_parameter = today+" 00:00:00 - "+today+" 23:59:59"

    #Report URL
    url = "https://cp-inst528-client.phonexa.com/export/api?menuItemId=report::lead::index&apiId=2872DEB47BAD420C9BF9B270C912DB1B&signature="+signature+"&component=lms&searchForm[creationDatetime]="+date_parameter    
    return url

def fetch_csv_stream(url: str):
    headers = {"Accept": "text/csv, application/octet-stream"}
    resp = requests.get(url, headers=headers, timeout=60, stream=True)
    resp.raise_for_status()
    return resp

def upload_to_gcs(resp) -> str:
    """Upload streamed CSV to GCS and return gs:// URI."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET)

    # Date-partitioned object path
    now = datetime.datetime.utcnow()
    date_path = now.strftime("%Y/%m/%d")
    filename = f"export_lead_details_{now.strftime('%Y%m%dT%H%M%S')}.csv"
    # blob_path = f"{GCS_PREFIX}/{date_path}/{filename}"
    blob_path = f"{filename}"
    blob = bucket.blob(blob_path)

    # Upload in chunks from the streaming response
    with blob.open("wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)

    return f"gs://{GCS_BUCKET}/{blob_path}"

def load_to_bigquery(gs_uri: str):
    bq = bigquery.Client(location=BQ_LOCATION)
    table_id = f"{bq.project}.{BQ_DATASET}.{BQ_TABLE}"

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        # autodetect=False if BQ_SCHEMA else True,
        # schema=BQ_SCHEMA if BQ_SCHEMA else None,
        # autodetect=True,
        # schema= None,
        skip_leading_rows=2,
        field_delimiter=",",
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE_DATA,
        encoding="UTF-8",
        allow_quoted_newlines=True,
        max_bad_records=0,
    )

    load_job = bq.load_table_from_uri(gs_uri, table_id, job_config=job_config)
    result = load_job.result()  # wait for completion
    return result

def run_pipeline():
    report_url = get_report_url()
    resp = fetch_csv_stream(report_url)
    gs_uri = upload_to_gcs(resp)
    result = load_to_bigquery(gs_uri)
    return {
        "status": "ok",
        "gcs_uri": gs_uri,
        "output_rows": getattr(result, "output_rows", None),
        "table": f"{BQ_DATASET}.{BQ_TABLE}",
    }


if __name__ == "__main__":
    try:
        out = run_pipeline()
        print(json.dumps(out))
        sys.exit(0)  # success -> Job stops
    except Exception as e:
        print(json.dumps({"status": "error", "error": str(e)}))
        sys.exit(1)  # failure -> Job stops with non-zero
EOF
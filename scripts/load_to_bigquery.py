#!/usr/bin/env python3
"""
BigQuery Data Loader for LearnPulse AI

This script loads the mock game logs CSV to BigQuery for production use.
It creates the dataset and table if they don't exist, and supports
incremental updates.

Usage:
    python scripts/load_to_bigquery.py
    
Environment:
    Set GOOGLE_APPLICATION_CREDENTIALS for local development
    Cloud Run uses automatic credentials
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from google.cloud import bigquery
from google.api_core.exceptions import Conflict, NotFound
import pandas as pd


# Configuration
PROJECT_ID = os.getenv("PROJECT_ID", "learnpulse-ai-assistant")
DATASET_ID = "learnpulse_data"
TABLE_ID = "game_logs"
LOCATION = "US"

# Full table reference
FULL_TABLE_ID = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

# Schema definition matching our CSV
SCHEMA = [
    bigquery.SchemaField("student_id", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("student_name", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("class_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("challenge_name", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("concept", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("attempts", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("success_rate", "FLOAT", mode="REQUIRED"),
    bigquery.SchemaField("interaction_accuracy", "FLOAT", mode="REQUIRED"),
    bigquery.SchemaField("avg_time_spent_min", "FLOAT", mode="REQUIRED"),
    bigquery.SchemaField("streak_days", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("language_preference", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("motivation_score", "FLOAT", mode="REQUIRED"),
    bigquery.SchemaField("feedback_notes", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("difficulty_level", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("retry_rate", "FLOAT", mode="REQUIRED"),
    bigquery.SchemaField("peer_rank", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("week_number", "INTEGER", mode="REQUIRED"),
]


def create_dataset(client: bigquery.Client) -> None:
    """Create the dataset if it doesn't exist."""
    dataset_ref = bigquery.Dataset(f"{PROJECT_ID}.{DATASET_ID}")
    dataset_ref.location = LOCATION
    dataset_ref.description = "LearnPulse AI student activity data"
    
    try:
        client.create_dataset(dataset_ref, exists_ok=True)
        print(f"[OK] Dataset '{DATASET_ID}' ready")
    except Exception as e:
        print(f"[WARN] Dataset creation: {e}")


def create_table(client: bigquery.Client) -> bigquery.Table:
    """Create the table with schema if it doesn't exist."""
    table_ref = bigquery.Table(FULL_TABLE_ID, schema=SCHEMA)
    table_ref.description = "Student game log activity data"
    
    try:
        table = client.create_table(table_ref)
        print(f"[OK] Table '{TABLE_ID}' created")
        return table
    except Conflict:
        print(f"[OK] Table '{TABLE_ID}' already exists")
        return client.get_table(FULL_TABLE_ID)


def load_csv_to_bigquery(client: bigquery.Client, csv_path: str, mode: str = "WRITE_TRUNCATE") -> int:
    """
    Load CSV data to BigQuery table.
    
    Args:
        client: BigQuery client
        csv_path: Path to CSV file
        mode: WRITE_TRUNCATE (replace) or WRITE_APPEND (add)
        
    Returns:
        Number of rows loaded
    """
    job_config = bigquery.LoadJobConfig(
        schema=SCHEMA,
        skip_leading_rows=1,  # Skip header
        source_format=bigquery.SourceFormat.CSV,
        write_disposition=mode,
        allow_quoted_newlines=True,
    )
    
    print(f"[LOAD] Loading data from {csv_path}...")
    
    with open(csv_path, "rb") as source_file:
        job = client.load_table_from_file(
            source_file,
            FULL_TABLE_ID,
            job_config=job_config,
        )
    
    # Wait for job to complete
    job.result()
    
    # Get row count
    table = client.get_table(FULL_TABLE_ID)
    print(f"[OK] Loaded {table.num_rows} rows to {FULL_TABLE_ID}")
    
    return table.num_rows


def verify_data(client: bigquery.Client) -> None:
    """Run verification queries on the loaded data."""
    print("\n[VERIFY] Verifying data...")
    
    # Query 1: Row count and unique students
    query1 = f"""
    SELECT 
        COUNT(*) as total_rows,
        COUNT(DISTINCT student_name) as unique_students,
        COUNT(DISTINCT class_id) as unique_classes,
        COUNT(DISTINCT concept) as unique_concepts
    FROM `{FULL_TABLE_ID}`
    """
    
    result = client.query(query1).result()
    for row in result:
        print(f"   Total rows: {row.total_rows}")
        print(f"   Unique students: {row.unique_students}")
        print(f"   Unique classes: {row.unique_classes}")
        print(f"   Unique concepts: {row.unique_concepts}")
    
    # Query 2: Sample data
    query2 = f"""
    SELECT student_name, class_id, concept, success_rate
    FROM `{FULL_TABLE_ID}`
    LIMIT 5
    """
    
    print("\n   Sample data:")
    result = client.query(query2).result()
    for row in result:
        print(f"   - {row.student_name} ({row.class_id}): {row.concept} - {row.success_rate:.0%}")
    
    # Query 3: Student performance summary
    query3 = f"""
    SELECT 
        student_name,
        ROUND(AVG(success_rate) * 100, 1) as avg_success_rate,
        COUNT(*) as total_sessions
    FROM `{FULL_TABLE_ID}`
    GROUP BY student_name
    ORDER BY avg_success_rate DESC
    LIMIT 5
    """
    
    print("\n   Top 5 students by success rate:")
    result = client.query(query3).result()
    for row in result:
        print(f"   - {row.student_name}: {row.avg_success_rate}% ({row.total_sessions} sessions)")


def main():
    """Main entry point."""
    print("=" * 60)
    print("LearnPulse AI - BigQuery Data Loader")
    print("=" * 60)
    print(f"\nProject: {PROJECT_ID}")
    print(f"Dataset: {DATASET_ID}")
    print(f"Table: {TABLE_ID}")
    print()
    
    # Initialize client
    client = bigquery.Client(project=PROJECT_ID)
    
    # Step 1: Create dataset
    create_dataset(client)
    
    # Step 2: Create table
    create_table(client)
    
    # Step 3: Load CSV data
    csv_path = Path(__file__).parent.parent / "mock_data" / "mock_game_logs.csv"
    if not csv_path.exists():
        print(f"[ERROR] CSV file not found: {csv_path}")
        sys.exit(1)
    
    row_count = load_csv_to_bigquery(client, str(csv_path))
    
    # Step 4: Verify data
    verify_data(client)
    
    print("\n" + "=" * 60)
    print("[SUCCESS] Data loading complete!")
    print("=" * 60)
    print(f"\nBigQuery table: {FULL_TABLE_ID}")
    print(f"Total rows: {row_count}")
    print("\nTo update data later, run this script again.")
    print("Use WRITE_APPEND mode for incremental updates.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

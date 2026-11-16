"""Airflow DAG: refresh the cost-of-living warehouse and the public tool's data file.

Each ingest task asks Statistics Canada for the table's release time and downloads only when it changed,
so most daily runs finish in seconds. dbt then rebuilds the models and runs every data test; a failing
test fails the run before anything is exported.

The tasks shell out to the project's own Python (COL_PYTHON) so Airflow and dbt can live in separate
environments, which avoids pinning one to the other's dependencies.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG

try:  # Airflow 3 moved the bash operator into the standard provider
    from airflow.providers.standard.operators.bash import BashOperator
except ImportError:  # Airflow 2.x
    from airflow.operators.bash import BashOperator

PROJECT_DIR = os.environ.get("COL_PROJECT_DIR", str(Path(__file__).resolve().parents[1]))
PYTHON = os.environ.get("COL_PYTHON", "python")
RUN = f'cd "{PROJECT_DIR}" && "{PYTHON}" -m pipeline.run'
TABLES = ["rent", "food_prices", "wages"]

with DAG(
    dag_id="canada_cost_of_living",
    description="Incremental Statistics Canada ingest, dbt build with data tests, export for the public tool",
    start_date=datetime(2026, 1, 1),
    schedule="17 14 * * *",          # 09:17 Eastern, after Statistics Canada's 08:30 release
    catchup=False,
    max_active_runs=1,
    default_args={"owner": "amir", "retries": 2, "retry_delay": timedelta(minutes=10)},
    tags=["statcan", "dbt", "portfolio"],
) as dag:
    ingest = [
        BashOperator(task_id=f"ingest_{t}", bash_command=f"{RUN} ingest --table {t}", append_env=True)
        for t in TABLES
    ]
    build = BashOperator(task_id="dbt_build_and_test", bash_command=f"{RUN} build", append_env=True)
    export = BashOperator(task_id="export_site_data", bash_command=f"{RUN} export", append_env=True)

    # The ingest tasks share one manifest file, so they run one after another.
    ingest[0] >> ingest[1] >> ingest[2] >> build >> export

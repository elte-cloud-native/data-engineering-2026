"""A small Airflow DAG coordinating the prepared sensor processing code."""

import sys
from datetime import datetime, timezone

from airflow.sdk import dag, task


sys.path.insert(0, "/opt/airflow/lab/starter")
import process_sensors  # noqa: E402


@dag(
    dag_id="sensor_processing_lab",
    start_date=datetime(2025, 9, 2, tzinfo=timezone.utc),
    schedule=None,
    catchup=False,
    tags=["lab05"],
)
def sensor_processing_lab():
    @task(task_id="check_input")
    def check_input_task():
        process_sensors.check_input()

    @task(task_id="process_sensors")
    def process_task():
        process_sensors.process_file()

    @task(task_id="check_outputs")
    def check_outputs_task():
        process_sensors.check_outputs()

    check_input_task() >> process_task() >> check_outputs_task()


sensor_processing_lab()

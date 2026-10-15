# Lab 05 — Batch data processing with Airflow

Lab 03 showed how raw data lands in Bronze; Lab 04 showed that Kafka can sit
between event producers and consumers. This lab starts from a **prepared
Bronze-like CSV** of sensor events. We process it into clean records and
rejected records, then use Airflow to run and observe the same processing
steps. You do not need to complete Lab 04 to run this exercise.

The main question is: **what do we do when source data is not immediately
usable?** We will check it, apply a small transformation, keep problematic
rows with a reason, and verify the result. The Python and Airflow files are
prepared helpers, **not programming assignments**.

The processing part works locally with Python 3.10+ and no extra packages.
Airflow is a separate, local Docker demonstration; no Azure subscription,
public server, or connection string is required. As in the Kafka lab, Docker
gives everyone the same prepared local runtime without requiring a manual
installation of the demonstrated platform.

## Part 1 — Inspect the prepared input

From this `lab 05` folder, display the source file:

```bash
head -n 11 data/sensors.csv
```

It represents a small raw sensor export already available to the data
platform. The first five event IDs match the *example* sensor events from
Lab 04; the file is provided independently so this lab does not depend on a
running Kafka broker. The timestamps are fictional fixed examples.

The planned processing rules are:

- Keep a row only if its identifiers and timestamp are usable and its
  temperature is a number from −50°C to 100°C.
- Keep only the first **accepted** row for an `event_id`; send a later
  duplicate to the rejected output.
- For accepted rows, standardize the Celsius number and calculate Fahrenheit.
- Preserve rejected rows separately with a reason; do not silently repair or
  discard them. The original `data/sensors.csv` remains unchanged.

Questions: Which rows seem usable? Which ones have a missing, malformed,
out-of-range or duplicate value? Why might silently replacing a bad
temperature with an average be misleading?

## Part 2 — Run and inspect the processing job

Run the prepared helper. You do not need to edit its Python code:

```bash
python3 starter/process_sensors.py
```

It creates three outputs under the ignored `output/` practice folder:

```text
output/silver/sensors_clean.csv          accepted, transformed rows
output/quarantine/sensors_rejected.csv  original rejected rows + reason
output/summary.json                     row counts and rejection reasons
```

Inspect them:

```bash
cat output/summary.json
head -n 6 output/silver/sensors_clean.csv
head -n 6 output/quarantine/sensors_rejected.csv
```

Expect **10 input rows: 5 clean and 5 rejected**. In the clean file, the
first temperature is `21.5°C = 70.7°F`. The rejected file contains one
reason for each bad row. This is a simple **Silver** output and a
**quarantine** output, not a claim that every production pipeline must use
these exact folder names.

Run the helper again:

```bash
python3 starter/process_sensors.py
```

The derived output files are deliberately recomputed
from the unchanged source, so a rerun gives the same contents rather than
adding duplicate clean rows. We can do this because these are derived
outputs; we are **not** overwriting the raw input.

Questions: Which step is validation, which step is transformation, and which
step is the quality check? Why keep the rejected rows rather than just
deleting them? What does `summary.json` let you observe?

## Part 3 — See a failure before any output is changed

The second prepared file has a missing `temperature_c` column. Ask the same
helper to process it:

```bash
python3 starter/process_sensors.py data/sensors_bad_header.csv
```

It should report `PROCESSING FAILED: Expected CSV header ...`. The input
check stops the job before it rewrites the previous outputs. Now run the
normal command again and see that it succeeds:

```bash
python3 starter/process_sensors.py
```

Question: Why should a missing required column stop this job rather than be
treated like an ordinary bad row? Where would you look first if such a run
failed in production?

## Part 4 — Let Airflow coordinate the same job

**What is Airflow?** Apache Airflow is a tool for orchestrating workflows:
it runs tasks in a defined order and lets us see when each task ran, whether
it succeeded, and what it logged. A workflow is called a **DAG** (directed
acyclic graph): tasks can depend on earlier tasks, but the dependencies do
not form a loop. Airflow can schedule a DAG, but in this lab we start each
run manually. Airflow coordinates the work; it does not itself decide which
sensor readings are valid.

The Python helper contains the *processing rules*. Our prepared DAG has
this shape:

```text
check_input → process_sensors → check_outputs
```

The middle task calls the **same** processor you ran in Part 2. The Airflow
container follows Airflow's
[standalone quick start](https://airflow.apache.org/docs/apache-airflow/3.3.1/start.html).

Docker starts Airflow and mounts the lab's folders into the container; it does
**not** define the workflow. `dags/sensor_processing_dag.py` defines that
workflow in Python:

- `@dag(dag_id="sensor_processing_lab", ...)` names the workflow;
  `schedule=None` means that this example has no automatic schedule.
- Each `@task(...)` defines one visible Airflow task. Its function calls a
  prepared function in `starter/process_sensors.py`.
- The line `check_input_task() >> process_task() >> check_outputs_task()`
  defines the left-to-right dependencies. The second
  task starts only after the first succeeds, and the third after the second.

The processor file, `starter/process_sensors.py`, contains the processing
rules called by the tasks. You do not need to edit either Python file.

You need Docker, introduced in the Kafka lab. We use it here for the same
reason: the pinned official image already contains Airflow and its runtime
dependencies, so the local setup is reproducible and disposable. Kafka is not
started or required in this lab. Running Airflow in a container is a local
setup choice; containerization is not an additional processing stage and a
production Airflow deployment may use a different architecture.

This lab needs only one standalone Airflow container, so Docker Compose would
add another concept without helping us coordinate multiple containers. The UI
is exposed only on your computer's port `8080`. This is a learning setup, not
a production deployment. Airflow uses more memory than the Kafka example;
allow roughly 4 GB to Docker. The image download can take time.

If `docker version` does not work, follow the **Setup — install and verify
Docker** section of the **First steps with Kafka** lab before continuing. On
Linux, macOS or WSL, run the following commands from this lab folder:

```bash
docker version
mkdir -p output
docker run -d \
  --name airflow-sensor-lab \
  --user "$(id -u):0" \
  -p 127.0.0.1:8080:8080 \
  -e AIRFLOW__CORE__LOAD_EXAMPLES=False \
  -v "$PWD/dags:/opt/airflow/dags:ro" \
  -v "$PWD/starter:/opt/airflow/lab/starter:ro" \
  -v "$PWD/data:/opt/airflow/lab/data:ro" \
  -v "$PWD/output:/opt/airflow/lab/output" \
  apache/airflow:3.3.1 standalone
docker ps --filter name=airflow-sensor-lab
```

`--user "$(id -u):0"` lets the container write generated files using your
local user ID. The four `-v` options make the DAG, processor, input and output
folders available at the paths expected by the workflow; only `output/` is
writable. Wait for Airflow to start—the first start can take several minutes.
If it does not start, inspect its logs:

```bash
docker logs airflow-sensor-lab --tail 50
```

If `docker run` reports that the name `airflow-sensor-lab` is already in use,
the container was created earlier. Run `docker start airflow-sensor-lab`
instead of creating a second one, then inspect it with `docker ps` and
`docker logs` as above.

Open [http://localhost:8080](http://localhost:8080). The username is
`admin`. The local standalone instance generates a password; read it with:

```bash
docker exec airflow-sensor-lab \
  cat /opt/airflow/simple_auth_manager_passwords.json.generated
```

Do not share or commit this password. In the **left-hand menu, click Dags**,
then find and open `sensor_processing_lab` (refresh after a short wait if it
has not appeared). Enable the DAG if it is paused, and click **Trigger**.
Wait for the run to finish. On the DAG's page, use **Runs** to find the new
run and its status, and **Tasks** to find `check_input`, `process_sensors`
and `check_outputs`. The **Graph View** tab, when visible on this DAG page,
draws the dependencies as arrows; you do not need it to complete the lab.
The [Airflow UI guide](https://airflow.apache.org/docs/apache-airflow/3.3.1/ui.html)
shows where that view appears.
You can also click a task in **Grid View** or in a run's task list to open
its details and **Logs**.

After a successful run, inspect `output/summary.json` again. The counts
should still be 5 clean and 5 rejected.

Questions: Which task would fail first if the input file were missing? Does
the DAG itself implement the temperature rules? What do three separately
visible tasks make easier to observe than one opaque task?

Before stopping Airflow, take a short guided tour of its UI:

1. In **Runs**, find your manual run. Did the whole DAG succeed? Can you see
   when it started and how long it took?
2. In **Grid View** or the run's task list, open `process_sensors` and its
   **Logs**. Find `PROCESSED: 5 clean, 5 rejected`. Then open
   `check_outputs`: which message confirms the quality check?
3. In **Code**, locate the three `@task` definitions and the `>>` line from
   above. In **Details**, find the DAG's schedule. Why is there no automatic
   next run?
4. If you find **Graph View**, compare its arrows with the three-step text
   diagram above. Which task depends directly on `process_sensors`?

It is fine to explore other read-only views as well. Do not use actions
such as **Clear** or **Mark Success** for this exercise: those change the
recorded task state.

When finished, stop the local container without deleting it:

```bash
docker stop airflow-sensor-lab
```

`docker start airflow-sensor-lab` can restart the same container. If you later
want to remove this local Airflow instance and its UI run history, stop it and
run `docker rm airflow-sensor-lab`. The generated `output/` files are mounted
from your laptop and remain there.

<details>
<summary>Suggested answers for self-check</summary>

**Part 1.** `evt-001` through `evt-005` are usable. `evt-006` is not numeric,
`evt-007` is missing a temperature, `evt-008` is implausibly high, the second
`evt-001` is a duplicate, and `evt-009` has an invalid timestamp. Filling a
bad reading with a mean would invent a measurement and hide the source issue.

**Part 2.** Required fields, timestamp, range and duplicate checks are
validation; calculating Fahrenheit is transformation. The output-count and
unique-ID checks are quality checks. Quarantine preserves evidence for
investigation or later reprocessing. The summary shows volume and the types
of rejected data.

**Part 3.** A missing column changes the structure of the whole input, so we
cannot apply the agreed row rules reliably. Stop, inspect the file and task
log, and determine whether the source changed or the wrong file arrived.

**Part 4.** `check_input` should fail before processing starts if the source
is missing. The rules live in `starter/process_sensors.py`; the DAG calls
those functions in order. Separate tasks reveal whether the failure was in
input checking, processing, or result checking. The successful manual run
appears in **Runs**; the processor log reports the 5/5 split, and the
`check_outputs` log reports `QUALITY CHECK OK`. `schedule=None` means the DAG
has no automatic next run. In the dependency chain, `check_outputs` depends
directly on `process_sensors`.

</details>

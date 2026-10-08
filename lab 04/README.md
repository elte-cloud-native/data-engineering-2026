# Lab 04 — First steps with Kafka

In Lab 03 we landed a file and an API response in Bronze. Here we look at a
different situation: an application produces small events continuously, and
other applications may need to read them. Kafka is **one possible** way to
transport and retain those events; it is not required for every ingestion
pipeline and it does not replace the Bronze landing area.
It is particularly useful when several systems need the same live events and
must be able to catch up or replay them while those events are retained.

Our example is a few temperature readings. The record flow is:

```text
prepared events → producer (Kafka client) → [Kafka broker: sensor-data topic/partitions] → consumer (Kafka client) → landing area
```

The broker is the Kafka server that holds the topic; the producer and consumer
are programs that connect to it as Kafka clients.

The goal is to see what a **topic**, **record key**, **partition**, **offset**
and **replay** mean in practice. No Python or Java programming is required.
Parts 1–4 use Kafka tools already inside its Docker image; Part 5 runs one
prepared Python consumer to connect the example back to a landing area.

## Why we use Docker

Kafka is server software: a broker must be running before producers and
consumers can connect to it. Instead of installing Kafka and Java directly on
every computer, we run the official Kafka image with Docker.

A **Docker image** is a prepared package containing Kafka and its runtime
dependencies. A **container** is a running instance of that image. Docker is
not a component of the data pipeline in this lab; it is only a convenient way
to run the same local Kafka environment on different computers.

You need only three Docker operations here:

- `docker run` creates and starts the Kafka container;
- `docker exec` runs a Kafka command inside the running container;
- `docker stop` and `docker start` stop and restart the same container.

This is a local learning setup, not a production Kafka deployment. It has one
broker, one replica, no authentication and no storage outside the container.

## Setup — install and verify Docker

All lab commands use Bash syntax. On Windows, run them from a WSL terminal;
on Linux, use your usual terminal. You do **not** need to install Kafka or a
separate Java SDK.

### Windows 11 — WSL 2 and Docker Desktop

1. Open PowerShell as Administrator and install WSL:

   ```powershell
   wsl --install
   ```

   Restart Windows if requested. After the restart, update WSL if necessary:

   ```powershell
   wsl --update
   ```

   On first launch, the installed Linux distribution may ask you to create a
   Linux username and password.

2. Download and install
   [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/).
   Use the WSL 2 backend when prompted, then start Docker Desktop.

3. In Docker Desktop, check **Settings → General → Use the WSL 2 based
   engine**. Under **Settings → Resources → WSL Integration**, enable the
   Linux distribution in which you will run the lab. See the
   [Docker WSL guide](https://docs.docker.com/desktop/features/wsl/) for
   screenshots and troubleshooting.

4. Open that WSL terminal and verify the installation:

   ```bash
   docker version
   docker run --rm hello-world
   ```

On most current Windows 11 computers, `wsl --install` enables the required
Windows features automatically. Hardware virtualization must still be enabled
in BIOS/UEFI; check it only if WSL or Docker reports a virtualization error.

### Linux

Follow the official
[Docker Engine installation guide](https://docs.docker.com/engine/install/)
for your distribution. For example, use the dedicated
[Ubuntu instructions](https://docs.docker.com/engine/install/ubuntu/) rather
than commands written for a different distribution.

After installation, start Docker and verify it:

```bash
sudo systemctl enable --now docker
sudo docker run --rm hello-world
```

The commands in this lab omit `sudo`. You may either prefix Docker commands
with `sudo`, or follow Docker's
[Linux post-installation guide](https://docs.docker.com/engine/install/linux-postinstall/)
to allow your user to access Docker. Membership in the `docker` group grants
administrator-level access to the machine, so use it only on a system where
that is appropriate.

### Python for Part 5

Part 5 uses Python 3 and a virtual environment. On Ubuntu or an Ubuntu-based
WSL distribution, install them if needed:

```bash
sudo apt update
sudo apt install -y python3 python3-venv
python3 --version
```

## Start the local Kafka broker

Run all remaining commands from the `Kafka/lab` folder. Create and start one
Kafka container:

```bash
docker run --name kafka-lab -d \
  -p 127.0.0.1:9092:9092 \
  apache/kafka:4.0.2
docker ps --filter name=kafka-lab
```

The options have the following purpose:

- `--name kafka-lab` gives the container a predictable name;
- `-d` runs it in the background;
- `-p 127.0.0.1:9092:9092` makes Kafka available only on this computer's
  port `9092`;
- `apache/kafka:4.0.2` is the pinned Kafka image used by the lab.

The first run downloads the image and can take several minutes. Wait until
the broker is ready, then ask Kafka to list its topics:

```bash
docker exec kafka-lab /opt/kafka/bin/kafka-topics.sh \
  --list --bootstrap-server localhost:9092
```

An empty result is normal because no topic exists yet. If the broker does not
answer, wait a little and retry.

### Common setup problems

- **Cannot connect to the Docker daemon:** start Docker Desktop on Windows, or
  start the Docker service on Linux.
- **The container name is already in use:** the container was created earlier.
  Start it again with `docker start kafka-lab` instead of repeating
  `docker run`.
- **Port 9092 is already allocated:** another program or container is using
  that port. Stop the conflicting process before continuing.
- **The container started but Kafka does not answer yet:** inspect startup
  messages with `docker logs kafka-lab`, wait, and retry the topic-list command.
- **You want a completely fresh broker:** run `docker rm -f kafka-lab`, then
  repeat the `docker run` command. Removing the container also removes the
  Kafka records stored inside it.

## Part 1 — Create a topic

Create a topic named `sensor-data` with two partitions:

```bash
docker exec kafka-lab /opt/kafka/bin/kafka-topics.sh \
  --create --if-not-exists --topic sensor-data \
  --partitions 2 --replication-factor 1 \
  --bootstrap-server localhost:9092
```

Inspect what Kafka created:

```bash
docker exec kafka-lab /opt/kafka/bin/kafka-topics.sh \
  --describe --topic sensor-data --bootstrap-server localhost:9092
```

Find `PartitionCount: 2` and `ReplicationFactor: 1`. A **topic** is a named
stream of records. Kafka stores its records in **partitions**; each partition
has its own sequence of positions, called **offsets**. Here both partitions
live on the same broker, so two partitions do **not** mean two servers.

Questions: Why do we need a topic name? How many brokers and how many
partitions do we have? Is replication factor 1 fault-tolerant?

## Part 2 — Produce four prepared events

Display the prepared file. It has four lines:

```bash
head -n 4 data/sensor_events.txt
```

Each line has this form:

```text
record-key|JSON value
```

For example, the key `S1` identifies a sensor. The JSON value is the event
payload. The `|` is only a separator understood by the **console producer**
in this exercise; it is not part of the JSON or the Kafka key. The timestamps
are fixed fictional event times, so everyone can use the same example.

Send the four lines to Kafka:

```bash
docker exec -i kafka-lab /opt/kafka/bin/kafka-console-producer.sh \
  --topic sensor-data --bootstrap-server localhost:9092 \
  --property parse.key=true --property 'key.separator=|' \
  < data/sensor_events.txt
```

The command may print little or nothing when it succeeds. The producer is
acting like an event-producing application, but the prepared file keeps this
first experiment repeatable. A real application could send events as they
occur instead of reading a file.

Questions: Which part of a line is the key? Is the JSON value automatically
validated by Kafka as a temperature event? Why might we use `sensor_id` as
the key?

## Part 3 — Read records, partitions and offsets

Read the four records from the beginning. The extra display options show
metadata that is normally hidden:

```bash
docker exec kafka-lab /opt/kafka/bin/kafka-console-consumer.sh \
  --topic sensor-data --bootstrap-server localhost:9092 \
  --from-beginning --max-messages 4 \
  --property print.key=true \
  --property print.partition=true \
  --property print.offset=true
```

The command exits after four records. Find each key, partition number and
offset. The two `S1` events should be in the **same** partition; likewise for
`S2`. Different keys are **not guaranteed** to land in different partitions,
but with this producer and an unchanged partition count, the same key
consistently goes to the same partition.
Within one partition, later records get larger offsets. Do not assume that
records in different partitions have one overall order.

Run the *same consumer command* again. You can read the stored events again:
this is **replay**. It does not mean the producer sent them twice. Kafka keeps
records according to a retention policy; reading does not remove them.
If you ran this exercise before without resetting the local broker, the first
four records shown may be from that earlier run.

Questions: Is offset `0` globally unique across the topic? What did the
second reading change in the topic? Why might replay be useful after fixing a
bug in downstream processing?

## Part 4 — Watch a new event arrive

Open **terminal A** in this same folder and start a consumer **without**
`--max-messages`:

```bash
docker exec -it kafka-lab /opt/kafka/bin/kafka-console-consumer.sh \
  --topic sensor-data --bootstrap-server localhost:9092 \
  --from-beginning \
  --property print.key=true \
  --property print.partition=true \
  --property print.offset=true
```

It prints the existing records and then waits. Leave it running. In
**terminal B**, from the same `Kafka/lab` folder, send one more prepared event:

```bash
head -n 1 data/one_more_event.txt
docker exec -i kafka-lab /opt/kafka/bin/kafka-console-producer.sh \
  --topic sensor-data --bootstrap-server localhost:9092 \
  --property parse.key=true --property 'key.separator=|' \
  < data/one_more_event.txt
```

The new `evt-005` should appear in terminal A without restarting the
consumer. Stop terminal A with `Ctrl+C`.

Question: What is the difference between the producer's job and the
consumer's job? Why can a consumer arrive later and still read earlier
events?

## Part 5 — Land Kafka events for Bronze

So far, the events are in a Kafka topic, **not** in the Lab 03 Bronze
container. A consumer must read them and write them to a landing destination.
The prepared `starter/consumer_to_landing.py` does this once for the records
currently retained in `sensor-data`. You only run the helper; writing or
understanding its Python code is not part of the task.

Install its Python dependency in a local virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The `.venv` folder keeps the Python package used by this lab separate from
packages installed elsewhere on your computer. `source` activates that
environment in the current terminal.

Now make a local landing copy:

```bash
python starter/consumer_to_landing.py
head -n 20 landing/sensors/2025/09/02/source=kafka/sensor_events.json
```

After Parts 1–4, the file should normally contain a JSON array with five
objects, one per Kafka record. Each object contains the event value **and**
its Kafka topic, key, partition and offset. The fixed folder date is an
exercise partition label, not the time at which the consumer ran. The helper
sorts the saved objects by partition and offset for easy inspection; this
does not create a global Kafka event order.

This is a **one-time teaching snapshot**, not a continuously running or
production-ready Kafka sink. It reads from the beginning, waits briefly for
the stream to go quiet, and then exits. Rerunning it does not overwrite the
existing landing file. If you produced more events in an earlier attempt, the
record count may exceed five.

If you have the Azure Storage account and private `bronze` container from
Lab 03, you can optionally upload this local file there. This is the point
where the Kafka-origin data actually enters Azure Bronze:

```bash
python -m pip install -r requirements-azure.txt
export AZURE_STORAGE_CONNECTION_STRING="<your connection string>"
export AZURE_STORAGE_CONTAINER="bronze"
python starter/upload_to_azure.py
unset AZURE_STORAGE_CONNECTION_STRING
```

The destination is the `bronze` container, with Blob name
`sensors/2025/09/02/source=kafka/sensor_events.json`.
The helper skips an existing Blob path rather than overwriting it; as in
Lab 03, it does **not** compare file contents. Do not put the connection
string in code, screenshots or commits.

Questions: Which new component moves data from Kafka into the landing area?
Why is the topic itself not the Bronze object? What would be lost if the
landing file saved only each message's JSON value?

## Finish and self-check

Stop the broker while keeping this container and its data for later:

```bash
docker stop kafka-lab
```

`docker start kafka-lab` restarts this stopped container with its existing
Kafka records. This exercise does not configure persistent storage outside
the container: `docker rm kafka-lab` removes the container and its stored
records. If you repeat Part 2 without resetting the container, you will
produce four *additional* records, so `--from-beginning` may show more than
the original four.

<details>
<summary>Suggested answers for self-check</summary>

**Part 1.** The topic name identifies which stream producers write and
consumers read. We have one broker and two partitions. With replication
factor 1 there is no second copy on another broker, so this setup is not
fault-tolerant.

**Part 2.** `S1` or `S2` before `|` is the Kafka record key; JSON after it is
the value. Kafka stores the bytes but does not automatically verify that the
JSON has a sensible temperature. Using the sensor as key keeps one sensor's
events together in a partition, which makes their order easier to reason
about.

**Part 3.** Offset `0` can exist in **each** partition; an offset identifies
a position only together with topic and partition. Reading again does not
delete or rewrite records. Replay lets a consumer re-read retained input,
for example after its processing logic is corrected.

**Part 4.** The producer writes events; the consumer reads them independently.
Kafka retains records for a configured period, so a consumer can read
retained events even if it was not running when they were produced. Kafka can
sit between source applications and later ingestion/processing, while Bronze
is a separate landing area for durable, source-faithful platform data.

**Part 5.** A consumer (or a tool using the consumer API) reads Kafka and
writes the landing file; Kafka does not automatically upload topic data to
Bronze. The topic is a retained event stream, while the Bronze object is a
separate file in storage. Saving only the JSON value would lose the Kafka
key, partition and offset that identify where a record came from and help
with tracing or replay.

</details>

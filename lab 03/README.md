# Lab 03 — Data ingestion

This lab follows two simple examples: a CSV export from a sales system and a
JSON response from a public API. We place both in a local landing area, then
copy them to an Azure Blob Storage `bronze` container. Finally, we look at a
changed CSV schema and a wrongly named folder.

The focus is **what arrives, where it lands, and how we can recognize it later**.
The Python files in `starter/` are prepared convenience helpers, **not Python
programming exercises**. You only need to run them. You do not need to build
an API, implement pagination, or understand the Azure SDK internals.

The lab has four parts (roughly 15 + 30 + 20 + 15 minutes, including
discussion). Parts 1, 3 and 4 work locally without an Azure account. If Azure
access is unavailable, use the dry-run in Part 2.

## Before you begin

Use a Linux, macOS or WSL terminal with Python 3.10 or newer. From this
`lab 03` folder, run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The two input files are already in `data/`. Do not edit them: this exercise is
about ingestion, not generating data. The `landing/` folder is your local
practice area; it is created by the steps below and ignored by Git. The fixed
date `2025/09/02` is only a repeatable **landing partition label** for this
exercise. It does not claim that every record was created on that day.

## Part 1 — See the sources and stage them locally

### A. A file export

Open the prepared CSV (`data/sales_data.csv`) in your editor, or display it:

```bash
head -n 6 data/sales_data.csv
```

Imagine that a sales application exported this file. Copy it to the local
landing area:

```bash
mkdir -p landing/sales/2025/09/02/source=file
cp data/sales_data.csv landing/sales/2025/09/02/source=file/
```

`cp` keeps the prepared source file unchanged. The folder name tells us the
domain (`sales`), the landing partition date and the source type (`file`). The
CSV itself contains the order fields and values.

### B. An API response

An API can be another source of data. The prepared `starter/fetch_users.py`
helper makes **one** request to the public
[JSONPlaceholder `/users` endpoint](https://jsonplaceholder.typicode.com/users)
and saves its JSON response. Run it from the `lab 03` folder:

```bash
python starter/fetch_users.py
```

If the service or your network is unavailable, use the small, fictional
`data/users_sample.json` instead. It is a fallback example, **not an exact
snapshot of the API response**:

```bash
mkdir -p landing/users/2025/09/02/source=api
cp data/users_sample.json landing/users/2025/09/02/source=api/users.json
```

Look at the beginning of the landed JSON:

```bash
head -n 15 landing/users/2025/09/02/source=api/users.json
```

Questions: What differs between the file and API sources? Which information
can you read from the landing path, and which only from the file contents?
Why keep a copy of the API response before changing its structure?

## Part 2 — Land the files in Azure Bronze

Our Bronze path convention is:

```text
<domain>/<YYYY>/<MM>/<DD>/source=<source>/<filename>
```

First, preview what would be uploaded. This works without Azure and does not
change anything remotely:

```bash
python starter/upload_to_blob.py --dry-run
```

You should see one `READY` line for each file. The two destinations are
`sales/2025/09/02/source=file/sales_data.csv` and
`users/2025/09/02/source=api/users.json`.

For the Azure part:

1. In the [Azure Portal](https://portal.azure.com/), create a Storage account
   in your assigned subscription/resource group. For that, choose a unique name, Standard
   performance and LRS redundancy for this exercise.
2. Under **Data storage → Containers**, create a **private** Blob container
   called `bronze`.
3. Under the Storage account's **Access keys** section, copy a connection
   string. 

Put the connection string in a temporary shell environment variable, not in a
file or screenshot:

```bash
export AZURE_STORAGE_CONNECTION_STRING="<your connection string>"
export AZURE_STORAGE_CONTAINER="bronze"
python starter/upload_to_blob.py
```

Open the container in the Portal and find both objects. Run the upload once
more. The helper prints `SKIP existing path` rather than overwriting an
existing object. **It checks the path, not whether the bytes are identical.**
That simple, safe policy is enough for this exercise; real ingestion systems
need a more explicit policy for changed data at the same path. When finished:

```bash
unset AZURE_STORAGE_CONNECTION_STRING
```

Questions: Which part of the path comes from the source file name, and which
part did we choose for the landing convention? Is copying data to Bronze a
transformation of its business meaning? What would happen if the same name
later referred to changed contents?

## Part 3 — Notice schema drift

The prepared `data/sales_data_v2.csv` has one extra column. Compare only the
headers first; no pandas or Python is required:

```bash
head -n 1 data/sales_data.csv
head -n 1 data/sales_data_v2.csv
```

Copy the second file beside the first, keeping a different file name:

```bash
cp data/sales_data_v2.csv landing/sales/2025/09/02/source=file/
python starter/upload_to_blob.py --dry-run
```

If you have Azure access, run `python starter/upload_to_blob.py` again. The
first CSV stays in Bronze; the second lands under its own name. We have not
rewritten or merged either raw file.

Questions: What changed in the schema? Can a reader that uses only the original
four columns still read the new file? Would an extra column always be harmless
for every downstream consumer? Where would you decide how to use `region`?

## Part 4 — Catch a wrong landing path

Folder names are useful metadata only if we apply the same convention each
time. The prepared upload helper checks that the path has the expected
domain/date/source structure and that the date is a real calendar date.
Create one deliberately wrong path:

```bash
mkdir -p landing/sales/source=file
cp data/sales_data.csv landing/sales/source=file/bad.csv
python starter/upload_to_blob.py --dry-run
```

The dry-run should report an error instead of silently ignoring the file.
No Azure upload is attempted. Remove **only this practice file**, then check
that the valid files are still ready:

```bash
rm landing/sales/source=file/bad.csv
python starter/upload_to_blob.py --dry-run
```

Question: Why can a wrong folder name be a data-quality or traceability issue
even when the CSV rows themselves are valid?

<details>
<summary>Suggested answers for self-check</summary>

**Part 1.** One source arrives as a CSV file; the other is fetched via HTTP
and saved as JSON. The path gives domain, chosen partition date, source type
and file name; order/customer/user fields live inside the data. Keeping the
response makes it possible to inspect or reprocess the original input later.

**Part 2.** The file name comes from the staged source; the domain/date/source
folders are our convention. Landing a source-faithful copy does not yet change
its business meaning. If contents change but the destination path is the same,
this helper skips it; a production system must choose whether to reject,
version, or deliberately replace such data.

**Part 3.** `region` was added. A reader that selects only the four old columns
can often still work, but a reader expecting exactly four columns might fail.
Whether `region` is optional, how it is interpreted, and how old rows are
handled are downstream processing or data-contract decisions.

**Part 4.** A missing or misplaced date/source folder can make data hard to
find, mix different inputs, or give a misleading lineage. The rows may be
valid while the landing metadata is not.

</details>

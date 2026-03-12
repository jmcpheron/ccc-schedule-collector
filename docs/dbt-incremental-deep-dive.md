# dbt Core Incremental Models: Conceptual Deep-Dive for the CCC Schedule Collector

## Context

This is a learning document — no code changes. The goal is to understand dbt Core's incremental models and how they map to the CCC Schedule Collector's existing data pipeline (JSON snapshots collected 3x daily via GitHub Actions, with Git-based change tracking).

---

## 1. How Incremental Models Work

An incremental model uses `materialized='incremental'` in its config. On **first run**, dbt creates the full table. On **subsequent runs**, it processes only new rows and merges them into the existing table.

The key construct is `{{ is_incremental() }}` — a Jinja macro that returns `True` when the target table already exists and this isn't a `--full-refresh` run. You use it to add a WHERE clause:

```sql
{{ config(materialized='incremental', unique_key='enrollment_key', incremental_strategy='merge') }}

SELECT college_id, crn, collection_timestamp, enrollment_actual, status
FROM {{ ref('stg_courses') }}

{% if is_incremental() %}
WHERE collection_timestamp > (SELECT MAX(collection_timestamp) FROM {{ this }})
{% endif %}
```

`{{ this }}` references the model's existing target table. The WHERE says: "only rows newer than what I've already processed."

**Compiled SQL** (on incremental run):
```sql
CREATE TEMP TABLE __dbt_tmp AS (
    SELECT ... FROM stg_courses
    WHERE collection_timestamp > (SELECT MAX(collection_timestamp) FROM target_table)
);

MERGE INTO target_table AS target
USING __dbt_tmp AS source
ON target.enrollment_key = source.enrollment_key
WHEN MATCHED THEN UPDATE SET ...
WHEN NOT MATCHED THEN INSERT ...;
```

---

## 2. How This Maps to the Schedule Collector

### Current pipeline
- GitHub Actions collects 3x daily → overwrites `schedule_202570_latest.json` (~1,915 courses)
- Git tracks diffs between commits (change history)
- `cli.py compare` computes pairwise diffs between two JSON files

### If using DuckDB + dbt, the layers would be:

**Raw:** Each collection appends ~1,915 rows to `raw_schedule_snapshots` (instead of overwriting one file). Over a semester: ~690K rows per college.

**Staging:** Views that clean/normalize (compute `fill_rate`, split meeting times, clean instructors). Not incremental — views are cheap.

**Marts (incremental):** Three examples:

### Mart 1: Enrollment History
Tracks enrollment changes per CRN over time. This is what `cli.py compare` does on the fly, but persisted.

```sql
{{ config(materialized='incremental', unique_key=['college_id','term_code','crn','collection_timestamp'], incremental_strategy='merge') }}

SELECT college_id, term_code, crn, subject, course_number, collection_timestamp,
       enrollment_actual, enrollment_capacity, fill_rate, status, instructor
FROM {{ ref('stg_courses') }}
{% if is_incremental() %}
WHERE collection_timestamp > (SELECT MAX(collection_timestamp) FROM {{ this }})
{% endif %}
```

Result over time:

| college_id | crn   | collection_timestamp     | enrollment_actual | delta |
|------------|-------|--------------------------|-------------------|-------|
| rio-hondo  | 77649 | 2026-03-10T06:41:12Z     | 25                | —     |
| rio-hondo  | 77649 | 2026-03-10T14:41:27Z     | 27                | +2    |
| rio-hondo  | 77649 | 2026-03-10T22:38:04Z     | 29                | +2    |

### Mart 2: Course Status Changes
Track Open→Closed transitions (analogous to `added`/`removed` sets in `compare`).

### Mart 3: Cross-College Comparison
JOIN across colleges by subject + course_number in one SQL query — something the current pipeline can't easily do.

---

## 3. unique_key and Merge Strategy

The `unique_key` determines what constitutes "the same row":

| Grain | unique_key | Use case |
|-------|-----------|----------|
| Per course per snapshot | `[college_id, term_code, crn, collection_timestamp]` | Full enrollment history |
| Per course (latest only) | `[college_id, term_code, crn]` | Current state dashboard |
| Per course per day | `[college_id, term_code, crn, collection_date]` | Daily aggregates |

The composite key ensures idempotent loads — if a GitHub Actions run retries, the MERGE updates instead of duplicating.

---

## 4. Incremental Strategies

| Strategy | Duplicates safe? | Updates existing? | Best for schedule data |
|----------|-----------------|-------------------|------------------------|
| **append** | No | No | Raw event log (`raw_schedule_snapshots`) |
| **merge** | Yes | Yes | Mart tables with composite keys |
| **delete+insert** | Yes | Yes (by replacement) | Daily aggregates, reprocessing after bug fixes |

---

## 5. The is_incremental() Pattern

Works well here because `collection_timestamp` is a reliable high-water mark:
- Each run has a distinct UTC timestamp
- Timestamps are monotonically increasing
- Filter is cheap (scalar subquery on MAX)

**Concretely:** If the mart has data through `2026-03-11T14:41:11Z` and a new snapshot arrives at `22:37:07Z`, the incremental run processes only the ~1,915 new rows rather than all ~690K accumulated rows.

**Subtlety with LAG():** Window functions like `LAG(enrollment_actual)` need the previous row, which lives in the target table, not the new batch. Common pattern: store raw facts incrementally, compute deltas in a downstream full-rebuild model.

---

## 6. When Incremental Does NOT Make Sense

- **Data is small:** ~700K rows/semester. DuckDB full-scans this in milliseconds. Incremental saves negligible time.
- **Transformation needs full history:** Window functions across all time require all rows regardless.
- **Source data gets retroactively corrected:** High-water-mark misses backfills. Need `--full-refresh`.
- **For this project specifically:** Data volumes are well within "just rebuild it" territory for DuckDB. The conceptual value is understanding the pattern for when scale grows.

---

## 7. How This Compares to What You Already Do

### Git as Change Data Capture
Every commit to `schedule_202570_latest.json` records the full state + exact diff + timestamp. This is structurally identical to a Type 2 Slowly Changing Dimension.

### `compare` is an incremental model in disguise
From `cli.py` lines 199-289:
```python
courses1 = {c.crn: c for c in schedule1.courses}
courses2 = {c.crn: c for c in schedule2.courses}
added = crns2 - crns1    # ← WHEN NOT MATCHED THEN INSERT
removed = crns1 - crns2  # ← rows in target but not source
```
This is MERGE logic, just stateless.

### What dbt would add

| Capability | Current (Git + JSON) | With dbt + DuckDB |
|-----------|---------------------|-------------------|
| Query "enrollment on March 5?" | `git show HEAD~15:data/...` then parse JSON | `SELECT * WHERE date = '2026-03-05'` |
| Cross-college analysis | Load two JSON files manually | SQL JOIN in one query |
| Trend analysis | Not directly supported | SQL window functions over full history |
| Infrastructure | Zero (GitHub Actions + Git) | DuckDB file + dbt CLI (still lightweight) |

### The bridge (if you ever want to implement)
1. Keep JSON collection pipeline (it works)
2. Add post-collection step to load each snapshot into DuckDB (append)
3. Build dbt staging/mart models on top
4. Incremental models process only the latest snapshot each run
5. Git continues as backup/audit trail

Your existing `collection_timestamp` field is the exact high-water mark dbt incremental models would use. The data model is already well-structured for this.

---

## 8. First Projects: dbt + DuckDB in GitHub Actions

These are practical starter projects, ordered from simplest to most ambitious. All run in GitHub Actions with zero infrastructure — DuckDB is an in-process database (just a file), and dbt-duckdb installs via pip.

### Project 1: JSON-to-DuckDB Loader (No dbt yet)

**What it does:** After each collection run, load the JSON snapshot into a DuckDB file and commit it alongside the JSON.

**Why start here:** Separates the "get data into DuckDB" problem from "learn dbt." You can query the DuckDB file locally with the `duckdb` CLI or Python.

**GitHub Actions integration:**
- Add a step after the existing collection step in `collect.yml`
- Python script reads `schedule_*_latest.json`, flattens courses into rows, appends to `data/schedule.duckdb`
- Commit the `.duckdb` file alongside the JSON

**What you learn:** DuckDB's JSON ingestion, schema design, how `.duckdb` files work in Git (binary, but small — ~5MB).

**Complexity:** Low. ~50 lines of Python. No dbt knowledge needed.

### Project 2: dbt Project with Full-Rebuild Models (No Incremental)

**What it does:** Initialize a dbt project that reads from the DuckDB file (from Project 1) and builds staging views + mart tables. All models use `materialized='table'` — full rebuild every run.

**Why start here:** Learn dbt project structure, `ref()`, `source()`, Jinja basics, and `dbt run` without the added complexity of incremental logic.

**GitHub Actions integration:**
- New workflow: `dbt.yml`, triggered after `collect.yml` completes (using `workflow_run` trigger)
- Steps: `pip install dbt-duckdb`, `dbt run --profiles-dir .`, `dbt test`
- The `profiles.yml` points to the committed `.duckdb` file

**Models to build:**
1. `stg_courses` — view that cleans raw data (normalize instructors, compute fill_rate)
2. `stg_meeting_times` — view that unnests the meeting_times JSON array
3. `mart_current_enrollment` — table of latest enrollment state per CRN
4. `mart_daily_summary` — table aggregating by subject (total sections, avg fill rate)

**dbt tests to add:**
- `unique` test on `stg_courses.snapshot_course_key`
- `not_null` tests on `crn`, `subject`, `collection_timestamp`
- `accepted_values` on `status` (Open, CLOSED)

**What you learn:** dbt project layout (`models/`, `dbt_project.yml`, `profiles.yml`), the ref/source DAG, dbt tests, running dbt in CI.

**Complexity:** Medium. ~10 SQL files, ~2 YAML configs. The dbt docs tutorial covers all of this.

### Project 3: Add Incremental Models

**What it does:** Convert `mart_current_enrollment` and add `mart_enrollment_history` as incremental models. This is where the concepts from this document become concrete.

**Why this order:** You already have working models from Project 2. Converting to incremental is a config change + adding the `is_incremental()` WHERE clause. You can compare full-rebuild vs incremental output to verify correctness.

**GitHub Actions integration:**
- Same `dbt.yml` workflow — `dbt run` automatically handles incremental logic
- Add a weekly `dbt run --full-refresh` scheduled job to rebuild from scratch (catches drift)

**Models to convert/add:**
1. Convert `mart_current_enrollment` to incremental with `unique_key=['college_id','term_code','crn']` and merge strategy — always keeps latest state
2. Add `mart_enrollment_history` with `unique_key=['college_id','term_code','crn','collection_timestamp']` — append-like with merge safety
3. Add `mart_status_changes` — incremental, only stores rows where status changed

**What you learn:** `is_incremental()`, `{{ this }}`, merge vs append vs delete+insert, `--full-refresh`, how the high-water mark pattern works with your `collection_timestamp`.

**Complexity:** Medium. Conceptually the hardest step, but mechanically small (add ~5 lines to each model).

### Project 4: dbt-Powered Reporting Dashboard

**What it does:** Add a post-dbt step that queries the mart tables and generates a static HTML or Markdown report, committed to the repo or published to GitHub Pages.

**Why:** Makes the dbt output visible and useful without needing a BI tool. Closes the loop from "data pipeline" to "something humans look at."

**GitHub Actions integration:**
- After `dbt run`, a Python script queries DuckDB marts and renders Jinja2 HTML templates
- Deploy to GitHub Pages via `actions/deploy-pages`

**Report contents:**
- Enrollment trends (chart from `mart_enrollment_history`)
- Recently closed sections (from `mart_status_changes`)
- Cross-college comparison table (from `mart_cross_college`)
- Data freshness (last collection timestamp)

**What you learn:** Using dbt output downstream, the full pipeline from collection → transformation → presentation.

**Complexity:** Medium-high. The dbt part is done; this is mostly frontend/templating work.

### Recommended Starting Point

**Start with Project 1** (JSON-to-DuckDB loader). It's self-contained, takes ~1 hour, and gives you a queryable database immediately. You can run `duckdb data/schedule.duckdb "SELECT subject, COUNT(*) FROM courses GROUP BY subject"` locally to explore your data in SQL — which is rewarding and motivating before diving into dbt's abstractions.

Then move to Project 2 when you want to learn dbt itself. Projects 3 and 4 build on each other naturally.

---

## Key files referenced
- `models.py` — Pydantic models that map directly to dbt source schemas
- `cli.py:199-289` — `compare` command implementing MERGE-like logic
- `utils/storage.py` — Current overwrite-latest pattern
- `.github/workflows/collect.yml` — 3x daily collection cadence
- `config.yml` — Multi-term, multi-department parameters

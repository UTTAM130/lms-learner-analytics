# LMS learner-analytics: synthetic data generator, validator and metrics

Synthetic, fully reproducible data for **course participation, content use, assessment progress and completion across learner cohorts**: a generator, a validator, metric definitions, labelled anomalies with a separate ground truth, and detectors scored against that ground truth.

- 11 related tables (Learner, Course, Cohort, ContentItem, CompletionRule, Assessment, Enrollment, EnrollmentStatusHistory, Attempt, ActivityEvent, CourseOutcome), ID conventions from the brief (`LRN-000001`, `CRS-000001`, `ENR-<learner>-<course>`, `EVT-<enrollment>-000001`, `ASM-2026-000001`).
- Full scale: **20,000 learners, 500 courses, 100,000 enrollments, 1,989,562 activity events** (seed `20261022`). The same generator produces the small `starter` and `tiny` sets (`--scale`).
- No external data: nothing is downloaded, no personal data. Schema ideas only are inspired by public learning-analytics specs (xAPI, IMS Caliper).

## Run it

```bash
pip install -r requirements.txt            # numpy, pandas, pytest (Python 3.10+)

python -m lms_synth generate --scale starter          # -> data/starter  (1k learners, ~99k events, seconds)
python -m lms_synth all --data data/starter           # validate + metrics + detector evaluation
python -m pytest -q                                   # 22 tests (~6 s)

scripts/run_full.sh                                   # full scale: ~3 min, ~1 GB RAM
python -m lms_synth repro --scale starter             # Step 10: generate twice, compare checksums
python -m lms_synth docs --out docs                   # regenerate data dictionary + DDL
python -m lms_synth sql --data data/starter           # INSERT-based seed.sql
python -m lms_synth sqlite --data data/starter --db lms.db   # load into SQLite + PRAGMA foreign_key_check
```

Generator command used for the full set: `python -m lms_synth generate --scale full --seed 20261022 --out data/full`.
Scale is parameterised: `--learners/--courses/--enrollments` override any preset. Output depends only on seed, scale and the fixed chunk size (10,000 enrollments).

## What is in the repo

| Path | Content |
|---|---|
| `lms_synth/` | generator (`masters.py`, `simulate.py`, `generate.py`), `schema.py` (single source of truth for dictionary, DDL and validator), `validate.py`, `recompute.py` (executable completion rule), `metrics.py`, `evaluate.py`, `repro.py`, `sqlgen.py` |
| `tests/` | pytest suite (IDs, keys, lifecycle, reconciliation, edge cases, dedup, windows, detectors, reproducibility, SQLite FK check) |
| `docs/data_dictionary.md`, `docs/schema.sql` | Step 1: every field with type, required, allowed values, unit, uniqueness, validation rule; cardinalities, lifecycle, ER diagram, anomaly catalogue |
| `data/starter/` | committed starter dataset: CSV (+JSON for small tables), `ground_truth/`, `manifest.json` (seed, command, row counts, SHA-256), validation, evaluation, metrics |
| `data/sample/seed.sql` | SQL seed (DDL + INSERTs) for the `tiny` set |
| `results/full/` | reports from the full run (manifest/checksums, validation, evaluation, reproducibility, metrics). The ~450 MB full CSVs are regenerated, not committed |

## How the data is generated (Steps 2-6)

Parents first: learners, courses, content hierarchy (module -> items), assessments (1:1 with quiz/assignment/exam items), versioned completion rules, cohorts, then enrollments (one cohort each, valid parent IDs). Per-enrollment simulation then produces events, attempts, status history and outcomes in that order, in chunks.

- **Behaviour comes from latent traits, not coin flips on outcomes.** Learners have an engagement segment (power/regular/casual/dormant/inactive) and ability; courses have difficulty; these drive how far a learner gets, how fast, retries and scores. Distributions: ~23% completion in closed cohorts, ~19% withdrawal, 23% of learners with no valid activity, 28% of attempts are repeats, 4% abandoned.
- **Outcomes are derived.** Completion = required-content threshold (per rule version in force at cohort start) **and** every required assessment passed. `final_score`, `rule_met_at_utc`, percentages and `outcome_status` are computed from deduplicated events and attempts. `recompute.py` re-derives them independently and the validator requires an exact match.
- **History is never overwritten.** Enrollment state changes are rows in `enrollment_status_history` (`enrolled -> active -> completed | dropped | expired`); `enrollments.current_status` equals the last row.
- Mobile/offline sync (`mobile_offline_sync`, lag up to 20 days), late events (ingestion lag > 24 h, ~3.5% of events), repeated attempts and inactive learners are part of the baseline.

## Labelled edge cases (Steps 5, 7)

Injected on top of valid baseline data and recorded in `ground_truth/ground_truth.csv` (+ `.json`). Input tables contain no label column, and the validator checks for leakage.

| issue_type | Full-scale rows | Effect if ignored |
|---|---|---|
| `duplicate_event` | 32,082 (1.6% of events) | inflates engagement counts |
| `activity_unenrolled` | 7,794 (never enrolled 5,457; before enrolment 2,337) | counts non-participants |
| `completion_before_required_assessment` | 3,453 enrollments | platform completion marks overstate completions by 13.7% |
| `timezone_shift` | 7,800 | event lands on the wrong learner-local day / week |

`ground_truth_learners.csv` holds the latent simulation variables (segment, ability) for evaluation only.

## Metrics (`metrics.py`, definitions in `results/*/metrics/metric_definitions.json`)

- **valid event**: first-ingested delivery of its `client_event_id`, existing enrollment, inside `[enrolled_at, access_end)`.
- **week**: ISO week (Monday) of the *learner-local* date (master offset). **Active** = >=1 valid event; **engaged** = >=5.
- **Raw vs clean** weekly engagement are both reported so the cost of dirty data is visible (`weekly_engagement.csv`).
- **Cohort comparisons use consistent windows**: early-engagement curve over cohort weeks 0-3 only for cohorts whose 4-week window has ended; completion and withdrawal rates only for cohorts whose completion window has closed (open cohorts are right-censored and excluded); comparisons are grouped by identical `duration_weeks` and start month.

## Validation and evaluation results (full scale)

- **Validation**: 317 checks, 310 pass, 0 fail, 7 informational exception counts (PK uniqueness, enums/format, all foreign keys, date ordering, lifecycle transitions, arithmetic reconciliation, ID derivation, event counters, completion-rule recompute). The only FK exception is the labelled unenrolled activity (SQLite `foreign_key_check` returns exactly those rows).
- **Detectors vs ground truth** (detectors never read the ground truth):

| issue | precision | recall |
|---|---|---|
| duplicate_event (same `client_event_id`, keep earliest ingested) | 1.000 | 1.000 |
| activity_unenrolled | 1.000 | 1.000 |
| completion_before_required_assessment (rule recompute) | 1.000 | 1.000 |
| timezone_shift (ingestion lag = -learner offset) | 1.000 | 0.882 |

  The timezone recall gap is deliberate realism: shifts on offline-synced events (898 of 7,800) have unconstrained lag and cannot be detected this way (recall 0.997 on online platforms; 100% of the detected ones are corrected to the true date).
- **Reproducibility (Step 10)**: two full runs with seed 20261022 produce identical row counts and SHA-256 for all 20 files; a control run with seed 20261023 differs in all 20 (`results/full/reproducibility_report.json`).

## Assumptions and limitations

- UTC offsets are fixed per learner (no DST); local-date logic uses that offset. Stated in the dictionary.
- Detectors are simple rules, meant to show anomalies are present and discoverable, not as a production anomaly model.
- Instructor is only an opaque `instructor_code` on cohorts (not an entity); support-staff and platform-admin actors are represented through `change_source` and the platform completion mark rather than separate tables.
- `ASM-2026-` uses 2026 as a fixed release-year token, as in the brief.
- The generator is calibrated to plausible MOOC-style behaviour but is not fitted to real data.

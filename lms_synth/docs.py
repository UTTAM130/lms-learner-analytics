"""Generates docs/data_dictionary.md and docs/schema.sql from schema.py (single source of truth)."""
from __future__ import annotations

import os

from . import config as C
from . import schema as S
from .sqlgen import ddl

ID_CONVENTIONS = """\
| Entity | Pattern | Notes |
|---|---|---|
| Learner | `LRN-000001` | 6-digit zero-padded counter, immutable |
| Course | `CRS-000001` | |
| Enrollment | `ENR-<learner-id>-<course-id>` | e.g. `ENR-LRN-000001-CRS-000042`; natural key, one per learner and course |
| ActivityEvent | `EVT-<enrollment-id>-000001` | per-enrollment counter in **ingestion order** (ties: generation order) |
| Assessment | `ASM-2026-000001` | year token is fixed to the data-model release year 2026 (spec) |
| *Cohort* | `COH-000001` | extra convention (spec silent) |
| *ContentItem* | `CNT-000001` | extra convention |
| *CompletionRule* | `RUL-000001` | extra convention; odd = version 1, even = version 2 of a course |
| *Attempt* | `ATT-<enrollment-id>-<assessment seq>-<attempt no>` | extra convention |
| *EnrollmentStatusHistory* | `ESH-<enrollment-id>-<seq>` | extra convention |
| *CourseOutcome* | `OUT-<enrollment-id>` | extra convention, 1:1 with enrollment |
"""

ISSUES = """\
| issue_type | subtype | What is injected | Expected decision |
|---|---|---|---|
| `duplicate_event` | `retry_duplicate` | A second delivery of a real event (same `client_event_id`, new `event_id`, later `ingested_at_utc`). Offline-sync events are duplicated ~5x more often than online ones. | drop, keep first ingested |
| `activity_unenrolled` | `never_enrolled` | Event whose `ENR-<learner>-<course>` has no enrollment record | exclude from engagement |
| `activity_unenrolled` | `before_enrollment` | Valid enrollment, but event_time precedes `enrolled_at` | exclude from engagement |
| `completion_before_required_assessment` | `required_assessment_not_passed` | Platform marked the enrollment completed once the content threshold was met although a required assessment was never passed | do not record completion |
| `completion_before_required_assessment` | `required_assessment_passed_later` | Platform completion time is the content-threshold time, > 1 h before the last required assessment was passed | completion time = rule_met_at |
| `timezone_shift` | `offset_present` / `offset_missing` | `event_time_utc` carries the device's local clock time instead of UTC (shifted by the learner's UTC offset), which moves the event to the next/previous learner-local day; device offset is reported in 40% of cases, missing in 60% | reassign to the true local date |
"""


def data_dictionary() -> str:
    L = ["# Data dictionary\n",
         "Generated from `lms_synth/schema.py`; the validator checks every delivered table against it.\n",
         "Conventions: timestamps are ISO-8601 UTC `YYYY-MM-DDTHH:MM:SSZ`; dates `YYYY-MM-DD`; booleans `true`/`false`; "
         "an empty CSV cell means NULL. `Required` = must be non-empty. Units are listed where relevant.\n",
         "## ID / nomenclature conventions\n", ID_CONVENTIONS,
         "## Entity relationships\n",
         "```mermaid\nerDiagram"]
    for t in S.TABLES.values():
        for col, parent, pcol in t.fks:
            if parent != t.name:
                L.append(f"  {parent} ||--o{{ {t.name} : \"{col}\"")
    L += ["```\n",
          "Learner N:M Course is resolved by **Enrollment** (bridge with state); Enrollment N:M ContentItem by **ActivityEvent**; "
          "Enrollment N:M Assessment by **Attempt**. ContentItem is self-referencing (module -> item). "
          "`activity_events.attempt_id`, `content_items.parent_content_id` and `courses.retired_date` are the optional relationships.\n",
          "## Tables\n"]
    for name in S.LOAD_ORDER:
        t = S.TABLES[name]
        L += [f"### {name}\n", t.description + "\n", f"- **Primary key:** `{t.pk}`",
              "- **Foreign keys:** " + (", ".join(f"`{c}` -> `{p}.{pc}`" for c, p, pc in t.fks) or "none"),
              f"- **Cardinality:** {t.cardinality}"]
        if t.lifecycle:
            L.append(f"- **Lifecycle / effective dates:** {t.lifecycle}")
        L += ["", "| field | type | req | allowed values | unit | unique | validation rule / description |", "|---|---|---|---|---|---|---|"]
        for f in t.fields:
            rule = (f.description + (" " + f.rule if f.rule else "")).replace("|", "\\|")
            L.append(f"| `{f.name}` | {f.type} | {'yes' if f.required else 'no'} | {f.allowed.replace('|', '/')} | {f.unit} | "
                     f"{'yes' if f.unique else ''} | {rule} |")
        L.append("")
    L += ["## Enrollment state machine\n", "```", "(new) -> enrolled -> active -> completed", "                 \\-> dropped   (also from enrolled)",
          "                 \\-> expired   (also from enrolled)", "```",
          "completed / dropped / expired are terminal. History is append-only: a state change adds a row, nothing is updated.\n",
          "## Labelled exception classes (ground truth)\n",
          "These are written to `ground_truth/ground_truth.csv` with columns "
          + ", ".join(f"`{c}`" for c in S.GROUND_TRUTH_COLUMNS) + ". Input tables carry **no** label column.\n", ISSUES,
          "Also in `ground_truth/`: `ground_truth_learners.csv` (hidden engagement segment, true ability, true inactivity) - latent variables used "
          "to simulate behaviour; never feature columns.\n"]
    return "\n".join(L)


def write_docs(out_dir: str) -> list:
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for fn, body in (("data_dictionary.md", data_dictionary()), ("schema.sql", ddl())):
        p = os.path.join(out_dir, fn)
        with open(p, "w") as f:
            f.write(body)
        paths.append(p)
    return paths

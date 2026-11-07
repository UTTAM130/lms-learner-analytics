"""SQL artefacts: DDL generated from schema.py, INSERT-based seed file, SQLite loader."""
from __future__ import annotations

import os
import sqlite3

import pandas as pd

from . import schema as S

SQL_TYPE = {"string": "TEXT", "integer": "INTEGER", "decimal": "REAL", "boolean": "TEXT", "date": "TEXT", "timestamp": "TEXT"}


def ddl() -> str:
    out = ["-- Generated from lms_synth/schema.py (do not edit by hand). SQLite / ANSI-compatible.",
           "-- Empty CSV cells are NULL. booleans are 'true'/'false'; timestamps ISO-8601 UTC text.",
           "-- NOTE: activity_events.enrollment_id carries the labelled 'activity from an unenrolled learner'",
           "-- exception, so rows violating that one FK are expected (see ground_truth/).", ""]
    for name in S.LOAD_ORDER:
        t = S.TABLES[name]
        cols = []
        for f in t.fields:
            c = f"  {f.name} {SQL_TYPE[f.type]}"
            if f.name == t.pk:
                c += " PRIMARY KEY"
            elif f.required:
                c += " NOT NULL"
            if f.type == "boolean":
                c += f" CHECK ({f.name} IN ('true','false'))" if f.required else f" CHECK ({f.name} IS NULL OR {f.name} IN ('true','false'))"
            if f.enum and f.type != "boolean":
                vals = ",".join(f"'{v}'" for v in f.enum)
                c += f" CHECK ({f.name} IN ({vals}))" if f.required else f" CHECK ({f.name} IS NULL OR {f.name} IN ({vals}))"
            if f.unique and f.name != t.pk:
                c += " UNIQUE"
            cols.append(c)
        for col, parent, pcol in t.fks:
            cols.append(f"  FOREIGN KEY ({col}) REFERENCES {parent}({pcol})")
        out.append(f"-- {t.description}\nCREATE TABLE {name} (\n" + ",\n".join(cols) + "\n);\n")
    out.append("CREATE INDEX ix_enrollments_cohort ON enrollments(cohort_id);")
    out.append("CREATE INDEX ix_events_enrollment ON activity_events(enrollment_id);")
    out.append("CREATE INDEX ix_events_client ON activity_events(client_event_id);")
    out.append("CREATE INDEX ix_attempts_enrollment ON attempts(enrollment_id, assessment_id);\n")
    return "\n".join(out)


def _lit(v):
    if v == "" or v is None:
        return "NULL"
    return "'" + str(v).replace("'", "''") + "'"


def write_seed_sql(data_dir: str, path: str, batch: int = 500, max_event_rows: int | None = None) -> dict:
    """DDL + multi-row INSERTs for every table. Foreign keys are not enforced during load
    (the labelled orphan events would otherwise abort it)."""
    counts = {}
    with open(path, "w") as fh:
        fh.write(ddl())
        fh.write("\nPRAGMA foreign_keys = OFF;\nBEGIN;\n")
        for name in S.LOAD_ORDER:
            cols = S.TABLES[name].columns
            n = 0
            for ch in pd.read_csv(os.path.join(data_dir, f"{name}.csv"), dtype=str, keep_default_na=False, chunksize=batch):
                if max_event_rows is not None and name == "activity_events" and n >= max_event_rows:
                    break
                vals = ",\n".join("(" + ",".join(_lit(v) for v in row) + ")" for row in ch.itertuples(index=False, name=None))
                fh.write(f"INSERT INTO {name} ({','.join(cols)}) VALUES\n{vals};\n")
                n += len(ch)
            counts[name] = n
        fh.write("COMMIT;\n")
    return counts


def load_sqlite(data_dir: str, db_path: str) -> dict:
    """Load the CSVs into SQLite using the generated DDL; returns table counts and FK-check results."""
    if os.path.exists(db_path):
        os.remove(db_path)
    con = sqlite3.connect(db_path)
    con.executescript(ddl())
    con.execute("PRAGMA foreign_keys = OFF")
    counts = {}
    for name in S.LOAD_ORDER:
        cols = S.TABLES[name].columns
        q = f"INSERT INTO {name} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})"
        n = 0
        for ch in pd.read_csv(os.path.join(data_dir, f"{name}.csv"), dtype=str, keep_default_na=False, chunksize=100_000):
            con.executemany(q, [tuple(None if v == "" else v for v in r) for r in ch.itertuples(index=False, name=None)])
            n += len(ch)
        counts[name] = n
    con.commit()
    fk = con.execute("PRAGMA foreign_key_check").fetchall()
    by_table = {}
    for tbl, _, parent, _ in fk:
        by_table[f"{tbl}->{parent}"] = by_table.get(f"{tbl}->{parent}", 0) + 1
    con.close()
    return {"rows": counts, "fk_violations": by_table}

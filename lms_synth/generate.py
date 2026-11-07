"""Generation driver: masters first, then chunked dependent records, then
ground truth, JSON exports, manifest. Everything is a pure function of
(seed, scale, generator version)."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import time

import numpy as np
import pandas as pd

from . import __version__
from . import config as C
from . import schema as S
from .masters import build_masters, master_tables
from .simulate import simulate_chunk


def _frame(tbl: dict, name: str) -> pd.DataFrame:
    return pd.DataFrame({c: tbl[c] for c in S.TABLES[name].columns})


class _Writer:
    def __init__(self, out_dir):
        self.out = out_dir
        self.rows = {}
        self.started = set()

    def write(self, name, df, filename=None):
        path = os.path.join(self.out, filename or f"{name}.csv")
        first = path not in self.started
        df.to_csv(path, mode="w" if first else "a", header=first, index=False, lineterminator="\n")
        self.started.add(path)
        self.rows[name] = self.rows.get(name, 0) + len(df)


def sha256_file(path, block=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(block)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def generate(scale_name="starter", seed=C.DEFAULT_SEED, out_dir="data/starter", chunk=C.CHUNK,
             n_learners=None, n_courses=None, n_enrollments=None, quiet=False):
    """Generate the dataset. Returns the manifest dict."""
    t_start = time.time()
    scale = C.SCALES[scale_name]
    if any(v is not None for v in (n_learners, n_courses, n_enrollments)):
        scale = C.Scale(scale_name, n_learners or scale.n_learners, n_courses or scale.n_courses,
                        n_enrollments or scale.n_enrollments)
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.join(out_dir, "ground_truth"), exist_ok=True)
    log = (lambda *a: None) if quiet else (lambda *a: print(*a, file=sys.stderr, flush=True))

    m = build_masters(scale, seed)
    m.pair_keys = np.sort(m.E.learner.astype(np.int64) * m.K.nc + m.E.course)
    w = _Writer(out_dir)
    for name, tbl in master_tables(m).items():
        w.write(name, _frame(tbl, name))
    log(f"masters written: {scale}")

    n_enr = m.E.n
    m.n_chunks = -(-n_enr // chunk)
    learner_events = np.zeros(m.L.n, dtype=np.int64)
    gt_parts, totals = [], {}
    for ci, lo in enumerate(range(0, n_enr, chunk)):
        hi = min(lo + chunk, n_enr)
        res = simulate_chunk(m, ci, lo, hi)
        w.write("enrollments", _frame(res["enrollments"], "enrollments"))
        w.write("enrollment_status_history", _frame(res["history"], "enrollment_status_history"))
        w.write("attempts", _frame(res["attempts"], "attempts"))
        w.write("activity_events", _frame(res["events"], "activity_events"))
        w.write("course_outcomes", _frame(res["outcomes"], "course_outcomes"))
        if res["gt"] is not None:
            gt_parts.append(pd.DataFrame(res["gt"]))
        st = res["stats"]
        np.add.at(learner_events, st.pop("baseline_learner_idx"), 1)
        for k, v in st.items():
            totals[k] = totals.get(k, 0) + v
        log(f"chunk {ci}: enrollments {lo}-{hi}, events {st['n_events']}")

    # ---- ground truth (separate files, never read by generators/validators as features)
    gt = pd.concat(gt_parts, ignore_index=True) if gt_parts else pd.DataFrame(columns=S.GROUND_TRUTH_COLUMNS[1:])
    gt.insert(0, "ground_truth_id", np.char.add("GT-", np.char.zfill(np.arange(1, len(gt) + 1).astype("U8"), 6)))
    gt = gt[S.GROUND_TRUTH_COLUMNS]
    gt.to_csv(os.path.join(out_dir, "ground_truth", "ground_truth.csv"), index=False, lineterminator="\n")
    gt.to_json(os.path.join(out_dir, "ground_truth", "ground_truth.json"), orient="records", indent=1)
    gl = pd.DataFrame({
        "learner_id": m.lrn_id,
        "engagement_segment": np.array(C.SEGMENTS)[m.L.seg],
        "true_ability": np.round(m.L.ability, 3),
        "baseline_event_count": learner_events,
        "true_inactive": np.where(learner_events == 0, "true", "false"),
    })
    gl.to_csv(os.path.join(out_dir, "ground_truth", "ground_truth_learners.csv"), index=False, lineterminator="\n")

    # ---- small tables also as JSON
    for name in ["learners", "courses", "content_items", "assessments", "completion_rules", "cohorts"]:
        pd.read_csv(os.path.join(out_dir, f"{name}.csv"), dtype=str, keep_default_na=False).to_json(
            os.path.join(out_dir, f"{name}.json"), orient="records", indent=1)

    # ---- manifest
    files = {}
    for fn in sorted(os.listdir(out_dir)):
        p = os.path.join(out_dir, fn)
        if os.path.isfile(p) and fn.endswith((".csv", ".json")):
            files[fn] = {"bytes": os.path.getsize(p), "sha256": sha256_file(p),
                         "rows": w.rows.get(fn[:-4]) if fn.endswith(".csv") else None}
    for fn in sorted(os.listdir(os.path.join(out_dir, "ground_truth"))):
        p = os.path.join(out_dir, "ground_truth", fn)
        files["ground_truth/" + fn] = {"bytes": os.path.getsize(p), "sha256": sha256_file(p), "rows": None}
    manifest = {
        "generator": "lms_synth", "generator_version": __version__, "seed": seed,
        "scale": {"name": scale.name, "learners": scale.n_learners, "courses": scale.n_courses,
                  "enrollments": scale.n_enrollments},
        "chunk_size": chunk, "as_of_utc": str(np.datetime64(C.AS_OF_SEC, "s")) + "Z",
        "row_counts": w.rows, "anomaly_counts": {k: int(v) for k, v in totals.items() if k != "n_events"},
        "command": f"python -m lms_synth generate --scale {scale_name} --seed {seed} --out {out_dir}",
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__},
        "external_data": "none - fully synthetic; no third-party datasets, no personal data",
        "files": files, "generation_seconds": round(time.time() - t_start, 1),
    }
    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    log(f"done in {manifest['generation_seconds']}s: {w.rows}")
    return manifest

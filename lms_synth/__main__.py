"""Command line: python -m lms_synth <command> ..."""
from __future__ import annotations

import argparse
import json
import sys

from . import config as C


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m lms_synth", description="Synthetic LMS learner-analytics data generator")
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate", help="generate a dataset (CSV + JSON + ground truth + manifest)")
    g.add_argument("--scale", default="starter", choices=list(C.SCALES))
    g.add_argument("--seed", type=int, default=C.DEFAULT_SEED)
    g.add_argument("--out", default=None, help="output dir (default data/<scale>)")
    g.add_argument("--learners", type=int); g.add_argument("--courses", type=int); g.add_argument("--enrollments", type=int)
    for name, h in (("validate", "run validation checks"), ("metrics", "compute engagement / completion metrics"),
                    ("evaluate", "score detectors against ground truth"), ("sql", "write SQL seed file"),
                    ("sqlite", "load CSVs into a SQLite db and run the FK check"), ("all", "validate + metrics + evaluate")):
        s = sub.add_parser(name, help=h)
        s.add_argument("--data", required=True, help="dataset directory")
        if name == "sql":
            s.add_argument("--out", default=None)
        if name == "sqlite":
            s.add_argument("--db", default="lms.db")
    d = sub.add_parser("docs", help="write data dictionary + DDL"); d.add_argument("--out", default="docs")
    r = sub.add_parser("repro", help="regenerate twice and compare checksums")
    r.add_argument("--scale", default="starter", choices=list(C.SCALES)); r.add_argument("--seed", type=int, default=C.DEFAULT_SEED)
    r.add_argument("--out", default=None)
    a = p.parse_args(argv)

    if a.cmd == "generate":
        from .generate import generate
        m = generate(a.scale, a.seed, a.out or f"data/{a.scale}", n_learners=a.learners, n_courses=a.courses, n_enrollments=a.enrollments)
        print(json.dumps({"row_counts": m["row_counts"], "anomaly_counts": m["anomaly_counts"]}, indent=1))
    elif a.cmd in ("validate", "all"):
        from .validate import validate
        s = validate(a.data)
        print(f"validation: {s['checks']} checks, {s['passed']} passed, {s['failed']} failed, {s['info']} informational")
        for x in s["results"]:
            if x["status"] == "FAIL":
                print("FAIL", x["group"], x["check"], x["detail"])
        if a.cmd == "all":
            from .evaluate import evaluate
            from .metrics import compute_metrics
            print(json.dumps(compute_metrics(a.data)["summary"], indent=1))
            ev = evaluate(a.data)
            for k, v in ev["detectors"].items():
                print(f"{k}: precision {v['precision']} recall {v['recall']}")
        return 1 if s["failed"] else 0
    elif a.cmd == "metrics":
        from .metrics import compute_metrics
        print(json.dumps(compute_metrics(a.data)["summary"], indent=1))
    elif a.cmd == "evaluate":
        from .evaluate import evaluate
        print(json.dumps(evaluate(a.data)["detectors"], indent=1))
    elif a.cmd == "sql":
        from .sqlgen import write_seed_sql
        print(write_seed_sql(a.data, a.out or f"{a.data}/seed.sql"))
    elif a.cmd == "sqlite":
        from .sqlgen import load_sqlite
        print(json.dumps(load_sqlite(a.data, a.db), indent=1))
    elif a.cmd == "docs":
        from .docs import write_docs
        print(write_docs(a.out))
    elif a.cmd == "repro":
        from .repro import reproducibility_check
        rep = reproducibility_check(a.scale, a.seed, a.out)
        print(json.dumps({k: v for k, v in rep.items() if not k.startswith("checksums")}, indent=1))
        return 0 if rep["reproducible"] else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

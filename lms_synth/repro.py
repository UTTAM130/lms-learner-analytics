"""Step 10 - regenerate twice with the same seed and compare row counts and checksums.
A control run with a different seed shows the comparison can actually fail."""
from __future__ import annotations

import json
import os
import shutil
import tempfile

from . import config as C
from .generate import generate


def _fingerprint(man):
    return {"row_counts": man["row_counts"], "files": {k: v["sha256"] for k, v in man["files"].items()}}


def reproducibility_check(scale="starter", seed=C.DEFAULT_SEED, out_path=None, keep=False):
    tmp = tempfile.mkdtemp(prefix="lms_repro_")
    try:
        runs = []
        for i in (1, 2):
            runs.append(_fingerprint(generate(scale, seed, os.path.join(tmp, f"run{i}"), quiet=True)))
        ctrl = _fingerprint(generate(scale, seed + 1, os.path.join(tmp, "control"), quiet=True))
    finally:
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)
    a, b = runs
    diff = [k for k in a["files"] if a["files"][k] != b["files"].get(k)]
    rep = {
        "scale": scale, "seed": seed,
        "row_counts_identical": a["row_counts"] == b["row_counts"],
        "all_file_checksums_identical": not diff and a["files"].keys() == b["files"].keys(),
        "files_compared": len(a["files"]), "differing_files": diff,
        "control_seed": seed + 1,
        "control_differs_from_baseline": sum(a["files"][k] != ctrl["files"].get(k) for k in a["files"]),
        "row_counts": a["row_counts"], "checksums_run1": a["files"], "checksums_run2": b["files"],
    }
    rep["reproducible"] = rep["row_counts_identical"] and rep["all_file_checksums_identical"]
    if out_path:
        with open(out_path, "w") as f:
            json.dump(rep, f, indent=1)
    return rep

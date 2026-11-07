#!/usr/bin/env bash
# Full-scale run: generate (20k learners / 500 courses / 100k enrollments / ~2M events), validate,
# metrics, detector evaluation and the two-run reproducibility check. ~3 minutes, ~1 GB RAM.
set -euo pipefail
cd "$(dirname "$0")/.."
python -m lms_synth generate --scale full --seed 20261022 --out data/full
python -m lms_synth all --data data/full
python -m lms_synth repro --scale full --out data/full/reproducibility_report.json

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from lms_synth.generate import generate  # noqa: E402


@pytest.fixture(scope="session")
def tiny_dir(tmp_path_factory):
    d = str(tmp_path_factory.mktemp("tiny"))
    generate("tiny", out_dir=d, quiet=True)
    return d


@pytest.fixture(scope="session")
def tables(tiny_dir):
    names = ["learners", "courses", "cohorts", "content_items", "assessments", "completion_rules", "enrollments",
             "enrollment_status_history", "attempts", "activity_events", "course_outcomes"]
    return {n: pd.read_csv(os.path.join(tiny_dir, f"{n}.csv"), dtype=str, keep_default_na=False) for n in names}


@pytest.fixture(scope="session")
def gt(tiny_dir):
    return pd.read_csv(os.path.join(tiny_dir, "ground_truth", "ground_truth.csv"), dtype=str, keep_default_na=False)

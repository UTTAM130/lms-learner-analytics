"""Edge cases, dedup, completion rule, metrics windows, detectors, reproducibility, SQL."""
import json
import os
import sqlite3

import numpy as np
import pandas as pd

from lms_synth.eventscan import dedup_keep_first, load_events
from lms_synth.evaluate import evaluate
from lms_synth.generate import generate
from lms_synth.metrics import COHORT_WINDOW_WEEKS, compute_metrics
from lms_synth.sqlgen import load_sqlite


def test_all_four_edge_cases_are_present_and_labelled(gt):
    counts = gt.groupby("issue_type").size()
    for issue in ("duplicate_event", "activity_unenrolled", "completion_before_required_assessment", "timezone_shift"):
        assert counts[issue] >= 10, issue


def test_dedup_removes_exactly_the_labelled_duplicates(tiny_dir, gt):
    ev = load_events(tiny_dir)
    keep = dedup_keep_first(ev)
    assert (~keep).sum() == (gt.issue_type == "duplicate_event").sum()
    # after dedup every client_event_id is unique
    assert len(np.unique(ev.ckey[keep])) == keep.sum()


def test_duplicates_inflate_raw_engagement(tiny_dir):
    r = compute_metrics(tiny_dir, write=False)
    w = r["weekly"]
    # raw = UTC-day weeks incl. duplicates/orphans; clean = learner-local weeks, deduplicated and valid only
    assert w.raw_events.sum() > w.events.sum()
    assert w.raw_events.sum() - w.events.sum() >= (pd.read_csv(os.path.join(tiny_dir, "ground_truth", "ground_truth.csv")).issue_type == "duplicate_event").sum()
    assert w.raw_engaged_learners.sum() > w.engaged_learners.sum()


def test_completion_follows_rule_and_premature_marks_are_found(tiny_dir, gt):
    rep = evaluate(tiny_dir, write=False)
    d = rep["detectors"]["completion_before_required_assessment"]
    assert d["precision"] == 1.0 and d["recall"] == 1.0
    out = pd.read_csv(os.path.join(tiny_dir, "course_outcomes.csv"), dtype=str, keep_default_na=False)
    labelled = set(gt[gt.issue_type == "completion_before_required_assessment"].record_id)
    flagged = set(out[out.completion_conflict == "true"].enrollment_id)
    assert labelled == flagged
    # outcome_status is rule-based, so labelled enrollments are NOT counted as completed unless the rule is met
    a = out[out.enrollment_id.isin(set(gt[gt.subtype == "required_assessment_not_passed"].record_id))]
    assert (a.outcome_status != "completed").all()


def test_detector_scores(tiny_dir):
    d = evaluate(tiny_dir, write=False)["detectors"]
    assert d["duplicate_event"]["f1"] == 1.0
    assert d["activity_unenrolled"]["f1"] == 1.0
    assert d["timezone_shift"]["precision"] == 1.0 and d["timezone_shift"]["recall"] > 0.8
    assert d["timezone_shift"]["recall_offline_sync_platform"] == 0.0  # documented limitation


def test_ground_truth_integrity(tiny_dir):
    assert all(evaluate(tiny_dir, write=False)["integrity"].values())


def test_cohort_comparisons_use_identical_windows(tiny_dir):
    cm = compute_metrics(tiny_dir, write=False)["cohort"]
    full = cm[cm.early_window_complete]
    assert len(full) > 0
    assert full[[f"week{k}_active_rate" for k in range(COHORT_WINDOW_WEEKS)]].notna().all().all()
    partial = cm[~cm.early_window_complete]
    assert partial[[f"week{k}_active_rate" for k in range(COHORT_WINDOW_WEEKS)]].isna().all().all()
    # completion rates only for cohorts whose completion window has closed (no right-censoring)
    assert cm[~cm.window_closed].completed_rate.isna().all()
    assert cm[cm.window_closed & (cm.enrollments > 0)].completed_rate.notna().all()


def test_timezone_shift_changes_local_day(tiny_dir, gt):
    tz = gt[gt.issue_type == "timezone_shift"]
    obs = tz.observed_value.str.replace("assigned_local_date=", "", regex=False)
    tru = tz.true_value.str.replace("true_local_date=", "", regex=False)
    assert (obs != tru).all()


def test_same_seed_reproduces_and_other_seed_differs(tmp_path):
    a = generate("tiny", out_dir=str(tmp_path / "a"), quiet=True)
    b = generate("tiny", out_dir=str(tmp_path / "b"), quiet=True)
    c = generate("tiny", seed=1, out_dir=str(tmp_path / "c"), quiet=True)
    assert a["row_counts"] == b["row_counts"]
    assert {k: v["sha256"] for k, v in a["files"].items()} == {k: v["sha256"] for k, v in b["files"].items()}
    assert a["files"]["activity_events.csv"]["sha256"] != c["files"]["activity_events.csv"]["sha256"]


def test_scale_is_parameterised(tmp_path):
    m = generate("tiny", out_dir=str(tmp_path / "s"), n_learners=120, n_courses=8, n_enrollments=400, quiet=True)
    assert m["row_counts"]["learners"] == 120 and m["row_counts"]["courses"] == 8 and m["row_counts"]["enrollments"] == 400


def test_sqlite_load_and_fk_check(tiny_dir, tmp_path):
    r = load_sqlite(tiny_dir, str(tmp_path / "t.db"))
    gt_n = (pd.read_csv(os.path.join(tiny_dir, "ground_truth", "ground_truth.csv")).subtype == "never_enrolled").sum()
    assert r["fk_violations"] == {"activity_events->enrollments": int(gt_n)}
    con = sqlite3.connect(str(tmp_path / "t.db"))
    assert con.execute("select count(*) from enrollments").fetchone()[0] == 1500

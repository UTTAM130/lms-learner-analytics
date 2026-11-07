"""Structure, IDs, keys, lifecycle, derived values and ground-truth separation on the tiny dataset."""
import json
import os
import re

import numpy as np
import pandas as pd

from lms_synth import schema as S
from lms_synth.validate import validate


def test_validation_has_no_hard_failures(tiny_dir):
    s = validate(tiny_dir, write=False)
    failed = [r for r in s["results"] if r["status"] == "FAIL"]
    assert not failed, failed
    assert s["checks"] > 250


def test_columns_match_data_dictionary(tables):
    for name, df in tables.items():
        assert list(df.columns) == S.TABLES[name].columns


def test_primary_keys_unique_and_ids_formatted(tables):
    rx = {"learners": r"LRN-\d{6}", "courses": r"CRS-\d{6}", "assessments": r"ASM-2026-\d{6}",
          "enrollments": r"ENR-LRN-\d{6}-CRS-\d{6}", "activity_events": r"EVT-ENR-LRN-\d{6}-CRS-\d{6}-\d{6}"}
    for name, df in tables.items():
        pk = S.TABLES[name].pk
        assert df[pk].is_unique, name
        if name in rx:
            assert df[pk].str.fullmatch(rx[name]).all(), name


def test_enrollment_id_is_learner_and_course(tables):
    e = tables["enrollments"]
    assert (e.enrollment_id == "ENR-" + e.learner_id + "-" + e.course_id).all()


def test_foreign_keys_valid_except_labelled_orphans(tables, gt):
    for name, df in tables.items():
        for col, parent, pcol in S.TABLES[name].fks:
            if name == "activity_events" and col in ("enrollment_id", "attempt_id"):
                continue
            vals = df[col][df[col] != ""]
            assert vals.isin(set(tables[parent][pcol])).all(), (name, col)
    ev = tables["activity_events"]
    orphan = ev[~ev.enrollment_id.isin(set(tables["enrollments"].enrollment_id))]
    labelled = set(gt[(gt.issue_type == "activity_unenrolled") & (gt.subtype == "never_enrolled")].record_id)
    assert set(orphan.event_id) == labelled and len(labelled) > 0


def test_history_is_append_only_and_follows_state_machine(tables):
    h = tables["enrollment_status_history"]
    for _, g in h.groupby("enrollment_id"):
        prev = None
        for _, r in g.iterrows():
            assert r.status in S.TRANSITIONS[prev]
            prev = r.status
    cur = h.groupby("enrollment_id").tail(1).set_index("enrollment_id").status
    e = tables["enrollments"].set_index("enrollment_id")
    assert (cur.reindex(e.index) == e.current_status).all()


def test_attempts_repeated_and_bounded(tables):
    a = tables["attempts"].assign(no=lambda d: d.attempt_no.astype(int))
    mx = tables["assessments"].set_index("assessment_id").max_attempts.astype(int)
    assert (a.no <= a.assessment_id.map(mx)).all()
    assert (a.no > 1).any(), "repeated attempts must exist"
    assert (a.status == "abandoned").any()
    sub = a[a.status == "submitted"]
    ps = sub.assessment_id.map(tables["assessments"].set_index("assessment_id").passing_score.astype(float))
    assert ((sub.score.astype(float) >= ps) == (sub.passed == "true")).all()


def test_derived_values_reconcile(tables):
    out = tables["course_outcomes"]
    pct = out.required_content_completed.astype(float) / out.required_content_total.astype(float) * 100
    assert np.allclose(pct, out.content_completion_pct.astype(float), atol=0.006)
    w = tables["assessments"]
    assert (w[w.is_required == "true"].groupby("course_id").weight_pct.apply(lambda s: s.astype(float).sum()).round(2) == 100).all()
    completed = out[out.outcome_status == "completed"]
    assert (completed.required_assessments_passed == completed.required_assessments_total).all()


def test_baseline_coverage(tables, tiny_dir):
    ev = tables["activity_events"]
    assert len(tables["enrollments"]) == 1500
    assert 15 < len(ev) / len(tables["enrollments"]) < 25  # ~20 events per enrollment as specified
    assert set(ev.platform) == {"web", "mobile_app", "mobile_offline_sync"}
    lag = pd.to_datetime(ev.ingested_at_utc) - pd.to_datetime(ev.event_time_utc)
    assert (lag > pd.Timedelta(days=1)).any(), "late events must exist"
    ev_by_learner = set(ev.learner_id)
    assert len(ev_by_learner) < len(tables["learners"]), "inactive learners must exist"


def test_ground_truth_is_separate_and_not_leaked(tiny_dir, tables, gt):
    assert os.path.exists(os.path.join(tiny_dir, "ground_truth", "ground_truth.csv"))
    assert os.path.exists(os.path.join(tiny_dir, "ground_truth", "ground_truth.json"))
    banned = re.compile(r"issue_type|ground_truth|expected_decision|true_value|true_ability|segment|injected")
    for name, df in tables.items():
        assert not [c for c in df.columns if banned.search(c)], name
    assert set(gt.issue_type) == set(S.ISSUE_TYPES)
    # hidden latent columns live only under ground_truth/
    gl = pd.read_csv(os.path.join(tiny_dir, "ground_truth", "ground_truth_learners.csv"))
    assert "true_ability" in gl.columns


def test_manifest_lists_checksums(tiny_dir):
    m = json.load(open(os.path.join(tiny_dir, "manifest.json")))
    assert m["seed"] == 20261022 and m["external_data"].startswith("none")
    assert all(len(v["sha256"]) == 64 for v in m["files"].values())
    assert m["row_counts"]["enrollments"] == 1500

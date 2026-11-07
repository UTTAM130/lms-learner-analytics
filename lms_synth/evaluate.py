"""Detector evaluation against the separate ground truth.

Four rule-based detectors look *only* at the delivered input tables (never at ground_truth/) and
flag suspicious events / enrollments. Their output is scored against ground_truth.csv, which is
read here and nowhere else. The score shows (a) that every labelled anomaly is actually present
and discoverable in the data and (b) which anomaly types are inherently hard (time shifts on
offline-synced events).

Detectors
  duplicate_event       a delivery whose client_event_id was already ingested earlier
  activity_unenrolled   event whose enrollment_id has no enrollment, or whose time precedes enrolled_at
  timezone_shift        online event whose ingestion lag equals minus the learner's UTC offset
                        (event_time was stamped with local clock time instead of UTC)
  completion_before_required_assessment
                        platform completion mark not backed by the rule recomputed from events/attempts
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from . import config as C
from .eventscan import dedup_keep_first, load_events, num, to_secs
from .metrics import _tables, valid_mask
from .recompute import recompute_outcomes
from .validate import _load_tables

TZ_TOLERANCE_S = 900


def _evkey(lrn, crs, seq):
    return (lrn.astype(np.int64) * 1_000_000 + crs.astype(np.int64)) * 10_000_000 + seq.astype(np.int64)


def _gt_evkey(ids: pd.Series) -> np.ndarray:
    return _evkey(num(ids, 12, 18), num(ids, 23, 29), num(ids, 30, 36))


def _prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else float("nan")
    r = tp / (tp + fn) if tp + fn else float("nan")
    f = 2 * p * r / (p + r) if p == p and r == r and (p + r) else float("nan")
    return {"tp": int(tp), "fp": int(fp), "fn": int(fn), "precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4)}


def evaluate(data_dir: str, ev=None, T=None, write=True) -> dict:
    T = T or _load_tables(data_dir)
    ev = ev or load_events(data_dir, attempt_ids=set(T["attempts"].attempt_id))
    gt = pd.read_csv(os.path.join(data_dir, "ground_truth", "ground_truth.csv"), dtype=str, keep_default_na=False)
    keep = dedup_keep_first(ev)
    ekey = _evkey(ev.lrn_e, ev.crs_e, ev.seq)
    report = {"ground_truth_rows": len(gt), "detectors": {}, "integrity": {}}

    # --- ground-truth integrity: every labelled record exists in the data
    g_ev = gt[gt.record_type == "activity_event"]
    g_en = gt[gt.record_type == "enrollment"]
    report["integrity"]["event_labels_found_in_events"] = bool(np.isin(_gt_evkey(g_ev.record_id), ekey).all())
    report["integrity"]["enrollment_labels_found_in_enrollments"] = bool(g_en.record_id.isin(set(T["enrollments"].enrollment_id)).all())
    report["integrity"]["ground_truth_id_unique"] = bool(gt.ground_truth_id.is_unique)
    report["integrity"]["labelled_records_unique"] = bool(not gt.duplicated(["record_id", "issue_type"]).any())

    # --- detectors ------------------------------------------------------------------
    enr = T["enrollments"]
    keys = num(enr.enrollment_id, 8, 14) * 1_000_000 + num(enr.enrollment_id, 19, 25)
    order = np.argsort(keys)
    pos = np.minimum(np.searchsorted(keys[order], ev.enr_key), len(keys) - 1)
    resolved = keys[order][pos] == ev.enr_key
    enrolled_at = to_secs(enr.enrolled_at)[order][pos]
    d_dup = ~keep
    d_unen = (~resolved) | (resolved & (ev.t < enrolled_at))
    lrn = T["learners"]
    off = np.zeros(int(num(lrn.learner_id, 4, 10).max()) + 1, dtype=np.int64)
    off[num(lrn.learner_id, 4, 10)] = lrn.utc_offset_minutes.astype(int).to_numpy()
    lag = ev.ing - ev.t
    online = ev.plat != 2  # offline-sync lag is unconstrained, so lag carries no signal there
    d_tz = online & (off[ev.lrn] != 0) & (np.abs(lag + off[ev.lrn] * 60) <= TZ_TOLERANCE_S)

    def score_events(issue, flag, gt_rows, extra=None):
        truth = np.isin(ekey, _gt_evkey(gt_rows.record_id))
        r = _prf((flag & truth).sum(), (flag & ~truth).sum(), (~flag & truth).sum())
        r["labelled"] = int(truth.sum())
        r["flagged"] = int(flag.sum())
        if extra:
            r.update(extra(flag, truth))
        report["detectors"][issue] = r
        return flag, truth

    score_events("duplicate_event", d_dup, g_ev[g_ev.issue_type == "duplicate_event"])
    g_un = g_ev[g_ev.issue_type == "activity_unenrolled"]
    f, t = score_events("activity_unenrolled", d_unen, g_un)
    report["detectors"]["activity_unenrolled"]["by_subtype"] = {
        s: round(float(np.isin(ekey[f], _gt_evkey(g_un[g_un.subtype == s].record_id)).sum() / max((g_un.subtype == s).sum(), 1)), 4)
        for s in sorted(g_un.subtype.unique())}
    g_tz = g_ev[g_ev.issue_type == "timezone_shift"]

    def tz_extra(flag, truth):
        tk = np.isin(ekey, _gt_evkey(g_tz[g_tz.subtype == "offset_missing"].record_id))
        pk = np.isin(ekey, _gt_evkey(g_tz[g_tz.subtype == "offset_present"].record_id))
        offline = ev.plat == 2
        return {"recall_offset_missing": round(float((flag & tk).sum() / max(tk.sum(), 1)), 4),
                "recall_offset_present": round(float((flag & pk).sum() / max(pk.sum(), 1)), 4),
                "recall_online_platforms": round(float((flag & truth & online).sum() / max((truth & online).sum(), 1)), 4),
                "recall_offline_sync_platform": round(float((flag & truth & offline).sum() / max((truth & offline).sum(), 1)), 4),
                "labelled_on_offline_sync": int((truth & offline).sum())}
    f, t = score_events("timezone_shift", d_tz, g_tz, tz_extra)
    # effect of the correction: share of flagged true positives whose corrected local date equals the labelled true date
    # The stamped time is the local clock time (true instant + offset); the true local date is therefore
    # simply the date of the stamped time: ((t - off) + off) // 86400 == t // 86400.
    corr_day = ev.t // 86400
    tp = f & t
    true_d = pd.Series(g_tz.true_value.str.replace("true_local_date=", "", regex=False).to_numpy(),
                       index=_gt_evkey(g_tz.record_id))
    got = pd.Series(pd.to_datetime(corr_day[tp], unit="D").strftime("%Y-%m-%d").to_numpy(), index=ekey[tp])
    report["detectors"]["timezone_shift"]["corrected_date_matches_truth"] = round(float((got == true_d.reindex(got.index)).mean()), 4) if tp.any() else None

    # completion: recompute from events/attempts and compare the platform mark with the rule
    E = recompute_outcomes(T, ev, keep)
    plat = to_secs(T["course_outcomes"].set_index("enrollment_id").reindex(E.enrollment_id).platform_completed_at_utc)
    flag = (plat >= 0) & ((~E.met.to_numpy()) | (plat < E.met_time.to_numpy()))
    g_c = g_en[g_en.issue_type == "completion_before_required_assessment"]
    truth = E.enrollment_id.isin(set(g_c.record_id)).to_numpy()
    r = _prf((flag & truth).sum(), (flag & ~truth).sum(), (~flag & truth).sum())
    r.update(labelled=int(truth.sum()), flagged=int(flag.sum()))
    sub = {}
    for s in sorted(g_c.subtype.unique()):
        ts = E.enrollment_id.isin(set(g_c[g_c.subtype == s].record_id)).to_numpy()
        sub[s] = {"labelled": int(ts.sum()), "recall": round(float((flag & ts).sum() / max(ts.sum(), 1)), 4)}
    r["by_subtype"] = sub
    report["detectors"]["completion_before_required_assessment"] = r

    # --- impact of data-quality handling on headline metrics (needs the cleaning from metrics.py)
    ok, _ = valid_mask(T, ev, keep)
    n_dup = int((~keep).sum())
    report["impact"] = {
        "events_delivered": int(ev.n), "duplicate_rows": n_dup, "duplicate_share": round(n_dup / ev.n, 5),
        "orphan_or_pre_enrollment_events": int(d_unen.sum()),
        "events_valid_for_metrics": int(ok.sum()),
        "premature_completions_in_platform_marks": int(flag.sum()),
        "completions_by_platform_mark": int((plat >= 0).sum()),
        "completions_by_rule": int(E.met.sum()),
        "completion_rate_overstatement_pct": round(float(((plat >= 0).sum() / max(E.met.sum(), 1) - 1) * 100), 3),
    }
    # labelled counts reconcile with what was injected
    report["ground_truth_counts"] = gt.groupby(["issue_type", "subtype"]).size().rename("rows").reset_index().to_dict("records")
    if write:
        with open(os.path.join(data_dir, "evaluation_report.json"), "w") as fh:
            json.dump(report, fh, indent=1)
        with open(os.path.join(data_dir, "evaluation_report.md"), "w") as fh:
            fh.write(to_markdown(report))
    return report


def to_markdown(r: dict) -> str:
    L = ["# Detector evaluation vs ground truth\n",
         "Detectors read only the input tables; `ground_truth/` is used here, for scoring, and nowhere else.\n",
         "| issue type | labelled | flagged | TP | FP | FN | precision | recall | F1 |", "|---|---|---|---|---|---|---|---|---|"]
    for k, v in r["detectors"].items():
        L.append(f"| {k} | {v['labelled']} | {v['flagged']} | {v['tp']} | {v['fp']} | {v['fn']} | {v['precision']} | {v['recall']} | {v['f1']} |")
    L.append("\nDetail:\n")
    for k, v in r["detectors"].items():
        extra = {a: b for a, b in v.items() if a not in ("tp", "fp", "fn", "precision", "recall", "f1", "labelled", "flagged")}
        if extra:
            L.append(f"- **{k}**: {json.dumps(extra)}")
    L += ["\nGround-truth integrity: " + json.dumps(r["integrity"]), "\nImpact on headline numbers: " + json.dumps(r["impact"]), ""]
    return "\n".join(L)

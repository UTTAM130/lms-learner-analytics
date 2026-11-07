"""Independent re-derivation of course outcomes from source tables.

This is the executable definition of the completion rule. It is used by the
validator (does the stored outcome follow the rule?) and by the detector
evaluation (does the platform's completion mark follow the rule?). It reads
only the delivered tables and events - never the ground truth.

Rule (per CompletionRule version in force on the cohort start date):
  content_ok  : distinct required video/reading/discussion items with a completion
                event (video_complete | content_complete | discussion_post) inside the
                enrollment window  >=  ceil(min_required_content_pct/100 * required items)
  assessment_ok: every required assessment has a *submitted* attempt with score >= passing_score
  rule_met_at : max(time the content threshold was reached, time the last required assessment was first passed)
Events are deduplicated by client_event_id (keep earliest ingested) and must reference an
existing enrollment and fall inside [enrolled_at, access_end_date + 1 day).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .eventscan import Events, num, to_secs

COMPLETION_TYPES = (2, 3, 4)  # video_complete, content_complete, discussion_post


def date_secs(series: pd.Series, plus_days: int = 0) -> np.ndarray:
    return (series.to_numpy(dtype=str).astype("datetime64[D]").astype(np.int64) + plus_days) * 86400


def recompute_outcomes(T: dict, ev: Events, keep: np.ndarray) -> pd.DataFrame:
    enr, coh, rul = T["enrollments"], T["cohorts"], T["completion_rules"]
    cnt, asm, att = T["content_items"], T["assessments"], T["attempts"]

    E = pd.DataFrame({
        "enrollment_id": enr.enrollment_id.to_numpy(),
        "key": num(enr.enrollment_id, 8, 14) * 1_000_000 + num(enr.enrollment_id, 19, 25),
        "crs": num(enr.course_id, 4, 10),
        "cohort_id": enr.cohort_id.to_numpy(), "rule_id": enr.rule_id.to_numpy(),
        "start": to_secs(enr.enrolled_at),
    })
    cend = pd.Series(date_secs(coh.access_end_date, 1), index=coh.cohort_id.to_numpy())
    E["end"] = E.cohort_id.map(cend).to_numpy()
    pct = pd.Series(rul.min_required_content_pct.astype(int).to_numpy(), index=rul.rule_id.to_numpy())
    E["pct"] = E.rule_id.map(pct).to_numpy()

    # required content per course
    rc = cnt[(cnt.depth == "2") & (cnt.is_required == "true") & cnt.content_type.isin(["video", "reading", "discussion"])]
    rc_cnt = num(rc.content_id, 4, 10)
    rc_crs = pd.Series(num(rc.course_id, 4, 10)).value_counts()
    E["total"] = E.crs.map(rc_crs).fillna(0).astype(int).to_numpy()
    E["k_need"] = np.ceil(E.pct.to_numpy() / 100.0 * E.total.to_numpy() - 1e-9).astype(int)

    # completion events -> earliest valid completion per (enrollment, content)
    m = keep & np.isin(ev.etype, COMPLETION_TYPES) & np.isin(ev.cnt, rc_cnt)
    C = pd.DataFrame({"key": ev.enr_key[m].astype(np.int64), "cnt": ev.cnt[m], "t": ev.t[m]})
    C = C.merge(E[["key", "start", "end"]], on="key", how="inner")
    C = C[(C.t >= C.start) & (C.t < C.end)]
    C = C.groupby(["key", "cnt"], as_index=False).t.min().sort_values(["key", "t"], kind="stable")
    C["rank"] = C.groupby("key").cumcount() + 1
    done = C.groupby("key").size()
    E["done"] = E.key.map(done).fillna(0).astype(int).to_numpy()
    kth = C.merge(E[["key", "k_need"]], on="key")
    kth = kth[kth["rank"] == kth.k_need].set_index("key").t
    E["t_content"] = E.key.map(kth).fillna(-1).astype(np.int64).to_numpy()
    E["content_ok"] = (E.done >= E.k_need) & (E.total > 0)

    # required assessments
    ra = asm[asm.is_required == "true"][["assessment_id", "course_id", "passing_score", "weight_pct"]].copy()
    ra["passing_score"] = ra.passing_score.astype(float)
    ra["weight_pct"] = ra.weight_pct.astype(float)
    a_total = pd.Series(num(ra.course_id, 4, 10)).value_counts()
    E["a_total"] = E.crs.map(a_total).fillna(0).astype(int).to_numpy()
    A = att[att.status == "submitted"].merge(ra, on="assessment_id", how="inner")
    A["score"] = A.score.astype(float)
    A["sub"] = to_secs(A.submitted_at_utc)
    A["pass"] = A.score >= A.passing_score
    best = A.groupby(["enrollment_id", "assessment_id"]).agg(best=("score", "max"), w=("weight_pct", "first")).reset_index()
    best["ws"] = best.best * best.w / 100.0
    fin = best.groupby("enrollment_id").ws.sum()
    P = A[A["pass"]].groupby(["enrollment_id", "assessment_id"], as_index=False).sub.min()
    npass = P.groupby("enrollment_id").size()
    tpass = P.groupby("enrollment_id").sub.max()
    E["a_passed"] = E.enrollment_id.map(npass).fillna(0).astype(int).to_numpy()
    E["t_assess"] = E.enrollment_id.map(tpass).fillna(-1).astype(np.int64).to_numpy()
    E["final"] = E.enrollment_id.map(fin).fillna(0.0).to_numpy()
    E["asm_ok"] = E.a_passed == E.a_total
    E["met"] = E.content_ok & E.asm_ok
    E["met_time"] = np.where(E.met, np.maximum(E.t_content, E.t_assess), -1)
    E["pct_done"] = np.where(E.total > 0, E.done / E.total.clip(lower=1) * 100.0, 0.0)
    return E

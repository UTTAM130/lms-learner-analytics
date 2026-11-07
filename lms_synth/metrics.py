"""Weekly active engagement and completion metrics with explicit definitions.

Every metric is computed from the delivered tables only. Two views are produced so the
effect of data-quality handling is measurable:

  raw   - what a naive pipeline would report: every delivered row counts, dates are UTC dates.
  clean - deduplicated (client_event_id, keep earliest ingested), enrollment must exist,
          event must fall inside [enrolled_at, cohort access_end), week = ISO week (Monday start)
          of the *learner-local* date (learners.utc_offset_minutes).
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from . import config as C
from .eventscan import dedup_keep_first, load_events, num, to_secs
from .recompute import date_secs

ENGAGED_MIN_EVENTS = 5       # "engaged" learner-week = at least this many valid events
COHORT_WINDOW_WEEKS = 4      # consistent early-engagement window: cohort weeks 0..3
FINAL_WINDOW_DAYS = C.GRACE_DAYS

DEFINITIONS = {
    "valid_event": "Row of activity_events that (1) is the first-ingested delivery of its client_event_id, "
                   "(2) references an existing enrollment, and (3) has event_time_utc within "
                   "[enrolled_at, cohort access_end_date + 1 day).",
    "learner_local_date": "UTC date of (event_time_utc + learners.utc_offset_minutes); the learner master offset is "
                          "used (not the device offset, which can be missing).",
    "week": "ISO week, Monday start, of the learner-local date. Weeks are labelled by their Monday.",
    "active_learner_week": "Learner with >= 1 valid event in the week.",
    "engaged_learner_week": f"Learner with >= {ENGAGED_MIN_EVENTS} valid events in the week.",
    "events_per_active_learner": "valid events / active learners in the week.",
    "late_event_share": "Share of the week's valid events ingested after the week had ended (restatement risk "
                        "for a report published at week end).",
    "cohort_week_k_active_rate": f"Enrollments of a cohort with >= 1 valid event in cohort week k (k = 0..{COHORT_WINDOW_WEEKS - 1}, "
                                 "week k = days [7k, 7k+6] after the cohort start date, learner-local) / enrollments of the cohort. "
                                 "Only cohorts whose whole window ended before the data cut-off are compared, so every "
                                 "cohort is measured over exactly the same number of weeks.",
    "completion_rate": "course_outcomes.outcome_status = completed / enrollments, for cohorts whose access window "
                       "(end_date + completion_window_days) closed before the cut-off. Open cohorts are right-censored and excluded.",
    "withdrawal_rate": "outcome_status = withdrawn / enrollments (same cohort set).",
    "median_days_to_complete": "median of (rule_met_at_utc - enrolled_at) in days over completed enrollments.",
    "cohort_comparison": "Cohorts are only compared within the same duration_weeks and start month, i.e. over identical windows.",
}


def _tables(d):
    rd = lambda n, cols=None: pd.read_csv(os.path.join(d, f"{n}.csv"), dtype=str, keep_default_na=False, usecols=cols)
    return {n: rd(n) for n in ("learners", "courses", "cohorts", "enrollments", "course_outcomes")}


def valid_mask(T, ev, keep):
    enr, coh = T["enrollments"], T["cohorts"]
    key = num(enr.enrollment_id, 8, 14) * 1_000_000 + num(enr.enrollment_id, 19, 25)
    start = to_secs(enr.enrolled_at)
    end = date_secs(enr.cohort_id.map(coh.set_index("cohort_id").access_end_date), 1)
    order = np.argsort(key)
    ks = key[order]
    pos = np.searchsorted(ks, ev.enr_key)
    pos = np.minimum(pos, len(ks) - 1)
    res = ks[pos] == ev.enr_key
    idx = order[pos]
    ok = keep & res & (ev.t >= start[idx]) & (ev.t < end[idx])
    return ok, np.where(res, idx, -1)


def weekly_engagement(T, ev, keep, ok):
    lrn = T["learners"]
    off = np.zeros(int(num(lrn.learner_id, 4, 10).max()) + 1, dtype=np.int64)
    off[num(lrn.learner_id, 4, 10)] = lrn.utc_offset_minutes.astype(int).to_numpy()
    local_day = (ev.t + off[ev.lrn] * 60) // 86400
    wk = (local_day + 3) // 7                     # 1970-01-01 is a Thursday -> Monday-based week number
    wk_raw = (ev.t // 86400 + 3) // 7             # naive UTC week
    ing_wk = (((ev.ing + off[ev.lrn] * 60) // 86400) + 3) // 7

    def agg(mask, wcol, lcol, prefix):
        d = pd.DataFrame({"wk": wcol[mask], "lrn": lcol[mask]})
        per = d.groupby(["wk", "lrn"]).size()
        g = per.groupby("wk")
        return pd.DataFrame({f"{prefix}events": d.groupby("wk").size(), f"{prefix}active_learners": g.size(),
                             f"{prefix}engaged_learners": (per >= ENGAGED_MIN_EVENTS).groupby("wk").sum()})
    clean = agg(ok, wk, ev.lrn, "")
    raw = agg(np.ones(ev.n, bool), wk_raw, ev.lrn, "raw_")
    out = clean.join(raw, how="outer").fillna(0).astype(int)
    late = pd.Series((ing_wk > wk)[ok]).groupby(wk[ok]).mean()
    out["late_event_share"] = late.reindex(out.index).fillna(0).round(4)
    out["events_per_active_learner"] = (out.events / out.active_learners.replace(0, np.nan)).round(2)
    out["raw_events_per_active_learner"] = (out.raw_events / out.raw_active_learners.replace(0, np.nan)).round(2)
    out["engaged_inflation_pct"] = ((out.raw_engaged_learners / out.engaged_learners.replace(0, np.nan) - 1) * 100).round(2)
    out.insert(0, "week_start", pd.to_datetime(out.index * 7 - 3, unit="D").strftime("%Y-%m-%d"))
    return out.reset_index(drop=True)


def cohort_metrics(T, ev, ok, eidx):
    enr, coh, out, crs = T["enrollments"], T["cohorts"], T["course_outcomes"], T["courses"]
    lrn = T["learners"]
    as_of_sec = int(to_secs(out.evaluated_as_of_utc).max())
    as_of_day = as_of_sec // 86400
    c = coh.assign(start=date_secs(coh.start_date) // 86400, access_end=date_secs(coh.access_end_date) // 86400,
                   dur=coh.course_id.map(crs.set_index("course_id").duration_weeks.astype(int)).to_numpy())
    cidx = pd.Series(np.arange(len(c)), index=c.cohort_id)
    e_coh = enr.cohort_id.map(cidx).to_numpy()
    n_enr = np.bincount(e_coh, minlength=len(c))
    o = out.set_index("enrollment_id").reindex(enr.enrollment_id)
    st = o.outcome_status.to_numpy()
    comp = st == "completed"
    to_days = np.where(comp, (to_secs(o.rule_met_at_utc) - to_secs(enr.enrolled_at)) / 86400.0, np.nan)
    res = pd.DataFrame({"cohort_id": c.cohort_id, "course_id": c.course_id, "start_date": c.start_date,
                        "duration_weeks": c.dur, "enrollments": n_enr,
                        "completed": np.bincount(e_coh[comp], minlength=len(c)),
                        "withdrawn": np.bincount(e_coh[st == "withdrawn"], minlength=len(c))})
    res["median_days_to_complete"] = pd.Series(to_days).groupby(e_coh).median().reindex(range(len(c))).round(1).to_numpy()
    res["window_closed"] = (c.access_end < as_of_day).to_numpy()
    res["early_window_complete"] = (c.start + 7 * COHORT_WINDOW_WEEKS <= as_of_day).to_numpy()
    for flag in ("completed", "withdrawn"):
        res[f"{flag}_rate"] = np.where(res.window_closed & (res.enrollments > 0), (res[flag] / res.enrollments.replace(0, np.nan)).round(4), np.nan)

    # early-engagement curve over the identical window for every cohort
    off = np.zeros(int(num(lrn.learner_id, 4, 10).max()) + 1, dtype=np.int64)
    off[num(lrn.learner_id, 4, 10)] = lrn.utc_offset_minutes.astype(int).to_numpy()
    m = ok & (eidx >= 0)
    ei = eidx[m]
    day = (ev.t[m] + off[ev.lrn[m]] * 60) // 86400
    cw = (day - c.start.to_numpy()[e_coh[ei]]) // 7
    inwin = (cw >= 0) & (cw < COHORT_WINDOW_WEEKS)
    pairs = pd.DataFrame({"e": ei[inwin], "w": cw[inwin]}).drop_duplicates()
    pairs["c"] = e_coh[pairs.e.to_numpy()]
    cnt = pairs.groupby(["c", "w"]).size().unstack(fill_value=0).reindex(index=range(len(c)), columns=range(COHORT_WINDOW_WEEKS), fill_value=0)
    for k in range(COHORT_WINDOW_WEEKS):
        res[f"week{k}_active_rate"] = np.where(res.early_window_complete & (res.enrollments > 0), (cnt[k].to_numpy() / res.enrollments.replace(0, np.nan)).round(4), np.nan)
    return res


def comparison(cm):
    """Cohorts compared only within identical windows: same duration, same start month; closed cohorts only."""
    d = cm[cm.window_closed & (cm.enrollments > 0)].copy()
    d["start_month"] = d.start_date.str.slice(0, 7)
    g = d.groupby(["duration_weeks", "start_month"])
    out = g.agg(cohorts=("cohort_id", "size"), enrollments=("enrollments", "sum"), completed=("completed", "sum"),
                withdrawn=("withdrawn", "sum")).reset_index()
    out["completion_rate"] = (out.completed / out.enrollments).round(4)
    out["withdrawal_rate"] = (out.withdrawn / out.enrollments).round(4)
    early = cm[cm.early_window_complete & (cm.enrollments > 0)].copy()
    early["start_month"] = early.start_date.str.slice(0, 7)
    e = early.groupby(["duration_weeks", "start_month"]).apply(
        lambda x: pd.Series({f"week{k}_active_rate": round(float(np.average(x[f"week{k}_active_rate"], weights=x.enrollments)), 4)
                             for k in range(COHORT_WINDOW_WEEKS)}), include_groups=False).reset_index()
    return out.merge(e, on=["duration_weeks", "start_month"], how="outer").sort_values(["duration_weeks", "start_month"])


def course_summary(T, cm):
    crs = T["courses"]
    d = cm[cm.window_closed].groupby("course_id").agg(closed_enrollments=("enrollments", "sum"), completed=("completed", "sum"), withdrawn=("withdrawn", "sum"))
    allc = cm.groupby("course_id").agg(cohorts=("cohort_id", "size"), enrollments=("enrollments", "sum"))
    out = crs[["course_id", "title", "category", "level", "duration_weeks"]].merge(allc, on="course_id", how="left").merge(d, on="course_id", how="left").fillna(0)
    out["completion_rate"] = np.where(out.closed_enrollments > 0, (out.completed / out.closed_enrollments.replace(0, np.nan)).round(4), np.nan)
    return out


def compute_metrics(data_dir: str, ev=None, write=True) -> dict:
    T = _tables(data_dir)
    ev = ev or load_events(data_dir)
    keep = dedup_keep_first(ev)
    ok, eidx = valid_mask(T, ev, keep)
    we = weekly_engagement(T, ev, keep, ok)
    cm = cohort_metrics(T, ev, ok, eidx)
    cmp_ = comparison(cm)
    cs = course_summary(T, cm)
    nl = len(T["learners"])
    lrn_ids = num(T["learners"].learner_id, 4, 10)
    as_of = int(to_secs(T["course_outcomes"].evaluated_as_of_utc).max())
    last = pd.Series(ev.t[ok]).groupby(ev.lrn[ok]).max().reindex(lrn_ids)
    never = int(last.isna().sum())
    dormant = int((last.notna() & (last < as_of - 60 * 86400)).sum())
    summary = {
        "learners": nl, "learners_without_valid_activity": never, "learners_dormant_60d": dormant,
        "events_delivered": int(ev.n), "events_valid": int(ok.sum()), "duplicate_rows_removed": int((~keep).sum()),
        "weeks": len(we), "cohorts": len(cm), "closed_cohorts": int(cm.window_closed.sum()),
        "overall_completion_rate_closed_cohorts": round(float(cm[cm.window_closed].completed.sum() / max(cm[cm.window_closed].enrollments.sum(), 1)), 4),
        "overall_withdrawal_rate_closed_cohorts": round(float(cm[cm.window_closed].withdrawn.sum() / max(cm[cm.window_closed].enrollments.sum(), 1)), 4),
        "engaged_inflation_pct_mean": round(float(we.engaged_inflation_pct.replace([np.inf, -np.inf], np.nan).mean()), 3),
    }
    if write:
        mdir = os.path.join(data_dir, "metrics")
        os.makedirs(mdir, exist_ok=True)
        we.to_csv(os.path.join(mdir, "weekly_engagement.csv"), index=False)
        cm.to_csv(os.path.join(mdir, "cohort_metrics.csv"), index=False)
        cmp_.to_csv(os.path.join(mdir, "cohort_comparison.csv"), index=False)
        cs.to_csv(os.path.join(mdir, "course_completion_summary.csv"), index=False)
        with open(os.path.join(mdir, "metric_definitions.json"), "w") as f:
            json.dump({"definitions": DEFINITIONS, "parameters": {"engaged_min_events": ENGAGED_MIN_EVENTS,
                       "cohort_window_weeks": COHORT_WINDOW_WEEKS, "completion_window_days": FINAL_WINDOW_DAYS}, "summary": summary}, f, indent=1)
    return {"weekly": we, "cohort": cm, "comparison": cmp_, "course": cs, "summary": summary}

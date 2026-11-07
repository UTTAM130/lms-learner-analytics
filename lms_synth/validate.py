"""Step 8 - validation of an exported dataset directory.

Reads only the delivered CSV files (never ground_truth/). Checks are grouped:
  structure, keys, enums/format, foreign keys, dates, lifecycle, arithmetic, events,
  completion rule. FAIL = hard defect in the baseline data model. INFO = the injected
  exception classes that are *expected* to be visible (duplicates, orphans, time shifts,
  premature completions); they are counted, not failed - evaluate.py checks them against
  the ground truth.
"""
from __future__ import annotations

import json
import os
import re

import numpy as np
import pandas as pd

from . import config as C
from . import schema as S
from .eventscan import dedup_keep_first, load_events, num, to_secs
from .recompute import date_secs, recompute_outcomes

TS_RX = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"
DATE_RX = r"\d{4}-\d{2}-\d{2}"
ID_RX = {
    "learner_id": r"LRN-\d{6}", "course_id": r"CRS-\d{6}", "cohort_id": r"COH-\d{6}",
    "content_id": r"CNT-\d{6}", "parent_content_id": r"CNT-\d{6}", "assessment_id": r"ASM-2026-\d{6}",
    "rule_id": r"RUL-\d{6}", "enrollment_id": r"ENR-LRN-\d{6}-CRS-\d{6}",
    "history_id": r"ESH-ENR-LRN-\d{6}-CRS-\d{6}-\d{2}",
    "attempt_id": r"ATT-ENR-LRN-\d{6}-CRS-\d{6}-\d{6}-\d{2}",
    "outcome_id": r"OUT-ENR-LRN-\d{6}-CRS-\d{6}",
}
TYPE_RX = {"integer": r"-?\d+", "decimal": r"-?\d+(\.\d+)?", "boolean": r"true|false", "date": DATE_RX, "timestamp": TS_RX}


class Collector:
    def __init__(self):
        self.rows = []

    def add(self, group, name, ok, detail="", info=False, count=None):
        status = "INFO" if info else ("PASS" if ok else "FAIL")
        self.rows.append({"group": group, "check": name, "status": status, "detail": str(detail),
                          "count": None if count is None else int(count)})

    def eq0(self, group, name, bad, detail=""):
        """PASS iff the number of violating rows is zero."""
        bad = int(bad)
        self.add(group, name, bad == 0, detail or f"{bad} violating rows", count=bad)


def _load_tables(d):
    T = {}
    for name in S.LOAD_ORDER:
        if name == "activity_events":
            continue
        T[name] = pd.read_csv(os.path.join(d, f"{name}.csv"), dtype=str, keep_default_na=False)
    for name in ("content_items", "courses", "assessments", "cohorts", "completion_rules"):
        pass
    return T


def _generic(R, T):
    for name, tbl in T.items():
        spec = S.TABLES[name]
        df = tbl
        R.add("structure", f"{name}: columns match data dictionary", list(df.columns) == spec.columns,
              f"{len(df)} rows")
        for f in spec.fields:
            col = df[f.name]
            if f.required:
                R.eq0("required", f"{name}.{f.name} not empty", (col == "").sum())
            nz = col[col != ""]
            if f.name in ID_RX:
                R.eq0("format", f"{name}.{f.name} id format", (~nz.str.fullmatch(ID_RX[f.name])).sum())
            if f.type in TYPE_RX and f.name not in ID_RX:
                R.eq0("format", f"{name}.{f.name} is {f.type}", (~nz.str.fullmatch(TYPE_RX[f.type])).sum())
            if f.enum:
                R.eq0("enum", f"{name}.{f.name} in allowed values", (~nz.isin(list(f.enum))).sum())
        R.add("keys", f"{name}.{spec.pk} primary key unique", df[spec.pk].is_unique, f"{len(df)} rows")
        for col, parent, pcol in spec.fks:
            if parent == "activity_events" or parent not in T:
                continue
            vals = df[col][df[col] != ""]
            R.eq0("foreign_keys", f"{name}.{col} -> {parent}.{pcol}", (~vals.isin(set(T[parent][pcol]))).sum())
        for f in spec.fields:
            if f.unique and f.name != spec.pk:
                R.add("keys", f"{name}.{f.name} unique", df[f.name][df[f.name] != ""].is_unique)


def _catalogue(R, T):
    crs, cnt, asm, rul, coh = T["courses"], T["content_items"], T["assessments"], T["completion_rules"], T["cohorts"]
    cnt = cnt.assign(depth=cnt.depth.astype(int), seq=cnt.sequence_no.astype(int), mins=cnt.est_minutes.astype(int),
                     week=cnt.week_number.astype(int))
    mod, leaf = cnt[cnt.depth == 1], cnt[cnt.depth == 2]
    c = crs.set_index("course_id")
    R.eq0("arithmetic", "courses.n_modules = module rows", (mod.groupby("course_id").size().reindex(c.index).fillna(0).astype(int) != c.n_modules.astype(int)).sum())
    R.eq0("arithmetic", "courses.n_items = leaf rows", (leaf.groupby("course_id").size().reindex(c.index).fillna(0).astype(int) != c.n_items.astype(int)).sum())
    R.eq0("arithmetic", "courses.total_est_minutes = sum leaf minutes", (leaf.groupby("course_id").mins.sum().reindex(c.index).fillna(0).astype(int) != c.total_est_minutes.astype(int)).sum())
    R.eq0("hierarchy", "module rows: parent null, type=module; leaf rows: parent set", ((mod.parent_content_id != "") | (mod.content_type != "module")).sum() + ((leaf.parent_content_id == "") | (leaf.content_type == "module")).sum())
    par = cnt.set_index("content_id").course_id
    R.eq0("hierarchy", "leaf item course = parent module course", (leaf.parent_content_id.map(par) != leaf.course_id).sum())
    R.add("hierarchy", "sequence_no unique within (course, parent)", not cnt.duplicated(["course_id", "parent_content_id", "seq"]).any())
    dur = cnt.course_id.map(c.duration_weeks.astype(int))
    R.eq0("hierarchy", "week_number within 1..duration_weeks", ((cnt.week < 1) | (cnt.week > dur)).sum())
    msum = leaf.groupby("parent_content_id").mins.sum()
    R.eq0("arithmetic", "module est_minutes = sum of its items", (mod.set_index("content_id").mins != msum.reindex(mod.content_id).fillna(0).astype(int)).sum())
    anyreq = (leaf.is_required == "true").groupby(leaf.parent_content_id).any()
    R.eq0("arithmetic", "module is_required = any item required", ((mod.set_index("content_id").is_required == "true") != anyreq.reindex(mod.content_id).fillna(False)).sum())
    R.eq0("rules", "discussions are never required", ((leaf.content_type == "discussion") & (leaf.is_required == "true")).sum())

    ct = cnt.set_index("content_id")
    a = asm.assign(w=asm.weight_pct.astype(float), mx=asm.max_score.astype(int), ps=asm.passing_score.astype(int))
    R.eq0("hierarchy", "assessment content_type matches assessment_type", (a.content_id.map(ct.content_type) != a.assessment_type).sum())
    R.eq0("hierarchy", "assessment.course_id = content course", (a.content_id.map(ct.course_id) != a.course_id).sum())
    R.eq0("hierarchy", "assessment.is_required = content.is_required", (a.content_id.map(ct.is_required) != a.is_required).sum())
    R.eq0("arithmetic", "required assessment weights sum to 100 per course", ((a[a.is_required == "true"].groupby("course_id").w.sum() - 100).abs() > 0.011).sum())
    R.eq0("arithmetic", "non-required assessment weight = 0", ((a.is_required == "false") & (a.w != 0)).sum())
    n_ass_leaf = leaf.content_type.isin(["quiz", "assignment", "exam"]).sum()
    R.add("hierarchy", "every quiz/assignment/exam item has exactly one assessment", n_ass_leaf == len(a), f"{n_ass_leaf} items vs {len(a)} assessments")
    R.eq0("rules", "passing_score <= max_score", (a.ps > a.mx).sum())

    r = rul.assign(ver=rul.rule_version.astype(int))
    v1, v2 = r[r.ver == 1].set_index("course_id"), r[r.ver == 2].set_index("course_id")
    R.eq0("dates", "rule v1.effective_to + 1 day = v2.effective_from",
          (pd.to_datetime(v1.effective_to) + pd.Timedelta(days=1) != pd.to_datetime(v2.effective_from).reindex(v1.index)).sum())
    R.add("dates", "rule v2 open-ended; one rule per version per course", (v2.effective_to == "").all() and not r.duplicated(["course_id", "ver"]).any())

    k = coh.assign(s=pd.to_datetime(coh.start_date), e=pd.to_datetime(coh.end_date), x=pd.to_datetime(coh.access_end_date))
    R.eq0("dates", "cohort start is a Monday", (k.s.dt.dayofweek != 0).sum())
    R.eq0("dates", "cohort end = start + 7*weeks - 1", (k.e != k.s + pd.to_timedelta(7 * k.course_id.map(c.duration_weeks.astype(int)) - 1, unit="D")).sum())
    R.eq0("dates", "cohort access_end = end + completion window", (k.x != k.e + pd.Timedelta(days=C.GRACE_DAYS)).sum())
    as_of = pd.Timestamp(np.datetime64(C.AS_OF_SEC, "s")).normalize()
    exp = np.where(k.s > as_of, "planned", np.where(k.e >= as_of, "active", np.where(k.x >= as_of, "grace", "closed")))
    R.eq0("lifecycle", "cohort.status consistent with as-of date", (exp != k.status.to_numpy()).sum())
    R.eq0("rules", "instructor_code null iff self_paced", ((k.instructor_code == "") != (k.course_id.map(c.delivery_mode) == "self_paced")).sum())
    pub, ret = pd.to_datetime(crs.published_date), pd.to_datetime(crs.retired_date.replace("", pd.NA))
    R.eq0("lifecycle", "retired iff retired_date <= as-of", ((crs.status == "retired") != (ret.notna() & (ret <= as_of))).sum())
    R.eq0("dates", "cohorts start after course published", (k.s <= k.course_id.map(pd.Series(pub.to_numpy(), index=crs.course_id))).sum())
    rd = k.course_id.map(pd.Series(ret.to_numpy(), index=crs.course_id))
    R.eq0("dates", "no cohort starts within 14 days of retirement", (rd.notna() & (k.s > rd - pd.Timedelta(days=14))).sum())


def _enrollment_side(R, T, as_of_sec):
    enr, his, att, out = T["enrollments"], T["enrollment_status_history"], T["attempts"], T["course_outcomes"]
    coh, rul, lrn, asm = T["cohorts"], T["completion_rules"], T["learners"], T["assessments"]
    R.add("keys", "enrollment_id = ENR-<learner_id>-<course_id>", (enr.enrollment_id == "ENR-" + enr.learner_id + "-" + enr.course_id).all())
    R.add("keys", "one enrollment per (learner, course)", not enr.duplicated(["learner_id", "course_id"]).any())
    R.eq0("foreign_keys", "enrollment.course = cohort.course", (enr.cohort_id.map(coh.set_index("cohort_id").course_id) != enr.course_id).sum())
    # rule snapshot in force on cohort start
    st = pd.to_datetime(enr.cohort_id.map(coh.set_index("cohort_id").start_date))
    rr = rul.assign(f=pd.to_datetime(rul.effective_from), t=pd.to_datetime(rul.effective_to.replace("", "2999-12-31")))
    m = enr.assign(st=st).merge(rr, left_on="rule_id", right_on="rule_id", suffixes=("", "_r"))
    R.eq0("rules", "enrollment.rule_id is the version in force at cohort start",
          ((m.course_id != m.course_id_r) | (m.st < m.f) | (m.st > m.t)).sum() + (len(enr) - len(m)))
    e_at = to_secs(enr.enrolled_at)
    sig = pd.to_datetime(enr.learner_id.map(lrn.set_index("learner_id").signup_date))
    R.eq0("dates", "learner.signup_date <= enrolled_at", (pd.to_datetime(pd.Series(e_at, index=enr.index), unit="s").dt.normalize() < sig).sum())
    xend = date_secs(enr.cohort_id.map(coh.set_index("cohort_id").access_end_date), 1)
    R.eq0("dates", "enrolled_at before cohort access_end and as-of", ((e_at >= xend) | (e_at > as_of_sec)).sum())

    # ---- status history -----------------------------------------------------
    h = his.assign(t=to_secs(his.effective_from)).reset_index(drop=True)
    h["n"] = h.groupby("enrollment_id").cumcount() + 1
    R.add("lifecycle", "history sorted by enrollment then time", (h.groupby("enrollment_id").t.diff().fillna(0) >= 0).all())
    R.eq0("keys", "history_id = ESH-<enrollment_id>-<seq>", (h.history_id != "ESH-" + h.enrollment_id + "-" + h.n.astype(str).str.zfill(2)).sum())
    h["prev"] = h.groupby("enrollment_id").status.shift(1).fillna("")
    R.eq0("lifecycle", "previous_status = status of the prior row", (h.prev != h.previous_status).sum())
    bad = sum(1 for p, s in zip(h.previous_status, h.status) if s not in S.TRANSITIONS[p or None])
    R.eq0("lifecycle", "every transition allowed by the state machine", bad)
    first = h[h.n == 1]
    R.add("lifecycle", "first history row is 'enrolled' at enrolled_at", bool((first.status == "enrolled").all()) and
          (first.set_index("enrollment_id").t.reindex(enr.enrollment_id).to_numpy() == e_at).all())
    R.add("lifecycle", "every enrollment has history", set(h.enrollment_id) == set(enr.enrollment_id))
    last = h.groupby("enrollment_id").tail(1).set_index("enrollment_id")
    R.eq0("lifecycle", "enrollment.current_status = last history status", (last.status.reindex(enr.enrollment_id).to_numpy() != enr.current_status.to_numpy()).sum())
    R.eq0("lifecycle", "enrollment.status_updated_at = last history time", (last.t.reindex(enr.enrollment_id).to_numpy() != to_secs(enr.status_updated_at)).sum())
    R.eq0("dates", "no history row after as-of", (h.t > as_of_sec).sum())

    # ---- attempts -----------------------------------------------------------
    a = att.assign(no=att.attempt_no.astype(int), s=to_secs(att.started_at_utc), u=to_secs(att.submitted_at_utc))
    ai = asm.set_index("assessment_id")
    a["max_att"] = a.assessment_id.map(ai.max_attempts.astype(int))
    R.eq0("lifecycle", "attempt_no <= max_attempts", (a.no > a.max_att).sum())
    g = a.groupby(["enrollment_id", "assessment_id"]).no
    R.add("lifecycle", "attempt numbers consecutive from 1 per (enrollment, assessment)", bool((g.max() == g.size()).all() and (g.min() == 1).all()))
    ordered = a.sort_values(["enrollment_id", "assessment_id", "no"])
    R.add("dates", "later attempts start after the previous one ended", bool((ordered.groupby(["enrollment_id", "assessment_id"]).s.diff().fillna(1) > 0).all()))
    sub = a.status == "submitted"
    R.eq0("dates", "submitted_at >= started_at (submitted)", (a.u[sub] < a.s[sub]).sum())
    R.eq0("required", "abandoned attempts have no submit/score/passed", ((~sub) & ((a.u != -1) | (a.score != "") | (a.passed != ""))).sum())
    R.eq0("required", "submitted attempts have submit/score/passed", (sub & ((a.u == -1) | (a.score == "") | (a.passed == ""))).sum())
    sc = pd.to_numeric(a.score.replace("", np.nan))
    R.eq0("arithmetic", "score within 0..max_score", ((sc < 0) | (sc > a.assessment_id.map(ai.max_score.astype(float)))).sum())
    ps = a.assessment_id.map(ai.passing_score.astype(float))
    R.eq0("arithmetic", "passed = (score >= passing_score)", (sub & ((sc >= ps) != (a.passed == "true"))).sum())
    dm = pd.to_numeric(a.duration_minutes.replace("", np.nan))
    R.eq0("arithmetic", "duration_minutes = (submitted-started)/60", (sub & ((dm - (a.u - a.s) / 60.0).abs() > 0.06)).sum())
    num_asm = num(a.assessment_id, 9)
    R.eq0("keys", "attempt_id = ATT-<enrollment>-<assessment seq>-<attempt_no>",
          (a.attempt_id != "ATT-" + a.enrollment_id + "-" + pd.Series(num_asm).astype(str).str.zfill(6) + "-" + a.no.astype(str).str.zfill(2)).sum())
    ws = a.enrollment_id.map(pd.Series(e_at, index=enr.enrollment_id)).to_numpy()
    R.eq0("dates", "attempts start after enrollment", (a.s.to_numpy() < ws).sum())
    stat = a.enrollment_id.map(enr.set_index("enrollment_id").current_status)
    R.add("lifecycle", "attempts exist only for enrollments with an 'active' history row",
          set(a.enrollment_id) <= set(h[h.status == "active"].enrollment_id))
    R.eq0("keys", "outcome_id = OUT-<enrollment_id>; one outcome per enrollment", (out.outcome_id != "OUT-" + out.enrollment_id).sum() + (set(out.enrollment_id) != set(enr.enrollment_id)))
    return h, e_at


def _events_and_outcomes(R, T, ev, h, e_at, as_of_sec):
    enr, out, att, cnt = T["enrollments"], T["course_outcomes"], T["attempts"], T["content_items"]
    nums = lambda s, a, b: set(num(s, a, b).tolist())
    R.add("structure", "activity_events: row count", ev.n > 0, f"{ev.n} rows")
    for c in [f.name for f in S.EVENT.fields if f.required]:
        R.eq0("required", f"activity_events.{c} not empty", ev.stats[f"empty:{c}"])
    for c in ("event_id", "enrollment_id", "learner_id", "course_id", "content_id", "client_event_id"):
        R.eq0("format", f"activity_events.{c} format", ev.stats[f"badformat:{c}"])
    R.eq0("enum", "activity_events.event_type in allowed values", ev.stats["bad_enum:event_type"])
    R.eq0("enum", "activity_events.platform in allowed values", ev.stats["bad_enum:platform"])
    R.add("keys", "activity_events.event_id primary key unique", len(np.unique(ev.eid_hash)) == ev.n)
    R.eq0("foreign_keys", "activity_events.learner_id -> learners", (~np.isin(ev.lrn, list(nums(T["learners"].learner_id, 4, 10)))).sum())
    R.eq0("foreign_keys", "activity_events.course_id -> courses", (~np.isin(ev.crs, list(nums(T["courses"].course_id, 4, 10)))).sum())
    R.eq0("foreign_keys", "activity_events.content_id -> content_items", (~np.isin(ev.cnt, list(nums(cnt.content_id, 4, 10)))).sum())
    R.eq0("foreign_keys", "activity_events.attempt_id -> attempts", ev.stats["fk_missing:attempt_id"])
    R.add("keys", "event.enrollment_id = ENR-<learner_id>-<course_id>", bool(ev.ids_consistent.all()))
    R.add("keys", "event_id = EVT-<enrollment_id>-<seq>", bool(ev.idpref_ok.all()))
    ccrs = pd.Series(num(cnt.course_id, 4, 10), index=num(cnt.content_id, 4, 10))
    R.eq0("foreign_keys", "event.content_id belongs to event.course_id", (pd.Series(ev.cnt).map(ccrs).to_numpy() != ev.crs).sum())
    R.add("rules", "attempt_id present iff assessment_start/submit", bool((ev.has_att == np.isin(ev.etype, (5, 6))).all()))
    R.eq0("dates", "ingested_at <= as-of", (ev.ing > as_of_sec).sum())
    same = np.r_[False, ev.enr_key[1:] == ev.enr_key[:-1]]
    prev_seq, prev_ing = np.r_[0, ev.seq[:-1]], np.r_[0, ev.ing[:-1]]
    ok_seq = np.where(same, (ev.seq == prev_seq + 1) & (ev.ing >= prev_ing), ev.seq == 1)
    R.eq0("keys", "event_id counter is 1..n per enrollment in ingestion order", (~ok_seq).sum())

    # ---- documented exceptions (INFO) ----------------------------------------
    keep = dedup_keep_first(ev)
    keys = (num(enr.enrollment_id, 8, 14) * 1_000_000 + num(enr.enrollment_id, 19, 25))
    resolved = np.isin(ev.enr_key, keys)
    ndup = int((~keep).sum())
    R.add("exceptions", "duplicate deliveries (same client_event_id)", True, f"{ndup} rows = {ndup / ev.n:.2%} of events", info=True, count=ndup)
    ck = pd.DataFrame({"ck": ev.ckey, "k": ev.enr_key, "c": ev.cnt, "e": ev.etype})
    R.eq0("exceptions", "duplicates repeat enrollment/content/event_type of their first delivery",
          (ck.groupby("ck").nunique().max(axis=1) > 1).sum())
    R.add("exceptions", "events whose enrollment_id has no enrollment record", True, f"{int((~resolved).sum())} rows", info=True, count=(~resolved).sum())
    est = pd.Series(e_at, index=keys).reindex(ev.enr_key)
    before = resolved & (ev.t < est.to_numpy())
    R.add("exceptions", "events earlier than enrolled_at", True, f"{int(before.sum())} rows", info=True, count=before.sum())
    R.add("exceptions", "event_time_utc later than ingested_at_utc (impossible)", True, f"{int((ev.t > ev.ing).sum())} rows", info=True, count=(ev.t > ev.ing).sum())
    R.add("exceptions", "late arrivals (ingestion lag > 24 h)", True, f"{int((ev.ing - ev.t > 86400).sum())} rows; offline-sync + backfill, legitimate", info=True, count=(ev.ing - ev.t > 86400).sum())
    R.add("exceptions", "events with missing device UTC offset", True, f"{int((ev.off == -99999).sum())} rows", info=True, count=(ev.off == -99999).sum())

    # ---- lifecycle: valid activity vs dropped state ------------------------------
    dropped = h[h.status == "dropped"].set_index("enrollment_id").t
    dt = pd.Series(ev.enr_key).map(pd.Series(dropped.reindex(enr.enrollment_id).to_numpy(), index=keys)).to_numpy()
    after_drop = resolved & keep & ~np.isnan(dt) & (ev.t > dt)
    R.eq0("lifecycle", "no activity after an enrollment was dropped", after_drop.sum())

    # ---- completion rule: stored outcome vs independent recompute -----------------
    E = recompute_outcomes(T, ev, keep)
    o = out.set_index("enrollment_id").reindex(E.enrollment_id)
    R.eq0("completion_rule", "required_content_total matches catalogue", (o.required_content_total.astype(int).to_numpy() != E.total.to_numpy()).sum())
    R.eq0("completion_rule", "required_content_completed matches deduplicated events", (o.required_content_completed.astype(int).to_numpy() != E.done.to_numpy()).sum())
    R.eq0("arithmetic", "content_completion_pct = completed/total*100", ((o.content_completion_pct.astype(float).to_numpy() - E.pct_done.to_numpy()).__abs__() > 0.006).sum())
    R.eq0("completion_rule", "required_assessments_total / passed match attempts",
          (o.required_assessments_total.astype(int).to_numpy() != E.a_total.to_numpy()).sum() + (o.required_assessments_passed.astype(int).to_numpy() != E.a_passed.to_numpy()).sum())
    R.eq0("arithmetic", "final_score = sum(weight * best score)/100", ((o.final_score.astype(float).to_numpy() - E.final.to_numpy()).__abs__() > 0.006).sum())
    st_met = to_secs(o.rule_met_at_utc)
    R.eq0("completion_rule", "rule_met_at_utc = max(content threshold, last required pass)", (st_met != E.met_time.to_numpy()).sum())
    cur = enr.set_index("enrollment_id").current_status.reindex(E.enrollment_id).to_numpy()
    acc = E.end.to_numpy() <= as_of_sec
    exp_status = np.where(E.met, "completed", np.where(cur == "dropped", "withdrawn", np.where(acc, "not_completed", "in_progress")))
    R.eq0("completion_rule", "outcome_status follows the rule (completed iff rule met)", (exp_status != o.outcome_status.to_numpy()).sum())
    R.eq0("arithmetic", "completed_date = UTC date of rule_met_at", ((o.completed_date.to_numpy() != np.where(E.met, pd.to_datetime(E.met_time, unit="s").dt.strftime("%Y-%m-%d").to_numpy(), "")).sum()))
    plat = to_secs(o.platform_completed_at_utc)
    comp_hist = h[h.status == "completed"].set_index("enrollment_id").t.reindex(E.enrollment_id).fillna(-1).astype(np.int64).to_numpy()
    R.eq0("lifecycle", "platform_completed_at = 'completed' history row", (plat != comp_hist).sum())
    conflict = (plat >= 0) & ((~E.met.to_numpy()) | (plat < E.met_time.to_numpy()))
    R.eq0("completion_rule", "completion_conflict flag recomputes", (conflict != (o.completion_conflict.to_numpy() == "true")).sum())
    R.add("exceptions", "platform completion not backed by the rule (completion_conflict)", True, f"{int(conflict.sum())} enrollments", info=True, count=conflict.sum())
    R.eq0("completion_rule", "completed enrollments reached the rule within the access window", (E.met & (E.met_time >= E.end)).sum())
    return E, keep, resolved


def validate(data_dir: str, write: bool = True) -> dict:
    T = _load_tables(data_dir)
    R = Collector()
    _generic(R, T)
    _catalogue(R, T)
    as_of_sec = int(to_secs(T["course_outcomes"].evaluated_as_of_utc).max())
    h, e_at = _enrollment_side(R, T, as_of_sec)
    ev = load_events(data_dir, attempt_ids=set(T["attempts"].attempt_id))
    _events_and_outcomes(R, T, ev, h, e_at, as_of_sec)
    # ground truth must stay out of the feature tables
    leaked = [c for n, t in T.items() for c in t.columns if re.search(r"issue_type|ground_truth|is_anomal|expected_decision|true_value|injected", c)]
    R.add("separation", "no ground-truth / label column in any input table", not leaked, ",".join(leaked))
    res = pd.DataFrame(R.rows)
    summary = {
        "data_dir": data_dir,
        "checks": len(res), "passed": int((res.status == "PASS").sum()), "failed": int((res.status == "FAIL").sum()),
        "info": int((res.status == "INFO").sum()),
        "row_counts": {n: len(t) for n, t in T.items()} | {"activity_events": ev.n},
        "results": R.rows,
    }
    if write:
        with open(os.path.join(data_dir, "validation_summary.json"), "w") as f:
            json.dump(summary, f, indent=1)
        with open(os.path.join(data_dir, "validation_summary.md"), "w") as f:
            f.write(to_markdown(summary))
    return summary


def to_markdown(s: dict) -> str:
    lines = [f"# Validation summary\n", f"{s['checks']} checks: **{s['passed']} passed, {s['failed']} failed**, "
             f"{s['info']} informational exception counts.\n", "Row counts: " + ", ".join(f"{k} {v:,}" for k, v in s["row_counts"].items()) + "\n"]
    for grp in dict.fromkeys(r["group"] for r in s["results"]):
        rows = [r for r in s["results"] if r["group"] == grp]
        lines += [f"\n## {grp} ({sum(r['status'] == 'PASS' for r in rows)}/{sum(r['status'] != 'INFO' for r in rows)} pass)\n",
                  "| status | check | detail |", "|---|---|---|"]
        lines += [f"| {r['status']} | {r['check']} | {r['detail']} |" for r in rows]
    return "\n".join(lines) + "\n"

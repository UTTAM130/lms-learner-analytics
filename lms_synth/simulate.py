"""Chunked simulation of activity, attempts, outcomes, status history and
labelled anomalies.

All enrollment-level records of one chunk are generated together, so every
parent ID exists before its children are created. Outcomes are *derived* from
the (deduplicated, arrived) events and attempts with the applicable rule; they
are never drawn independently."""
from __future__ import annotations

import numpy as np

from . import config as C
from .masters import ids, ts_str, date_str, bool_str

NULL_OFF = -99999  # sentinel for "device offset not reported"
BASE_SCORE = 64.0
STATUS = ["enrolled", "active", "completed", "dropped", "expired"]


def ingest_delay(rng, plat):
    n = len(plat)
    d = np.zeros(n, dtype=np.float64)
    w, a, o = plat == 0, plat == 1, plat == 2
    d[w] = np.exp(rng.normal(np.log(4.0), 1.0, int(w.sum())))
    d[a] = np.exp(rng.normal(np.log(12.0), 1.2, int(a.sum())))
    k = int(o.sum())
    u = rng.random(k)
    hours = np.where(u < 0.70, rng.uniform(1, 24, k), np.where(u < 0.95, rng.uniform(24, 120, k), rng.uniform(120, 480, k)))
    d[o] = hours * 3600
    late = (~o) & (rng.random(n) < 0.004)  # backfill / retry bugs on online platforms
    d[late] = rng.uniform(1 * 86400, 7 * 86400, int(late.sum()))
    return d.astype(np.int64)


def _hex(a):
    return np.array(["%016x" % int(v) for v in a], dtype="U16")


def _count_target(rate, n_eligible):
    if n_eligible == 0:
        return 0
    return min(n_eligible, max(int(round(rate * n_eligible)), min(C.MIN_ANOMALIES, n_eligible)))


def simulate_chunk(m, ci, lo, hi):
    rng = np.random.default_rng([m.seed, 10_000 + ci])
    L, K, En = m.L, m.K, m.E
    E = hi - lo
    sl = slice(lo, hi)
    l_idx, c_idx, h_idx = En.learner[sl], En.course[sl], En.cohort[sl]
    enr_at = En.esec[sl]
    seg, off, dev, ability = L.seg[l_idx], L.off[l_idx], L.dev[l_idx], L.ability[l_idx]
    start_day, end_day = K.coh_start[h_idx], K.coh_end[h_idx]
    access_end = (end_day + C.GRACE_DAYS + 1) * 86400
    limit = np.minimum(access_end, C.AS_OF_SEC)
    enr_str = m.enr_id[sl]
    arE = np.arange(E)

    # ---- learner intent --------------------------------------------------
    cp = np.clip(C.SEG_COMPLETER_P[seg] * np.clip(1 + 0.15 * ability - 0.1 * K.course_diff[c_idx], 0.4, 1.4), 0, 0.97)
    completer = rng.random(E) < cp
    ab = np.array(C.SEG_STOP_BETA)[seg]
    frac = rng.beta(ab[:, 0], ab[:, 1])
    Lc = K.leaf_cnt[c_idx]
    reach = np.where(completer, Lc, np.floor(frac * Lc).astype(int))
    reach = np.where(seg == 4, 0, reach)

    # ---- enrollment x leaf-item pairs --------------------------------------
    tot = int(Lc.sum())
    pe = np.repeat(arE, Lc)
    pp = np.arange(tot) - np.repeat(np.cumsum(Lc) - Lc, Lc)
    leaf = K.leaf_start[c_idx][pe] + pp
    ptype, pweek, preq = K.leaf["type"][leaf], K.leaf["week"][leaf], K.leaf["req"][leaf]
    engaged = pp < reach[pe]
    skip = rng.random(tot) < C.SKIP_P[ptype]
    skip &= ~(completer[pe] & preq)
    engaged &= ~skip

    lag = rng.exponential(C.LAG_MEAN_DAYS[seg][pe])
    day = start_day[pe] + np.floor((pweek - 1) * 7 + rng.random(tot) * 7 + lag).astype(np.int64)
    hr = np.searchsorted(C.HOUR_CDF, rng.random(tot))
    sod = hr * 3600 + rng.integers(0, 3600, tot)
    t0 = day * 86400 + sod - off[pe] * 60
    t0 = np.where(t0 < enr_at[pe], enr_at[pe] + rng.integers(60, 6 * 3600, tot), t0)
    minutes = K.leaf["minutes"][leaf]
    dur = np.maximum(30, (minutes * 60 * rng.lognormal(-0.05, 0.3, tot)).astype(np.int64))
    u1 = rng.integers(5, 41, tot)
    finish_p = np.where(completer[pe], np.where(preq, 1.0, 0.85), 0.88)
    finish = rng.random(tot) < finish_p
    plat = np.minimum((rng.random(tot)[:, None] > C.PLAT_CUM[dev[pe]]).sum(axis=1), 2)
    plat = np.where((ptype >= 3) & (plat == 2), 1, plat)  # assessments need connectivity

    lim_p = limit[pe]
    fits = np.where(ptype < 3, t0 + u1 + dur + 5 <= lim_p, t0 + 900 <= lim_p)
    engaged &= fits

    # ---- baseline events of non-assessment items ---------------------------
    P, T, TM, DU, AT = [], [], [], [], []

    def push(pair, etype, time, dur_=None, att=None):
        n = len(pair)
        P.append(pair); T.append(np.full(n, etype)); TM.append(time)
        DU.append(np.full(n, -1) if dur_ is None else dur_)
        AT.append(np.full(n, -1) if att is None else att)

    eng = np.flatnonzero(engaged)
    push(eng, 0, t0[eng])  # content_view
    vid = eng[ptype[eng] == 0]
    push(vid, 1, t0[vid] + u1[vid], dur[vid])  # video_play
    vf = vid[finish[vid]]
    push(vf, 2, t0[vf] + u1[vf] + dur[vf] + 5, dur[vf])  # video_complete
    rd = eng[(ptype[eng] == 1) & finish[eng]]
    push(rd, 3, t0[rd] + dur[rd], dur[rd])  # content_complete
    ds = eng[(ptype[eng] == 2) & finish[eng]]
    push(ds, 4, t0[ds] + dur[ds], dur[ds])  # discussion_post

    # ---- attempts ---------------------------------------------------------------
    ap = eng[ptype[eng] >= 3]
    n_a = len(ap)
    a_pe = pe[ap]
    a_asm = K.leaf_asm[leaf[ap]]
    a_ab, a_d, a_pass, a_max = ability[a_pe], K.asm_diff[a_asm], K.asm_pass[a_asm], K.asm_maxatt[a_asm]
    a_t = ptype[ap] - 3
    dlo, dhi = np.array([8, 30, 40])[a_t], np.array([45, 180, 110])[a_t]
    t_start = t0[ap] + rng.integers(30, 900, n_a)
    active = np.ones(n_a, bool)
    att = dict(ap=[], k=[], start=[], sub=[], score=[], status=[])
    for k in range(1, 4):
        can = active & (k <= a_max)
        if not can.any():
            break
        aband = rng.random(n_a) < C.ABANDON_P
        dmin = rng.uniform(dlo, dhi)
        t_end = t_start + (dmin * 60).astype(np.int64)
        can &= t_end <= limit[a_pe]
        aband &= can
        score = np.clip(np.round(BASE_SCORE + 9.0 * (a_ab - a_d) + 4.0 * (k - 1) + rng.normal(0, 11, n_a), 1), 0, 100)
        passed = can & ~aband & (score >= a_pass)
        sel = np.flatnonzero(can)
        att["ap"].append(sel); att["k"].append(np.full(len(sel), k))
        att["start"].append(t_start[sel]); att["sub"].append(np.where(aband[sel], -1, t_end[sel]))
        att["score"].append(np.where(aband[sel], np.nan, score[sel])); att["status"].append(aband[sel])
        retry = rng.random(n_a) < C.RETRY_P[seg[a_pe]]
        gap = (rng.uniform(0.3, 4.0, n_a) * 86400).astype(np.int64)
        active = can & ~passed & retry
        t_start = t_end + gap
    cat = lambda key, dtype=None: (np.concatenate(att[key]) if att[key] else np.zeros(0, dtype=dtype or np.int64))
    att_ap, att_k, att_start, att_sub = cat("ap"), cat("k"), cat("start"), cat("sub")
    att_score, att_aband = cat("score", np.float64), cat("status", bool)
    n_att = len(att_ap)
    att_pair = ap[att_ap]
    ai = np.arange(n_att)
    push(att_pair, 5, att_start, None, ai)  # assessment_start
    subm = np.flatnonzero(~att_aband)
    push(att_pair[subm], 6, att_sub[subm], (att_sub[subm] - att_start[subm]), subm)  # assessment_submit

    ev_pair, ev_type, ev_time = np.concatenate(P), np.concatenate(T), np.concatenate(TM)
    ev_dur, ev_att = np.concatenate(DU), np.concatenate(AT)
    ev_plat = plat[ev_pair]
    ev_delay = ingest_delay(rng, ev_plat)
    arrived = ev_time + ev_delay <= C.AS_OF_SEC
    bad_att = np.zeros(max(n_att, 1), bool)
    bad_att[ev_att[(ev_att >= 0) & ~arrived]] = True
    if n_att:  # an attempt that has not arrived by the cut-off invalidates every later attempt of the same item
        first_bad = np.full(tot, 99)
        np.minimum.at(first_bad, att_pair[bad_att[:n_att]], att_k[bad_att[:n_att]])
        bad_att[:n_att] |= att_k >= first_bad[att_pair]
    keep = arrived & ~((ev_att >= 0) & bad_att[np.maximum(ev_att, 0)])
    att_ok = ~bad_att[:n_att]
    ev_pair, ev_type, ev_time, ev_dur, ev_att, ev_plat, ev_delay = [a[keep] for a in (ev_pair, ev_type, ev_time, ev_dur, ev_att, ev_plat, ev_delay)]

    # ---- revisits (extra content_view events) fill the volume target --------
    quota = int(round(C.EVENTS_PER_ENROLLMENT * C.BASELINE_SHARE * E)) - len(ev_time)
    if quota > 0 and len(eng):
        wts = C.REVISIT_W[seg[pe[eng]]]
        if wts.sum() > 0:
            rp = rng.choice(eng, size=quota, p=wts / wts.sum())
            rt = t0[rp] + (rng.uniform(0.3, 25, quota) * 86400).astype(np.int64)
            ok = rt <= limit[pe[rp]]
            rp, rt = rp[ok], rt[ok]
            rpl = plat[rp]
            rd_ = ingest_delay(rng, rpl)
            ok = rt + rd_ <= C.AS_OF_SEC
            rp, rt, rpl, rd_ = rp[ok], rt[ok], rpl[ok], rd_[ok]
            ev_pair = np.concatenate([ev_pair, rp]); ev_type = np.concatenate([ev_type, np.zeros(len(rp), int)])
            ev_time = np.concatenate([ev_time, rt]); ev_dur = np.concatenate([ev_dur, np.full(len(rp), -1)])
            ev_att = np.concatenate([ev_att, np.full(len(rp), -1)]); ev_plat = np.concatenate([ev_plat, rpl])
            ev_delay = np.concatenate([ev_delay, rd_])

    # ---- derive course outcomes from the source records ---------------------
    comp = np.isin(ev_type, (2, 3, 4))
    pair_comp = np.full(tot, np.nan)
    pair_comp[ev_pair[comp]] = ev_time[comp]
    reqc = preq & (ptype < 3)
    done_mask = reqc & ~np.isnan(pair_comp)
    done = np.bincount(pe[done_mask], minlength=E)
    req_total = K.req_content_cnt[c_idx]
    k_need = np.ceil(K.rule_pct[En.rule[sl]] / 100.0 * req_total - 1e-9).astype(int)
    content_ok = done >= k_need
    content_time = np.full(E, np.nan)
    s = np.flatnonzero(done_mask)
    if len(s):
        s = s[np.lexsort((pair_comp[s], pe[s]))]
        pe_s, t_s = pe[s], pair_comp[s]
        gs = np.searchsorted(pe_s, arE)
        idx = np.clip(gs + k_need - 1, 0, len(t_s) - 1)
        content_time = np.where(content_ok, t_s[idx], np.nan)

    sub_ok = (~att_aband) & att_ok
    a_passed = sub_ok & (att_score >= a_pass[att_ap]) if n_att else np.zeros(0, bool)
    pair_pass = np.full(tot, np.inf)
    pair_best = np.zeros(tot)
    if n_att:
        np.minimum.at(pair_pass, att_pair[a_passed], att_sub[a_passed])
        np.maximum.at(pair_best, att_pair[sub_ok], att_score[sub_ok])
    reqa = preq & (ptype >= 3)
    passed_pair = reqa & np.isfinite(pair_pass)
    asm_passed = np.bincount(pe[passed_pair], minlength=E)
    asm_ok = asm_passed == K.req_asm_cnt[c_idx]
    asm_time = np.full(E, -np.inf)
    np.maximum.at(asm_time, pe[passed_pair], pair_pass[passed_pair])
    asm_time = np.where(asm_ok, asm_time, np.nan)
    wpair = np.where(ptype >= 3, K.asm_weight[np.maximum(K.leaf_asm[leaf], 0)], 0.0)
    final_score = np.bincount(pe[reqa], weights=wpair[reqa] * pair_best[reqa], minlength=E) / 100.0
    met = content_ok & asm_ok
    met_time = np.where(met, np.maximum(content_time, asm_time), np.nan)

    # ---- platform completion marks (incl. labelled premature completions) ------
    dcomp = rng.integers(C.COMPLETION_DELAY_SEC[0], C.COMPLETION_DELAY_SEC[1], E)
    plat_comp = np.where(met, met_time + dcomp, np.nan)
    elA = np.flatnonzero(content_ok & ~asm_ok)
    pickA = rng.choice(elA, _count_target(C.PREMATURE_A_RATE, len(elA)), replace=False) if len(elA) else np.zeros(0, int)
    elB = np.flatnonzero(met & (asm_time > content_time + 3600))
    pickB = rng.choice(elB, _count_target(C.PREMATURE_B_RATE, len(elB)), replace=False) if len(elB) else np.zeros(0, int)
    prem = np.concatenate([pickA, pickB])
    plat_comp[prem] = content_time[prem] + dcomp[prem]
    plat_comp = np.where(np.isnan(plat_comp), np.nan, np.minimum(plat_comp, C.AS_OF_SEC))

    # ---- enrollment status history ---------------------------------------------
    has_ev = np.zeros(E, bool)
    first_ev = np.full(E, np.iinfo(np.int64).max)
    last_ev = np.zeros(E, np.int64)
    pe_ev = pe[ev_pair]
    has_ev[pe_ev] = True
    np.minimum.at(first_ev, pe_ev, ev_time)
    np.maximum.at(last_ev, pe_ev, ev_time)
    noncomp = np.isnan(plat_comp)
    drop_t = np.where(has_ev, last_ev, enr_at) + (rng.uniform(1, 14, E) * 86400).astype(np.int64)
    drop_ok = noncomp & (rng.random(E) < C.DROP_P[seg]) & (drop_t < access_end) & (drop_t <= C.AS_OF_SEC)
    exp_ok = noncomp & ~drop_ok & (access_end <= C.AS_OF_SEC)
    comp_ok = ~noncomp
    hist = [
        (arE, 0, enr_at, "learner"),
        (arE[has_ev], 1, first_ev[has_ev], "system"),
        (arE[comp_ok], 2, np.nan_to_num(plat_comp[comp_ok]).astype(np.int64), "system"),
        (arE[drop_ok], 3, drop_t[drop_ok], "learner"),
        (arE[exp_ok], 4, access_end[exp_ok], "system"),
    ]
    h_e = np.concatenate([h[0] for h in hist])
    h_c = np.concatenate([np.full(len(h[0]), h[1]) for h in hist])
    h_t = np.concatenate([h[2] for h in hist]).astype(np.int64)
    h_s = np.concatenate([np.full(len(h[0]), h[3]) for h in hist])
    o = np.lexsort((h_c, h_e))
    h_e, h_c, h_t, h_s = h_e[o], h_c[o], h_t[o], h_s[o]
    nh = len(h_e)
    newg = np.r_[True, h_e[1:] != h_e[:-1]]
    seq = np.arange(nh) - np.maximum.accumulate(np.where(newg, np.arange(nh), 0)) + 1
    prev = np.where(newg, -1, np.r_[-1, h_c[:-1]])
    last_mask = np.r_[h_e[1:] != h_e[:-1], True]
    cur_code = np.zeros(E, int)
    cur_time = np.zeros(E, np.int64)
    cur_code[h_e[last_mask]] = h_c[last_mask]
    cur_time[h_e[last_mask]] = h_t[last_mask]
    snames = np.array(STATUS)

    status_tbl = {
        "history_id": np.char.add(np.char.add(np.char.add("ESH-", enr_str[h_e]), "-"), np.char.zfill(seq.astype("U3"), 2)),
        "enrollment_id": enr_str[h_e],
        "status": snames[h_c],
        "previous_status": np.where(prev >= 0, snames[np.maximum(prev, 0)], ""),
        "effective_from": ts_str(h_t),
        "change_source": h_s,
    }
    enroll_tbl = {
        "enrollment_id": enr_str, "learner_id": m.lrn_id[l_idx], "course_id": m.crs_id[c_idx],
        "cohort_id": m.coh_id[h_idx], "rule_id": m.rul_id[En.rule[sl]],
        "enrolled_at": ts_str(enr_at), "current_status": snames[cur_code], "status_updated_at": ts_str(cur_time),
    }
    ostat = np.where(met, "completed", np.where(cur_code == 3, "withdrawn",
             np.where(access_end <= C.AS_OF_SEC, "not_completed", "in_progress")))
    conflict = ~noncomp & (~met | (plat_comp < met_time))
    metm = ~np.isnan(met_time)
    met_i = np.nan_to_num(met_time).astype(np.int64)
    outcome_tbl = {
        "outcome_id": np.char.add("OUT-", enr_str), "enrollment_id": enr_str, "rule_id": m.rul_id[En.rule[sl]],
        "required_content_total": req_total, "required_content_completed": done,
        "content_completion_pct": np.char.mod("%.2f", done / req_total * 100.0),
        "required_assessments_total": K.req_asm_cnt[c_idx], "required_assessments_passed": asm_passed,
        "final_score": np.char.mod("%.2f", final_score),
        "rule_met_at_utc": ts_str(met_i, metm), "outcome_status": ostat,
        "completed_date": date_str(met_i // 86400, metm),
        "platform_completed_at_utc": ts_str(np.nan_to_num(plat_comp).astype(np.int64), ~noncomp),
        "completion_conflict": bool_str(conflict), "evaluated_as_of_utc": ts_str(np.full(E, C.AS_OF_SEC)),
    }
    gt_prem = []  # (enrollment local idx, subtype, true text)
    for e in pickA:
        gt_prem.append((e, "required_assessment_not_passed", f"rule_not_met;outcome_status={ostat[e]}"))
    for e in pickB:
        gt_prem.append((e, "required_assessment_passed_later", "rule_met_at=" + ts_str(met_i[e:e + 1])[0]))

    # ---- attempts table ----------------------------------------------------------
    k_ok = np.flatnonzero(att_ok)
    asm_num = (a_asm[att_ap] + 1)
    att_str = np.char.add(np.char.add(np.char.add(np.char.add("ATT-", enr_str[a_pe[att_ap]]), "-"),
              np.char.zfill(asm_num.astype("U8"), 6)), np.char.add("-", np.char.zfill(att_k.astype("U3"), 2))) if n_att else np.zeros(0, "U40")
    sub_mask = ~att_aband
    passed_flag = att_score >= a_pass[att_ap] if n_att else np.zeros(0, bool)
    attempt_tbl = {
        "attempt_id": att_str[k_ok], "enrollment_id": enr_str[a_pe[att_ap]][k_ok],
        "assessment_id": m.asm_id[a_asm[att_ap]][k_ok], "attempt_no": att_k[k_ok],
        "started_at_utc": ts_str(att_start[k_ok]),
        "submitted_at_utc": ts_str(att_sub[k_ok], sub_mask[k_ok]),
        "status": np.where(att_aband[k_ok], "abandoned", "submitted"),
        "score": np.where(att_aband[k_ok], "", np.char.mod("%.1f", np.nan_to_num(att_score[k_ok]))),
        "passed": np.where(att_aband[k_ok], "", bool_str(passed_flag[k_ok])),
        "duration_minutes": np.where(att_aband[k_ok], "", np.char.mod("%.1f", (att_sub[k_ok] - att_start[k_ok]) / 60.0)),
    }

    # ---- final event table: baseline + labelled anomalies ---------------------------
    n_b = len(ev_time)
    b_pe = pe[ev_pair]
    b_leaf = leaf[ev_pair]
    b_lrn, b_crs = l_idx[b_pe], c_idx[b_pe]
    b_off = off[b_pe]
    b_ing = ev_time + ev_delay
    b_cid = rng.integers(0, 2 ** 62, n_b)
    b_cnt = K.leaf["cnum"][b_leaf]

    rate = np.where(ev_plat == 2, C.DUP_RATE_OFFLINE, C.DUP_RATE_ONLINE)
    dup = np.flatnonzero(rng.random(n_b) < rate)
    if len(dup) < min(C.MIN_ANOMALIES, n_b):
        dup = np.unique(np.concatenate([dup, rng.choice(n_b, min(C.MIN_ANOMALIES, n_b), replace=False)]))
    d_delay = np.where(ev_plat[dup] == 2, rng.uniform(0.5, 48, len(dup)) * 3600, rng.uniform(0, 5, len(dup))).astype(np.int64)
    d_ing = b_ing[dup] + d_delay
    okd = d_ing <= C.AS_OF_SEC
    dup, d_ing = dup[okd], d_ing[okd]
    is_dup = np.zeros(n_b, bool)
    is_dup[dup] = True

    true_loc = (ev_time + b_off * 60) // 86400
    new_t = ev_time + b_off * 60
    cand = np.flatnonzero(np.isin(ev_type, (0, 1)) & (b_off != 0) & ~is_dup & (true_loc != (new_t + b_off * 60) // 86400)
                          & (new_t >= enr_at[b_pe]) & (new_t <= limit[b_pe]))
    tz_sel = rng.choice(cand, _count_target(C.TZ_RATE * n_b / max(len(cand), 1), len(cand)), replace=False) if len(cand) else np.zeros(0, int)
    tz_sel = np.sort(tz_sel)
    tz_missing = rng.random(len(tz_sel)) < C.TZ_OFFSET_MISSING_SHARE
    obs_time = ev_time.copy()
    obs_time[tz_sel] = new_t[tz_sel]
    off_rep = b_off.copy()
    off_rep[tz_sel[tz_missing]] = NULL_OFF
    kind = np.zeros(n_b, int)
    kind[tz_sel] = 2

    n_unen = max(int(round(C.UNENROLLED_RATE * n_b)), min(C.MIN_ANOMALIES * 2, n_b))
    n_before = int(round(C.UNENROLLED_BEFORE_SHARE * n_unen))
    n_never = n_unen - n_before

    # before-enrollment activity (valid enrollment id, event precedes enrolled_at)
    be = rng.integers(0, E, n_before)
    be_t = enr_at[be] - rng.integers(3600, 5 * 86400, n_before)
    be_leaf = K.leaf_start[c_idx[be]] + (rng.random(n_before) * K.leaf_cnt[c_idx[be]]).astype(int)
    be_plat = np.minimum((rng.random(n_before)[:, None] > C.PLAT_CUM[dev[be]]).sum(axis=1), 2)
    be_plat = np.where(K.leaf["type"][be_leaf] >= 3, np.minimum(be_plat, 1), be_plat)
    be_ing = be_t + ingest_delay(rng, be_plat)
    ok_be = be_ing <= C.AS_OF_SEC
    be, be_t, be_leaf, be_plat, be_ing = be[ok_be], be_t[ok_be], be_leaf[ok_be], be_plat[ok_be], be_ing[ok_be]
    n_before = len(be)

    # activity from learners that never enrolled in the course. Learners are partitioned by chunk
    # (learner % n_chunks == chunk) so an orphan enrollment id (and hence its EVT counter) is
    # produced by exactly one chunk and event_id stays globally unique.
    nl, nc = L.n, K.nc
    n_chunks = max(1, getattr(m, "n_chunks", 1))
    cl = rng.integers(0, nl // n_chunks + 1, n_never * 3 + 10) * n_chunks + ci % n_chunks
    cc = rng.integers(0, nc, n_never * 3 + 10)
    good = (cl < nl) & (K.pub[cc] < C.AS_OF_DAY - 10)
    good &= ~np.isin(np.minimum(cl, nl - 1).astype(np.int64) * nc + cc, m.pair_keys)
    cl, cc = cl[good][:n_never], cc[good][:n_never]
    n_never = len(cl)
    lo_day = np.maximum(K.pub[cc], L.signup[cl]) + 1
    nv_day = lo_day + (rng.random(n_never) * np.maximum(C.AS_OF_DAY - 3 - lo_day, 1)).astype(np.int64)
    nv_t = nv_day * 86400 + np.searchsorted(C.HOUR_CDF, rng.random(n_never)) * 3600 + rng.integers(0, 3600, n_never) - L.off[cl] * 60
    nv_leaf = K.leaf_start[cc] + (rng.random(n_never) * K.leaf_cnt[cc]).astype(int)
    lt = K.leaf["type"][nv_leaf]
    u = rng.random(n_never)
    nv_type = np.where(lt == 0, np.where(u < 0.6, 0, 1), np.where(lt == 1, np.where(u < 0.6, 0, 3), 0))
    nv_plat = np.minimum((rng.random(n_never)[:, None] > C.PLAT_CUM[L.dev[cl]]).sum(axis=1), 2)
    nv_ing = nv_t + ingest_delay(rng, nv_plat)
    ok_nv = nv_ing <= C.AS_OF_SEC
    cl, cc, nv_t, nv_leaf, nv_type, nv_plat, nv_ing = (a[ok_nv] for a in (cl, cc, nv_t, nv_leaf, nv_type, nv_plat, nv_ing))
    n_never = len(cl)
    pair_u, pair_inv = np.unique(cl.astype(np.int64) * nc + cc, return_inverse=True)

    def cols(*arrs):
        return np.concatenate(arrs)

    nd = len(dup)
    grp = cols(b_pe, b_pe[dup], be, E + pair_inv)
    enr_local = cols(b_pe, b_pe[dup], be, np.full(n_never, -1))
    lrn = cols(b_lrn, b_lrn[dup], l_idx[be], cl)
    crs = cols(b_crs, b_crs[dup], c_idx[be], cc)
    cnt = cols(b_cnt, b_cnt[dup], K.leaf["cnum"][be_leaf], K.leaf["cnum"][nv_leaf])
    etype = cols(ev_type, ev_type[dup], np.zeros(n_before, int), nv_type)
    etime = cols(obs_time, obs_time[dup], be_t, nv_t)
    orep = cols(off_rep, off_rep[dup], off[be], L.off[cl])
    ing = cols(b_ing, d_ing, be_ing, nv_ing)
    pl = cols(ev_plat, ev_plat[dup], be_plat, nv_plat)
    cid = cols(b_cid, b_cid[dup], rng.integers(0, 2 ** 62, n_before), rng.integers(0, 2 ** 62, n_never))
    edur = cols(ev_dur, ev_dur[dup], np.full(n_before, -1), np.full(n_never, -1))
    eatt = cols(ev_att, ev_att[dup], np.full(n_before, -1), np.full(n_never, -1))
    kd = cols(kind, np.full(nd, 1), np.full(n_before, 4), np.full(n_never, 3))
    orig = cols(np.full(n_b, -1), dup, np.full(n_before, -1), np.full(n_never, -1))
    nf = len(etime)

    order = np.lexsort((np.arange(nf), ing, grp))
    g_s = grp[order]
    newg = np.r_[True, g_s[1:] != g_s[:-1]]
    seq_s = np.arange(nf) - np.maximum.accumulate(np.where(newg, np.arange(nf), 0)) + 1
    seq_row = np.empty(nf, int)
    seq_row[order] = seq_s
    enr_s = np.empty(nf, dtype="U25")
    real = enr_local >= 0
    enr_s[real] = enr_str[enr_local[real]]
    enr_s[~real] = np.char.add(np.char.add(np.char.add("ENR-", m.lrn_id[lrn[~real]]), "-"), m.crs_id[crs[~real]])
    event_id = np.char.add(np.char.add(np.char.add("EVT-", enr_s), "-"), np.char.zfill(seq_row.astype("U7"), 6))
    cid_s = _hex(cid)
    et_names = np.array(C.EVENT_TYPES)
    att_lookup = att_str if n_att else np.zeros(1, "U40")
    event_cols = {
        "event_id": event_id, "enrollment_id": enr_s, "learner_id": m.lrn_id[lrn], "course_id": m.crs_id[crs],
        "content_id": m.cnt_id[cnt - 1], "event_type": et_names[etype], "event_time_utc": ts_str(etime),
        "device_utc_offset_minutes": np.where(orep == NULL_OFF, "", orep.astype("U6")),
        "ingested_at_utc": ts_str(ing), "platform": np.array(C.PLATFORMS)[pl], "client_event_id": cid_s,
        "duration_seconds": np.where(edur >= 0, edur.astype("U10"), ""),
        "attempt_id": np.where(eatt >= 0, att_lookup[np.maximum(eatt, 0)], ""),
    }
    event_tbl = {k: v[order] for k, v in event_cols.items()}

    # ---- ground truth ---------------------------------------------------------------
    gt = []

    def g(record_type, rid, issue, sub, rel, obs, tru, dec):
        n = len(rid)
        if n:
            gt.append({"record_type": np.full(n, record_type), "record_id": rid, "issue_type": np.full(n, issue),
                       "subtype": sub, "related_record_id": rel, "observed_value": obs, "true_value": tru,
                       "expected_decision": np.full(n, dec)})

    dup_rows = np.flatnonzero(kd == 1)
    g("activity_event", event_id[dup_rows], "duplicate_event", np.full(len(dup_rows), "retry_duplicate"),
      event_id[orig[dup_rows]], np.full(len(dup_rows), "duplicate_delivery"), np.full(len(dup_rows), "single_real_event"),
      "drop_duplicate_keep_first_ingested")
    nb_rows = np.flatnonzero(kd == 3)
    g("activity_event", event_id[nb_rows], "activity_unenrolled", np.full(len(nb_rows), "never_enrolled"),
      np.full(len(nb_rows), ""), np.char.add("enrollment_id=", enr_s[nb_rows]), np.full(len(nb_rows), "no_enrollment_record"),
      "exclude_from_engagement")
    br_rows = np.flatnonzero(kd == 4)
    g("activity_event", event_id[br_rows], "activity_unenrolled", np.full(len(br_rows), "before_enrollment"),
      np.full(len(br_rows), ""), np.char.add("event_time=", ts_str(etime[br_rows])),
      np.char.add("enrolled_at=", ts_str(enr_at[enr_local[br_rows]])), "exclude_from_engagement")
    tz_rows = np.flatnonzero(kd == 2)
    # true event instant = observed - offset; true local date = (true instant + offset) // 86400
    true_inst = etime[tz_rows] - L.off[lrn[tz_rows]] * 60
    tru_d = date_str((true_inst + L.off[lrn[tz_rows]] * 60) // 86400)
    obs_d = date_str((etime[tz_rows] + L.off[lrn[tz_rows]] * 60) // 86400)
    g("activity_event", event_id[tz_rows], "timezone_shift",
      np.where(orep[tz_rows] == NULL_OFF, "offset_missing", "offset_present"), np.full(len(tz_rows), ""),
      np.char.add("assigned_local_date=", obs_d), np.char.add("true_local_date=", tru_d), "reassign_to_true_local_date")
    if gt_prem:
        pe_i = np.array([x[0] for x in gt_prem])
        g("enrollment", enr_str[pe_i], "completion_before_required_assessment", np.array([x[1] for x in gt_prem]),
          np.full(len(pe_i), ""), np.char.add("platform_completed_at=", ts_str(np.nan_to_num(plat_comp[pe_i]).astype(np.int64))),
          np.array([x[2] for x in gt_prem]), "do_not_record_completion_before_rule_met")
    gt_tbl = {k: np.concatenate([x[k] for x in gt]) for k in gt[0]} if gt else None

    stats = dict(
        n_events=nf, n_baseline=n_b, n_dup=int(nd), n_tz=int(len(tz_sel)), n_unen_never=int(n_never), n_unen_before=int(n_before),
        n_attempts=int(len(k_ok)), n_prem_a=int(len(pickA)), n_prem_b=int(len(pickB)),
        baseline_learner_idx=l_idx[b_pe],
    )
    return dict(events=event_tbl, attempts=attempt_tbl, enrollments=enroll_tbl, history=status_tbl,
                outcomes=outcome_tbl, gt=gt_tbl, stats=stats)

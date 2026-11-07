"""Master and dependent static data: learners, courses, content, assessments,
completion rules, cohorts and enrollments. Everything is drawn from named
random streams so that results depend only on (seed, scale)."""
from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import numpy as np

from . import config as C


def stream(seed: int, k: int) -> np.random.Generator:
    return np.random.default_rng([seed, k])


def ids(prefix: str, nums, width: int = 6):
    return np.char.add(prefix, np.char.zfill(np.asarray(nums).astype("int64").astype("U12"), width))


def ts_str(sec, mask=None):
    """epoch seconds -> ISO strings ('' where mask is False)."""
    sec = np.asarray(sec, dtype="int64")
    if mask is None:
        return np.char.add(sec.astype("datetime64[s]").astype("U19"), "Z")
    out = np.full(sec.shape, "", dtype="U20")
    if mask.any():
        out[mask] = np.char.add(sec[mask].astype("datetime64[s]").astype("U19"), "Z")
    return out


def date_str(day, mask=None):
    day = np.asarray(day, dtype="int64")
    if mask is None:
        return day.astype("datetime64[D]").astype("U10")
    out = np.full(day.shape, "", dtype="U10")
    if mask.any():
        out[mask] = day[mask].astype("datetime64[D]").astype("U10")
    return out


def bool_str(a):
    return np.where(np.asarray(a, dtype=bool), "true", "false")


TOPICS = {
    "Data Science": ["Statistics Foundations", "Machine Learning", "Data Visualisation", "SQL for Analysts", "Applied Forecasting", "Deep Learning"],
    "Software Engineering": ["Python Programming", "Web Development", "Cloud Fundamentals", "Software Testing", "APIs and Microservices", "DevOps Practice"],
    "Business": ["Project Management", "Operations Strategy", "Marketing Analytics", "Product Management", "Negotiation Skills", "Business Writing"],
    "Design": ["UX Research", "Interface Design", "Design Systems", "Visual Communication", "Prototyping", "Accessibility"],
    "Health": ["Public Health Basics", "Nutrition Science", "Clinical Informatics", "Mental Health First Aid", "Biostatistics", "Health Policy"],
    "Languages": ["Spanish Conversation", "Business English", "German for Beginners", "Technical Writing", "French Essentials", "Mandarin Basics"],
    "Finance": ["Corporate Finance", "Personal Investing", "Financial Modelling", "Risk Management", "Accounting Basics", "Fintech Overview"],
    "Mathematics": ["Linear Algebra", "Calculus Review", "Discrete Mathematics", "Probability Theory", "Optimisation", "Numerical Methods"],
}
LEVEL_TITLE = ["Beginner", "Intermediate", "Advanced"]


def _build_learners(scale, seed):
    rng = stream(seed, 1)
    n = scale.n_learners
    seg = rng.choice(len(C.SEGMENTS), n, p=C.SEG_P)
    tzw = np.array([t[3] for t in C.TIMEZONES])
    tz = rng.choice(len(C.TIMEZONES), n, p=tzw / tzw.sum())
    dev = rng.choice(3, n, p=C.DEVICE_P)
    ch = rng.choice(len(C.CHANNELS), n, p=C.CHANNEL_P)
    ability = rng.normal(0, 1, n) + C.ABILITY_SHIFT[seg]
    signup = rng.integers(C.SIGNUP_FIRST_DAY, C.SIGNUP_LAST_DAY + 1, n)
    off = np.array([t[2] for t in C.TIMEZONES])[tz]
    return SimpleNamespace(n=n, seg=seg, tz=tz, dev=dev, ch=ch, ability=ability, signup=signup, off=off)


def _build_catalogue(scale, seed):
    rng = stream(seed, 2)
    nc = scale.n_courses
    cat = rng.integers(0, len(C.CATEGORIES), nc)
    level = rng.choice(3, nc, p=C.LEVEL_P)
    dur = rng.choice(C.DURATIONS, nc, p=C.DURATION_P)
    mode = rng.choice(2, nc, p=C.MODE_P)
    pub = rng.integers(C.epoch_day("2025-09-01"), C.epoch_day("2026-08-10") + 1, nc)
    flag = rng.random(nc) < 0.06
    ret = np.where(flag, pub + rng.integers(120, 301, nc), -1)
    ret = np.where(ret > C.AS_OF_DAY, -1, ret)
    topic_idx = rng.integers(0, 6, nc)
    pop = 1.0 / (rng.permutation(nc) + 1.0) ** 0.6
    pop = pop / pop.sum()
    course_diff = C.LEVEL_DIFFICULTY[level] + rng.normal(0, 0.15, nc)

    # ---- content hierarchy -------------------------------------------------
    crow = dict(course=[], parent=[], type=[], seq=[], depth=[], week=[], req=[], minutes=[], title=[])
    leaf = dict(course=[], type=[], week=[], req=[], minutes=[], cnum=[])
    n_mod_arr = np.zeros(nc, int)
    cnum = 0

    def add_row(c, parent, tcode, seq, depth, week, req, minutes, title):
        nonlocal cnum
        cnum += 1
        crow["course"].append(c); crow["parent"].append(parent); crow["type"].append(tcode)
        crow["seq"].append(seq); crow["depth"].append(depth); crow["week"].append(week)
        crow["req"].append(req); crow["minutes"].append(minutes); crow["title"].append(title)
        return cnum

    type_names = ["video", "reading", "discussion", "quiz", "assignment", "exam"]
    for c in range(nc):
        d = int(dur[c])
        n_mod = int(np.clip(d // 2 + rng.integers(-1, 2), 2, 6))
        n_mod_arr[c] = n_mod
        edges = np.linspace(0, d, n_mod + 1)
        first_video_done = False
        for m in range(n_mod):
            lo = int(np.floor(edges[m])) + 1
            hi = max(int(np.floor(edges[m + 1])), lo)
            if m == n_mod - 1:
                hi = d
            mod_row_idx = len(crow["course"])
            mod_num = add_row(c, 0, 6, m + 1, 1, lo, True, 0, f"Module {m + 1}")
            nv, nr = int(rng.integers(1, 3)), int(rng.integers(0, 2))
            seq_t = []
            while nv > 0 or nr > 0:
                if nv > 0:
                    seq_t.append(0); nv -= 1
                if nr > 0:
                    seq_t.append(1); nr -= 1
            if rng.random() < 0.35:
                seq_t.append(2)
            if rng.random() < 0.25:
                seq_t.append(4)
            seq_t.append(3)
            if m == n_mod - 1:
                seq_t.append(5)
            weeks = np.sort(rng.integers(lo, hi + 1, len(seq_t)))
            weeks[-1] = hi
            mins = 0
            any_req = False
            for j, t in enumerate(seq_t):
                lo_m, hi_m = C.MINUTES[t]
                minutes = int(rng.integers(lo_m, hi_m + 1))
                req = bool(rng.random() < C.REQUIRED_P[t])
                if t == 0 and not first_video_done:
                    req, first_video_done = True, True
                num = add_row(c, mod_num, t, j + 1, 2, int(weeks[j]), req, minutes,
                              f"{type_names[t].title()} {m + 1}.{j + 1}")
                leaf["course"].append(c); leaf["type"].append(t); leaf["week"].append(int(weeks[j]))
                leaf["req"].append(req); leaf["minutes"].append(minutes); leaf["cnum"].append(num)
                mins += minutes
                any_req |= req
            crow["minutes"][mod_row_idx] = mins
            crow["req"][mod_row_idx] = any_req

    crow = {k: np.array(v) for k, v in crow.items()}
    leaf = {k: np.array(v) for k, v in leaf.items()}
    leaf_cnt = np.bincount(leaf["course"], minlength=nc)
    leaf_start = np.cumsum(leaf_cnt) - leaf_cnt
    n_leaf = len(leaf["course"])

    # ---- assessments (1:1 with quiz/assignment/exam leaves) ------------------
    is_asm = leaf["type"] >= 3
    asm_leaf = np.flatnonzero(is_asm)
    n_asm = len(asm_leaf)
    a_type = leaf["type"][asm_leaf] - 3  # 0 quiz, 1 assignment, 2 exam
    a_course = leaf["course"][asm_leaf]
    a_req = leaf["req"][asm_leaf]
    a_pass = np.array([60, 65, 70])[a_type]
    a_maxatt = np.array([3, 2, 2])[a_type]
    rating = np.clip(np.rint(2 + 1.2 * level[a_course] + rng.normal(0, 0.7, n_asm)), 1, 5).astype(int)
    a_diff = 0.3 * (rating - 3) + course_diff[a_course] * 0.5
    raw = np.array([1.0, 2.0, 4.0])[a_type] * a_req
    weight = np.zeros(n_asm)
    for c in range(nc):
        idx = np.flatnonzero((a_course == c) & a_req)
        if len(idx) == 0:
            continue
        w = np.round(raw[idx] / raw[idx].sum() * 100, 2)
        w[-1] = round(100.0 - w[:-1].sum(), 2)
        weight[idx] = w
    leaf_asm = np.full(n_leaf, -1)
    leaf_asm[asm_leaf] = np.arange(n_asm)

    req_content_cnt = np.bincount(leaf["course"][leaf["req"] & (leaf["type"] < 3)], minlength=nc)
    req_asm_cnt = np.bincount(leaf["course"][leaf["req"] & (leaf["type"] >= 3)], minlength=nc)
    assert (req_content_cnt >= 1).all() and (req_asm_cnt >= 1).all()

    # ---- completion rules ----------------------------------------------------
    pct1 = rng.choice([70, 80, 90], nc)
    pct2 = np.minimum(95, pct1 + rng.choice([0, 5, 5, 10], nc))
    rule_pct = np.empty(2 * nc, int)
    rule_pct[0::2], rule_pct[1::2] = pct1, pct2

    # ---- cohorts -------------------------------------------------------------
    mondays = np.arange(C.FIRST_COHORT_DAY, C.LAST_COHORT_DAY + 1, 7)
    coh_course, coh_start = [], []
    for c in range(nc):
        lo = pub[c] + 3
        hi = C.LAST_COHORT_DAY if ret[c] < 0 else ret[c] - 14
        cand = mondays[(mondays >= lo) & (mondays <= hi)]
        k = min(int(rng.integers(3, 9)), len(cand))
        pick = np.sort(rng.choice(cand, size=k, replace=False))
        coh_course += [c] * k
        coh_start += pick.tolist()
    coh_course = np.array(coh_course)
    coh_start = np.array(coh_start)
    coh_end = coh_start + 7 * dur[coh_course] - 1
    coh_access_end = coh_end + C.GRACE_DAYS
    n_coh = len(coh_course)
    coh_first = np.searchsorted(coh_course, np.arange(nc), side="left")
    coh_n = np.bincount(coh_course, minlength=nc)
    cap = rng.integers(40, 201, n_coh)
    inst = rng.integers(1, 60, n_coh)

    return SimpleNamespace(
        nc=nc, cat=cat, level=level, dur=dur, mode=mode, pub=pub, ret=ret, topic_idx=topic_idx, pop=pop,
        course_diff=course_diff, crow=crow, n_content=cnum, n_mod=n_mod_arr,
        leaf=leaf, leaf_cnt=leaf_cnt, leaf_start=leaf_start, n_leaf=n_leaf, leaf_asm=leaf_asm,
        n_asm=n_asm, asm_leaf=asm_leaf, asm_type=a_type, asm_course=a_course, asm_req=a_req,
        asm_pass=a_pass, asm_maxatt=a_maxatt, asm_rating=rating, asm_diff=a_diff, asm_weight=weight,
        req_content_cnt=req_content_cnt, req_asm_cnt=req_asm_cnt, rule_pct=rule_pct,
        n_coh=n_coh, coh_course=coh_course, coh_start=coh_start, coh_end=coh_end,
        coh_access_end=coh_access_end, coh_first=coh_first, coh_n=coh_n, coh_cap=cap, coh_inst=inst,
    )


def _build_enrollments(scale, seed, L, K):
    rng = stream(seed, 3)
    nl, nc, ne = L.n, K.nc, scale.n_enrollments
    w = C.SEG_ENROLL_WEIGHT[L.seg] * rng.lognormal(0, 0.5, nl)
    cap = min(nc, 30)
    counts = np.minimum(rng.multinomial(ne, w / w.sum()), cap)
    while counts.sum() < ne:
        room = np.flatnonzero(counts < cap)
        if len(room) == 0:
            break
        k = min(ne - counts.sum(), len(room))
        pick = rng.choice(room, size=k, replace=False, p=w[room] / w[room].sum())
        counts[pick] += 1
    learner = np.repeat(np.arange(nl), counts)
    n = len(learner)
    course = rng.choice(nc, size=n, p=K.pop)
    for _ in range(60):
        key = learner.astype(np.int64) * nc + course
        _, first = np.unique(key, return_index=True)
        dup = np.ones(n, bool)
        dup[first] = False
        if not dup.any():
            break
        course[dup] = rng.choice(nc, size=int(dup.sum()), p=K.pop)
    else:  # deterministic fallback for saturated learners
        key = learner.astype(np.int64) * nc + course
        _, first = np.unique(key, return_index=True)
        dup = np.ones(n, bool)
        dup[first] = False
        for i in np.flatnonzero(dup):
            used = set(course[learner == learner[i]].tolist())
            free = [c for c in range(nc) if c not in used]
            course[i] = free[int(rng.integers(0, len(free)))]

    h = K.coh_first[course] + (rng.random(n) * K.coh_n[course]).astype(int)
    start = K.coh_start[h]
    lead = np.minimum(np.floor(rng.exponential(9, n)).astype(int) + 1, 30)
    late = rng.random(n) < 0.08
    eday = start + np.where(late, rng.integers(0, 8, n), -lead)
    eday = np.maximum(eday, K.pub[course])
    eday = np.minimum(eday, C.AS_OF_DAY - 1)
    hr = np.searchsorted(C.HOUR_CDF, rng.random(n))
    sod = hr * 3600 + rng.integers(0, 3600, n)
    esec = eday * 86400 + sod - L.off[learner] * 60
    esec = np.minimum(esec, C.AS_OF_SEC - 3600)

    order = np.lexsort((course, learner))
    learner, course, h, eday, esec = learner[order], course[order], h[order], eday[order], esec[order]
    first_e = np.full(nl, 10 ** 9, dtype=np.int64)
    np.minimum.at(first_e, learner, eday)
    signup = np.minimum(L.signup, first_e - rng.integers(7, 91, nl))
    rule = 2 * course + (K.coh_start[h] >= C.RULE_V2_DAY).astype(int)
    return SimpleNamespace(n=n, learner=learner, course=course, cohort=h, eday=eday, esec=esec,
                           rule=rule, signup=signup)


def build_masters(scale, seed):
    L = _build_learners(scale, seed)
    K = _build_catalogue(scale, seed)
    E = _build_enrollments(scale, seed, L, K)
    L.signup = E.signup
    m = SimpleNamespace(scale=scale, seed=seed, L=L, K=K, E=E)
    # id string arrays reused by the simulation
    m.lrn_id = ids("LRN-", np.arange(L.n) + 1)
    m.crs_id = ids("CRS-", np.arange(K.nc) + 1)
    m.cnt_id = ids("CNT-", np.arange(K.n_content) + 1)
    m.asm_id = ids("ASM-2026-", np.arange(K.n_asm) + 1)
    m.coh_id = ids("COH-", np.arange(K.n_coh) + 1)
    m.rul_id = ids("RUL-", np.arange(2 * K.nc) + 1)
    m.enr_id = np.char.add(np.char.add(np.char.add("ENR-", m.lrn_id[E.learner]), "-"), m.crs_id[E.course])
    return m


# ---- master tables as dict-of-string-arrays (column order = schema) ------------
def master_tables(m):
    L, K, E = m.L, m.K, m.E
    t = {}
    t["learners"] = {
        "learner_id": m.lrn_id,
        "signup_date": date_str(L.signup),
        "country_code": np.array([x[0] for x in C.TIMEZONES])[L.tz],
        "timezone": np.array([x[1] for x in C.TIMEZONES])[L.tz],
        "utc_offset_minutes": L.off,
        "primary_device": np.array(C.DEVICES)[L.dev],
        "acquisition_channel": np.array(C.CHANNELS)[L.ch],
    }
    retired = K.ret >= 0
    topics = np.array([TOPICS[c][i] for c, i in zip(np.array(C.CATEGORIES)[K.cat], K.topic_idx)])
    crow = K.crow
    is_leaf = crow["depth"] == 2
    n_items = np.bincount(crow["course"][is_leaf], minlength=K.nc)
    tot_min = np.bincount(crow["course"][is_leaf], weights=crow["minutes"][is_leaf], minlength=K.nc).astype(int)
    t["courses"] = {
        "course_id": m.crs_id,
        "title": np.char.add(np.char.add(topics, " - "), np.array(LEVEL_TITLE)[K.level]),
        "category": np.array(C.CATEGORIES)[K.cat],
        "level": np.array(C.LEVELS)[K.level],
        "duration_weeks": K.dur,
        "delivery_mode": np.array(C.MODES)[K.mode],
        "published_date": date_str(K.pub),
        "status": np.where(retired, "retired", "published"),
        "retired_date": date_str(K.ret, retired),
        "n_modules": K.n_mod,
        "n_items": n_items,
        "total_est_minutes": tot_min,
    }
    tcode = crow["type"]
    names = np.array(["video", "reading", "discussion", "quiz", "assignment", "exam", "module"])
    parent = np.where(crow["parent"] > 0, ids("CNT-", np.maximum(crow["parent"], 1)), "")
    t["content_items"] = {
        "content_id": m.cnt_id,
        "course_id": m.crs_id[crow["course"]],
        "parent_content_id": parent,
        "content_type": names[tcode],
        "title": crow["title"],
        "sequence_no": crow["seq"],
        "depth": crow["depth"],
        "week_number": crow["week"],
        "is_required": bool_str(crow["req"]),
        "est_minutes": crow["minutes"],
    }
    anames = np.array(["quiz", "assignment", "exam"])
    leaf_cnum = K.leaf["cnum"][K.asm_leaf]
    t["assessments"] = {
        "assessment_id": m.asm_id,
        "content_id": m.cnt_id[leaf_cnum - 1],
        "course_id": m.crs_id[K.asm_course],
        "assessment_type": anames[K.asm_type],
        "max_score": np.full(K.n_asm, 100),
        "passing_score": K.asm_pass,
        "max_attempts": K.asm_maxatt,
        "is_required": bool_str(K.asm_req),
        "weight_pct": np.char.mod("%.2f", K.asm_weight),
        "difficulty_rating": K.asm_rating,
    }
    r = np.arange(2 * K.nc)
    course_of_rule = r // 2
    ver = r % 2 + 1
    eff_from = np.where(ver == 1, C.epoch_day("2025-01-01"), C.RULE_V2_DAY)
    t["completion_rules"] = {
        "rule_id": m.rul_id,
        "course_id": m.crs_id[course_of_rule],
        "rule_version": ver,
        "effective_from": date_str(eff_from),
        "effective_to": date_str(np.full(len(r), C.RULE_V2_DAY - 1), ver == 1),
        "min_required_content_pct": K.rule_pct,
        "assessment_policy": np.full(len(r), "all_required_passed"),
        "completion_window_days": np.full(len(r), C.GRACE_DAYS),
    }
    base = dt.date(1970, 1, 1)
    labels = []
    for d in K.coh_start:
        iso = (base + dt.timedelta(days=int(d))).isocalendar()
        labels.append(f"{iso[0]}-W{iso[1]:02d}")
    status = np.where(K.coh_start > C.AS_OF_DAY, "planned",
              np.where(K.coh_end >= C.AS_OF_DAY, "active",
              np.where(K.coh_access_end >= C.AS_OF_DAY, "grace", "closed")))
    self_paced = K.mode[K.coh_course] == 1
    t["cohorts"] = {
        "cohort_id": m.coh_id,
        "course_id": m.crs_id[K.coh_course],
        "cohort_label": np.array(labels),
        "start_date": date_str(K.coh_start),
        "end_date": date_str(K.coh_end),
        "access_end_date": date_str(K.coh_access_end),
        "instructor_code": np.where(self_paced, "", ids("INS-", K.coh_inst, 4)),
        "capacity": K.coh_cap,
        "status": status,
    }
    return t

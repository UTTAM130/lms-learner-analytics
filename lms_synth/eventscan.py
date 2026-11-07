"""Memory-light loader for activity_events.csv.

Reads the 2M-row file in chunks, runs row-level format checks while reading,
and returns compact integer arrays that validate / metrics / evaluate share.
No ground-truth file is ever read here.
"""
from __future__ import annotations

import os
from collections import Counter

import numpy as np
import pandas as pd

from . import config as C
from . import schema as S

NULL_OFF = -99999
ETYPE_CODE = {n: i for i, n in enumerate(C.EVENT_TYPES)}
PLAT_CODE = {n: i for i, n in enumerate(C.PLATFORMS)}
ENGAGEMENT_TYPES = tuple(range(len(C.EVENT_TYPES)))  # every event type counts as learner activity

RX = {
    "event_id": r"EVT-ENR-LRN-\d{6}-CRS-\d{6}-\d{6}",
    "enrollment_id": r"ENR-LRN-\d{6}-CRS-\d{6}",
    "learner_id": r"LRN-\d{6}",
    "course_id": r"CRS-\d{6}",
    "content_id": r"CNT-\d{6}",
    "client_event_id": r"[0-9a-f]{16}",
}


def to_secs(series: pd.Series) -> np.ndarray:
    """ISO 'YYYY-MM-DDTHH:MM:SSZ' -> epoch seconds (int64); '' -> -1."""
    a = series.to_numpy(dtype=str)
    out = np.full(len(a), -1, dtype=np.int64)
    m = a != ""
    if m.any():
        out[m] = a[m].astype("U19").astype("datetime64[s]").astype(np.int64)
    return out


def num(series: pd.Series, start: int, stop: int | None = None) -> np.ndarray:
    """Digits of an ID like 'LRN-000123' -> int (-1 when malformed)."""
    v = pd.to_numeric(series.str.slice(start, stop), errors="coerce").to_numpy(dtype=float)
    return np.where(np.isnan(v), -1, v).astype(np.int64)


def hash_str(series: pd.Series) -> np.ndarray:
    return pd.util.hash_pandas_object(series, index=False).to_numpy(dtype=np.uint64)


class Events:
    """Compact, column-oriented view of activity_events (row order = file order)."""

    def __init__(self, cols: dict, stats: Counter, n: int):
        self.__dict__.update(cols)
        self.stats = stats
        self.n = n

    @property
    def enr_key(self):
        # key of the enrollment id carried by the event (int64: 20,000 * 1e6 overflows int32)
        return self.lrn_e.astype(np.int64) * 1_000_000 + self.crs_e


def load_events(data_dir: str, attempt_ids: set | None = None, chunksize: int = 250_000) -> Events:
    path = os.path.join(data_dir, "activity_events.csv")
    keys = ["lrn", "crs", "cnt", "lrn_e", "crs_e", "etype", "t", "off", "ing", "plat", "ckey", "dur",
            "has_att", "seq", "idpref_ok", "eid_hash", "ids_consistent"]
    parts = {k: [] for k in keys}
    st = Counter()
    req = [f.name for f in S.EVENT.fields if f.required]
    for ch in pd.read_csv(path, dtype=str, keep_default_na=False, chunksize=chunksize):
        for c in req:
            st[f"empty:{c}"] += int((ch[c] == "").sum())
        for c, rx in RX.items():
            st[f"badformat:{c}"] += int((~ch[c].str.fullmatch(rx)).sum())
        st["bad_enum:event_type"] += int((~ch.event_type.isin(C.EVENT_TYPES)).sum())
        st["bad_enum:platform"] += int((~ch.platform.isin(C.PLATFORMS)).sum())
        if attempt_ids is not None:
            a = ch.attempt_id[ch.attempt_id != ""]
            st["fk_missing:attempt_id"] += int((~a.isin(attempt_ids)).sum())
        lrn, crs, cnt = num(ch.learner_id, 4, 10), num(ch.course_id, 4, 10), num(ch.content_id, 4, 10)
        lrn_e, crs_e = num(ch.enrollment_id, 8, 14), num(ch.enrollment_id, 19, 25)
        parts["lrn"].append(lrn.astype(np.int32)); parts["crs"].append(crs.astype(np.int32))
        parts["cnt"].append(cnt.astype(np.int32))
        parts["lrn_e"].append(lrn_e.astype(np.int32)); parts["crs_e"].append(crs_e.astype(np.int32))
        parts["etype"].append(ch.event_type.map(ETYPE_CODE).fillna(-1).to_numpy(dtype=np.int8))
        parts["t"].append(to_secs(ch.event_time_utc))
        off = pd.to_numeric(ch.device_utc_offset_minutes.replace("", np.nan), errors="coerce").to_numpy(dtype=float)
        parts["off"].append(np.where(np.isnan(off), NULL_OFF, off).astype(np.int32))
        parts["ing"].append(to_secs(ch.ingested_at_utc))
        parts["plat"].append(ch.platform.map(PLAT_CODE).fillna(-1).to_numpy(dtype=np.int8))
        parts["ckey"].append(hash_str(ch.client_event_id))
        dur = pd.to_numeric(ch.duration_seconds.replace("", np.nan), errors="coerce").to_numpy(dtype=float)
        parts["dur"].append(np.where(np.isnan(dur), -1, dur).astype(np.int32))
        parts["has_att"].append((ch.attempt_id != "").to_numpy())
        parts["seq"].append(num(ch.event_id, -6).astype(np.int32))
        parts["idpref_ok"].append((ch.event_id.str.slice(0, -7) == "EVT-" + ch.enrollment_id).to_numpy())
        parts["eid_hash"].append(hash_str(ch.event_id))
        parts["ids_consistent"].append(((lrn == lrn_e) & (crs == crs_e)).__and__(
            (ch.enrollment_id == "ENR-" + ch.learner_id + "-" + ch.course_id).to_numpy()))
    cols = {k: np.concatenate(v) if v else np.zeros(0) for k, v in parts.items()}
    return Events(cols, st, len(cols["t"]))


def dedup_keep_first(ev: Events) -> np.ndarray:
    """Boolean mask of rows to keep: for every client_event_id keep the earliest-ingested row
    (ties: lowest file position). This is the documented deduplication rule."""
    order = np.lexsort((np.arange(ev.n), ev.ing, ev.ckey))
    ck = ev.ckey[order]
    first = np.r_[True, ck[1:] != ck[:-1]]
    keep = np.zeros(ev.n, dtype=bool)
    keep[order[first]] = True
    return keep

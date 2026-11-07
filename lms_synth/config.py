"""Constants, scale presets and generation parameters.

Everything that influences random draws lives here or in generator.py; the
fixed seed + fixed CHUNK size are the reproducibility contract.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

DEFAULT_SEED = 20261022
GENERATOR_VERSION = "1.0.0"
CHUNK = 10_000  # enrollments per simulation chunk (part of the reproducibility contract)


def epoch_day(s: str) -> int:
    return int(np.datetime64(s, "D").astype("int64"))


def epoch_sec(s: str) -> int:
    return int(np.datetime64(s, "s").astype("int64"))


# ---- observation window --------------------------------------------------
AS_OF_SEC = epoch_sec("2026-10-31T00:00:00")  # data cut-off (by ingestion time)
AS_OF_DAY = AS_OF_SEC // 86400
GRACE_DAYS = 30
FIRST_COHORT_DAY = epoch_day("2026-01-05")  # a Monday
LAST_COHORT_DAY = epoch_day("2026-11-30")  # a Monday (cohorts after AS_OF are 'planned')
RETIRE_DAY = epoch_day("2026-07-01")
RULE_V2_DAY = epoch_day("2026-06-01")
SIGNUP_FIRST_DAY = epoch_day("2025-06-01")
SIGNUP_LAST_DAY = epoch_day("2026-08-31")


@dataclass(frozen=True)
class Scale:
    name: str
    n_learners: int
    n_courses: int
    n_enrollments: int


SCALES = {
    "tiny": Scale("tiny", 300, 12, 1_500),
    "starter": Scale("starter", 1_000, 40, 5_000),
    "full": Scale("full", 20_000, 500, 100_000),
}

# ---- learner population ---------------------------------------------------
SEGMENTS = ["power", "regular", "casual", "dormant", "inactive"]
SEG_P = np.array([0.10, 0.35, 0.28, 0.15, 0.12])
SEG_ENROLL_WEIGHT = np.array([12.0, 6.0, 3.0, 2.0, 0.8])
# probability a learner finishes the whole course path / else the fraction reached (Beta)
SEG_COMPLETER_P = np.array([0.80, 0.42, 0.12, 0.01, 0.0])
SEG_STOP_BETA = [(4, 2.5), (2.5, 3), (1.5, 3.5), (1, 8), (1, 1)]

# (country, IANA tz, standard UTC offset minutes (no DST), weight)
TIMEZONES = [
    ("IN", "Asia/Kolkata", 330, 0.575),
    ("US", "America/New_York", -300, 0.05),
    ("US", "America/Chicago", -360, 0.025),
    ("US", "America/Los_Angeles", -480, 0.025),
    ("GB", "Europe/London", 0, 0.05),
    ("AE", "Asia/Dubai", 240, 0.05),
    ("SG", "Asia/Singapore", 480, 0.05),
    ("AU", "Australia/Sydney", 600, 0.04),
    ("DE", "Europe/Berlin", 60, 0.04),
    ("BR", "America/Sao_Paulo", -180, 0.04),
    ("NG", "Africa/Lagos", 60, 0.03),
    ("CA", "America/Toronto", -300, 0.025),
]
DEVICES = ["desktop", "mobile", "mixed"]
DEVICE_P = [0.35, 0.45, 0.20]
CHANNELS = ["organic", "referral", "employer", "partner"]
CHANNEL_P = [0.5, 0.2, 0.2, 0.1]

# ---- catalogue -----------------------------------------------------------
CATEGORIES = ["Data Science", "Software Engineering", "Business", "Design",
              "Health", "Languages", "Finance", "Mathematics"]
LEVELS = ["beginner", "intermediate", "advanced"]
LEVEL_P = [0.4, 0.4, 0.2]
LEVEL_DIFFICULTY = np.array([-0.4, 0.0, 0.5])
DURATIONS = [4, 6, 8, 10, 12]
DURATION_P = [0.15, 0.25, 0.30, 0.15, 0.15]
MODES = ["instructor_led", "self_paced"]
MODE_P = [0.6, 0.4]

ITEM_TYPES = ["video", "reading", "discussion", "quiz", "assignment", "exam"]  # codes 0..5
# probability an item of a type is flagged required
REQUIRED_P = [0.92, 0.85, 0.0, 0.6, 0.5, 1.0]
MINUTES = {0: (5, 25), 1: (5, 15), 2: (10, 10), 3: (10, 20), 4: (30, 90), 5: (60, 120)}
SKIP_P = np.array([0.06, 0.06, 0.5, 0.10, 0.10, 0.10])

# ---- events --------------------------------------------------------------
EVENT_TYPES = ["content_view", "video_play", "video_complete", "content_complete",
               "discussion_post", "assessment_start", "assessment_submit"]  # codes 0..6
PLATFORMS = ["web", "mobile_app", "mobile_offline_sync"]
# local hour-of-day distribution (evening peak)
_h = np.ones(24) * 0.6
_h[6:10] = 2.0
_h[12:15] = 1.8
_h[19:23] = 4.5
_h[0:5] = 0.15
HOUR_P = _h / _h.sum()
HOUR_CDF = np.cumsum(HOUR_P)

# ---- anomaly injection ---------------------------------------------------
DUP_RATE_ONLINE = 0.012
DUP_RATE_OFFLINE = 0.06
UNENROLLED_RATE = 0.004  # of baseline events
UNENROLLED_BEFORE_SHARE = 0.30
TZ_RATE = 0.004
TZ_OFFSET_MISSING_SHARE = 0.60
PREMATURE_A_RATE = 0.12  # of enrollments that met the content rule but never passed a required assessment
PREMATURE_B_RATE = 0.10  # of rule-completed enrollments where the last assessment pass came >1h after content threshold
MIN_ANOMALIES = 5  # floor per chunk and anomaly type so small scales still exercise every path

# ---- simulation knobs ----------------------------------------------------
EVENTS_PER_ENROLLMENT = 20.0  # spec: 2M events / 100k enrollments
BASELINE_SHARE = 0.975  # baseline events as share of the target; duplicates/orphans make up the rest
PLAT_CUM = np.cumsum([[0.97, 0.03, 0.0], [0.05, 0.65, 0.30], [0.45, 0.40, 0.15]], axis=1)  # by device
LAG_MEAN_DAYS = np.array([0.7, 1.8, 3.0, 5.0, 3.0])  # per segment
RETRY_P = np.array([0.95, 0.80, 0.55, 0.30, 0.0])  # retry after a failed attempt, per segment
REVISIT_W = np.array([3.0, 1.5, 1.0, 0.7, 0.0])
DROP_P = np.array([0.10, 0.25, 0.35, 0.30, 0.05])  # explicit withdrawal among non-completers
ABANDON_P = 0.04
ABILITY_SHIFT = np.array([0.4, 0.1, -0.1, -0.3, 0.0])
COMPLETION_DELAY_SEC = (30, 900)  # platform marks completion this long after the rule is met

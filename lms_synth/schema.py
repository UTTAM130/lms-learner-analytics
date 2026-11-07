"""Single source of truth for table definitions.

Used to generate the data dictionary (docs/data_dictionary.md), the SQL DDL
(docs/schema.sql) and by the validator (required fields, enums, uniqueness).
"""
from __future__ import annotations

from dataclasses import dataclass

from . import config as C

# ---- enumerations --------------------------------------------------------
LEVELS = C.LEVELS
MODES = C.MODES
COURSE_STATUS = ["published", "retired"]
CONTENT_TYPES = ["video", "reading", "discussion", "quiz", "assignment", "exam"]  # leaf codes 0..5
CONTENT_TYPES_ALL = CONTENT_TYPES + ["module"]
ASSESSMENT_TYPES = ["quiz", "assignment", "exam"]
COHORT_STATUS = ["planned", "active", "grace", "closed"]
ENROLL_STATUS = ["enrolled", "active", "completed", "dropped", "expired"]
CHANGE_SOURCE = ["learner", "system"]
EVENT_TYPES = C.EVENT_TYPES
PLATFORMS = C.PLATFORMS
ATTEMPT_STATUS = ["submitted", "abandoned"]
OUTCOME_STATUS = ["completed", "in_progress", "withdrawn", "not_completed"]
ASSESSMENT_POLICY = ["all_required_passed"]
DEVICES = C.DEVICES
CHANNELS = C.CHANNELS
COUNTRIES = sorted({t[0] for t in C.TIMEZONES})
TIMEZONE_OFFSETS = {t[1]: t[2] for t in C.TIMEZONES}

# allowed enrollment status transitions (None = initial)
TRANSITIONS = {
    None: {"enrolled"},
    "enrolled": {"active", "dropped", "expired"},
    "active": {"completed", "dropped", "expired"},
    "completed": set(),
    "dropped": set(),
    "expired": set(),
}


@dataclass(frozen=True)
class Field:
    name: str
    type: str  # string | integer | decimal | boolean | date | timestamp
    required: bool
    description: str
    allowed: str = ""
    unit: str = ""
    unique: bool = False
    rule: str = ""
    enum: tuple = ()


@dataclass(frozen=True)
class Table:
    name: str
    pk: str
    description: str
    fields: tuple
    fks: tuple = ()  # (column, parent_table, parent_column)
    cardinality: str = ""
    lifecycle: str = ""

    @property
    def columns(self):
        return [f.name for f in self.fields]


def F(name, type, required, description, allowed="", unit="", unique=False, rule="", enum=()):
    return Field(name, type, required, description, allowed, unit, unique, rule, tuple(enum))


TS = "ISO-8601 UTC, YYYY-MM-DDTHH:MM:SSZ"

LEARNER = Table(
    "learners", "learner_id",
    "A person with a platform account. Master data, generated first.",
    (
        F("learner_id", "string", True, "Primary key.", r"LRN-\d{6}", unique=True, rule="zero-padded counter, immutable"),
        F("signup_date", "date", True, "Account creation date.", "2025-01-01..as-of", rule="<= date of the learner's first enrollment (7-90 days earlier)"),
        F("country_code", "string", True, "ISO-3166 alpha-2 country.", ",".join(COUNTRIES), enum=COUNTRIES),
        F("timezone", "string", True, "IANA timezone of the learner.", "; ".join(TIMEZONE_OFFSETS), rule="must agree with utc_offset_minutes", enum=list(TIMEZONE_OFFSETS)),
        F("utc_offset_minutes", "integer", True, "Standard (non-DST) UTC offset used to derive learner-local dates.", "-720..840", unit="minutes", rule="DST is deliberately ignored; see README limitations"),
        F("primary_device", "string", True, "Most-used device class.", ",".join(DEVICES), enum=DEVICES),
        F("acquisition_channel", "string", True, "How the learner arrived.", ",".join(CHANNELS), enum=CHANNELS),
    ),
    cardinality="Learner 1:N Enrollment (N:M with Course via Enrollment)",
    lifecycle="Static master record; no lifecycle in this model.",
)

COURSE = Table(
    "courses", "course_id",
    "A course in the catalogue.",
    (
        F("course_id", "string", True, "Primary key.", r"CRS-\d{6}", unique=True),
        F("title", "string", True, "Display title."),
        F("category", "string", True, "Subject area.", ",".join(C.CATEGORIES), enum=C.CATEGORIES),
        F("level", "string", True, "Difficulty level.", ",".join(LEVELS), enum=LEVELS),
        F("duration_weeks", "integer", True, "Planned length of a cohort run.", "4,6,8,10,12", unit="weeks"),
        F("delivery_mode", "string", True, "Delivery mode.", ",".join(MODES), enum=MODES),
        F("published_date", "date", True, "Effective-from date of the course and its content."),
        F("status", "string", True, "Lifecycle state at the data cut-off.", ",".join(COURSE_STATUS), enum=COURSE_STATUS,
          rule="retired iff retired_date <= as-of date"),
        F("retired_date", "date", False, "Effective-to date.", rule="required iff status = retired; no cohort starts within 14 days of it"),
        F("n_modules", "integer", True, "Number of module rows in content_items.", rule="= count of content_items(type=module)"),
        F("n_items", "integer", True, "Number of leaf content items.", rule="= count of content_items with depth 2"),
        F("total_est_minutes", "integer", True, "Sum of est_minutes of leaf items.", unit="minutes", rule="= sum(content_items.est_minutes, depth 2)"),
    ),
    cardinality="Course 1:N ContentItem, Course 1:N Cohort, Course 1:N CompletionRule",
    lifecycle="published -> retired (terminal).",
)

CONTENT = Table(
    "content_items", "content_id",
    "Course content hierarchy: module rows (depth 1) and leaf items (depth 2).",
    (
        F("content_id", "string", True, "Primary key.", r"CNT-\d{6}", unique=True),
        F("course_id", "string", True, "Owning course."),
        F("parent_content_id", "string", False, "Module row for leaf items; null for modules.", rule="null iff content_type=module"),
        F("content_type", "string", True, "Type.", ",".join(CONTENT_TYPES_ALL), enum=CONTENT_TYPES_ALL),
        F("title", "string", True, "Display title."),
        F("sequence_no", "integer", True, "Position within parent (modules: within course).", ">=1", rule="unique within (course_id, parent_content_id)"),
        F("depth", "integer", True, "Hierarchy depth.", "1,2"),
        F("week_number", "integer", True, "Planned week in the cohort schedule.", "1..duration_weeks", unit="week index"),
        F("is_required", "boolean", True, "Counts towards the CompletionRule.", "true,false", rule="module: true iff any child required; discussions are never required"),
        F("est_minutes", "integer", True, "Expected effort.", ">=0", unit="minutes", rule="module = sum of its children (derived)"),
    ),
    fks=(("course_id", "courses", "course_id"), ("parent_content_id", "content_items", "content_id")),
    cardinality="ContentItem N:1 Course; ContentItem 1:N ContentItem (module -> items); ContentItem N:M Enrollment via ActivityEvent",
)

ASSESSMENT = Table(
    "assessments", "assessment_id",
    "Graded item attached 1:1 to a quiz/assignment/exam content item.",
    (
        F("assessment_id", "string", True, "Primary key.", r"ASM-2026-\d{6}", unique=True),
        F("content_id", "string", True, "The content item that hosts the assessment.", unique=True, rule="content_type in (quiz, assignment, exam) and matches assessment_type"),
        F("course_id", "string", True, "Owning course.", rule="= content_items.course_id of content_id"),
        F("assessment_type", "string", True, "Type.", ",".join(ASSESSMENT_TYPES), enum=ASSESSMENT_TYPES),
        F("max_score", "integer", True, "Maximum score.", "100", unit="points"),
        F("passing_score", "integer", True, "Minimum score to pass.", "quiz 60, assignment 65, exam 70", unit="points"),
        F("max_attempts", "integer", True, "Attempts allowed.", "quiz 3, assignment 2, exam 2"),
        F("is_required", "boolean", True, "Must be passed for completion.", rule="= content_items.is_required"),
        F("weight_pct", "decimal", True, "Weight in the course final score.", "0..100", unit="percent", rule="required assessments of a course sum to exactly 100; others 0"),
        F("difficulty_rating", "integer", True, "Published difficulty (noisy proxy of true difficulty).", "1..5"),
    ),
    fks=(("content_id", "content_items", "content_id"), ("course_id", "courses", "course_id")),
    cardinality="Assessment 1:1 ContentItem; Assessment 1:N Attempt",
)

RULE = Table(
    "completion_rules", "rule_id",
    "Versioned course completion rule with effective dates.",
    (
        F("rule_id", "string", True, "Primary key.", r"RUL-\d{6}", unique=True),
        F("course_id", "string", True, "Course the rule applies to."),
        F("rule_version", "integer", True, "Version number.", "1,2", rule="unique within course"),
        F("effective_from", "date", True, "First day the version applies (by cohort start date)."),
        F("effective_to", "date", False, "Last day; null = open ended.", rule="versions of a course are contiguous and non-overlapping"),
        F("min_required_content_pct", "integer", True, "Share of required video/reading/discussion items that must be completed.", "70..95", unit="percent"),
        F("assessment_policy", "string", True, "Assessment condition.", ",".join(ASSESSMENT_POLICY), enum=ASSESSMENT_POLICY,
          rule="all_required_passed: every required assessment has a submitted attempt with score >= passing_score"),
        F("completion_window_days", "integer", True, "Days after cohort end during which progress still counts.", "30", unit="days"),
    ),
    fks=(("course_id", "courses", "course_id"),),
    cardinality="CompletionRule N:1 Course; CompletionRule 1:N Enrollment (rule snapshot at cohort start)",
)

COHORT = Table(
    "cohorts", "cohort_id",
    "A scheduled run of a course; enrollments belong to exactly one cohort.",
    (
        F("cohort_id", "string", True, "Primary key.", r"COH-\d{6}", unique=True),
        F("course_id", "string", True, "Course being run."),
        F("cohort_label", "string", True, "ISO year-week of the start.", r"\d{4}-W\d{2}"),
        F("start_date", "date", True, "First day (always a Monday)."),
        F("end_date", "date", True, "Last scheduled day.", rule="= start_date + 7*duration_weeks - 1"),
        F("access_end_date", "date", True, "Last day content/assessments can be used and progress counts.", rule="= end_date + 30"),
        F("instructor_code", "string", False, "External instructor reference (instructor_led only).", r"INS-\d{4}", rule="null iff delivery_mode = self_paced"),
        F("capacity", "integer", True, "Seat limit.", "40..200"),
        F("status", "string", True, "State at the data cut-off.", ",".join(COHORT_STATUS), enum=COHORT_STATUS,
          rule="planned: start>as-of; active: start<=as-of<=end; grace: end<as-of<=access_end; closed: after"),
    ),
    fks=(("course_id", "courses", "course_id"),),
    cardinality="Cohort N:1 Course; Cohort 1:N Enrollment",
    lifecycle="planned -> active -> grace -> closed (snapshot at as-of date).",
)

ENROLLMENT = Table(
    "enrollments", "enrollment_id",
    "Bridge between Learner and Course (N:M), placed in one Cohort. Current state is derived from enrollment_status_history.",
    (
        F("enrollment_id", "string", True, "Primary key.", r"ENR-LRN-\d{6}-CRS-\d{6}", unique=True, rule="ENR-<learner_id>-<course_id>; one per learner and course"),
        F("learner_id", "string", True, "Learner."),
        F("course_id", "string", True, "Course.", rule="= cohorts.course_id of cohort_id"),
        F("cohort_id", "string", True, "Cohort."),
        F("rule_id", "string", True, "Completion rule version in force at the cohort start date.", rule="rule effective on cohorts.start_date"),
        F("enrolled_at", "timestamp", True, TS, rule=">= learners.signup_date; <= cohort access_end; <= as-of"),
        F("current_status", "string", True, "Latest status in the history.", ",".join(ENROLL_STATUS), enum=ENROLL_STATUS, rule="= last row of enrollment_status_history"),
        F("status_updated_at", "timestamp", True, TS, rule="= effective_from of the last history row"),
    ),
    fks=(("learner_id", "learners", "learner_id"), ("course_id", "courses", "course_id"),
         ("cohort_id", "cohorts", "cohort_id"), ("rule_id", "completion_rules", "rule_id")),
    cardinality="Learner N:M Course via Enrollment; Enrollment 1:N ActivityEvent, 1:N Attempt, 1:N StatusHistory, 1:1 CourseOutcome",
    lifecycle="enrolled -> active -> completed | dropped | expired; enrolled -> dropped | expired. History is append-only.",
)

HISTORY = Table(
    "enrollment_status_history", "history_id",
    "Append-only log of enrollment state changes (history is never overwritten).",
    (
        F("history_id", "string", True, "Primary key.", r"ESH-<enrollment_id>-\d{2}", unique=True),
        F("enrollment_id", "string", True, "Enrollment."),
        F("status", "string", True, "New status.", ",".join(ENROLL_STATUS), enum=ENROLL_STATUS),
        F("previous_status", "string", False, "Status before the change; null for the first row.", enum=ENROLL_STATUS),
        F("effective_from", "timestamp", True, TS, rule="non-decreasing within enrollment"),
        F("change_source", "string", True, "Who caused the change.", ",".join(CHANGE_SOURCE), enum=CHANGE_SOURCE),
    ),
    fks=(("enrollment_id", "enrollments", "enrollment_id"),),
    cardinality="StatusHistory N:1 Enrollment",
    lifecycle="Transitions limited to schema.TRANSITIONS.",
)

EVENT = Table(
    "activity_events", "event_id",
    "Learner activity as received by the platform, one row per delivery (duplicates are possible).",
    (
        F("event_id", "string", True, "Primary key, assigned at ingestion in arrival order.", r"EVT-<enrollment_id>-\d{6}", unique=True),
        F("enrollment_id", "string", True, "Enrollment (ENR-<learner>-<course>).", rule="should resolve to enrollments; unresolved ids are the 'unenrolled activity' exception"),
        F("learner_id", "string", True, "Learner."),
        F("course_id", "string", True, "Course."),
        F("content_id", "string", True, "Content item touched.", rule="must belong to course_id"),
        F("event_type", "string", True, "Type.", ",".join(EVENT_TYPES), enum=EVENT_TYPES),
        F("event_time_utc", "timestamp", True, "When the activity happened, as normalised by the server. " + TS, rule="should be <= ingested_at_utc"),
        F("device_utc_offset_minutes", "integer", False, "UTC offset reported by the device.", unit="minutes", rule="null if the device did not report it"),
        F("ingested_at_utc", "timestamp", True, "When the platform received the event. " + TS, rule="<= as-of; late/offline events have large lag"),
        F("platform", "string", True, "Source.", ",".join(PLATFORMS), enum=PLATFORMS),
        F("client_event_id", "string", True, "Idempotency key generated on the client; retries reuse it.", r"[0-9a-f]{16}", rule="distinct real events never share it"),
        F("duration_seconds", "integer", False, "Time spent.", ">=0", unit="seconds", rule="null for content_view and assessment_start"),
        F("attempt_id", "string", False, "Attempt for assessment_start/assessment_submit events.", rule="non-null iff event_type in (assessment_start, assessment_submit)"),
    ),
    fks=(("enrollment_id", "enrollments", "enrollment_id"), ("learner_id", "learners", "learner_id"),
         ("course_id", "courses", "course_id"), ("content_id", "content_items", "content_id"),
         ("attempt_id", "attempts", "attempt_id")),
    cardinality="ActivityEvent N:1 Enrollment, N:1 ContentItem (the N:M bridge between them)",
)

ATTEMPT = Table(
    "attempts", "attempt_id",
    "One try at an assessment by an enrollment (repeated attempts allowed up to max_attempts).",
    (
        F("attempt_id", "string", True, "Primary key.", r"ATT-<enrollment_id>-\d{6}-\d{2}", unique=True, rule="ATT-<enrollment_id>-<assessment seq>-<attempt_no>"),
        F("enrollment_id", "string", True, "Enrollment."),
        F("assessment_id", "string", True, "Assessment."),
        F("attempt_no", "integer", True, "1-based counter.", "1..max_attempts", rule="consecutive per (enrollment, assessment)"),
        F("started_at_utc", "timestamp", True, TS),
        F("submitted_at_utc", "timestamp", False, TS, rule="null iff status=abandoned; >= started_at_utc"),
        F("status", "string", True, "Outcome of the try.", ",".join(ATTEMPT_STATUS), enum=ATTEMPT_STATUS),
        F("score", "decimal", False, "Score achieved.", "0..max_score", unit="points", rule="null iff abandoned"),
        F("passed", "boolean", False, "Derived: score >= passing_score.", "true,false", rule="null iff abandoned"),
        F("duration_minutes", "decimal", False, "submitted - started.", unit="minutes"),
    ),
    fks=(("enrollment_id", "enrollments", "enrollment_id"), ("assessment_id", "assessments", "assessment_id")),
    cardinality="Attempt N:1 Enrollment, N:1 Assessment (N:M bridge between them)",
)

OUTCOME = Table(
    "course_outcomes", "outcome_id",
    "One derived outcome per enrollment, evaluated from deduplicated activity, attempts and the applicable rule.",
    (
        F("outcome_id", "string", True, "Primary key.", r"OUT-<enrollment_id>", unique=True),
        F("enrollment_id", "string", True, "Enrollment (1:1).", unique=True),
        F("rule_id", "string", True, "Rule applied."),
        F("required_content_total", "integer", True, "Required video/reading/discussion items in the course."),
        F("required_content_completed", "integer", True, "Distinct required items with a completion event (deduplicated, valid enrollment, within window)."),
        F("content_completion_pct", "decimal", True, "completed / total * 100.", "0..100", unit="percent"),
        F("required_assessments_total", "integer", True, "Required assessments in the course."),
        F("required_assessments_passed", "integer", True, "Required assessments with a passing submitted attempt."),
        F("final_score", "decimal", True, "sum(weight_pct * best submitted score) / 100 over required assessments (0 if never submitted).", "0..100", unit="points"),
        F("rule_met_at_utc", "timestamp", False, "Time both rule conditions first held.", rule="max(content threshold reached, last required assessment passed); null if not met"),
        F("outcome_status", "string", True, "Rule-based outcome at the cut-off.", ",".join(OUTCOME_STATUS), enum=OUTCOME_STATUS,
          rule="completed iff rule met; else withdrawn if dropped; else not_completed once access window closed; else in_progress"),
        F("completed_date", "date", False, "UTC date of rule_met_at_utc.", rule="null unless completed"),
        F("platform_completed_at_utc", "timestamp", False, "When the platform marked the enrollment completed (history)."),
        F("completion_conflict", "boolean", True, "Platform completion recorded although the rule was not met, or before it was met.", "true,false"),
        F("evaluated_as_of_utc", "timestamp", True, "Data cut-off used for evaluation."),
    ),
    fks=(("enrollment_id", "enrollments", "enrollment_id"), ("rule_id", "completion_rules", "rule_id")),
    cardinality="CourseOutcome 1:1 Enrollment",
)

TABLES = {t.name: t for t in (LEARNER, COURSE, CONTENT, ASSESSMENT, RULE, COHORT, ENROLLMENT, HISTORY, EVENT, ATTEMPT, OUTCOME)}
# order in which tables can be loaded without forward references
LOAD_ORDER = ["learners", "courses", "content_items", "assessments", "completion_rules", "cohorts",
              "enrollments", "enrollment_status_history", "attempts", "activity_events", "course_outcomes"]

GROUND_TRUTH_COLUMNS = ["ground_truth_id", "record_type", "record_id", "issue_type", "subtype",
                        "related_record_id", "observed_value", "true_value", "expected_decision"]
ISSUE_TYPES = ["duplicate_event", "activity_unenrolled", "completion_before_required_assessment", "timezone_shift"]

-- Generated from lms_synth/schema.py (do not edit by hand). SQLite / ANSI-compatible.
-- Empty CSV cells are NULL. booleans are 'true'/'false'; timestamps ISO-8601 UTC text.
-- NOTE: activity_events.enrollment_id carries the labelled 'activity from an unenrolled learner'
-- exception, so rows violating that one FK are expected (see ground_truth/).

-- A person with a platform account. Master data, generated first.
CREATE TABLE learners (
  learner_id TEXT PRIMARY KEY,
  signup_date TEXT NOT NULL,
  country_code TEXT NOT NULL CHECK (country_code IN ('AE','AU','BR','CA','DE','GB','IN','NG','SG','US')),
  timezone TEXT NOT NULL CHECK (timezone IN ('Asia/Kolkata','America/New_York','America/Chicago','America/Los_Angeles','Europe/London','Asia/Dubai','Asia/Singapore','Australia/Sydney','Europe/Berlin','America/Sao_Paulo','Africa/Lagos','America/Toronto')),
  utc_offset_minutes INTEGER NOT NULL,
  primary_device TEXT NOT NULL CHECK (primary_device IN ('desktop','mobile','mixed')),
  acquisition_channel TEXT NOT NULL CHECK (acquisition_channel IN ('organic','referral','employer','partner'))
);

-- A course in the catalogue.
CREATE TABLE courses (
  course_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  category TEXT NOT NULL CHECK (category IN ('Data Science','Software Engineering','Business','Design','Health','Languages','Finance','Mathematics')),
  level TEXT NOT NULL CHECK (level IN ('beginner','intermediate','advanced')),
  duration_weeks INTEGER NOT NULL,
  delivery_mode TEXT NOT NULL CHECK (delivery_mode IN ('instructor_led','self_paced')),
  published_date TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('published','retired')),
  retired_date TEXT,
  n_modules INTEGER NOT NULL,
  n_items INTEGER NOT NULL,
  total_est_minutes INTEGER NOT NULL
);

-- Course content hierarchy: module rows (depth 1) and leaf items (depth 2).
CREATE TABLE content_items (
  content_id TEXT PRIMARY KEY,
  course_id TEXT NOT NULL,
  parent_content_id TEXT,
  content_type TEXT NOT NULL CHECK (content_type IN ('video','reading','discussion','quiz','assignment','exam','module')),
  title TEXT NOT NULL,
  sequence_no INTEGER NOT NULL,
  depth INTEGER NOT NULL,
  week_number INTEGER NOT NULL,
  is_required TEXT NOT NULL CHECK (is_required IN ('true','false')),
  est_minutes INTEGER NOT NULL,
  FOREIGN KEY (course_id) REFERENCES courses(course_id),
  FOREIGN KEY (parent_content_id) REFERENCES content_items(content_id)
);

-- Graded item attached 1:1 to a quiz/assignment/exam content item.
CREATE TABLE assessments (
  assessment_id TEXT PRIMARY KEY,
  content_id TEXT NOT NULL UNIQUE,
  course_id TEXT NOT NULL,
  assessment_type TEXT NOT NULL CHECK (assessment_type IN ('quiz','assignment','exam')),
  max_score INTEGER NOT NULL,
  passing_score INTEGER NOT NULL,
  max_attempts INTEGER NOT NULL,
  is_required TEXT NOT NULL CHECK (is_required IN ('true','false')),
  weight_pct REAL NOT NULL,
  difficulty_rating INTEGER NOT NULL,
  FOREIGN KEY (content_id) REFERENCES content_items(content_id),
  FOREIGN KEY (course_id) REFERENCES courses(course_id)
);

-- Versioned course completion rule with effective dates.
CREATE TABLE completion_rules (
  rule_id TEXT PRIMARY KEY,
  course_id TEXT NOT NULL,
  rule_version INTEGER NOT NULL,
  effective_from TEXT NOT NULL,
  effective_to TEXT,
  min_required_content_pct INTEGER NOT NULL,
  assessment_policy TEXT NOT NULL CHECK (assessment_policy IN ('all_required_passed')),
  completion_window_days INTEGER NOT NULL,
  FOREIGN KEY (course_id) REFERENCES courses(course_id)
);

-- A scheduled run of a course; enrollments belong to exactly one cohort.
CREATE TABLE cohorts (
  cohort_id TEXT PRIMARY KEY,
  course_id TEXT NOT NULL,
  cohort_label TEXT NOT NULL,
  start_date TEXT NOT NULL,
  end_date TEXT NOT NULL,
  access_end_date TEXT NOT NULL,
  instructor_code TEXT,
  capacity INTEGER NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('planned','active','grace','closed')),
  FOREIGN KEY (course_id) REFERENCES courses(course_id)
);

-- Bridge between Learner and Course (N:M), placed in one Cohort. Current state is derived from enrollment_status_history.
CREATE TABLE enrollments (
  enrollment_id TEXT PRIMARY KEY,
  learner_id TEXT NOT NULL,
  course_id TEXT NOT NULL,
  cohort_id TEXT NOT NULL,
  rule_id TEXT NOT NULL,
  enrolled_at TEXT NOT NULL,
  current_status TEXT NOT NULL CHECK (current_status IN ('enrolled','active','completed','dropped','expired')),
  status_updated_at TEXT NOT NULL,
  FOREIGN KEY (learner_id) REFERENCES learners(learner_id),
  FOREIGN KEY (course_id) REFERENCES courses(course_id),
  FOREIGN KEY (cohort_id) REFERENCES cohorts(cohort_id),
  FOREIGN KEY (rule_id) REFERENCES completion_rules(rule_id)
);

-- Append-only log of enrollment state changes (history is never overwritten).
CREATE TABLE enrollment_status_history (
  history_id TEXT PRIMARY KEY,
  enrollment_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('enrolled','active','completed','dropped','expired')),
  previous_status TEXT CHECK (previous_status IS NULL OR previous_status IN ('enrolled','active','completed','dropped','expired')),
  effective_from TEXT NOT NULL,
  change_source TEXT NOT NULL CHECK (change_source IN ('learner','system')),
  FOREIGN KEY (enrollment_id) REFERENCES enrollments(enrollment_id)
);

-- One try at an assessment by an enrollment (repeated attempts allowed up to max_attempts).
CREATE TABLE attempts (
  attempt_id TEXT PRIMARY KEY,
  enrollment_id TEXT NOT NULL,
  assessment_id TEXT NOT NULL,
  attempt_no INTEGER NOT NULL,
  started_at_utc TEXT NOT NULL,
  submitted_at_utc TEXT,
  status TEXT NOT NULL CHECK (status IN ('submitted','abandoned')),
  score REAL,
  passed TEXT CHECK (passed IS NULL OR passed IN ('true','false')),
  duration_minutes REAL,
  FOREIGN KEY (enrollment_id) REFERENCES enrollments(enrollment_id),
  FOREIGN KEY (assessment_id) REFERENCES assessments(assessment_id)
);

-- Learner activity as received by the platform, one row per delivery (duplicates are possible).
CREATE TABLE activity_events (
  event_id TEXT PRIMARY KEY,
  enrollment_id TEXT NOT NULL,
  learner_id TEXT NOT NULL,
  course_id TEXT NOT NULL,
  content_id TEXT NOT NULL,
  event_type TEXT NOT NULL CHECK (event_type IN ('content_view','video_play','video_complete','content_complete','discussion_post','assessment_start','assessment_submit')),
  event_time_utc TEXT NOT NULL,
  device_utc_offset_minutes INTEGER,
  ingested_at_utc TEXT NOT NULL,
  platform TEXT NOT NULL CHECK (platform IN ('web','mobile_app','mobile_offline_sync')),
  client_event_id TEXT NOT NULL,
  duration_seconds INTEGER,
  attempt_id TEXT,
  FOREIGN KEY (enrollment_id) REFERENCES enrollments(enrollment_id),
  FOREIGN KEY (learner_id) REFERENCES learners(learner_id),
  FOREIGN KEY (course_id) REFERENCES courses(course_id),
  FOREIGN KEY (content_id) REFERENCES content_items(content_id),
  FOREIGN KEY (attempt_id) REFERENCES attempts(attempt_id)
);

-- One derived outcome per enrollment, evaluated from deduplicated activity, attempts and the applicable rule.
CREATE TABLE course_outcomes (
  outcome_id TEXT PRIMARY KEY,
  enrollment_id TEXT NOT NULL UNIQUE,
  rule_id TEXT NOT NULL,
  required_content_total INTEGER NOT NULL,
  required_content_completed INTEGER NOT NULL,
  content_completion_pct REAL NOT NULL,
  required_assessments_total INTEGER NOT NULL,
  required_assessments_passed INTEGER NOT NULL,
  final_score REAL NOT NULL,
  rule_met_at_utc TEXT,
  outcome_status TEXT NOT NULL CHECK (outcome_status IN ('completed','in_progress','withdrawn','not_completed')),
  completed_date TEXT,
  platform_completed_at_utc TEXT,
  completion_conflict TEXT NOT NULL CHECK (completion_conflict IN ('true','false')),
  evaluated_as_of_utc TEXT NOT NULL,
  FOREIGN KEY (enrollment_id) REFERENCES enrollments(enrollment_id),
  FOREIGN KEY (rule_id) REFERENCES completion_rules(rule_id)
);

CREATE INDEX ix_enrollments_cohort ON enrollments(cohort_id);
CREATE INDEX ix_events_enrollment ON activity_events(enrollment_id);
CREATE INDEX ix_events_client ON activity_events(client_event_id);
CREATE INDEX ix_attempts_enrollment ON attempts(enrollment_id, assessment_id);

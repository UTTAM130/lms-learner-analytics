# Validation summary

317 checks: **310 passed, 0 failed**, 7 informational exception counts.

Row counts: learners 1,000, courses 40, content_items 749, assessments 234, completion_rules 80, cohorts 223, enrollments 5,000, enrollment_status_history 11,525, attempts 14,612, course_outcomes 5,000, activity_events 98,702


## structure (11/11 pass)

| status | check | detail |
|---|---|---|
| PASS | learners: columns match data dictionary | 1000 rows |
| PASS | courses: columns match data dictionary | 40 rows |
| PASS | content_items: columns match data dictionary | 749 rows |
| PASS | assessments: columns match data dictionary | 234 rows |
| PASS | completion_rules: columns match data dictionary | 80 rows |
| PASS | cohorts: columns match data dictionary | 223 rows |
| PASS | enrollments: columns match data dictionary | 5000 rows |
| PASS | enrollment_status_history: columns match data dictionary | 11525 rows |
| PASS | attempts: columns match data dictionary | 14612 rows |
| PASS | course_outcomes: columns match data dictionary | 5000 rows |
| PASS | activity_events: row count | 98702 rows |

## required (95/95 pass)

| status | check | detail |
|---|---|---|
| PASS | learners.learner_id not empty | 0 violating rows |
| PASS | learners.signup_date not empty | 0 violating rows |
| PASS | learners.country_code not empty | 0 violating rows |
| PASS | learners.timezone not empty | 0 violating rows |
| PASS | learners.utc_offset_minutes not empty | 0 violating rows |
| PASS | learners.primary_device not empty | 0 violating rows |
| PASS | learners.acquisition_channel not empty | 0 violating rows |
| PASS | courses.course_id not empty | 0 violating rows |
| PASS | courses.title not empty | 0 violating rows |
| PASS | courses.category not empty | 0 violating rows |
| PASS | courses.level not empty | 0 violating rows |
| PASS | courses.duration_weeks not empty | 0 violating rows |
| PASS | courses.delivery_mode not empty | 0 violating rows |
| PASS | courses.published_date not empty | 0 violating rows |
| PASS | courses.status not empty | 0 violating rows |
| PASS | courses.n_modules not empty | 0 violating rows |
| PASS | courses.n_items not empty | 0 violating rows |
| PASS | courses.total_est_minutes not empty | 0 violating rows |
| PASS | content_items.content_id not empty | 0 violating rows |
| PASS | content_items.course_id not empty | 0 violating rows |
| PASS | content_items.content_type not empty | 0 violating rows |
| PASS | content_items.title not empty | 0 violating rows |
| PASS | content_items.sequence_no not empty | 0 violating rows |
| PASS | content_items.depth not empty | 0 violating rows |
| PASS | content_items.week_number not empty | 0 violating rows |
| PASS | content_items.is_required not empty | 0 violating rows |
| PASS | content_items.est_minutes not empty | 0 violating rows |
| PASS | assessments.assessment_id not empty | 0 violating rows |
| PASS | assessments.content_id not empty | 0 violating rows |
| PASS | assessments.course_id not empty | 0 violating rows |
| PASS | assessments.assessment_type not empty | 0 violating rows |
| PASS | assessments.max_score not empty | 0 violating rows |
| PASS | assessments.passing_score not empty | 0 violating rows |
| PASS | assessments.max_attempts not empty | 0 violating rows |
| PASS | assessments.is_required not empty | 0 violating rows |
| PASS | assessments.weight_pct not empty | 0 violating rows |
| PASS | assessments.difficulty_rating not empty | 0 violating rows |
| PASS | completion_rules.rule_id not empty | 0 violating rows |
| PASS | completion_rules.course_id not empty | 0 violating rows |
| PASS | completion_rules.rule_version not empty | 0 violating rows |
| PASS | completion_rules.effective_from not empty | 0 violating rows |
| PASS | completion_rules.min_required_content_pct not empty | 0 violating rows |
| PASS | completion_rules.assessment_policy not empty | 0 violating rows |
| PASS | completion_rules.completion_window_days not empty | 0 violating rows |
| PASS | cohorts.cohort_id not empty | 0 violating rows |
| PASS | cohorts.course_id not empty | 0 violating rows |
| PASS | cohorts.cohort_label not empty | 0 violating rows |
| PASS | cohorts.start_date not empty | 0 violating rows |
| PASS | cohorts.end_date not empty | 0 violating rows |
| PASS | cohorts.access_end_date not empty | 0 violating rows |
| PASS | cohorts.capacity not empty | 0 violating rows |
| PASS | cohorts.status not empty | 0 violating rows |
| PASS | enrollments.enrollment_id not empty | 0 violating rows |
| PASS | enrollments.learner_id not empty | 0 violating rows |
| PASS | enrollments.course_id not empty | 0 violating rows |
| PASS | enrollments.cohort_id not empty | 0 violating rows |
| PASS | enrollments.rule_id not empty | 0 violating rows |
| PASS | enrollments.enrolled_at not empty | 0 violating rows |
| PASS | enrollments.current_status not empty | 0 violating rows |
| PASS | enrollments.status_updated_at not empty | 0 violating rows |
| PASS | enrollment_status_history.history_id not empty | 0 violating rows |
| PASS | enrollment_status_history.enrollment_id not empty | 0 violating rows |
| PASS | enrollment_status_history.status not empty | 0 violating rows |
| PASS | enrollment_status_history.effective_from not empty | 0 violating rows |
| PASS | enrollment_status_history.change_source not empty | 0 violating rows |
| PASS | attempts.attempt_id not empty | 0 violating rows |
| PASS | attempts.enrollment_id not empty | 0 violating rows |
| PASS | attempts.assessment_id not empty | 0 violating rows |
| PASS | attempts.attempt_no not empty | 0 violating rows |
| PASS | attempts.started_at_utc not empty | 0 violating rows |
| PASS | attempts.status not empty | 0 violating rows |
| PASS | course_outcomes.outcome_id not empty | 0 violating rows |
| PASS | course_outcomes.enrollment_id not empty | 0 violating rows |
| PASS | course_outcomes.rule_id not empty | 0 violating rows |
| PASS | course_outcomes.required_content_total not empty | 0 violating rows |
| PASS | course_outcomes.required_content_completed not empty | 0 violating rows |
| PASS | course_outcomes.content_completion_pct not empty | 0 violating rows |
| PASS | course_outcomes.required_assessments_total not empty | 0 violating rows |
| PASS | course_outcomes.required_assessments_passed not empty | 0 violating rows |
| PASS | course_outcomes.final_score not empty | 0 violating rows |
| PASS | course_outcomes.outcome_status not empty | 0 violating rows |
| PASS | course_outcomes.completion_conflict not empty | 0 violating rows |
| PASS | course_outcomes.evaluated_as_of_utc not empty | 0 violating rows |
| PASS | abandoned attempts have no submit/score/passed | 0 violating rows |
| PASS | submitted attempts have submit/score/passed | 0 violating rows |
| PASS | activity_events.event_id not empty | 0 violating rows |
| PASS | activity_events.enrollment_id not empty | 0 violating rows |
| PASS | activity_events.learner_id not empty | 0 violating rows |
| PASS | activity_events.course_id not empty | 0 violating rows |
| PASS | activity_events.content_id not empty | 0 violating rows |
| PASS | activity_events.event_type not empty | 0 violating rows |
| PASS | activity_events.event_time_utc not empty | 0 violating rows |
| PASS | activity_events.ingested_at_utc not empty | 0 violating rows |
| PASS | activity_events.platform not empty | 0 violating rows |
| PASS | activity_events.client_event_id not empty | 0 violating rows |

## format (79/79 pass)

| status | check | detail |
|---|---|---|
| PASS | learners.learner_id id format | 0 violating rows |
| PASS | learners.signup_date is date | 0 violating rows |
| PASS | learners.utc_offset_minutes is integer | 0 violating rows |
| PASS | courses.course_id id format | 0 violating rows |
| PASS | courses.duration_weeks is integer | 0 violating rows |
| PASS | courses.published_date is date | 0 violating rows |
| PASS | courses.retired_date is date | 0 violating rows |
| PASS | courses.n_modules is integer | 0 violating rows |
| PASS | courses.n_items is integer | 0 violating rows |
| PASS | courses.total_est_minutes is integer | 0 violating rows |
| PASS | content_items.content_id id format | 0 violating rows |
| PASS | content_items.course_id id format | 0 violating rows |
| PASS | content_items.parent_content_id id format | 0 violating rows |
| PASS | content_items.sequence_no is integer | 0 violating rows |
| PASS | content_items.depth is integer | 0 violating rows |
| PASS | content_items.week_number is integer | 0 violating rows |
| PASS | content_items.is_required is boolean | 0 violating rows |
| PASS | content_items.est_minutes is integer | 0 violating rows |
| PASS | assessments.assessment_id id format | 0 violating rows |
| PASS | assessments.content_id id format | 0 violating rows |
| PASS | assessments.course_id id format | 0 violating rows |
| PASS | assessments.max_score is integer | 0 violating rows |
| PASS | assessments.passing_score is integer | 0 violating rows |
| PASS | assessments.max_attempts is integer | 0 violating rows |
| PASS | assessments.is_required is boolean | 0 violating rows |
| PASS | assessments.weight_pct is decimal | 0 violating rows |
| PASS | assessments.difficulty_rating is integer | 0 violating rows |
| PASS | completion_rules.rule_id id format | 0 violating rows |
| PASS | completion_rules.course_id id format | 0 violating rows |
| PASS | completion_rules.rule_version is integer | 0 violating rows |
| PASS | completion_rules.effective_from is date | 0 violating rows |
| PASS | completion_rules.effective_to is date | 0 violating rows |
| PASS | completion_rules.min_required_content_pct is integer | 0 violating rows |
| PASS | completion_rules.completion_window_days is integer | 0 violating rows |
| PASS | cohorts.cohort_id id format | 0 violating rows |
| PASS | cohorts.course_id id format | 0 violating rows |
| PASS | cohorts.start_date is date | 0 violating rows |
| PASS | cohorts.end_date is date | 0 violating rows |
| PASS | cohorts.access_end_date is date | 0 violating rows |
| PASS | cohorts.capacity is integer | 0 violating rows |
| PASS | enrollments.enrollment_id id format | 0 violating rows |
| PASS | enrollments.learner_id id format | 0 violating rows |
| PASS | enrollments.course_id id format | 0 violating rows |
| PASS | enrollments.cohort_id id format | 0 violating rows |
| PASS | enrollments.rule_id id format | 0 violating rows |
| PASS | enrollments.enrolled_at is timestamp | 0 violating rows |
| PASS | enrollments.status_updated_at is timestamp | 0 violating rows |
| PASS | enrollment_status_history.history_id id format | 0 violating rows |
| PASS | enrollment_status_history.enrollment_id id format | 0 violating rows |
| PASS | enrollment_status_history.effective_from is timestamp | 0 violating rows |
| PASS | attempts.attempt_id id format | 0 violating rows |
| PASS | attempts.enrollment_id id format | 0 violating rows |
| PASS | attempts.assessment_id id format | 0 violating rows |
| PASS | attempts.attempt_no is integer | 0 violating rows |
| PASS | attempts.started_at_utc is timestamp | 0 violating rows |
| PASS | attempts.submitted_at_utc is timestamp | 0 violating rows |
| PASS | attempts.score is decimal | 0 violating rows |
| PASS | attempts.passed is boolean | 0 violating rows |
| PASS | attempts.duration_minutes is decimal | 0 violating rows |
| PASS | course_outcomes.outcome_id id format | 0 violating rows |
| PASS | course_outcomes.enrollment_id id format | 0 violating rows |
| PASS | course_outcomes.rule_id id format | 0 violating rows |
| PASS | course_outcomes.required_content_total is integer | 0 violating rows |
| PASS | course_outcomes.required_content_completed is integer | 0 violating rows |
| PASS | course_outcomes.content_completion_pct is decimal | 0 violating rows |
| PASS | course_outcomes.required_assessments_total is integer | 0 violating rows |
| PASS | course_outcomes.required_assessments_passed is integer | 0 violating rows |
| PASS | course_outcomes.final_score is decimal | 0 violating rows |
| PASS | course_outcomes.rule_met_at_utc is timestamp | 0 violating rows |
| PASS | course_outcomes.completed_date is date | 0 violating rows |
| PASS | course_outcomes.platform_completed_at_utc is timestamp | 0 violating rows |
| PASS | course_outcomes.completion_conflict is boolean | 0 violating rows |
| PASS | course_outcomes.evaluated_as_of_utc is timestamp | 0 violating rows |
| PASS | activity_events.event_id format | 0 violating rows |
| PASS | activity_events.enrollment_id format | 0 violating rows |
| PASS | activity_events.learner_id format | 0 violating rows |
| PASS | activity_events.course_id format | 0 violating rows |
| PASS | activity_events.content_id format | 0 violating rows |
| PASS | activity_events.client_event_id format | 0 violating rows |

## enum (20/20 pass)

| status | check | detail |
|---|---|---|
| PASS | learners.country_code in allowed values | 0 violating rows |
| PASS | learners.timezone in allowed values | 0 violating rows |
| PASS | learners.primary_device in allowed values | 0 violating rows |
| PASS | learners.acquisition_channel in allowed values | 0 violating rows |
| PASS | courses.category in allowed values | 0 violating rows |
| PASS | courses.level in allowed values | 0 violating rows |
| PASS | courses.delivery_mode in allowed values | 0 violating rows |
| PASS | courses.status in allowed values | 0 violating rows |
| PASS | content_items.content_type in allowed values | 0 violating rows |
| PASS | assessments.assessment_type in allowed values | 0 violating rows |
| PASS | completion_rules.assessment_policy in allowed values | 0 violating rows |
| PASS | cohorts.status in allowed values | 0 violating rows |
| PASS | enrollments.current_status in allowed values | 0 violating rows |
| PASS | enrollment_status_history.status in allowed values | 0 violating rows |
| PASS | enrollment_status_history.previous_status in allowed values | 0 violating rows |
| PASS | enrollment_status_history.change_source in allowed values | 0 violating rows |
| PASS | attempts.status in allowed values | 0 violating rows |
| PASS | course_outcomes.outcome_status in allowed values | 0 violating rows |
| PASS | activity_events.event_type in allowed values | 0 violating rows |
| PASS | activity_events.platform in allowed values | 0 violating rows |

## keys (21/21 pass)

| status | check | detail |
|---|---|---|
| PASS | learners.learner_id primary key unique | 1000 rows |
| PASS | courses.course_id primary key unique | 40 rows |
| PASS | content_items.content_id primary key unique | 749 rows |
| PASS | assessments.assessment_id primary key unique | 234 rows |
| PASS | assessments.content_id unique |  |
| PASS | completion_rules.rule_id primary key unique | 80 rows |
| PASS | cohorts.cohort_id primary key unique | 223 rows |
| PASS | enrollments.enrollment_id primary key unique | 5000 rows |
| PASS | enrollment_status_history.history_id primary key unique | 11525 rows |
| PASS | attempts.attempt_id primary key unique | 14612 rows |
| PASS | course_outcomes.outcome_id primary key unique | 5000 rows |
| PASS | course_outcomes.enrollment_id unique |  |
| PASS | enrollment_id = ENR-<learner_id>-<course_id> |  |
| PASS | one enrollment per (learner, course) |  |
| PASS | history_id = ESH-<enrollment_id>-<seq> | 0 violating rows |
| PASS | attempt_id = ATT-<enrollment>-<assessment seq>-<attempt_no> | 0 violating rows |
| PASS | outcome_id = OUT-<enrollment_id>; one outcome per enrollment | 0 violating rows |
| PASS | activity_events.event_id primary key unique |  |
| PASS | event.enrollment_id = ENR-<learner_id>-<course_id> |  |
| PASS | event_id = EVT-<enrollment_id>-<seq> |  |
| PASS | event_id counter is 1..n per enrollment in ingestion order | 0 violating rows |

## foreign_keys (21/21 pass)

| status | check | detail |
|---|---|---|
| PASS | content_items.course_id -> courses.course_id | 0 violating rows |
| PASS | content_items.parent_content_id -> content_items.content_id | 0 violating rows |
| PASS | assessments.content_id -> content_items.content_id | 0 violating rows |
| PASS | assessments.course_id -> courses.course_id | 0 violating rows |
| PASS | completion_rules.course_id -> courses.course_id | 0 violating rows |
| PASS | cohorts.course_id -> courses.course_id | 0 violating rows |
| PASS | enrollments.learner_id -> learners.learner_id | 0 violating rows |
| PASS | enrollments.course_id -> courses.course_id | 0 violating rows |
| PASS | enrollments.cohort_id -> cohorts.cohort_id | 0 violating rows |
| PASS | enrollments.rule_id -> completion_rules.rule_id | 0 violating rows |
| PASS | enrollment_status_history.enrollment_id -> enrollments.enrollment_id | 0 violating rows |
| PASS | attempts.enrollment_id -> enrollments.enrollment_id | 0 violating rows |
| PASS | attempts.assessment_id -> assessments.assessment_id | 0 violating rows |
| PASS | course_outcomes.enrollment_id -> enrollments.enrollment_id | 0 violating rows |
| PASS | course_outcomes.rule_id -> completion_rules.rule_id | 0 violating rows |
| PASS | enrollment.course = cohort.course | 0 violating rows |
| PASS | activity_events.learner_id -> learners | 0 violating rows |
| PASS | activity_events.course_id -> courses | 0 violating rows |
| PASS | activity_events.content_id -> content_items | 0 violating rows |
| PASS | activity_events.attempt_id -> attempts | 0 violating rows |
| PASS | event.content_id belongs to event.course_id | 0 violating rows |

## arithmetic (13/13 pass)

| status | check | detail |
|---|---|---|
| PASS | courses.n_modules = module rows | 0 violating rows |
| PASS | courses.n_items = leaf rows | 0 violating rows |
| PASS | courses.total_est_minutes = sum leaf minutes | 0 violating rows |
| PASS | module est_minutes = sum of its items | 0 violating rows |
| PASS | module is_required = any item required | 0 violating rows |
| PASS | required assessment weights sum to 100 per course | 0 violating rows |
| PASS | non-required assessment weight = 0 | 0 violating rows |
| PASS | score within 0..max_score | 0 violating rows |
| PASS | passed = (score >= passing_score) | 0 violating rows |
| PASS | duration_minutes = (submitted-started)/60 | 0 violating rows |
| PASS | content_completion_pct = completed/total*100 | 0 violating rows |
| PASS | final_score = sum(weight * best score)/100 | 0 violating rows |
| PASS | completed_date = UTC date of rule_met_at | 0 violating rows |

## hierarchy (8/8 pass)

| status | check | detail |
|---|---|---|
| PASS | module rows: parent null, type=module; leaf rows: parent set | 0 violating rows |
| PASS | leaf item course = parent module course | 0 violating rows |
| PASS | sequence_no unique within (course, parent) |  |
| PASS | week_number within 1..duration_weeks | 0 violating rows |
| PASS | assessment content_type matches assessment_type | 0 violating rows |
| PASS | assessment.course_id = content course | 0 violating rows |
| PASS | assessment.is_required = content.is_required | 0 violating rows |
| PASS | every quiz/assignment/exam item has exactly one assessment | 234 items vs 234 assessments |

## rules (5/5 pass)

| status | check | detail |
|---|---|---|
| PASS | discussions are never required | 0 violating rows |
| PASS | passing_score <= max_score | 0 violating rows |
| PASS | instructor_code null iff self_paced | 0 violating rows |
| PASS | enrollment.rule_id is the version in force at cohort start | 0 violating rows |
| PASS | attempt_id present iff assessment_start/submit |  |

## dates (14/14 pass)

| status | check | detail |
|---|---|---|
| PASS | rule v1.effective_to + 1 day = v2.effective_from | 0 violating rows |
| PASS | rule v2 open-ended; one rule per version per course |  |
| PASS | cohort start is a Monday | 0 violating rows |
| PASS | cohort end = start + 7*weeks - 1 | 0 violating rows |
| PASS | cohort access_end = end + completion window | 0 violating rows |
| PASS | cohorts start after course published | 0 violating rows |
| PASS | no cohort starts within 14 days of retirement | 0 violating rows |
| PASS | learner.signup_date <= enrolled_at | 0 violating rows |
| PASS | enrolled_at before cohort access_end and as-of | 0 violating rows |
| PASS | no history row after as-of | 0 violating rows |
| PASS | later attempts start after the previous one ended |  |
| PASS | submitted_at >= started_at (submitted) | 0 violating rows |
| PASS | attempts start after enrollment | 0 violating rows |
| PASS | ingested_at <= as-of | 0 violating rows |

## lifecycle (14/14 pass)

| status | check | detail |
|---|---|---|
| PASS | cohort.status consistent with as-of date | 0 violating rows |
| PASS | retired iff retired_date <= as-of | 0 violating rows |
| PASS | history sorted by enrollment then time |  |
| PASS | previous_status = status of the prior row | 0 violating rows |
| PASS | every transition allowed by the state machine | 0 violating rows |
| PASS | first history row is 'enrolled' at enrolled_at |  |
| PASS | every enrollment has history |  |
| PASS | enrollment.current_status = last history status | 0 violating rows |
| PASS | enrollment.status_updated_at = last history time | 0 violating rows |
| PASS | attempt_no <= max_attempts | 0 violating rows |
| PASS | attempt numbers consecutive from 1 per (enrollment, assessment) |  |
| PASS | attempts exist only for enrollments with an 'active' history row |  |
| PASS | no activity after an enrollment was dropped | 0 violating rows |
| PASS | platform_completed_at = 'completed' history row | 0 violating rows |

## exceptions (1/1 pass)

| status | check | detail |
|---|---|---|
| INFO | duplicate deliveries (same client_event_id) | 1596 rows = 1.62% of events |
| PASS | duplicates repeat enrollment/content/event_type of their first delivery | 0 violating rows |
| INFO | events whose enrollment_id has no enrollment record | 271 rows |
| INFO | events earlier than enrolled_at | 116 rows |
| INFO | event_time_utc later than ingested_at_utc (impossible) | 344 rows |
| INFO | late arrivals (ingestion lag > 24 h) | 3521 rows; offline-sync + backfill, legitimate |
| INFO | events with missing device UTC offset | 225 rows |
| INFO | platform completion not backed by the rule (completion_conflict) | 166 enrollments |

## completion_rule (7/7 pass)

| status | check | detail |
|---|---|---|
| PASS | required_content_total matches catalogue | 0 violating rows |
| PASS | required_content_completed matches deduplicated events | 0 violating rows |
| PASS | required_assessments_total / passed match attempts | 0 violating rows |
| PASS | rule_met_at_utc = max(content threshold, last required pass) | 0 violating rows |
| PASS | outcome_status follows the rule (completed iff rule met) | 0 violating rows |
| PASS | completion_conflict flag recomputes | 0 violating rows |
| PASS | completed enrollments reached the rule within the access window | 0 violating rows |

## separation (1/1 pass)

| status | check | detail |
|---|---|---|
| PASS | no ground-truth / label column in any input table |  |

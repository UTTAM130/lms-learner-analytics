# Detector evaluation vs ground truth

Detectors read only the input tables; `ground_truth/` is used here, for scoring, and nowhere else.

| issue type | labelled | flagged | TP | FP | FN | precision | recall | F1 |
|---|---|---|---|---|---|---|---|---|
| duplicate_event | 1596 | 1596 | 1596 | 0 | 0 | 1.0 | 1.0 | 1.0 |
| activity_unenrolled | 387 | 387 | 387 | 0 | 0 | 1.0 | 1.0 | 1.0 |
| timezone_shift | 387 | 351 | 351 | 0 | 36 | 1.0 | 0.907 | 0.9512 |
| completion_before_required_assessment | 166 | 166 | 166 | 0 | 0 | 1.0 | 1.0 | 1.0 |

Detail:

- **activity_unenrolled**: {"by_subtype": {"before_enrollment": 1.0, "never_enrolled": 1.0}}
- **timezone_shift**: {"recall_offset_missing": 0.9067, "recall_offset_present": 0.9074, "recall_online_platforms": 1.0, "recall_offline_sync_platform": 0.0, "labelled_on_offline_sync": 36, "corrected_date_matches_truth": 1.0}
- **completion_before_required_assessment**: {"by_subtype": {"required_assessment_not_passed": {"labelled": 95, "recall": 1.0}, "required_assessment_passed_later": {"labelled": 71, "recall": 1.0}}}

Ground-truth integrity: {"event_labels_found_in_events": true, "enrollment_labels_found_in_enrollments": true, "ground_truth_id_unique": true, "labelled_records_unique": true}

Impact on headline numbers: {"events_delivered": 98702, "duplicate_rows": 1596, "duplicate_share": 0.01617, "orphan_or_pre_enrollment_events": 387, "events_valid_for_metrics": 96719, "premature_completions_in_platform_marks": 166, "completions_by_platform_mark": 830, "completions_by_rule": 735, "completion_rate_overstatement_pct": 12.925}

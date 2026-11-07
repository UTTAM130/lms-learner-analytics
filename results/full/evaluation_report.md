# Detector evaluation vs ground truth

Detectors read only the input tables; `ground_truth/` is used here, for scoring, and nowhere else.

| issue type | labelled | flagged | TP | FP | FN | precision | recall | F1 |
|---|---|---|---|---|---|---|---|---|
| duplicate_event | 32082 | 32082 | 32082 | 0 | 0 | 1.0 | 1.0 | 1.0 |
| activity_unenrolled | 7794 | 7794 | 7794 | 0 | 0 | 1.0 | 1.0 | 1.0 |
| timezone_shift | 7800 | 6881 | 6881 | 0 | 919 | 1.0 | 0.8822 | 0.9374 |
| completion_before_required_assessment | 3453 | 3453 | 3453 | 0 | 0 | 1.0 | 1.0 | 1.0 |

Detail:

- **activity_unenrolled**: {"by_subtype": {"before_enrollment": 1.0, "never_enrolled": 1.0}}
- **timezone_shift**: {"recall_offset_missing": 0.8812, "recall_offset_present": 0.8837, "recall_online_platforms": 0.997, "recall_offline_sync_platform": 0.0, "labelled_on_offline_sync": 898, "corrected_date_matches_truth": 1.0}
- **completion_before_required_assessment**: {"by_subtype": {"required_assessment_not_passed": {"labelled": 2027, "recall": 1.0}, "required_assessment_passed_later": {"labelled": 1426, "recall": 1.0}}}

Ground-truth integrity: {"event_labels_found_in_events": true, "enrollment_labels_found_in_enrollments": true, "ground_truth_id_unique": true, "labelled_records_unique": true}

Impact on headline numbers: {"events_delivered": 1989562, "duplicate_rows": 32082, "duplicate_share": 0.01613, "orphan_or_pre_enrollment_events": 7794, "events_valid_for_metrics": 1949686, "premature_completions_in_platform_marks": 3453, "completions_by_platform_mark": 16778, "completions_by_rule": 14751, "completion_rate_overstatement_pct": 13.741}

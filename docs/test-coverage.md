# Automated test coverage

Recorded 2026-11-08 15:13:40 Asia/Shanghai, implementation base d4fe894.
No product implementation changed in this test-only milestone.

Command: `MYSQL_DATABASE=certificate_admin_test .venv/bin/python -m unittest discover -s tests -v`.
Result: **22 passed, 0 failures, 0 errors, 0 skips**, 0.261 seconds.
Python 3.15.2, FastAPI 0.115.12, PyMySQL 1.1.1, MySQL 9.3.0.

| Behavior | Evidence |
| --- | --- |
| Health, demo actors, tenant-scoped courses | test_health_and_actor_choices; test_courses_are_tenant_scoped |
| Missing and unknown identity | test_missing_and_unknown_identity |
| Invalid pagination, sort, direction, search length | test_illegal_query_parameters |
| Missing/invalid course, forbidden payload fields, missing/empty/oversized keys | test_illegal_issue_payloads_and_keys |
| Search, pagination, local date display, every allowed sort field and stable tie-break | test_list_search_pagination_sort_and_dst; test_all_sort_fields_are_allowlisted_and_stable |
| Empty list and service failure | test_empty_list; test_database_failure_is_not_success |
| Detail and audit timestamps | test_detail_and_audit |
| Forced foreign detail/revoke/course IDs and no writes | test_forced_cross_tenant_detail_revoke_and_issue; test_forced_foreign_ids_leave_real_database_unchanged |
| Eligible, incomplete and duplicate outcomes; issuance commit/audit | test_bulk_mixed_outcomes_commit_and_audit |
| Same-key replay and changed nonexistent course 409 before lookup | test_same_key_replays_saved_result_without_writes; test_same_key_changed_missing_course_conflicts_before_lookup |
| First/repeated revocation | test_revocation_first_and_repeat |
| Filtered/sorted streaming CSV, bounded batch, CSV quoting, local date | test_export_uses_search_sort_local_date_and_csv_escaping |
| Sydney/Perth DST example | test_west_dst; test_list_search_pagination_sort_and_dst |
| Certificate inserted, then audit IntegrityError | test_audit_integrity_failure_rolls_back_just_failed_learner: same-transaction SQL proves certificate exists before injection; savepoint removes it; other learner succeeds |
| Second learner audit fails after first successful certificate/audit writes | test_second_audit_failure_rolls_back_entire_transaction: HTTP 500, zero certificates/audits/operation; same-key retry succeeds |
| Status changed to REVOKED, then audit fails | test_revocation_audit_failure_rolls_back_status: status inside transaction is REVOKED; separate post-failure read is ACTIVE with zero revocation audits |
| Controlled pre-commit concurrency | test_uncommitted_issuance_invisible_and_retry_waits_for_commit: pause first commit, separate connection observes no writes, second request reaches FOR UPDATE but cannot acquire lock; release barrier then identical results, two certificates/two audits/one operation |

The transaction tests are **integration tests with mock fault/timing hooks**, not a fake database.
The concurrency test uses Events to prove the first transaction is paused and the second is actually
attempting the lock, rather than starting requests and inferring ordering from their final state.
Waits have bounded 3/5-second deadlines and the first transaction is always released in a finally block.
The 150ms negative wait checks that the second lock cannot complete while the first is deliberately held.

Limitations: this suite does not claim exhaustive branch coverage or Vue component unit coverage.
The previous 100,000-row performance result remains in verification/acceptance.json; the new unit
suite does not replace performance measurement or previously recorded browser verification.
Fixtures are uniquely named and retained in the isolated database. Mocked API tenant tests also
assert SQL tenant parameters; real-MySQL foreign-ID tests verify isolation without dependency overrides.

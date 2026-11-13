# Graph Report - sintesis  (2026-11-13)

## Corpus Check
- 289 files · ~161,716 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 24 file(s) not represented in the graph (top: .csv 10, (none) 6, .css 3)

## Summary
- 2783 nodes · 9087 edges · 142 communities (116 shown, 26 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 1031 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c2805ac5`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_master_preparation.py
- sqlalchemy_orm
- sqlalchemy_engine
- pytest
- sqlalchemy
- pdpj/router.py
- master/router.py
- test_correction_map.py
- spatial/router.py
- config.py
- react
- UploadBatch
- upgrade_foundations
- extract_standard_fields
- CorrectionKind
- master.ts
- results.py
- ReconciliationProcess
- PdpjReview
- test_master_catalog.py
- re
- test_authentication.py
- corrections.ts
- activity_lock
- EvidenceLookup
- Pdpj.tsx
- e2e/conftest.py
- SourceRecord
- pages/CorrectionMap.tsx
- test_pdpj_validation.py
- archive.py
- test_pdpj_browser.py
- auth/router.py
- test_master_browser.py
- MatchingRun
- MatchingRun
- Master.tsx
- package.json
- test_corrections.py
- application.py
- PLN GeoMatch
- advance
- schemas/user.py
- leaflet.js
- CorrectionResults.tsx
- test_processing_progress_browser.py
- frontend/package.json
- reader.py
- components.json
- compilerOptions
- startup_schema.py
- seed_test.py
- get_preparation
- dependencies
- test_upload_files.py
- ref_lucide_react
- SearchWriter
- test_upload_file_deletion.py
- test_correction_results.py
- compilerOptions
- security.py
- test_sqlite_concurrency.py
- httpx
- MatchCandidate
- PRD-sintesis.md
- re
- openpyxl
- read_progress
- test_upload_pause.py
- analisis-alur-rekonsiliasi.md
- F
- test_authentication_browser.py
- Analisis waktu proses
- e
- test_manual_corrections_browser.py
- test_upload_progress_browser.py
- 15. Roadmap Implementasi
- preview_file
- Data Koreksi — tahap 3
- Validasi dan pelengkapan PDPJ — tahap 2
- types.ts
- p
- benchmark_processing.py
- test_source_preview_paging.py
- test_upload_header_row.py
- master_snapshot_id
- TestCalculateDistance
- Analisis perubahan alur PLN GeoMatch
- Antarmuka ruang kerja PLN GeoMatch
- 7. Flow Sistem End-to-End
- upload/router.py
- spatial_tasks.py
- .oxlintrc.json
- scripts
- Jt
- test_map_radius_summary.py
- 8. Kebutuhan Fungsional
- 4. Alur yang diusulkan
- Tahap 4: Peta Koreksi
- supabase.ts
- vite.config.ts
- d
- Settings
- test_refresh_activity_browser.py
- Browser Automation — agent-browser
- Data Master — tahap 1
- Hasil Koreksi dan Riwayat Proses
- Pencarian koreksi dari seluruh observasi koordinat
- i
- 11. Arsitektur Teknis yang Direkomendasikan
- get_candidates
- test_reset_hides_unexpected_database_error_and_rolls_back
- Riwayat file dan impor sheet
- bi
- oi
- React + TypeScript + Vite
- test_partial_map_choice_survives_more_saved_rows_and_completion
- 12. Spesifikasi UI/UX Neo-Brutalism
- 2. Masalah, Tujuan, dan Ukuran Keberhasilan
- 9. Status, Siklus Hidup Proses, dan Perhitungan Statistik
- test_processing_performance.py
- test_search_index.py
- tsconfig.json
- 14. Acceptance Criteria dan Strategi Pengujian
- 3. Pengguna dan Hak Akses
- 5. Scope Produk
- CLAUDE.md
- leaflet-1.9.4/README.md
- radius_summary
- concurrent_client
- test_master_totals_load_before_details_and_survive_refresh
- koordinat-xy.md

## God Nodes (most connected - your core abstractions)
1. `SourceRecord` - 182 edges
2. `UploadBatch` - 165 edges
3. `ReconciliationProcess` - 91 edges
4. `DatasetType` - 88 edges
5. `MatchingRun` - 76 edges
6. `PdpjReview` - 73 edges
7. `Base` - 72 edges
8. `MatchCandidate` - 72 edges
9. `PdpjRow` - 70 edges
10. `BatchStatus` - 68 edges

## Surprising Connections (you probably didn't know these)
- `Optimasi yang diterapkan pada 27 Oktober 2026` --references--> `create_review()`  [INFERRED]
  docs/analisis-performa.md → backend/app/modules/pdpj/service.py
- `Riwayat file dan impor sheet` --references--> `UploadBatch`  [INFERRED]
  docs/riwayat-file-sheet.md → backend/app/models/upload.py
- `Riwayat file dan impor sheet` --references--> `SourceRecord`  [INFERRED]
  docs/riwayat-file-sheet.md → backend/app/models/upload.py
- `Renderer dan verifikasi` --references--> `MapProvider`  [INFERRED]
  docs/peta-koreksi.md → frontend/src/lib/correction-map.ts
- `API yang terkait` --references--> `master_snapshot_id()`  [INFERRED]
  docs/fondasi-data.md → backend/tests/conftest.py

## Import Cycles
- None detected.

## Communities (142 total, 26 thin omitted)

### Community 0 - "test_master_preparation.py"
Cohesion: 0.22
Nodes (15): upgrade(), upgrade_master_preparation(), MasterPreparation, MasterPreparationIdentity, advance(), approved_review(), finish_preparation(), start() (+7 more)

### Community 1 - "sqlalchemy_orm"
Cohesion: 0.07
Nodes (13): add_keys(), build_index(), chunk_context(), clear_pdpj_indexes(), CompactIndex, ConflictContext, get_index(), timed() (+5 more)

### Community 2 - "sqlalchemy_engine"
Cohesion: 0.06
Nodes (13): upgrade(), upgrade(), upgrade(), downgrade(), upgrade(), upgrade(), upgrade(), upgrade_correction_progress() (+5 more)

### Community 3 - "pytest"
Cohesion: 0.07
Nodes (16): test_all_observations_source_and_coordinate_warning_survive_refresh(), test_partial_results_export_history_resume_replace_and_cancel(), launch(), prepare(), test_mobile_empty_idpel_import_pagination_summary_and_candidate_pages(), test_not_found_import_conflicts_candidates_missing_coordinates_and_category_isolation(), test_radius_retry_preserves_previous_candidate_generation(), upload() (+8 more)

### Community 4 - "sqlalchemy"
Cohesion: 0.08
Nodes (12): run_migrations_offline(), run_migrations_online(), upgrade(), Base, ensure_schema_compatibility(), utc_now(), PdpjRecommendation, UploadFileArchive (+4 more)

### Community 5 - "pdpj/router.py"
Cohesion: 0.05
Nodes (46): pdpj_coordinates_missing(), pdpj_issue_count(), batch_info(), advance_processing(), apply_recommendation(), ApplyRecommendation, batch_preview(), CompleteWithExceptions (+38 more)

### Community 6 - "master/router.py"
Cohesion: 0.08
Nodes (19): source_coordinates_missing(), catalogue_query(), delete_master_batch(), get_master_batch(), get_master_record(), get_master_summary(), incomplete_location(), list_master_batches() (+11 more)

### Community 7 - "test_correction_map.py"
Cohesion: 0.22
Nodes (11): body(), details(), mapped(), test_choice_schema_upgrade_is_additive_idempotent(), test_choice_survives_expansion_historical_versions_read_only(), test_choices_are_scoped_and_legacy_writes_cannot_bypass_audit(), test_map_radius_reuses_snapshot_and_never_reads_master(), test_one_choice_replace_clear_audit_and_idempotency() (+3 more)

### Community 8 - "spatial/router.py"
Cohesion: 0.13
Nodes (17): build_master_endpoint(), BuildMasterRequest, BulkDecisionRequest, DecisionRequest, dispatch_matching(), ensure_current_candidate(), finalize_review(), list_master_snapshots() (+9 more)

### Community 9 - "config.py"
Cohesion: 0.12
Nodes (4): AuthUser, get_current_user(), get_supabase_jwks(), require_roles()

### Community 10 - "react"
Cohesion: 0.09
Nodes (38): App(), Navbar(), PasswordDialog(), RequireAuth(), Shell(), Item, menu, NavigationItem() (+30 more)

### Community 11 - "UploadBatch"
Cohesion: 0.07
Nodes (30): downgrade(), upgrade(), upgrade_master_catalog(), CleanedMasterRecord, MasterSisaRecord, BatchStatus, SourceRecord, UploadBatch (+22 more)

### Community 12 - "upgrade_foundations"
Cohesion: 0.12
Nodes (9): downgrade(), upgrade(), upgrade(), upgrade_foundations(), validate_sqlite_foreign_keys(), test_existing_matching_runs_gain_nullable_failure_code_without_losing_history(), test_migration_preserves_legacy_decisions_and_is_idempotent(), test_startup_upgrade_accepts_fresh_metadata_with_foreign_keys() (+1 more)

### Community 13 - "extract_standard_fields"
Cohesion: 0.08
Nodes (23): upgrade(), repair_xy_coordinates(), CoordinateRepair, _canonical_items(), canonical_mapping(), clean_text(), _column_plan(), coordinate_source_columns() (+15 more)

### Community 14 - "CorrectionKind"
Cohesion: 0.08
Nodes (32): advance_check(), batch_preview(), cached_preview_fields(), check_info(), dispatch(), get_check(), get_pdpj_update(), list_batches() (+24 more)

### Community 15 - "master.ts"
Cohesion: 0.08
Nodes (42): papaparse@^5.7.0, count(), duration(), ImportProgress(), labels, ImportPreview, MasterImport(), readError() (+34 more)

### Community 16 - "results.py"
Cohesion: 0.08
Nodes (31): CorrectionDecision, choice_history(), ChoiceRequest, choose_candidate(), decision_info(), get_choice(), target_scope(), coordinate_sources() (+23 more)

### Community 17 - "ReconciliationProcess"
Cohesion: 0.09
Nodes (39): ReconciliationProcess, DatasetType, calculate_haversine_distance(), create_matching_run(), lock_matching_session(), matching_run_summary(), run_spatial_matching_job(), validate_target_batch() (+31 more)

### Community 18 - "PdpjReview"
Cohesion: 0.06
Nodes (30): PdpjReview, PdpjRow, CandidateLocation, run_correction_matching(), pdpj_update_info(), reserved_keys(), include(), reference_tokens() (+22 more)

### Community 19 - "test_master_catalog.py"
Cohesion: 0.08
Nodes (27): upgrade(), upgrade(), upgrade_master_filters(), upgrade_master_summary(), MasterSummaryCache, import_master(), test_actual_dil_headers_keep_codes_meters_and_blank_columns_separate(), test_catalogue_cannot_mix_master_types_or_target_batches() (+19 more)

### Community 20 - "re"
Cohesion: 0.11
Nodes (14): setup_map(), test_choose_replace_radius_expansion_history_and_category_isolation(), test_clear_target_keeps_saved_decision_filters_and_table_page(), test_map_all_points_hover_selection_and_candidate_pagination(), test_map_highlights_selected_target_and_links_candidate_to_later_card_page(), test_map_preview_page_input_sizes_filters_and_mobile(), test_map_unavailable_keeps_mobile_table_and_choice_flow(), test_select_target_loads_candidates_automatically_and_preserves_read_only_flow() (+6 more)

### Community 21 - "test_authentication.py"
Cohesion: 0.13
Nodes (29): upgrade(), upgrade_auth(), AuthAudit, AuthGuard, AuthSession, AuthThrottle, utcnow(), User (+21 more)

### Community 22 - "corrections.ts"
Cohesion: 0.10
Nodes (33): usePdpjUpdate(), CheckRequest, ChoiceRequest, conflictLabel, correctionApi, CorrectionCheck, CorrectionChoice, CorrectionDetail (+25 more)

### Community 23 - "activity_lock"
Cohesion: 0.14
Nodes (10): activity_lock(), database_engine(), file_lock(), lock_path(), monitored(), request_activity(), utc_now(), test_activity_is_not_inferred_from_saved_state_and_releases_after_exception() (+2 more)

### Community 25 - "Pdpj.tsx"
Cohesion: 0.14
Nodes (29): CorrectionProgress(), count(), revision(), CompleteWithExceptionsDialog(), count(), duration(), PdpjProgress(), revision() (+21 more)

### Community 26 - "e2e/conftest.py"
Cohesion: 0.16
Nodes (7): authenticated_api(), wrap(), browser(), free_port(), page(), servers(), wait_server()

### Community 27 - "SourceRecord"
Cohesion: 0.16
Nodes (15): post_csv(), test_chunked_upload_and_mapping_preserve_all_rows(), insert(), test_csv_detects_windows_encoding_beyond_delimiter_sample(), test_csv_encoding_preserves_special_characters_and_identifiers(), test_csv_with_corrupt_bom_encoding_does_not_silently_replace_characters(), test_excel_incorrect_dimensions_preview_and_import_actual_cells(), test_excel_skips_leading_empty_rows_and_preserves_source_numbers() (+7 more)

### Community 28 - "pages/CorrectionMap.tsx"
Cohesion: 0.12
Nodes (25): CandidateCoordinateSource(), CorrectionMap(), count(), PreviewPagination(), PreviewPaginationProps, SearchFeedback(), useDebouncedSearch(), useMapRadiusSummary() (+17 more)

### Community 29 - "test_pdpj_validation.py"
Cohesion: 0.05
Nodes (52): upgrade(), PdpjChange, upgrade_pdpj_results(), pending(), request_body(), test_bulk_commit_failure_rolls_back_exceptions_audit_and_completion(), test_bulk_completion_preserves_issues_sources_old_exceptions_and_audit(), test_bulk_completion_requires_scope_confirmation_and_fresh_revision() (+44 more)

### Community 30 - "archive.py"
Cohesion: 0.11
Nodes (13): get_db(), archive_info(), get_archive(), import_sheet(), attach_import(), list_files(), preview_sheet(), selected_sheet() (+5 more)

### Community 31 - "test_pdpj_browser.py"
Cohesion: 0.14
Nodes (10): test_bulk_exceptions_enable_correction_map_and_preserve_reserved_identities(), test_duplicate_pdpj_identities_allow_normal_completion_with_different_coordinates_and_service(), test_mobile_pending_pdpj_mapping_and_manual_coordinates(), test_pdpj_import_recommendations_manual_exception_completion_and_matching(), test_pdpj_mapping_storage_error_can_retry_without_uploading_again(), test_replacing_filled_recommendation_requires_explicit_overwrite(), upload_source(), test_fast_progress_does_not_cancel_a_slow_table_request() (+2 more)

### Community 32 - "auth/router.py"
Cohesion: 0.20
Nodes (17): change_password(), clear_cookies(), create_user(), ensure_password(), list_users(), login(), logout(), me() (+9 more)

### Community 33 - "test_master_browser.py"
Cohesion: 0.24
Nodes (9): test_csv_encoding_matches_preview_and_saved_data(), test_csv_upload_mapping_details_and_category_isolation(), test_excel_bad_dimensions_preview_matches_import_and_empty_sheet_can_recover(), test_excel_empty_first_sheet_uses_data_sheet(), test_excel_empty_workbook_can_select_sheet_and_replace_file(), test_excel_header_after_empty_rows_is_previewed_and_imported(), test_excel_sheet_selection_preserves_source_details(), test_mobile_navigation_and_upload_separation() (+1 more)

### Community 34 - "MatchingRun"
Cohesion: 0.12
Nodes (15): CorrectionAttempt, utc_now(), MatchingRun, ReviewStatus, advance_progress(), control_progress(), initialize_progress(), locked_run() (+7 more)

### Community 35 - "MatchingRun"
Cohesion: 0.25
Nodes (10): ProcessStatus, counts(), finish(), histories(), test_active_history_blocks_clear_all_before_any_deletions(), test_active_request_lock_blocks_deletion_even_when_saved_status_is_complete(), test_clear_all_removes_correction_and_legacy_history_but_not_sources(), test_database_failure_rolls_back_every_deletion() (+2 more)

### Community 36 - "Master.tsx"
Cohesion: 0.17
Nodes (24): react-dom@^19.3.1, CorrectionDetail(), present(), InspectionDrawer(), DetailEditor(), empty(), historyLabel, HistorySources() (+16 more)

### Community 37 - "package.json"
Cohesion: 0.10
Nodes (27): dependencies, @designcodeio/threeui@^1.2.0, framer-motion@^14.7.1, gsap@^3.15.0, @lucasmarkes/hairline@^0.5.1, lucide-react@^1.59.0, motion@^14.7.1, @tabler/icons-react@^3.50.0 (+19 more)

### Community 38 - "test_corrections.py"
Cohesion: 0.24
Nodes (18): check(), reference(), test_candidate_details_use_saved_evidence_and_keep_zero_candidate_rows(), test_correction_worker_failure_is_final_until_explicit_retry(), test_empty_category_compares_typed_references_and_only_warns_on_same_coordinates(), test_idempotent_requests_rerun_history_stale_retry_and_late_failure(), test_migration_ready_pdpj_legacy_categories_and_reset(), test_not_found_category_checks_every_row_and_counts_rows_not_candidates() (+10 more)

### Community 40 - "PLN GeoMatch"
Cohesion: 0.07
Nodes (25): Pencarian data, Pengujian, Pengukuran lokal, Penyebab lambat, Persiapan data lama dan konsistensi, Perubahan, 1. Clone Repository, 2. Setup Backend (+17 more)

### Community 41 - "advance"
Cohesion: 0.13
Nodes (21): upgrade(), upgrade_correction_observations(), CorrectionMasterObservation, CorrectionObservationCatalog, scenario(), test_legacy_checkpoint_resumes_old_policy_and_explicit_retry_starts_from_zero(), test_new_observation_search_preserves_previously_approved_coordinate(), test_observation_preparation_checkpoints_resume_without_duplicate_rows() (+13 more)

### Community 42 - "schemas/user.py"
Cohesion: 0.39
Nodes (6): Token, TokenData, UserBase, UserCreate, UserResponse, Config

### Community 43 - "leaflet.js"
Cohesion: 0.09
Nodes (4): a(), Ci(), l(), x()

### Community 44 - "CorrectionResults.tsx"
Cohesion: 0.23
Nodes (17): CorrectionResults(), count(), DecisionHistory(), ResultDetail(), buttonClass, CorrectionDecision, Fields, DecisionEvent (+9 more)

### Community 45 - "test_processing_progress_browser.py"
Cohesion: 0.14
Nodes (9): test_master_progress_is_saved_and_ready_snapshot_can_be_reused(), sources(), test_connection_loss_keeps_checkpoint_and_reload_can_continue(), test_stop_reload_and_resume_from_saved_rows(), captured(), test_committed_correction_rows_refresh_while_next_chunk_is_running(), test_correction_progress_saves_pauses_and_resumes_after_reload(), test_final_validation_and_approval_saving_are_visible() (+1 more)

### Community 46 - "frontend/package.json"
Cohesion: 0.12
Nodes (23): devDependencies, autoprefixer@^10.6.1, oxlint@^1.88.0, postcss@^8.5.31, tailwindcss@^4.3.3, @types/node@^24.19.2, @types/papaparse@^5.5.2, @types/react@^19.3.0 (+15 more)

### Community 47 - "reader.py"
Cohesion: 0.27
Nodes (6): normalize_source_headers(), detect_csv_encoding(), read_upload(), csv_rows(), excel_rows(), validate_text_encoding()

### Community 48 - "components.json"
Cohesion: 0.09
Nodes (21): aliases, components, hooks, lib, ui, utils, iconLibrary, menuAccent (+13 more)

### Community 49 - "compilerOptions"
Cohesion: 0.10
Nodes (20): compilerOptions, allowArbitraryExtensions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection (+12 more)

### Community 50 - "startup_schema.py"
Cohesion: 0.09
Nodes (12): upgrade(), upgrade(), upgrade(), upgrade(), upgrade_correction_map(), SchemaState, upgrade_pdpj_summary(), apply_once() (+4 more)

### Community 51 - "seed_test.py"
Cohesion: 0.24
Nodes (8): ensure_dir(), generate_acmt(), generate_all_dummy(), generate_koordinat_kosong(), generate_lpb(), generate_pdpj_verif(), generate_target_lapangan(), offset_coord()

### Community 52 - "get_preparation"
Cohesion: 0.14
Nodes (12): MasterPreparationExcluded, MasterSnapshot, advance_observations(), observation_period(), advance_preparation(), cached_fields(), get_preparation(), materialize_chunk() (+4 more)

### Community 53 - "dependencies"
Cohesion: 0.10
Nodes (20): dependencies, axios@^1.20.0, leaflet.markercluster@^1.5.3, @lucasmarkes/hairline@^0.5.1, lucide-react@^1.59.0, motion@^14.7.1, react@^19.3.1, react-router-dom@^7.18.4 (+12 more)

### Community 55 - "test_upload_files.py"
Cohesion: 0.28
Nodes (13): archive_path(), archive(), confirm(), import_sheet(), test_failed_sheet_write_rolls_back_rows_but_retains_original_for_retry(), test_fingerprint_deduplicates_reuploads_but_not_changed_contents(), test_invalid_sheet_and_missing_original_leave_no_partial_reference(), test_invalid_uploads_are_not_archived() (+5 more)

### Community 56 - "ref_lucide_react"
Cohesion: 0.19
Nodes (14): MapRadiusSummary(), icons, MetricCard(), MetricTone, API_BASE_URL, CORRECTION_TYPES, count(), DashboardPage() (+6 more)

### Community 57 - "SearchWriter"
Cohesion: 0.14
Nodes (3): SearchWriter, candidate_observations(), test_inflight_status_is_readable_and_pause_prevents_duplicate_work()

### Community 58 - "test_upload_file_deletion.py"
Cohesion: 0.30
Nodes (12): admin_client(), confirm(), import_sheet(), test_delete_file_404(), test_delete_file_blocked_when_batch_used_in_pdpj(), test_delete_file_removes_archive_batches_and_records(), test_delete_file_without_imports(), test_delete_sheet_404_wrong_dataset_type() (+4 more)

### Community 59 - "test_correction_results.py"
Cohesion: 0.32
Nodes (11): advance(), choose(), partial(), sheet_rows(), test_latest_choice_is_scoped_to_its_process_even_for_the_same_source_row(), test_partial_choice_appears_in_results_history_and_xlsx_without_changing_source(), test_replacement_cancellation_filters_and_history_are_not_counted_as_extra_choices(), test_resume_and_new_search_preserve_choices_and_allow_historical_result_export() (+3 more)

### Community 60 - "compilerOptions"
Cohesion: 0.12
Nodes (16): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, noEmit, noFallthroughCasesInSwitch (+8 more)

### Community 61 - "security.py"
Cohesion: 0.09
Nodes (18): UserRole, main(), ChangePassword, CreateUser, LoginRequest, StrictRequest, UpdateUser, current_actor() (+10 more)

### Community 62 - "test_sqlite_concurrency.py"
Cohesion: 0.10
Nodes (12): database_busy_response(), register_database_error_handlers(), configure_connection(), configure_sqlite_engine(), sqlite_busy(), api_for(), test_busy_legacy_reader_returns_503_then_recovers_without_sql_leaks(), test_connections_keep_foreign_keys_and_full_durability_and_rollback() (+4 more)

### Community 63 - "httpx"
Cohesion: 0.27
Nodes (8): test_global_expansion_without_target_and_radius_specific_status_filters(), test_initial_check_updates_summary_without_showing_expansion_panel(), choose_original(), open_import(), test_preview_empty_sheet_recovery_and_checkmarks_follow_period(), test_same_file_history_can_be_reused_in_pdpj_without_master_checkmarks(), test_sheet_history_checks_survive_reload_and_other_sheet_uses_same_original(), workbook()

### Community 64 - "MatchCandidate"
Cohesion: 0.08
Nodes (15): downgrade(), upgrade(), upgrade_corrections(), CorrectionCandidateEvidence, CorrectionCheck, CorrectionTarget, MatchCandidate, delete_history() (+7 more)

### Community 65 - "PRD-sintesis.md"
Cohesion: 0.14
Nodes (13): 10. Rancangan Data Konseptual, 13. Kebutuhan Nonfungsional, 16. Risiko dan Mitigasi, 17. Keputusan yang Masih Harus Dikonfirmasi, 18. Definisi Selesai Produk (Definition of Done), 1. Ringkasan Produk, 4. Glosarium dan Definisi Data, 6. Aturan Bisnis (+5 more)

### Community 66 - "re"
Cohesion: 0.20
Nodes (6): test_switch_to_final_pdpj_while_old_correction_remains_paused(), test_admin_local_search_matches_real_usernames(), test_correction_search_filters_and_clears(), test_map_and_saved_result_search_keep_the_selected_scope(), test_master_search_debounces_prepares_and_preserves_pagination(), test_pdpj_search_includes_kwh_meter_and_clear()

### Community 68 - "read_progress"
Cohesion: 0.24
Nodes (7): create_progress(), get_progress(), pause_path(), pause_upload(), progress_path(), read_progress(), resume_upload()

### Community 69 - "test_upload_pause.py"
Cohesion: 0.13
Nodes (8): UploadProgress, decorate(), measured(), file_client(), test_failure_after_resume_can_retry_without_missing_or_duplicate_rows(), test_repeat_pause_resume_preserves_every_row_and_releases_database(), measured(), wait_paused()

### Community 71 - "F"
Cohesion: 0.24
Nodes (11): F(), G(), h(), j(), k(), ke(), me(), Oe() (+3 more)

### Community 72 - "test_authentication_browser.py"
Cohesion: 0.44
Nodes (7): login_ui(), sign_out(), test_admin_creates_real_account_and_nonadmin_cannot_manage_users(), test_blocking_account_revokes_browser_session(), test_default_login_no_registration_wrong_password_and_logout(), test_logout_clears_another_open_tab(), test_user_can_change_own_password_and_must_login_again()

### Community 73 - "Analisis waktu proses"
Cohesion: 0.20
Nodes (9): Analisis awal pada 26 Oktober 2026, Analisis waktu proses, Backend 502 saat startup, Optimasi yang diterapkan pada 27 Oktober 2026, Pembacaan daftar gagal ketika pemeriksaan menulis database, Pengukuran terisolasi, Reset ketika database terkunci, Temuan (+1 more)

### Community 74 - "e"
Cohesion: 0.27
Nodes (10): c(), e(), hi(), m(), q(), Qe(), ve(), xe() (+2 more)

### Community 75 - "test_manual_corrections_browser.py"
Cohesion: 0.29
Nodes (4): fill_point(), test_manual_coordinates_validated_before_saving_on_mobile(), test_manual_mapping_retry_reuses_saved_point(), test_manual_point_check_map_choice_and_export()

### Community 76 - "test_upload_progress_browser.py"
Cohesion: 0.24
Nodes (3): test_master_import_displays_measured_progress_and_waits_for_commit(), test_pause_and_resume_master_import_waits_for_server_acknowledgement(), test_preview_worker_can_pause_and_resume_without_losing_preview_rows()

### Community 77 - "15. Roadmap Implementasi"
Cohesion: 0.20
Nodes (10): 15. Roadmap Implementasi, Gate antarphase, Phase 0 — Validasi kebutuhan dan aturan bisnis, Phase 1 — Fondasi aplikasi dan model data, Phase 2 — Import dinamis, Phase 3 — Dataset preparation dan Master Sisa, Phase 4 — Mesin matching spasial, Phase 5 — Daftar Kandidat & Peta dan review (+2 more)

### Community 78 - "preview_file"
Cohesion: 0.25
Nodes (4): check_file_size(), preview_file(), upload_file(), test_real_500_mb_file_size_boundary()

### Community 79 - "Data Koreksi — tahap 3"
Cohesion: 0.22
Nodes (9): API, Data Koreksi — tahap 3, Master dan kandidat, Pemeriksaan benturan dan kategori, Penggunaan, Penyimpanan dan kompatibilitas, Progres dan penyimpanan bertahap, Status dan ringkasan (+1 more)

### Community 80 - "Validasi dan pelengkapan PDPJ — tahap 2"
Cohesion: 0.22
Nodes (9): Alur penggunaan, Aturan pemeriksaan, Hubungan dengan proses koreksi, Menyelesaikan validasi data tersimpan sambil melanjutkan PDPJ, Pengujian, Penyimpanan dan API, Progres, penghentian, dan kelanjutan pemeriksaan otomatis, Validasi dan pelengkapan PDPJ — tahap 2 (+1 more)

### Community 81 - "types.ts"
Cohesion: 0.28
Nodes (5): GithubIcon, AnimatedIconHandle, AnimatedIconProps, DEFAULT_STROKE_WIDTH, IconEasing

### Community 82 - "p"
Cohesion: 0.22
Nodes (9): Ae(), be(), De(), ei(), Ie(), ii(), p(), pe() (+1 more)

### Community 83 - "benchmark_processing.py"
Cohesion: 0.22
Nodes (3): run_tests(), main(), revision_module()

### Community 84 - "test_source_preview_paging.py"
Cohesion: 0.35
Nodes (5): test_correction_preview_keeps_invalid_coordinate_errors(), test_legacy_and_invalid_pages_load_original_cells_in_one_bounded_query(), test_legacy_missing_batch_count_uses_database_count(), test_source_preview_pages_cross_files_preserve_scope_and_use_covering_indexes(), capture()

### Community 85 - "test_upload_header_row.py"
Cohesion: 0.33
Nodes (6): header_row_index(), test_early_title_row_within_the_scan_window(), test_header_row_index_prefers_the_row_naming_several_columns(), test_sheet_without_any_named_cell_is_rejected(), test_title_rows_above_the_header_are_skipped(), workbook()

### Community 86 - "master_snapshot_id"
Cohesion: 0.29
Nodes (6): master_snapshot_id(), API yang terkait, Database lama, Perbaikan fondasi data, Perilaku data, Verifikasi

### Community 88 - "Analisis perubahan alur PLN GeoMatch"
Cohesion: 0.25
Nodes (8): 1. Pemahaman kebutuhan, 2. Kondisi proyek saat ini, 3. Selisih terhadap kebutuhan, 5. Perbaikan fondasi yang diperlukan, 6. Urutan implementasi, 7. Skenario penerimaan utama, 8. Rincian yang perlu dipastikan saat implementasi, Analisis perubahan alur PLN GeoMatch

### Community 89 - "Antarmuka ruang kerja PLN GeoMatch"
Cohesion: 0.25
Nodes (7): Antarmuka ruang kerja PLN GeoMatch, Dashboard dan halaman lain, Fondasi visual, Pemeriksaan data, Ruang kerja peta, Struktur aplikasi, Validasi

### Community 90 - "7. Flow Sistem End-to-End"
Cohesion: 0.25
Nodes (8): 7.1 Flow keseluruhan, 7.2 Flow upload dinamis, 7.3 Flow matching dan review, 7.4 Flow navigasi dan perilaku tombol, 7.5 Dua siklus status yang terpisah, 7. Flow Sistem End-to-End, Definisi unit matching, Perilaku import

### Community 91 - "upload/router.py"
Cohesion: 0.18
Nodes (8): import_raw_sheet(), batch_process_endpoint(), list_batches(), BatchProcessRequest, MappingRequest, UploadBatchBase, UploadBatchResponse, Config

### Community 92 - "spatial_tasks.py"
Cohesion: 0.31
Nodes (3): execute_batch_reconciliation_pipeline(), execute_matching_task(), mark_process_failed()

### Community 93 - ".oxlintrc.json"
Cohesion: 0.29
Nodes (6): ignorePatterns, plugins, rules, react/only-export-components, react/rules-of-hooks, $schema

### Community 94 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, backend, build, dev, lint, preview, start

### Community 95 - "Jt"
Cohesion: 0.29
Nodes (7): Jt(), Le(), O(), Qt(), Re(), $t(), te()

### Community 97 - "8. Kebutuhan Fungsional"
Cohesion: 0.29
Nodes (7): 8.1 Autentikasi dan dashboard, 8.2 Upload dan mapping Excel, 8.3 Normalisasi dan pembentukan data, 8.4 Mesin matching, 8.5 Review kandidat dan input manual, 8.6 Hasil, riwayat, dan ekspor, 8. Kebutuhan Fungsional

### Community 98 - "4. Alur yang diusulkan"
Cohesion: 0.33
Nodes (6): 4.1 Pengelolaan master, 4.2 Validasi dan pelengkapan PDPJ, 4.3 Pemeriksaan dua kelompok data koreksi, 4.4 Peta dan radius, 4.5 Pemilihan dan hasil, 4. Alur yang diusulkan

### Community 99 - "Tahap 4: Peta Koreksi"
Cohesion: 0.33
Nodes (6): API, Interaksi, Pilihan dan audit, Radius dan versi, Renderer dan verifikasi, Tahap 4: Peta Koreksi

### Community 100 - "supabase.ts"
Cohesion: 0.33
Nodes (5): @supabase/supabase-js@^2.118.0, supabase, supabaseAnonKey, supabaseUrl, @supabase/supabase-js

### Community 101 - "vite.config.ts"
Cohesion: 0.33
Nodes (4): vite@^8.3.4, @vitejs/plugin-react@^6.1.2, vite, @vitejs/plugin-react

### Community 102 - "d"
Cohesion: 0.33
Nodes (6): at(), d(), ht(), Li(), v(), W()

### Community 104 - "test_refresh_activity_browser.py"
Cohesion: 0.29
Nodes (3): activity_files(), servers(), test_refresh_observes_actual_server_activity_and_then_offers_resume()

### Community 105 - "Browser Automation — agent-browser"
Cohesion: 0.40
Nodes (4): Browser Automation — agent-browser, Engineering Workflow, GSAP Animation Guidelines, UI Icon Guidelines

### Community 106 - "Data Master — tahap 1"
Cohesion: 0.40
Nodes (5): Data Master — tahap 1, Kolom DIL, Penggunaan, Tahap berikutnya, Verifikasi

### Community 107 - "Hasil Koreksi dan Riwayat Proses"
Cohesion: 0.40
Nodes (5): Alur penggunaan, API, Hasil Koreksi dan Riwayat Proses, Sumber hasil dan arti hitungan, Susunan XLSX

### Community 108 - "Pencarian koreksi dari seluruh observasi koordinat"
Cohesion: 0.40
Nodes (4): Aturan pencarian, Pencarian koreksi dari seluruh observasi koordinat, Persiapan dan kinerja, Versi dan proses yang sedang berjalan

### Community 109 - "i"
Cohesion: 0.50
Nodes (5): i(), Mi(), ne(), e(), zi()

### Community 110 - "11. Arsitektur Teknis yang Direkomendasikan"
Cohesion: 0.40
Nodes (5): 11.1 Prinsip arsitektur, 11.2 Stack rekomendasi, 11.3 Batas tanggung jawab, 11.4 Endpoint konseptual, 11. Arsitektur Teknis yang Direkomendasikan

### Community 111 - "get_candidates"
Cohesion: 0.33
Nodes (3): apply_candidate_filters(), get_candidates(), list_matching_runs()

### Community 113 - "Riwayat file dan impor sheet"
Cohesion: 0.50
Nodes (3): API, Penyimpanan dan migrasi, Riwayat file dan impor sheet

### Community 114 - "bi"
Cohesion: 0.50
Nodes (4): bi(), Pi(), Ti(), u()

### Community 115 - "oi"
Cohesion: 0.67
Nodes (4): Je(), ni(), oi(), si()

### Community 116 - "React + TypeScript + Vite"
Cohesion: 0.50
Nodes (3): Expanding the Oxlint configuration, React Compiler, React + TypeScript + Vite

### Community 118 - "12. Spesifikasi UI/UX Neo-Brutalism"
Cohesion: 0.50
Nodes (4): 12.1 Arah visual, 12.2 Aturan UX operasional, 12.3 Spesifikasi halaman dan status UI, 12. Spesifikasi UI/UX Neo-Brutalism

### Community 119 - "2. Masalah, Tujuan, dan Ukuran Keberhasilan"
Cohesion: 0.50
Nodes (4): 2.1 Masalah yang hendak diselesaikan, 2.2 Tujuan produk, 2.3 Ukuran keberhasilan, 2. Masalah, Tujuan, dan Ukuran Keberhasilan

### Community 120 - "9. Status, Siklus Hidup Proses, dan Perhitungan Statistik"
Cohesion: 0.50
Nodes (4): 9.1 Status upload, 9.2 Status matching dan review, 9.3 Definisi statistik, 9. Status, Siklus Hidup Proses, dan Perhitungan Statistik

### Community 121 - "test_processing_performance.py"
Cohesion: 0.13
Nodes (7): tracked(), test_bulk_candidates_keep_correct_evidence_even_if_returning_order_changes(), test_heavy_pdpj_request_does_not_block_unrelated_api(), test_indexes_upgrade_old_database_without_losing_data(), test_pdpj_ingestion_detects_duplicates_across_chunks_and_carries_changes(), test_stage_timing_never_logs_cells_or_exception_messages(), operation()

### Community 122 - "test_search_index.py"
Cohesion: 0.25
Nodes (7): db_session(), original(), test_background_preparation_is_reported_and_resumes(), test_index_follows_edits_rollbacks_inserts_and_deletes(), test_pdpj_and_saved_result_search_preserve_candidates_actors_and_versions(), test_preparation_bounds_reads_when_generated_master_rows_are_skipped(), test_source_search_matches_original_substrings_scope_and_pages()

### Community 124 - "14. Acceptance Criteria dan Strategi Pengujian"
Cohesion: 0.67
Nodes (3): 14.1 Skenario penerimaan utama, 14.2 Layer pengujian, 14. Acceptance Criteria dan Strategi Pengujian

### Community 125 - "3. Pengguna dan Hak Akses"
Cohesion: 0.67
Nodes (3): 3.1 Peran minimal, 3.2 Prinsip otorisasi, 3. Pengguna dan Hak Akses

### Community 126 - "5. Scope Produk"
Cohesion: 0.67
Nodes (3): 5.1 Termasuk dalam MVP, 5.2 Di luar scope MVP atau fase lanjutan, 5. Scope Produk

## Knowledge Gaps
- **26 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Riwayat file dan impor sheet` connect `Riwayat file dan impor sheet` to `UploadBatch`?**
  _High betweenness centrality (0.207) - this node is a cross-community bridge._
- **Are the 106 inferred relationships involving `SourceRecord` (e.g. with `repair_xy_coordinates()` and `upgrade_master_filters()`) actually correct?**
  _`SourceRecord` has 106 INFERRED edges - model-reasoned connections that need verification._
- **Should `sqlalchemy_orm` be split into smaller, more focused modules?**
  _Cohesion score 0.0711864406779661 - nodes in this community are weakly interconnected._
- **Why does `Tahap 4: Peta Koreksi` connect `Tahap 4: Peta Koreksi` to `analisis-alur-rekonsiliasi.md`?**
  _High betweenness centrality (0.189) - this node is a cross-community bridge._
- **Are the 91 inferred relationships involving `UploadBatch` (e.g. with `repair_xy_coordinates()` and `upgrade_master_catalog()`) actually correct?**
  _`UploadBatch` has 91 INFERRED edges - model-reasoned connections that need verification._
- **Should `sqlalchemy_engine` be split into smaller, more focused modules?**
  _Cohesion score 0.0602322206095791 - nodes in this community are weakly interconnected._
- **Why does `Renderer dan verifikasi` connect `Tahap 4: Peta Koreksi` to `pages/CorrectionMap.tsx`?**
  _High betweenness centrality (0.187) - this node is a cross-community bridge._
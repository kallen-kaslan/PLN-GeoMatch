# Graph Report - sintesis  (2026-11-13)

## Corpus Check
- 327 files · ~187,676 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 25 file(s) not represented in the graph (top: .csv 10, (none) 6, .css 4)

## Summary
- 3077 nodes · 10268 edges · 156 communities (125 shown, 31 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 873 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `74ce6001`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- master_preparation.py
- test_progress_reports_bytes_and_chunk_counts_through_confirmation
- sqlalchemy
- pytest
- sqlalchemy
- pdpj/router.py
- master/router.py
- test_correction_map.py
- matching.py
- config.py
- react
- SourceRecord
- upgrade_foundations
- sqlalchemy_orm
- CorrectionKind
- master.ts
- results.py
- ReconciliationProcess
- PdpjReview
- test_master_catalog.py
- re
- test_authentication.py
- corrections.ts
- test_history_deletion.py
- EvidenceLookup
- Pdpj.tsx
- e2e/conftest.py
- automatic.py
- pages/CorrectionMap.tsx
- test_pdpj_validation.py
- archive.py
- test_pdpj_browser.py
- auth/router.py
- test_master_browser.py
- MatchingRun
- react
- Corrections.tsx
- package.json
- test_corrections.py
- security.py
- PLN GeoMatch
- advance
- unpaired_search.py
- leaflet.js
- CorrectionResults.tsx
- test_processing_progress_browser.py
- frontend/package.json
- test_automatic_selection.py
- components.json
- compilerOptions
- test_pdpj_saved_reads.py
- seed_test.py
- test_pdpj_progress.py
- dependencies
- test_upload_files.py
- Dashboard.tsx
- SearchWriter
- test_upload_file_deletion.py
- test_correction_results.py
- compilerOptions
- security.py
- test_sqlite_concurrency.py
- httpx
- CorrectionCandidateEvidence
- PRD-sintesis.md
- re
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
- complete_selection.py
- test_source_preview_paging.py
- test_upload_header_row.py
- master_snapshot_id
- MasterSisaRecord
- Analisis perubahan alur PLN GeoMatch
- Antarmuka ruang kerja PLN GeoMatch
- 7. Flow Sistem End-to-End
- upload/router.py
- search_index.py
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
- UploadProgress
- test_pdpj_results_paging.py
- Browser Automation — agent-browser
- Data Master — tahap 1
- Hasil Koreksi dan Riwayat Proses
- Pencarian koreksi dari seluruh observasi koordinat
- i
- 11. Arsitektur Teknis yang Direkomendasikan
- pdpj/summary.py
- test_reset_hides_unexpected_database_error_and_rolls_back
- Riwayat file dan impor sheet
- bi
- oi
- React + TypeScript + Vite
- test_partial_map_choice_survives_more_saved_rows_and_completion
- 12. Spesifikasi UI/UX Neo-Brutalism
- 2. Masalah, Tujuan, dan Ukuran Keberhasilan
- 9. Status, Siklus Hidup Proses, dan Perhitungan Statistik
- test_heavy_pdpj_request_does_not_block_unrelated_api
- test_search_index.py
- tsconfig.json
- 14. Acceptance Criteria dan Strategi Pengujian
- 3. Pengguna dan Hak Akses
- 5. Scope Produk
- CLAUDE.md
- leaflet-1.9.4/README.md
- decisions.py
- advanced_candidates
- master-preview.worker.ts
- fastapi_testclient
- koordinat-xy.md
- automatic_candidates.py
- master/summary.py
- client
- test_advanced_correction_search.py
- upload_file_schema.py
- test_tie_suggestions.py
- test_automatic_selection_preview_save_export_and_map
- test_map_and_results_export_original_objectid_filtered_radius_and_real_distance

## God Nodes (most connected - your core abstractions)
1. `SourceRecord` - 176 edges
2. `UploadBatch` - 158 edges
3. `ReconciliationProcess` - 93 edges
4. `MatchingRun` - 89 edges
5. `DatasetType` - 88 edges
6. `MatchCandidate` - 81 edges
7. `PdpjReview` - 72 edges
8. `Base` - 72 edges
9. `upload()` - 71 edges
10. `PdpjRow` - 70 edges

## Surprising Connections (you probably didn't know these)
- `Optimasi yang diterapkan pada 27 Oktober 2026` --references--> `create_review()`  [INFERRED]
  docs/analisis-performa.md → backend/app/modules/pdpj/service.py
- `Startup dengan jutaan baris pada 27 Oktober 2026` --references--> `main()`  [INFERRED]
  docs/analisis-performa.md → backend/app/modules/auth/bootstrap.py
- `Riwayat file dan impor sheet` --references--> `SourceRecord`  [INFERRED]
  docs/riwayat-file-sheet.md → backend/app/models/upload.py
- `Riwayat file dan impor sheet` --references--> `UploadBatch`  [INFERRED]
  docs/riwayat-file-sheet.md → backend/app/models/upload.py
- `Renderer dan verifikasi` --references--> `MapProvider`  [INFERRED]
  docs/peta-koreksi.md → frontend/src/lib/correction-map.ts

## Import Cycles
- None detected.

## Communities (156 total, 31 thin omitted)

### Community 0 - "master_preparation.py"
Cohesion: 0.10
Nodes (26): upgrade(), upgrade_master_preparation(), MasterPreparation, MasterPreparationExcluded, MasterPreparationIdentity, observation_period(), candidate_observations(), advance_preparation() (+18 more)

### Community 1 - "test_progress_reports_bytes_and_chunk_counts_through_confirmation"
Cohesion: 0.28
Nodes (4): test_failed_mapping_retains_pending_batch_and_reports_failure(), test_progress_reports_bytes_and_chunk_counts_through_confirmation(), test_progress_token_is_validated_and_unknown_ids_do_not_start_imports(), test_status_file_contention_does_not_fail_a_successful_import()

### Community 2 - "sqlalchemy"
Cohesion: 0.05
Nodes (19): upgrade(), upgrade(), upgrade(), upgrade(), upgrade(), upgrade(), upgrade_correction_map(), upgrade_correction_observations() (+11 more)

### Community 3 - "pytest"
Cohesion: 0.06
Nodes (19): test_automatic_page_handles_empty_unfinished_and_mismatched_sources(), test_complete_save_export_result_and_inherited_map_candidates(), test_all_observations_source_and_coordinate_warning_survive_refresh(), test_partial_results_export_history_resume_replace_and_cancel(), launch(), prepare(), test_mobile_empty_idpel_import_pagination_summary_and_candidate_pages(), test_not_found_import_conflicts_candidates_missing_coordinates_and_category_isolation() (+11 more)

### Community 4 - "sqlalchemy"
Cohesion: 0.10
Nodes (17): run_migrations_offline(), run_migrations_online(), upgrade(), Base, ensure_schema_compatibility(), AuthAudit, AuthGuard, AuthThrottle (+9 more)

### Community 5 - "pdpj/router.py"
Cohesion: 0.08
Nodes (29): advance_processing(), apply_recommendation(), ApplyRecommendation, batch_preview(), CompleteWithExceptions, decide_row(), DecideRow, edit_row() (+21 more)

### Community 6 - "master/router.py"
Cohesion: 0.09
Nodes (16): source_coordinates_missing(), batch_info(), catalogue_query(), delete_master_batch(), get_master_batch(), get_master_record(), get_master_summary(), incomplete_location() (+8 more)

### Community 7 - "test_correction_map.py"
Cohesion: 0.12
Nodes (19): apply(), preview(), test_complete_saves_ties_and_extensions_and_preserves_history_and_map(), test_stale_preview_and_failure_leave_no_partial_version_or_choices(), test_ties_can_be_saved_without_expansion_then_only_remaining_targets_expand(), body(), details(), mapped() (+11 more)

### Community 8 - "matching.py"
Cohesion: 0.06
Nodes (32): ProcessStatus, ReviewStatus, CandidateLocation, run_correction_matching(), completed_review(), calculate_haversine_distance(), create_matching_run(), lock_matching_session() (+24 more)

### Community 9 - "config.py"
Cohesion: 0.16
Nodes (4): AuthUser, get_current_user(), get_supabase_jwks(), require_roles()

### Community 10 - "react"
Cohesion: 0.08
Nodes (34): App(), AuthSplash(), PlnLogo(), Navbar(), PasswordDialog(), RequireAuth(), Shell(), Item (+26 more)

### Community 11 - "SourceRecord"
Cohesion: 0.08
Nodes (33): downgrade(), upgrade(), upgrade_master_catalog(), SourceRecord, UploadBatch, post_csv(), test_chunked_upload_and_mapping_preserve_all_rows(), insert() (+25 more)

### Community 12 - "upgrade_foundations"
Cohesion: 0.14
Nodes (7): downgrade(), upgrade(), upgrade(), upgrade_foundations(), test_existing_matching_runs_gain_nullable_failure_code_without_losing_history(), test_migration_preserves_legacy_decisions_and_is_idempotent(), test_startup_upgrade_accepts_fresh_metadata_with_foreign_keys()

### Community 13 - "sqlalchemy_orm"
Cohesion: 0.05
Nodes (36): upgrade(), repair_xy_coordinates(), add_keys(), build_index(), chunk_context(), clear_pdpj_indexes(), CompactIndex, ConflictContext (+28 more)

### Community 14 - "CorrectionKind"
Cohesion: 0.08
Nodes (31): filtered_info(), has_candidate_in_radius(), validate_radius(), advance_check(), batch_preview(), cached_preview_fields(), check_info(), dispatch() (+23 more)

### Community 15 - "master.ts"
Cohesion: 0.09
Nodes (35): count(), duration(), ImportProgress(), labels, ImportPreview, MasterImport(), readError(), ImportActivity (+27 more)

### Community 16 - "results.py"
Cohesion: 0.12
Nodes (21): coordinate_sources(), result_columns(), source_label(), target_columns(), text(), append_evidence(), download_history(), download_results() (+13 more)

### Community 17 - "ReconciliationProcess"
Cohesion: 0.10
Nodes (34): MatchCandidate, ReconciliationProcess, DatasetType, execute_pipeline(), pin_pipeline_sources(), prepare_process_master(), process_master_sisa_exclusion(), auto_pipeline_endpoint() (+26 more)

### Community 18 - "PdpjReview"
Cohesion: 0.08
Nodes (26): downgrade(), upgrade(), upgrade(), PdpjChange, PdpjRecommendation, PdpjReview, PdpjRow, publish_saved_rows() (+18 more)

### Community 19 - "test_master_catalog.py"
Cohesion: 0.10
Nodes (24): upgrade(), upgrade_master_summary(), import_master(), test_actual_dil_headers_keep_codes_meters_and_blank_columns_separate(), test_catalogue_cannot_mix_master_types_or_target_batches(), test_dil_latest_observation_is_selected_while_sources_are_retained(), test_dil_supplement_uses_latest_source_without_erasing_known_coordinates(), test_dil_supplements_missing_fields_without_replacing_known_location() (+16 more)

### Community 20 - "re"
Cohesion: 0.10
Nodes (15): setup_map(), test_choose_replace_radius_expansion_history_and_category_isolation(), test_clear_target_keeps_saved_decision_filters_and_table_page(), test_map_all_points_hover_selection_and_candidate_pagination(), test_map_highlights_selected_target_and_links_candidate_to_later_card_page(), test_map_preview_page_input_sizes_filters_and_mobile(), test_map_unavailable_keeps_mobile_table_and_choice_flow(), test_select_target_loads_candidates_automatically_and_preserves_read_only_flow() (+7 more)

### Community 21 - "test_authentication.py"
Cohesion: 0.11
Nodes (25): create_application(), Settings, utcnow(), create_initial_admin(), cookie_name(), digest(), add_user(), login() (+17 more)

### Community 22 - "corrections.ts"
Cohesion: 0.08
Nodes (36): AutomaticExtensionNote(), AutomaticSelection(), count(), CompleteAutomaticSelection(), count(), methods, useDebouncedSearch(), usePdpjUpdate() (+28 more)

### Community 23 - "test_history_deletion.py"
Cohesion: 0.06
Nodes (26): tracked(), activity_lock(), database_engine(), file_lock(), lock_path(), decorate(), monitored(), request_activity() (+18 more)

### Community 25 - "Pdpj.tsx"
Cohesion: 0.11
Nodes (40): CorrectionProgress(), count(), revision(), CompleteWithExceptionsDialog(), count(), duration(), PdpjProgress(), revision() (+32 more)

### Community 26 - "e2e/conftest.py"
Cohesion: 0.09
Nodes (11): authenticated_api(), wrap(), browser(), free_port(), page(), servers(), wait_server(), test_login_logo_intro_responsive_layout_password_visibility_and_sign_in() (+3 more)

### Community 27 - "automatic.py"
Cohesion: 0.15
Nodes (18): apply_selection(), ApplyRequest, automatic_reason(), build_plan(), decision_version(), export_suggestions(), operation_prefix(), preview_selection() (+10 more)

### Community 28 - "pages/CorrectionMap.tsx"
Cohesion: 0.15
Nodes (23): CandidateCoordinateSource(), CorrectionMap(), MapRadiusSummary(), useMapRadiusSummary(), coordinates(), createCorrectionMap(), Group, Layer (+15 more)

### Community 29 - "test_pdpj_validation.py"
Cohesion: 0.11
Nodes (32): pending(), request_body(), test_bulk_commit_failure_rolls_back_exceptions_audit_and_completion(), test_bulk_completion_preserves_issues_sources_old_exceptions_and_audit(), test_bulk_completion_requires_scope_confirmation_and_fresh_revision(), test_bulk_completion_unblocks_map_and_never_reuses_pdpj_identity(), test_duplicate_identity_with_different_locations_or_service_can_complete(), test_legacy_duplicate_migration_reclassifies_open_reviews_and_keeps_history() (+24 more)

### Community 30 - "archive.py"
Cohesion: 0.11
Nodes (16): UploadFileArchive, archive_info(), archive_path(), delete_file(), delete_sheet(), get_archive(), import_sheet(), attach_import() (+8 more)

### Community 31 - "test_pdpj_browser.py"
Cohesion: 0.14
Nodes (10): test_bulk_exceptions_enable_correction_map_and_preserve_reserved_identities(), test_duplicate_pdpj_identities_allow_normal_completion_with_different_coordinates_and_service(), test_mobile_pending_pdpj_mapping_and_manual_coordinates(), test_pdpj_import_recommendations_manual_exception_completion_and_matching(), test_pdpj_mapping_storage_error_can_retry_without_uploading_again(), test_replacing_filled_recommendation_requires_explicit_overwrite(), upload_source(), test_fast_progress_does_not_cancel_a_slow_table_request() (+2 more)

### Community 32 - "auth/router.py"
Cohesion: 0.20
Nodes (19): AuthSession, User, change_password(), clear_cookies(), create_user(), ensure_password(), list_users(), login() (+11 more)

### Community 33 - "test_master_browser.py"
Cohesion: 0.12
Nodes (13): test_group_review_verifies_one_choice_refreshes_preview_and_keeps_idpel_unique(), test_global_expansion_without_target_and_radius_specific_status_filters(), test_initial_check_updates_summary_without_showing_expansion_panel(), test_csv_encoding_matches_preview_and_saved_data(), test_csv_upload_mapping_details_and_category_isolation(), test_excel_bad_dimensions_preview_matches_import_and_empty_sheet_can_recover(), test_excel_empty_first_sheet_uses_data_sheet(), test_excel_empty_workbook_can_select_sheet_and_replace_file() (+5 more)

### Community 34 - "MatchingRun"
Cohesion: 0.07
Nodes (24): CorrectionAttempt, CorrectionCheck, MatchingRun, candidate_generations(), candidate_scope(), advance_progress(), control_progress(), initialize_progress() (+16 more)

### Community 35 - "react"
Cohesion: 0.18
Nodes (19): actionLabel, reasons, count(), GroupedCorrectionReview(), reasonLabel(), ReviewGroup(), ReviewTarget(), count() (+11 more)

### Community 36 - "Corrections.tsx"
Cohesion: 0.15
Nodes (29): AdvancedCandidateSearch(), AutomaticCandidateResults(), count(), CorrectionDetail(), present(), InspectionDrawer(), icons, MetricCard() (+21 more)

### Community 37 - "package.json"
Cohesion: 0.10
Nodes (27): dependencies, @designcodeio/threeui@^1.2.0, framer-motion@^14.7.1, gsap@^3.15.0, @lucasmarkes/hairline@^0.5.1, lucide-react@^1.59.0, motion@^14.7.1, @tabler/icons-react@^3.50.0 (+19 more)

### Community 38 - "test_corrections.py"
Cohesion: 0.16
Nodes (23): CorrectionTarget, finder(), test_extension_publishes_previously_empty_target_and_radius_summary(), check(), reference(), test_candidate_details_use_saved_evidence_and_keep_zero_candidate_rows(), test_correction_worker_failure_is_final_until_explicit_retry(), test_empty_category_compares_typed_references_and_only_warns_on_same_coordinates() (+15 more)

### Community 39 - "security.py"
Cohesion: 0.11
Nodes (6): current_actor(), current_user(), Principal, require_access(), require_admin(), require_origin()

### Community 40 - "PLN GeoMatch"
Cohesion: 0.07
Nodes (25): Pencarian data, Pengujian, Pengukuran lokal, Penyebab lambat, Persiapan data lama dan konsistensi, Perubahan, 1. Clone Repository, 2. Setup Backend (+17 more)

### Community 41 - "advance"
Cohesion: 0.19
Nodes (16): scenario(), test_legacy_checkpoint_resumes_old_policy_and_explicit_retry_starts_from_zero(), test_new_observation_search_preserves_previously_approved_coordinate(), test_observation_preparation_checkpoints_resume_without_duplicate_rows(), test_search_all_sources_then_deduplicate_and_export_selected_observation(), advance(), finish(), path() (+8 more)

### Community 42 - "unpaired_search.py"
Cohesion: 0.13
Nodes (13): candidate_usage(), current_choices(), identity_owners(), equal_distance_matching(), propose_ties(), Edge, export_unpaired(), find_unpaired() (+5 more)

### Community 43 - "leaflet.js"
Cohesion: 0.09
Nodes (4): a(), Ci(), l(), x()

### Community 44 - "CorrectionResults.tsx"
Cohesion: 0.15
Nodes (26): CorrectionResults(), count(), DecisionHistory(), ResultDetail(), api, API_BASE_URL, AdvancedCandidate, CORRECTION_TYPES (+18 more)

### Community 45 - "test_processing_progress_browser.py"
Cohesion: 0.11
Nodes (10): test_master_progress_is_saved_and_ready_snapshot_can_be_reused(), test_master_totals_load_before_details_and_survive_refresh(), sources(), test_connection_loss_keeps_checkpoint_and_reload_can_continue(), test_stop_reload_and_resume_from_saved_rows(), captured(), test_committed_correction_rows_refresh_while_next_chunk_is_running(), test_correction_progress_saves_pauses_and_resumes_after_reload() (+2 more)

### Community 46 - "frontend/package.json"
Cohesion: 0.12
Nodes (23): devDependencies, autoprefixer@^10.6.1, oxlint@^1.88.0, postcss@^8.5.31, tailwindcss@^4.3.3, @types/node@^24.19.2, @types/papaparse@^5.5.2, @types/react@^19.3.0 (+15 more)

### Community 47 - "test_automatic_selection.py"
Cohesion: 0.15
Nodes (19): apply(), choose(), preview(), scenario(), test_change_between_planning_and_writer_lock_is_rejected(), test_equal_candidates_on_one_target_require_review(), test_equal_distance_across_targets_reserves_identity_for_review(), test_failure_after_insert_rolls_back_and_same_request_can_retry() (+11 more)

### Community 48 - "components.json"
Cohesion: 0.09
Nodes (21): aliases, components, hooks, lib, ui, utils, iconLibrary, menuAccent (+13 more)

### Community 49 - "compilerOptions"
Cohesion: 0.10
Nodes (20): compilerOptions, allowArbitraryExtensions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection (+12 more)

### Community 50 - "test_pdpj_saved_reads.py"
Cohesion: 0.20
Nodes (9): upgrade(), upgrade_pdpj_summary(), capture_rows(), prepare(), test_first_summary_uses_covering_index_and_unchanged_reads_skip_row_counts(), test_reset_with_reused_ids_and_revisions_does_not_reuse_old_summary(), test_summary_cache_follows_processing_checkpoints(), test_summary_index_upgrade_preserves_rows_and_can_repeat() (+1 more)

### Community 51 - "seed_test.py"
Cohesion: 0.15
Nodes (13): build_combined_master(), seed_dummy_data(), ensure_dir(), generate_acmt(), generate_all_dummy(), generate_koordinat_kosong(), generate_lpb(), generate_pdpj_verif() (+5 more)

### Community 52 - "test_pdpj_progress.py"
Cohesion: 0.18
Nodes (9): upgrade(), upgrade_pdpj_progress(), finish_steps(), pending(), step(), test_failed_chunk_rolls_back_without_losing_previous_checkpoint(), test_pause_reload_resume_preserves_rows_and_finishes_validation(), test_progress_schema_upgrade_is_additive_and_idempotent() (+1 more)

### Community 53 - "dependencies"
Cohesion: 0.09
Nodes (22): dependencies, axios@^1.20.0, leaflet.markercluster@^1.5.3, @lucasmarkes/hairline@^0.5.1, lucide-react@^1.59.0, motion@^14.7.1, papaparse@^5.7.0, react@^19.3.1 (+14 more)

### Community 55 - "test_upload_files.py"
Cohesion: 0.33
Nodes (12): archive(), confirm(), import_sheet(), test_failed_sheet_write_rolls_back_rows_but_retains_original_for_retry(), test_fingerprint_deduplicates_reuploads_but_not_changed_contents(), test_invalid_sheet_and_missing_original_leave_no_partial_reference(), test_invalid_uploads_are_not_archived(), test_original_and_previews_do_not_create_reference_or_batches() (+4 more)

### Community 56 - "Dashboard.tsx"
Cohesion: 0.53
Nodes (5): count(), DashboardPage(), ProcessItem, processLink(), status()

### Community 58 - "test_upload_file_deletion.py"
Cohesion: 0.30
Nodes (12): admin_client(), confirm(), import_sheet(), test_delete_file_404(), test_delete_file_blocked_when_batch_used_in_pdpj(), test_delete_file_removes_archive_batches_and_records(), test_delete_file_without_imports(), test_delete_sheet_404_wrong_dataset_type() (+4 more)

### Community 59 - "test_correction_results.py"
Cohesion: 0.29
Nodes (12): advance(), choose(), partial(), sheet_rows(), test_export_keeps_original_objectid_and_applies_filter_radius_to_saved_choices(), test_latest_choice_is_scoped_to_its_process_even_for_the_same_source_row(), test_partial_choice_appears_in_results_history_and_xlsx_without_changing_source(), test_replacement_cancellation_filters_and_history_are_not_counted_as_extra_choices() (+4 more)

### Community 60 - "compilerOptions"
Cohesion: 0.12
Nodes (16): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, noEmit, noFallthroughCasesInSwitch (+8 more)

### Community 61 - "security.py"
Cohesion: 0.09
Nodes (19): upgrade(), upgrade_auth(), UserRole, main(), ChangePassword, CreateUser, LoginRequest, StrictRequest (+11 more)

### Community 62 - "test_sqlite_concurrency.py"
Cohesion: 0.08
Nodes (16): database_busy_response(), register_database_error_handlers(), touch_session(), configure_connection(), configure_sqlite_engine(), sqlite_busy(), test_application_sqlite_connections_enforce_foreign_keys(), db_session() (+8 more)

### Community 63 - "httpx"
Cohesion: 0.58
Nodes (6): choose_original(), open_import(), test_preview_empty_sheet_recovery_and_checkmarks_follow_period(), test_same_file_history_can_be_reused_in_pdpj_without_master_checkmarks(), test_sheet_history_checks_survive_reload_and_other_sheet_uses_same_original(), workbook()

### Community 64 - "CorrectionCandidateEvidence"
Cohesion: 0.11
Nodes (10): upgrade(), downgrade(), upgrade(), upgrade_correction_progress(), upgrade_corrections(), CorrectionCandidateEvidence, canonical_result(), main() (+2 more)

### Community 65 - "PRD-sintesis.md"
Cohesion: 0.14
Nodes (13): 10. Rancangan Data Konseptual, 13. Kebutuhan Nonfungsional, 16. Risiko dan Mitigasi, 17. Keputusan yang Masih Harus Dikonfirmasi, 18. Definisi Selesai Produk (Definition of Done), 1. Ringkasan Produk, 4. Glosarium dan Definisi Data, 6. Aturan Bisnis (+5 more)

### Community 66 - "re"
Cohesion: 0.11
Nodes (8): test_advanced_finder_evidence_expansion_and_verified_unique_selection(), test_switch_to_final_pdpj_while_old_correction_remains_paused(), test_export_stays_available_during_background_refresh_and_uses_current_radius(), test_admin_local_search_matches_real_usernames(), test_correction_search_filters_and_clears(), test_map_and_saved_result_search_keep_the_selected_scope(), test_master_search_debounces_prepares_and_preserves_pagination(), test_pdpj_search_includes_kwh_meter_and_clear()

### Community 68 - "read_progress"
Cohesion: 0.27
Nodes (7): create_progress(), get_progress(), pause_path(), pause_upload(), progress_path(), read_progress(), resume_upload()

### Community 69 - "test_upload_pause.py"
Cohesion: 0.22
Nodes (5): file_client(), test_failure_after_resume_can_retry_without_missing_or_duplicate_rows(), test_repeat_pause_resume_preserves_every_row_and_releases_database(), measured(), wait_paused()

### Community 71 - "F"
Cohesion: 0.24
Nodes (11): F(), G(), h(), j(), k(), ke(), me(), Oe() (+3 more)

### Community 72 - "test_authentication_browser.py"
Cohesion: 0.24
Nodes (11): login_ui(), sign_out(), test_admin_creates_real_account_and_nonadmin_cannot_manage_users(), test_blocking_account_revokes_browser_session(), test_default_login_no_registration_wrong_password_and_logout(), test_logout_clears_another_open_tab(), test_user_can_change_own_password_and_must_login_again(), switch_role() (+3 more)

### Community 73 - "Analisis waktu proses"
Cohesion: 0.18
Nodes (10): Analisis awal pada 26 Oktober 2026, Analisis waktu proses, Backend 502 saat startup, Optimasi yang diterapkan pada 27 Oktober 2026, Pembacaan daftar gagal ketika pemeriksaan menulis database, Pengukuran terisolasi, Reset ketika database terkunci, Startup dengan jutaan baris pada 27 Oktober 2026 (+2 more)

### Community 74 - "e"
Cohesion: 0.27
Nodes (10): c(), e(), hi(), m(), q(), Qe(), ve(), xe() (+2 more)

### Community 75 - "test_manual_corrections_browser.py"
Cohesion: 0.29
Nodes (4): fill_point(), test_manual_coordinates_validated_before_saving_on_mobile(), test_manual_mapping_retry_reuses_saved_point(), test_manual_point_check_map_choice_and_export()

### Community 76 - "test_upload_progress_browser.py"
Cohesion: 0.22
Nodes (3): test_master_import_displays_measured_progress_and_waits_for_commit(), test_pause_and_resume_master_import_waits_for_server_acknowledgement(), test_preview_worker_can_pause_and_resume_without_losing_preview_rows()

### Community 77 - "15. Roadmap Implementasi"
Cohesion: 0.20
Nodes (10): 15. Roadmap Implementasi, Gate antarphase, Phase 0 — Validasi kebutuhan dan aturan bisnis, Phase 1 — Fondasi aplikasi dan model data, Phase 2 — Import dinamis, Phase 3 — Dataset preparation dan Master Sisa, Phase 4 — Mesin matching spasial, Phase 5 — Daftar Kandidat & Peta dan review (+2 more)

### Community 78 - "preview_file"
Cohesion: 0.16
Nodes (8): check_file_size(), detect_csv_encoding(), read_upload(), csv_rows(), validate_text_encoding(), preview_file(), upload_file(), test_real_500_mb_file_size_boundary()

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

### Community 83 - "complete_selection.py"
Cohesion: 0.24
Nodes (10): utc_now(), apply_complete(), complete_plan(), CompleteApply, CompleteRequest, extension_run(), operation_key(), preview_complete() (+2 more)

### Community 84 - "test_source_preview_paging.py"
Cohesion: 0.39
Nodes (5): test_correction_preview_keeps_invalid_coordinate_errors(), test_legacy_and_invalid_pages_load_original_cells_in_one_bounded_query(), test_legacy_missing_batch_count_uses_database_count(), test_source_preview_pages_cross_files_preserve_scope_and_use_covering_indexes(), capture()

### Community 85 - "test_upload_header_row.py"
Cohesion: 0.33
Nodes (6): header_row_index(), test_early_title_row_within_the_scan_window(), test_header_row_index_prefers_the_row_naming_several_columns(), test_sheet_without_any_named_cell_is_rejected(), test_title_rows_above_the_header_are_skipped(), workbook()

### Community 86 - "master_snapshot_id"
Cohesion: 0.29
Nodes (6): master_snapshot_id(), API yang terkait, Database lama, Perbaikan fondasi data, Perilaku data, Verifikasi

### Community 87 - "MasterSisaRecord"
Cohesion: 0.08
Nodes (5): MasterSisaRecord, advance_observations(), TestCalculateDistance, TestUnder5mIndependent, TestValidityStatusLogic

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
Cohesion: 0.10
Nodes (14): MasterSnapshot, BatchStatus, batch_process_endpoint(), confirm_mapping(), list_batches(), reset_database(), BatchProcessRequest, MappingRequest (+6 more)

### Community 92 - "search_index.py"
Cohesion: 0.28
Nodes (10): _build(), _chunk(), _eligible(), _engine(), _initialize(), _name(), pending_search(), prepare_search() (+2 more)

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

### Community 103 - "UploadProgress"
Cohesion: 0.21
Nodes (5): import_raw_sheet(), UploadProgress, apply_mapping(), decorate(), measured()

### Community 104 - "test_pdpj_results_paging.py"
Cohesion: 0.19
Nodes (4): upgrade(), upgrade_pdpj_results(), test_pages_use_ordered_covering_index_and_keep_original_fields_out_of_payload(), test_paging_index_upgrade_is_additive_and_repeatable()

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

### Community 111 - "pdpj/summary.py"
Cohesion: 0.26
Nodes (7): pdpj_coordinates_missing(), pdpj_issue_count(), list_rows(), cache_key(), cached_counts(), review_counts(), saved_total()

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

### Community 122 - "test_search_index.py"
Cohesion: 0.35
Nodes (6): original(), test_background_preparation_is_reported_and_resumes(), test_index_follows_edits_rollbacks_inserts_and_deletes(), test_pdpj_and_saved_result_search_preserve_candidates_actors_and_versions(), test_preparation_bounds_reads_when_generated_master_rows_are_skipped(), test_source_search_matches_original_substrings_scope_and_pages()

### Community 124 - "14. Acceptance Criteria dan Strategi Pengujian"
Cohesion: 0.67
Nodes (3): 14.1 Skenario penerimaan utama, 14.2 Layer pengujian, 14. Acceptance Criteria dan Strategi Pengujian

### Community 125 - "3. Pengguna dan Hak Akses"
Cohesion: 0.67
Nodes (3): 3.1 Peran minimal, 3.2 Prinsip otorisasi, 3. Pengguna dan Hak Akses

### Community 126 - "5. Scope Produk"
Cohesion: 0.67
Nodes (3): 5.1 Termasuk dalam MVP, 5.2 Di luar scope MVP atau fase lanjutan, 5. Scope Produk

### Community 131 - "decisions.py"
Cohesion: 0.12
Nodes (9): get_db(), choice_history(), ChoiceRequest, choose_candidate(), decision_info(), get_choice(), target_scope(), radius_summary() (+1 more)

### Community 132 - "advanced_candidates"
Cohesion: 0.22
Nodes (6): advanced_candidates(), comparable(), coordinate_distance(), matches(), pinned_sources(), reference_value()

### Community 133 - "master-preview.worker.ts"
Cohesion: 0.31
Nodes (12): xlsx@^0.18.5, cleanSourceHeader(), hasSourceHeaders(), normalizeSourceHeaders(), checkpoint(), detectCsvEncoding(), readCsv(), readExcelPreview() (+4 more)

### Community 142 - "automatic_candidates.py"
Cohesion: 0.24
Nodes (3): candidate_frontier(), Pair, test_frontier_reads_beyond_first_page_and_stops_at_radius()

### Community 143 - "master/summary.py"
Cohesion: 0.44
Nodes (4): batch_counts(), master_summary(), signature(), stored_counts()

### Community 144 - "client"
Cohesion: 0.25
Nodes (3): client(), db_session(), isolated_file_archives()

### Community 145 - "test_advanced_correction_search.py"
Cohesion: 0.43
Nodes (6): search(), test_excludes_pdpj_used_idpel_and_new_uploads(), test_names_gardu_pagination_and_search_readiness(), test_outside_radius_and_missing_coordinates_need_explicit_follow_up(), test_search_finds_identity_evidence_and_retains_stored_coordinates(), test_stale_generation_changed_mapping_and_scope_rejected()

### Community 147 - "test_tie_suggestions.py"
Cohesion: 0.60
Nodes (4): request(), setup(), test_tie_mode_continues_to_alternatives_and_nearer_distance_keeps_priority(), test_tie_mode_proposes_unique_pairs_without_saving_and_exports_separate_sheet()

## Knowledge Gaps
- **31 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Riwayat file dan impor sheet` connect `Riwayat file dan impor sheet` to `SourceRecord`?**
  _High betweenness centrality (0.249) - this node is a cross-community bridge._
- **Are the 87 inferred relationships involving `SourceRecord` (e.g. with `repair_xy_coordinates()` and `upgrade_master_filters()`) actually correct?**
  _`SourceRecord` has 87 INFERRED edges - model-reasoned connections that need verification._
- **Should `master_preparation.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09783368273934312 - nodes in this community are weakly interconnected._
- **Why does `Tahap 4: Peta Koreksi` connect `Tahap 4: Peta Koreksi` to `analisis-alur-rekonsiliasi.md`?**
  _High betweenness centrality (0.236) - this node is a cross-community bridge._
- **Are the 75 inferred relationships involving `UploadBatch` (e.g. with `repair_xy_coordinates()` and `upgrade_master_catalog()`) actually correct?**
  _`UploadBatch` has 75 INFERRED edges - model-reasoned connections that need verification._
- **Should `sqlalchemy` be split into smaller, more focused modules?**
  _Cohesion score 0.045168456127360236 - nodes in this community are weakly interconnected._
- **Why does `Renderer dan verifikasi` connect `Tahap 4: Peta Koreksi` to `pages/CorrectionMap.tsx`?**
  _High betweenness centrality (0.222) - this node is a cross-community bridge._
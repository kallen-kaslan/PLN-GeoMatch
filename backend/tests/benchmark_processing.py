"""Compare a trusted Git revision against current code using isolated test data.

Run from backend: python -m tests.benchmark_processing --baseline <commit> --targets 500
Requires the development dependencies; never opens the configured live database.
"""

import argparse
import json
import os
import statistics
import subprocess
from pathlib import Path
from time import perf_counter

import pytest
from sqlalchemy import event

ROOT = Path(__file__).resolve().parents[2]


def revision_module(revision: str, path: str):
    source = subprocess.check_output(
        [
            "git",
            "-c",
            f"safe.directory={ROOT.as_posix()}",
            "show",
            f"{revision}:{path}",
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    )
    namespace = {"__name__": "isolated_benchmark_baseline"}
    exec(compile(source, path, "exec"), namespace)  # noqa: S102 -- Explicit trusted local baseline, isolated DB.
    return namespace


def canonical_result(db, result):
    from app.models.correction import CorrectionCandidateEvidence, CorrectionTarget
    from app.models.matching import MatchCandidate

    outcomes = (
        db.query(CorrectionTarget)
        .filter_by(run_id=result["latest_run"]["id"])
        .order_by(CorrectionTarget.source_record_id)
        .all()
    )
    candidates = (
        db.query(MatchCandidate, CorrectionCandidateEvidence)
        .join(CorrectionCandidateEvidence)
        .filter(MatchCandidate.process_id == result["process_id"])
        .order_by(MatchCandidate.target_record_id, MatchCandidate.rank)
        .all()
    )
    return (
        [
            (
                row.source_record_id,
                row.fields,
                row.search_status,
                row.identity_status,
                row.errors,
                row.conflicts,
                row.warnings,
                row.candidate_count,
            )
            for row in outcomes
        ],
        [
            (
                {
                    column.name: getattr(candidate, column.name)
                    for column in MatchCandidate.__table__.columns
                    if column.name not in {"id", "process_id", "generation"}
                },
                evidence.fields,
                evidence.observations,
            )
            for candidate, evidence in candidates
        ],
    )


def main():
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    from app.modules.corrections import engine as current_engine
    from app.modules.upload import normalization as current_normalization
    from tests import conftest
    from tests import test_corrections as fixtures

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline", required=True, help="Trusted commit to execute as baseline"
    )
    parser.add_argument("--targets", type=int, default=500)
    args = parser.parse_args()
    if not 1 <= args.targets <= 5000:
        parser.error("targets must be between 1 and 5000")
    baseline = revision_module(
        args.baseline, "backend/app/modules/corrections/engine.py"
    )["run_correction_matching"]
    normalization = revision_module(
        args.baseline, "backend/app/modules/upload/normalization.py"
    )["extract_standard_fields"]
    original = current_engine.run_correction_matching
    database_fixture = conftest.db_session.__wrapped__()
    db = next(database_fixture)
    client_fixture = conftest.client.__wrapped__(db)
    client = next(client_fixture)
    patch = pytest.MonkeyPatch()
    try:
        review_id = fixtures.reference.__wrapped__(client, patch)
        batch_id = fixtures.upload(
            client,
            "idpel_kosong",
            "ID_TITIK,LAT,LON\n"
            + "".join(f"BENCH-{i},-6.2,106.8\n" for i in range(args.targets)),
        )
        results, metrics = [], {}
        for label, implementation in [("before", baseline), ("after", original)]:
            writes = []

            def count(
                connection,
                cursor,
                statement,
                parameters,
                context,
                executemany,
                _writes=writes,
            ):
                if statement.startswith("INSERT INTO match_candidates"):
                    _writes.append(1)

            patch.setattr(current_engine, "run_correction_matching", implementation)
            event.listen(db.get_bind(), "after_cursor_execute", count)
            try:
                started = perf_counter()
                result = fixtures.check(
                    client,
                    "idpel_kosong",
                    batch_id,
                    review_id,
                    key=f"benchmark_{label}",
                )
                elapsed = perf_counter() - started
            finally:
                event.remove(db.get_bind(), "after_cursor_execute", count)
            results.append(canonical_result(db, result))
            metrics[label] = {
                "seconds": round(elapsed, 4),
                "candidate_insert_statements": len(writes),
                "targets": args.targets,
                "candidates": len(results[-1][1]),
            }
        assert results[0] == results[1], (
            "Results changed; performance comparison is invalid"
        )
        metrics["identical_results"] = True
        print(json.dumps(metrics, indent=2), flush=True)
        sample = {
            "IDPEL": "000123",
            "NAMA": "Contoh",
            "LAT": "-6.2",
            "LON": "106.8",
            **{f"EXTRA_{i}": str(i) for i in range(70)},
        }
        mapping = {"idpel": "IDPEL", "nama": "NAMA", "lat": "LAT", "lon": "LON"}
        assert normalization(
            sample, mapping
        ) == current_normalization.extract_standard_fields(sample, mapping)
        for label, implementation in [
            ("before", normalization),
            ("after", current_normalization.extract_standard_fields),
        ]:
            measurements = []
            for _ in range(3):
                started = perf_counter()
                for _ in range(10000):
                    implementation(sample, mapping)
                measurements.append(perf_counter() - started)
            print(
                f"extraction_{label}_10000_rows_median_seconds={statistics.median(measurements):.4f}",
                flush=True,
            )
    finally:
        patch.undo()
        client_fixture.close()
        database_fixture.close()


if __name__ == "__main__":
    main()

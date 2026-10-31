"""Bounded bulk writes correlated by target/rank, independent of RETURNING order."""

from typing import Any, cast

from sqlalchemy import Table, insert
from sqlalchemy.orm import Session

from app.models.correction import CorrectionCandidateEvidence, CorrectionTarget
from app.models.matching import MatchCandidate
from app.models.upload import SourceRecord
from app.modules.spatial.engine import calculate_haversine_distance
from app.modules.spatial.master_evidence import candidate_observations

CANDIDATE_WRITE_ROWS = 400
OUTCOME_WRITE_ROWS = 100


class SearchWriter:
    def __init__(self, db: Session):
        self.db = db
        self.candidates: list[dict[str, Any]] = []
        self.sources: dict[tuple[int, int], tuple[int, int, int | None]] = {}
        self.outcomes: list[dict[str, Any]] = []

    def outcome(self, values: dict[str, Any]) -> None:
        self.outcomes.append(values)
        if len(self.outcomes) >= OUTCOME_WRITE_ROWS:
            self.flush_outcomes()

    def candidate(
        self,
        values: dict[str, Any],
        master_id: int,
        source_id: int,
        observation_source_id: int | None = None,
    ) -> None:
        self.candidates.append(values)
        self.sources[(values["target_record_id"], values["rank"])] = (
            master_id,
            source_id,
            observation_source_id,
        )
        if len(self.candidates) >= CANDIDATE_WRITE_ROWS:
            self.flush_candidates()

    def flush_outcomes(self) -> None:
        if self.outcomes:
            self.db.execute(
                insert(cast(Table, CorrectionTarget.__table__)), self.outcomes
            )
            self.outcomes.clear()

    def flush_candidates(self) -> None:
        if not self.candidates:
            return
        wanted = {source_id for _, source_id, _ in self.sources.values()}
        originals = {
            source_id: data or {}
            for source_id, data in self.db.query(SourceRecord.id, SourceRecord.data)
            .filter(SourceRecord.id.in_(wanted))
            .all()
        }
        if set(originals) != wanted:
            raise ValueError("Observasi sumber kandidat tidak lengkap")
        observations = candidate_observations(self.db, originals)
        returned = self.db.execute(
            insert(cast(Table, MatchCandidate.__table__)).returning(
                MatchCandidate.id, MatchCandidate.target_record_id, MatchCandidate.rank
            ),
            self.candidates,
        )
        evidence = []
        for candidate_id, target_id, rank in returned:
            master_id, source_id, observation_source_id = self.sources[
                (target_id, rank)
            ]
            data = originals[source_id] or {}
            fields = {
                key: value
                for key, value in data.items()
                if key not in {"source_observations", "source_observation_batches"}
            }
            if observation_source_id is not None:
                selected = next(
                    (
                        item
                        for item in observations[source_id]
                        if item["record_id"] == observation_source_id
                    ),
                    None,
                )
                if selected is None:
                    raise ValueError("Sumber koordinat kandidat tidak lengkap")
                fields.update(
                    {
                        key: value
                        for key, value in selected["fields"].items()
                        if value not in (None, "")
                    }
                )
                fields.update(
                    source_record_id=observation_source_id,
                    source_batch_id=selected["batch_id"],
                    source_dataset_type=selected["dataset_type"],
                    coordinate_source_file=selected["filename"],
                    coordinate_source_sheet=selected["source_sheet"],
                    coordinate_source_row=selected["row_number"],
                    coordinate_source_period=selected["fields"].get("tglbaca"),
                )
                if selected["dataset_type"] in {"prabayar", "pascabayar"}:
                    fields["jenis_pel"] = selected["dataset_type"].upper()
                fields["coordinate_max_difference_meters"] = max(
                    (
                        calculate_haversine_distance(
                            fields["lat"],
                            fields["lon"],
                            item["fields"]["lat"],
                            item["fields"]["lon"],
                        )
                        for item in observations[source_id]
                        if item["fields"].get("lat") is not None
                        and item["fields"].get("lon") is not None
                    ),
                    default=0.0,
                )
            evidence.append(
                {
                    "candidate_id": candidate_id,
                    "master_record_id": master_id,
                    "fields": fields,
                    "observations": observations[source_id],
                }
            )
        if len(evidence) != len(self.candidates):
            raise ValueError("Penyimpanan kandidat tidak lengkap")
        self.db.execute(
            insert(cast(Table, CorrectionCandidateEvidence.__table__)), evidence
        )
        self.candidates.clear()
        self.sources.clear()

    def flush(self) -> None:
        self.flush_candidates()
        self.flush_outcomes()

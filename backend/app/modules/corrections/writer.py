"""Bounded bulk writes correlated by target/rank, independent of RETURNING order."""

from typing import Any

from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.models.correction import CorrectionCandidateEvidence, CorrectionTarget
from app.models.matching import MatchCandidate
from app.models.upload import SourceRecord

CANDIDATE_WRITE_ROWS = 400
OUTCOME_WRITE_ROWS = 100


class SearchWriter:
    def __init__(self, db: Session):
        self.db = db
        self.candidates: list[dict[str, Any]] = []
        self.sources: dict[tuple[int, int], tuple[int, int]] = {}
        self.outcomes: list[dict[str, Any]] = []

    def outcome(self, values: dict[str, Any]) -> None:
        self.outcomes.append(values)
        if len(self.outcomes) >= OUTCOME_WRITE_ROWS:
            self.flush_outcomes()

    def candidate(self, values: dict[str, Any], master_id: int, source_id: int) -> None:
        self.candidates.append(values)
        self.sources[(values["target_record_id"], values["rank"])] = (
            master_id,
            source_id,
        )
        if len(self.candidates) >= CANDIDATE_WRITE_ROWS:
            self.flush_candidates()

    def flush_outcomes(self) -> None:
        if self.outcomes:
            self.db.execute(insert(CorrectionTarget.__table__), self.outcomes)
            self.outcomes.clear()

    def flush_candidates(self) -> None:
        if not self.candidates:
            return
        wanted = {source_id for _, source_id in self.sources.values()}
        originals = dict(
            self.db.query(SourceRecord.id, SourceRecord.data)
            .filter(SourceRecord.id.in_(wanted))
            .all()
        )
        if set(originals) != wanted:
            raise ValueError("Observasi sumber kandidat tidak lengkap")
        returned = self.db.execute(
            insert(MatchCandidate.__table__).returning(
                MatchCandidate.id, MatchCandidate.target_record_id, MatchCandidate.rank
            ),
            self.candidates,
        )
        evidence = []
        for candidate_id, target_id, rank in returned:
            master_id, source_id = self.sources[(target_id, rank)]
            data = originals[source_id] or {}
            evidence.append(
                {
                    "candidate_id": candidate_id,
                    "master_record_id": master_id,
                    "fields": {
                        key: value
                        for key, value in data.items()
                        if key != "source_observations"
                    },
                    "observations": data.get("source_observations", []),
                }
            )
        if len(evidence) != len(self.candidates):
            raise ValueError("Penyimpanan kandidat tidak lengkap")
        self.db.execute(insert(CorrectionCandidateEvidence.__table__), evidence)
        self.candidates.clear()
        self.sources.clear()

    def flush(self) -> None:
        self.flush_candidates()
        self.flush_outcomes()

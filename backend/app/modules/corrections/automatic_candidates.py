"""Merge per-target ranked candidates using the existing target/rank index."""

import heapq
from collections import deque
from collections.abc import Iterator
from typing import NamedTuple

from app.models.correction import CorrectionTarget
from app.models.matching import MatchCandidate, MatchingRun
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session


class Pair(NamedTuple):
    distance_meters: float
    id: int
    target_record_id: int
    candidate_idpel: str
    rank: int


def candidate_frontier(
    db: Session,
    run: MatchingRun,
    radius: float,
    protected: set[int],
    selected: dict[int, int],
    tied: set[int],
) -> Iterator[Pair]:
    """Read the nearest edge first, fetching alternatives only for unresolved targets.

    Completed search generations store candidates in nondecreasing distance/rank.
    A correlated index seek starts each target; no global million-row sort is needed.
    """
    columns = (
        MatchCandidate.distance_meters,
        MatchCandidate.id,
        MatchCandidate.target_record_id,
        MatchCandidate.candidate_idpel,
        MatchCandidate.rank,
    )
    first_id = (
        db.query(MatchCandidate.id)
        .filter(
            MatchCandidate.process_id == run.process_id,
            MatchCandidate.generation == run.generation,
            MatchCandidate.target_record_id == CorrectionTarget.source_record_id,
        )
        .order_by(MatchCandidate.rank, MatchCandidate.id)
        .limit(1)
        .correlate(CorrectionTarget)
        .scalar_subquery()
    )
    initial = (
        db.query(*columns)
        .select_from(CorrectionTarget)
        .join(MatchCandidate, MatchCandidate.id == first_id)
        .filter(
            CorrectionTarget.run_id == run.id,
            CorrectionTarget.search_status == "matched",
        )
    )
    frontier = [
        Pair(*row)
        for row in initial
        if row.target_record_id not in protected and 0 <= row.distance_meters <= radius
    ]
    heapq.heapify(frontier)
    pages: dict[int, deque[Pair]] = {}
    while frontier:
        pair = heapq.heappop(frontier)
        record = pair.target_record_id
        if record in selected or record in tied:
            pages.pop(record, None)
            continue
        yield pair
        if record in selected or record in tied:
            pages.pop(record, None)
            continue
        page = pages.get(record)
        if not page:
            query = (
                db.query(*columns)
                .filter(
                    MatchCandidate.process_id == run.process_id,
                    MatchCandidate.generation == run.generation,
                    MatchCandidate.target_record_id == record,
                    MatchCandidate.rank >= pair.rank,
                    or_(
                        MatchCandidate.rank > pair.rank,
                        and_(
                            MatchCandidate.rank == pair.rank,
                            MatchCandidate.id > pair.id,
                        ),
                    ),
                )
                .order_by(MatchCandidate.rank, MatchCandidate.id)
                .limit(16)
            )
            page = deque(Pair(*row) for row in query)
            pages[record] = page
        if page:
            following = page.popleft()
            if following.distance_meters <= radius:
                heapq.heappush(frontier, following)
            else:
                pages.pop(record, None)
        else:
            pages.pop(record, None)

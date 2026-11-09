"""Read inherited immutable candidates in a targeted automatic extension."""

from app.models.matching import MatchCandidate, MatchingRun
from sqlalchemy import and_


def candidate_generations(run: MatchingRun) -> list[int]:
    inherited = (run.processing or {}).get("inherited_candidate_generations", [])
    return sorted(
        {
            run.generation,
            *(
                value
                for value in inherited
                if isinstance(value, int) and 0 < value < run.generation
            ),
        }
    )


def candidate_scope(run: MatchingRun, process_id: int | None = None):
    generations = candidate_generations(run)
    generation = (
        MatchCandidate.generation == generations[0]
        if len(generations) == 1
        else MatchCandidate.generation.in_(generations)
    )
    return and_(
        MatchCandidate.process_id
        == (run.process_id if process_id is None else process_id),
        generation,
    )

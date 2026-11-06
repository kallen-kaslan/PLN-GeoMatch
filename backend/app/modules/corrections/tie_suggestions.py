"""Propose unique pairs at equal distances, preserving the conservative plan."""

from collections import Counter, deque
from itertools import groupby
from typing import Any

from app.models.correction import CorrectionTarget
from app.models.matching import MatchCandidate, MatchingRun
from app.modules.corrections.automatic_candidates import candidate_frontier
from app.modules.corrections.selection_state import identity_owners
from sqlalchemy.orm import Session


def equal_distance_matching(graph: dict[int, dict[str, Any]]) -> dict[int, str]:
    """Deterministic maximum matching for one distance bucket, without recursion."""
    neighbors = {record: sorted(values) for record, values in sorted(graph.items())}
    chosen: dict[int, str] = {}
    owners: dict[str, int] = {}
    while True:
        levels = {record: 0 for record in neighbors if record not in chosen}
        queue = deque(levels)
        available = False
        while queue:
            record = queue.popleft()
            for identity in neighbors[record]:
                owner = owners.get(identity)
                if owner is None:
                    available = True
                elif owner not in levels:
                    levels[owner] = levels[record] + 1
                    queue.append(owner)
        if not available:
            break
        advanced = False
        for root, identities in neighbors.items():
            if root in chosen:
                continue
            stack = [(root, iter(identities))]
            path: list[tuple[int, str]] = []
            while stack:
                record, iterator = stack[-1]
                for identity in iterator:
                    owner = owners.get(identity)
                    if owner is None:
                        chosen[record], owners[identity] = identity, record
                        for previous, edge in reversed(path):
                            chosen[previous], owners[edge] = edge, previous
                        advanced = True
                        stack.clear()
                        break
                    if levels.get(owner) == levels[record] + 1:
                        path.append((record, identity))
                        stack.append((owner, iter(neighbors[owner])))
                        break
                else:
                    levels[record] = -1
                    stack.pop()
                    if path:
                        path.pop()
        if not advanced:
            break
    return chosen


def propose_ties(
    db: Session, run: MatchingRun, radius: float, base: dict[str, Any]
) -> dict[str, Any]:
    remaining = {item["record_id"]: item for item in base["review"]}
    protected = {
        record
        for (record,) in db.query(CorrectionTarget.source_record_id).filter_by(
            run_id=run.id
        )
    } - remaining.keys()
    used = set(identity_owners(db, run.process_id))
    selections = list(base["_selected"].values())
    for offset in range(0, len(selections), 400):
        used.update(
            identity
            for (identity,) in db.query(MatchCandidate.candidate_idpel).filter(
                MatchCandidate.id.in_(selections[offset : offset + 400])
            )
        )
    initially_used = frozenset(used)
    proposed: dict[int, int] = {}
    details: dict[int, Any] = {}
    has_candidate: set[int] = set()
    has_available: set[int] = set()
    pairs = candidate_frontier(db, run, radius, protected, proposed, set())
    for _, bucket in groupby(pairs, key=lambda pair: pair.distance_meters):
        graph: dict[int, dict[str, Any]] = {}
        for pair in bucket:
            record, identity = pair.target_record_id, pair.candidate_idpel
            if not identity:
                continue
            has_candidate.add(record)
            if identity not in initially_used:
                has_available.add(record)
            if record in proposed or identity in used:
                continue
            graph.setdefault(record, {})[identity] = pair
        for record, identity in equal_distance_matching(graph).items():
            pair = graph[record][identity]
            proposed[record], details[record] = pair.id, pair
            used.add(identity)
    suggestions = [
        {
            "record_id": record,
            "row_number": remaining[record]["row_number"],
            "candidate_id": pair.id,
            "idpel": pair.candidate_idpel,
            "distance_meters": pair.distance_meters,
            "needs_verification": True,
        }
        for record, pair in details.items()
    ]
    suggestions.sort(key=lambda item: (item["row_number"], item["record_id"]))
    unpaired = [
        {
            **item,
            "reason": "no_available_idpel"
            if record in has_candidate and record not in has_available
            else "shared_candidates"
            if record in has_candidate
            else item["reason"],
        }
        for record, item in remaining.items()
        if record not in proposed
    ]
    return {
        **base,
        "tie_strategy": "suggest",
        "suggestion_count": len(suggestions),
        "suggestions": suggestions,
        "unpaired_count": len(unpaired),
        "unpaired": unpaired,
        "unpaired_reasons": dict(Counter(item["reason"] for item in unpaired)),
        "_suggestions": proposed,
    }

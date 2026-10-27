"""Stage timings with identifiers/counts only, never source cells or SQL values."""

import inspect
import logging
from collections.abc import Callable
from functools import wraps
from time import perf_counter
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")

logger = logging.getLogger("uvicorn.error.performance")
SAFE_COUNTS = {
    "process_id",
    "batch_id",
    "review_id",
    "total_rows",
    "rows",
    "total_targets",
    "matched_targets",
    "valid_rows",
    "error_rows",
    "total_master_clean",
    "total_master_sisa",
    "total_excluded_by_pdpj",
    "removed_duplicates",
    "run_id",
    "master_batch_id",
    "master_snapshot_id",
}


def timed(stage: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorate(function: Callable[P, R]) -> Callable[P, R]:
        signature = inspect.signature(function)

        @wraps(function)
        def measured(*args: P.args, **kwargs: P.kwargs) -> R:
            started = perf_counter()
            status = "failed"
            counters = {
                key: value
                for key, value in signature.bind(*args, **kwargs).arguments.items()
                if key in SAFE_COUNTS and isinstance(value, int)
            }
            try:
                result = function(*args, **kwargs)
                metrics = (
                    result
                    if isinstance(result, dict)
                    else getattr(result, "__dict__", {})
                )
                if isinstance(metrics, dict):
                    counters.update(
                        {
                            key: value
                            for key, value in metrics.items()
                            if key in SAFE_COUNTS and isinstance(value, int)
                        }
                    )
                    if getattr(
                        type(result), "__tablename__", ""
                    ) == "upload_batches" and isinstance(metrics.get("id"), int):
                        counters["batch_id"] = metrics["id"]
                status = "completed"
                return result
            finally:
                logger.info(
                    "stage=%s status=%s duration_ms=%.3f counts=%s",
                    stage,
                    status,
                    (perf_counter() - started) * 1000,
                    counters,
                )

        return measured

    return decorate

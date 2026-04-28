from __future__ import annotations


class TiktokenEstimator:
    def __init__(self) -> None:
        self._encoding = None
        self._optional_dependency_missing = False
        try:
            import tiktoken  # type: ignore

            self._encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self._optional_dependency_missing = True

    @property
    def warning(self) -> str | None:
        return None

    @property
    def optional_dependency_missing(self) -> bool:
        return self._optional_dependency_missing

    def estimate(self, text: str) -> int | None:
        if not text:
            return 0
        if self._encoding is None:
            return None
        try:
            return len(self._encoding.encode(text))
        except Exception:
            return None


def estimate_with_warnings(text: str, estimator: TiktokenEstimator | None = None) -> tuple[int | None, list[str]]:
    active_estimator = estimator or TiktokenEstimator()
    warnings: list[str] = []
    if active_estimator.warning:
        warnings.append(active_estimator.warning)
    count = active_estimator.estimate(text)
    if count is None and not active_estimator.warning and not active_estimator.optional_dependency_missing:
        warnings.append("Failed to estimate tokens for node.")
    return count, warnings


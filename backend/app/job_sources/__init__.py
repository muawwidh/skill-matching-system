"""Job sources: evaluation, manual and live adapters."""
EVALUATION_SOURCE = "evaluation"
MANUAL_SOURCE = "manual"
NON_LIVE_SOURCES = frozenset({EVALUATION_SOURCE, MANUAL_SOURCE})


def candidate_excluded_sources(config=None) -> frozenset[str]:
    """Sources left out of the candidate Jobs page: evaluation jobs unless enabled."""
    from app.core.config import settings

    config = config or settings
    return frozenset() if config.CANDIDATE_VIEW_INCLUDES_EVALUATION_JOBS else frozenset({EVALUATION_SOURCE})

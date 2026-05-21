"""FixEngine stub — placeholder until Task 2 implementation."""

from ascend_agent.diagnosis.router import ModelRouter


class FixEngine:
    """Generates fix suggestions for diagnosis hypotheses."""

    def __init__(self, router: ModelRouter, repo_path: str):
        self._router = router
        self._repo_path = repo_path

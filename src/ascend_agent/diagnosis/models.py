from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Evidence(BaseModel):
    """A single piece of evidence supporting a hypothesis."""

    model_config = ConfigDict(extra="forbid")

    file_path: str = Field(description="Absolute or repo-relative path to the source file")
    line_number: int = Field(ge=1, description="Line number where the evidence is found")
    code_snippet: str = Field(description="5-10 lines of surrounding code context")
    relevance: str = Field(description="Why this evidence is relevant to the hypothesis")


class Hypothesis(BaseModel):
    """A single diagnosis hypothesis with supporting evidence."""

    model_config = ConfigDict(extra="forbid")

    root_cause: str = Field(description="What went wrong — concise statement of the root cause")
    evidence: list[Evidence] = Field(description="Supporting evidence items (file:line + code snippets)")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0.0 to 1.0")


class SearchAction(BaseModel):
    """A single search the LLM wants to perform."""

    model_config = ConfigDict(extra="forbid")

    pattern: str = Field(description="Regex or function name to search for")
    rationale: str = Field(description="Why this search will help the diagnosis")


class SearchDecision(BaseModel):
    """LLM decides: perform more searches or produce final diagnosis."""

    model_config = ConfigDict(extra="forbid")

    action: str = Field(
        pattern=r"^(search|hypothesize)$",
        description="'search' to continue, 'hypothesize' to produce final diagnosis",
    )
    searches: list[SearchAction] = Field(
        default_factory=list,
        description="Searches to perform. Only set when action='search'. Max 3 searches per iteration.",
    )
    reasoning: str = Field(description="Brief explanation of the decision")


class PartialFailure(BaseModel):
    """Information about a partial failure during diagnosis."""

    model_config = ConfigDict(extra="forbid")

    stage: str = Field(description="Where the failure occurred (e.g., 'search', 'code_read', 'llm_call')")
    reason: str = Field(description="Specific failure reason")
    details: str | None = Field(default=None, description="Additional details (error message, etc.)")


class DiagnosisResult(BaseModel):
    """Final output of the diagnosis engine."""

    model_config = ConfigDict(extra="forbid")

    hypotheses: list[Hypothesis] = Field(
        default_factory=list,
        description="Top 3 hypotheses ranked by confidence (highest first)",
    )
    errors: list[PartialFailure] = Field(
        default_factory=list,
        description="Partial failures encountered. Never empty without explanation (D-04).",
    )
    iterations_used: int = Field(
        default=0, ge=0, le=3, description="Number of search iterations actually used"
    )


class Replacement(BaseModel):
    """A single search-and-replace operation on a file."""

    model_config = ConfigDict(extra="forbid")

    file_path: str = Field(description="Repo-relative path to the file being edited")
    old_text: str = Field(
        description="Exact text to find in the file. Must match uniquely."
    )
    new_text: str = Field(description="Text to replace old_text with")


class FixResponse(BaseModel):
    """Structured output from the LLM for a single hypothesis fix."""

    model_config = ConfigDict(extra="forbid")

    explanation: str = Field(
        description="Clear explanation of what the fix does and why it addresses the root cause"
    )
    replacements: list[Replacement] = Field(
        description="One or more search-and-replace operations to fix the issue. "
        "Multiple replacements in the same file are allowed."
    )


class FixSuggestion(BaseModel):
    """A single fix suggestion for one file."""

    model_config = ConfigDict(extra="forbid")

    file_path: str = Field(
        description="Repo-relative path to the file that needs modification"
    )
    diff_patch: str = Field(
        description="Unified diff patch showing the changes (computed by FixEngine from replacements)"
    )
    explanation: str = Field(
        description="Human-readable explanation of what the fix does and why"
    )
    hypothesis_id: int = Field(
        description="Index of the hypothesis this fix addresses (0-based)"
    )
    replacements: list[Replacement] = Field(
        description="The search-and-replace operations that produce this diff"
    )


class FixGenerationResult(BaseModel):
    """Result of the fix generation process."""

    model_config = ConfigDict(extra="forbid")

    suggestions: list[FixSuggestion] = Field(
        default_factory=list, description="Generated fix suggestions"
    )
    errors: list[PartialFailure] = Field(
        default_factory=list, description="Partial failures during fix generation"
    )
    total_hypotheses: int = Field(
        default=0, description="Total number of hypotheses processed"
    )


class TestDetail(BaseModel):
    """A single test result detail."""

    model_config = ConfigDict(extra="forbid")

    nodeid: str = Field(description="Pytest node ID (e.g., tests/test_foo.py::test_bar)")
    outcome: str = Field(description="Test outcome: passed, failed, error, skipped, xfailed, xpassed")
    duration: float | None = Field(default=None, description="Test duration in seconds")
    message: str | None = Field(default=None, description="Failure/error message if applicable")


class VerificationResult(BaseModel):
    """Structured result from verification execution (D-01 through D-04)."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(
        pattern=r"^(pass|fail|error|timeout|no_tests)$",
        description="Overall verification status",
    )
    hypothesis_id_verified: int = Field(
        description="Index of hypothesis this verification addresses",
    )
    framework: str | None = Field(default=None, description="Detected test framework (e.g., 'pytest') or None if not found")
    command: str = Field(description="The test command that was executed")
    summary: str = Field(description="Human-readable summary of verification results")
    tests_found: int = Field(default=0, description="Number of test files mapped")
    tests_run: int = Field(default=0, description="Number of tests actually executed")
    passed: int = Field(default=0, description="Number of tests that passed")
    failed: int = Field(default=0, description="Number of tests that failed")
    errors: int = Field(default=0, description="Number of tests that errored")
    skipped: int = Field(default=0, description="Number of tests skipped")
    xfailed: int = Field(default=0, description="Number of expected failures")
    xpassed: int = Field(default=0, description="Number of unexpected passes")
    tests: list[TestDetail] = Field(default_factory=list, description="Per-test details (empty if no tests)")
    exit_code: int = Field(default=-1, description="pytest process exit code")
    duration_seconds: float = Field(ge=0.0, description="Wall-clock duration of test execution")
    files_tested: list[str] = Field(default_factory=list, description="Repo-relative paths of test files that were executed")
    stdout: str = Field(default="", description="Raw test output (if parsing fails)")

    @model_validator(mode="after")
    def _derive_test_counts(self) -> "VerificationResult":
        """Populate summary counters from per-test details when omitted."""
        if self.tests and not any(
            [self.tests_run, self.passed, self.failed, self.errors, self.skipped, self.xfailed, self.xpassed]
        ):
            counts: dict[str, int] = {}
            for test in self.tests:
                counts[test.outcome] = counts.get(test.outcome, 0) + 1
            self.passed = counts.get("passed", 0)
            self.failed = counts.get("failed", 0)
            self.errors = counts.get("error", 0) + counts.get("errors", 0)
            self.skipped = counts.get("skipped", 0)
            self.xfailed = counts.get("xfailed", 0)
            self.xpassed = counts.get("xpassed", 0)
            self.tests_run = sum(counts.values())
        return self


class ReproductionAttempt(BaseModel):
    """One command attempted during reproduction."""

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(description="Attempt type, e.g. existing_command or generated_bad_case")
    command: str = Field(default="", description="Command that was executed")
    repro_file: str = Field(default="", description="Repo-relative generated repro file, if any")
    status: str = Field(default="", description="Raw execution status")
    exit_code: int = Field(default=-1, description="Process exit code")
    matched_error: bool = Field(default=False, description="Whether this attempt matched the original error")
    matched_signal: str = Field(default="", description="The error signal matched in command output")
    summary: str = Field(default="", description="Short human-readable attempt summary")


class ReproductionResult(BaseModel):
    """Structured result from reproduction execution (D-11, D-12)."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(
        pattern=r"^(success|fail|error)$",
        description="Outcome: success (exit 0), fail (non-zero exit), error (execution failure)",
    )
    command: str = Field(description="The command that was executed")
    stdout: str = Field(default="", description="Standard output captured")
    stderr: str = Field(default="", description="Standard error captured")
    exit_code: int = Field(default=-1, description="Process exit code")
    duration_seconds: float = Field(ge=0.0, description="Wall-clock duration of command execution")
    hypothesis_id_tested: int = Field(
        ge=-1, description="Index of hypothesis this test addresses (-1 if none)"
    )
    repo_path: str = Field(
        default="", description="Repo-absolute path to the target repository"
    )
    files_changed: list[str] = Field(
        default_factory=list,
        description="List of repo-relative paths to files modified during reproduction",
    )
    reproduced: bool = Field(
        default=False,
        description="True when a failing command matched the original error signal",
    )
    repro_file: str = Field(
        default="", description="Repo-relative generated bad-case file path, if any"
    )
    matched_error: bool = Field(
        default=False, description="Whether output matched the original error signal"
    )
    matched_error_signal: str = Field(
        default="", description="Error signal matched in stdout/stderr"
    )
    attempts: list[ReproductionAttempt] = Field(
        default_factory=list, description="Executed reproduction attempts"
    )


class DiagnosisOutput(BaseModel):
    """Wrapper for diagnosis output combining context document and diagnosis result."""

    model_config = ConfigDict(extra="forbid")

    context_doc: "ContextDocument" = Field(
        description="The context document with repo, trace, and config information"
    )
    diagnosis_result: DiagnosisResult = Field(description="The diagnosis result")


# Resolve forward reference for ContextDocument at runtime.
# Import is deferred to avoid circular imports.
def _rebuild_diagnosis_output():
    from ascend_agent.context.models import ContextDocument  # noqa: F811

    DiagnosisOutput.model_rebuild()


_rebuild_diagnosis_output()

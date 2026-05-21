from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


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


class DiagnosisOutput(BaseModel):
    """Wrapper for diagnosis output combining context document and diagnosis result."""

    model_config = ConfigDict(extra="forbid")

    context_doc: "ContextDocument" = Field(
        description="The context document with repo, trace, and config information"
    )
    diagnosis_result: DiagnosisResult = Field(description="The diagnosis result")

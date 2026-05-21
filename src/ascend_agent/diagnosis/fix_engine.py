"""FixEngine — generates unified diff fix suggestions from diagnosis hypotheses.

Follows the Engine class pattern from Phase 2: constructor takes
router + repo_path, public method returns structured result with
error handling via PartialFailure.
"""

import difflib
import logging
from pathlib import Path
from typing import Optional

from ascend_agent.diagnosis.models import (
    DiagnosisResult,
    FixGenerationResult,
    FixResponse,
    FixSuggestion,
    PartialFailure,
    Replacement,
)
from ascend_agent.diagnosis.router import ModelRouter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fix system prompt
# ---------------------------------------------------------------------------

_FIX_SYSTEM_PROMPT = (
    "You are a Python code fixing expert. Given a diagnosis hypothesis with "
    "evidence, re-read the relevant code context and generate a precise fix.\n\n"
    "Output search-and-replace operations (old_text -> new_text) where old_text "
    "is an exact byte-for-byte match of the original file content. Include enough "
    "surrounding context (2-3 lines around the change) in old_text to ensure "
    "unique matching.\n\n"
    "Rules:\n"
    "1. old_text must be an exact byte-for-byte match — copy it exactly from the file.\n"
    "2. Include 2-3 lines of surrounding context for uniqueness.\n"
    "3. If the fix requires changes in multiple locations in the same file, "
    "include multiple replacements.\n"
    "4. Explain what the fix does and why it addresses the root cause."
)


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def _build_fix_user_prompt(hypothesis, code_context: str) -> str:
    """Build the user message for a single hypothesis fix generation.

    Args:
        hypothesis: A Hypothesis instance with root_cause and evidence.
        code_context: Re-read code context string from _read_code_context.

    Returns:
        A formatted user prompt string.
    """
    lines = [
        "Generate a fix for the following diagnosis hypothesis.",
        "",
        f"Root cause: {hypothesis.root_cause}",
        "",
        "Evidence:",
    ]
    for ev in hypothesis.evidence:
        lines.append(f"  - {ev.file_path}:{ev.line_number} — {ev.relevance}")
        if ev.code_snippet:
            lines.append(f"    Code: {ev.code_snippet}")
    lines.append("")
    if code_context:
        lines.append("Relevant code context (re-read from source):")
        lines.append(code_context)
        lines.append("")
    lines.append(
        "Output search-and-replace operations with old_text being an exact "
        "match of the original file content. Do NOT change the old_text "
        "content — copy it exactly from the file. old_text must include "
        "2-3 lines of surrounding context for uniqueness."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# FixEngine
# ---------------------------------------------------------------------------


class FixEngine:
    """Generates fix suggestions for diagnosis hypotheses.

    Follows the Engine pattern from Phase 2: constructor takes
    router + repo_path, public method returns structured result.
    """

    def __init__(self, router: ModelRouter, repo_path: str):
        self._router = router
        self._repo_path_resolved = Path(repo_path).resolve()

    # -- Public API ----------------------------------------------------------

    def generate_fixes(self, diagnosis: DiagnosisResult) -> FixGenerationResult:
        """Generate fix suggestions for all hypotheses in the diagnosis.

        For each hypothesis with evidence, re-read the relevant code,
        call the LLM to generate a fix, validate, and produce a FixSuggestion
        with a unified diff patch (D-05: generate for ALL hypotheses).

        Args:
            diagnosis: DiagnosisResult with ranked hypotheses and evidence.

        Returns:
            FixGenerationResult with suggestions, errors, and total count.
        """
        suggestions: list[FixSuggestion] = []
        errors: list[PartialFailure] = []

        for idx, hypothesis in enumerate(diagnosis.hypotheses):
            try:
                suggestion = self._generate_for_hypothesis(hypothesis, idx)
                if suggestion is not None:
                    suggestions.append(suggestion)
            except Exception as exc:
                logger.warning(
                    "Fix generation failed for hypothesis %d: %s", idx, exc
                )
                errors.append(
                    PartialFailure(
                        stage="fix_generation",
                        reason=str(exc),
                        details=f"Hypothesis: {hypothesis.root_cause[:100]}",
                    )
                )

        return FixGenerationResult(
            suggestions=suggestions,
            errors=errors,
            total_hypotheses=len(diagnosis.hypotheses),
        )

    # -- Internal: single hypothesis fix ------------------------------------

    def _generate_for_hypothesis(
        self, hypothesis, hypothesis_id: int
    ) -> Optional[FixSuggestion]:
        """Generate a fix for a single hypothesis.

        Steps (per D-06/D-08):
        1. Read relevant code from evidence file:line references
        2. Call LLM with code context + hypothesis
        3. Validate LLM output (old_text exists, unique match)
        4. Compute unified diff from original -> modified
        5. Return FixSuggestion

        Args:
            hypothesis: Hypothesiss instance with root_cause and evidence.
            hypothesis_id: 0-based index of the hypothesis.

        Returns:
            FixSuggestion if successful, None if no code context or
            LLM output is malformed (D-08: single-shot, skip on failure).
        """
        # Step 1: Read code context from evidence
        code_context = self._read_code_context(hypothesis)
        if not code_context:
            logger.info(
                "No code context available for hypothesis %d, skipping",
                hypothesis_id,
            )
            return None

        # Step 2: LLM generates fix
        try:
            llm_response: FixResponse = self._router.completion(
                messages=[
                    {"role": "system", "content": _FIX_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": _build_fix_user_prompt(
                            hypothesis=hypothesis,
                            code_context=code_context,
                        ),
                    },
                ],
                response_model=FixResponse,
                max_tokens=4096,
                temperature=0.1,
            )
        except Exception as exc:
            logger.warning(
                "LLM call failed for hypothesis %d: %s", hypothesis_id, exc
            )
            return None

        # Step 3: Validate replacements
        valid_replacements: list[Replacement] = []
        for replacement in llm_response.replacements:
            resolved_path = (
                self._repo_path_resolved / replacement.file_path
            ).resolve()

            # Path traversal protection
            if not str(resolved_path).startswith(
                str(self._repo_path_resolved)
            ):
                logger.warning(
                    "Path traversal blocked: %s resolves outside repo",
                    replacement.file_path,
                )
                continue

            if not resolved_path.exists():
                logger.warning(
                    "File not found: %s (%s)",
                    replacement.file_path,
                    resolved_path,
                )
                continue

            original_text = resolved_path.read_text()
            if replacement.old_text not in original_text:
                logger.warning(
                    "old_text not found in %s — skipping replacement",
                    replacement.file_path,
                )
                continue

            if original_text.count(replacement.old_text) > 1:
                logger.warning(
                    "old_text appears %d times in %s — "
                    "include more context for uniqueness",
                    original_text.count(replacement.old_text),
                    replacement.file_path,
                )
                continue

            valid_replacements.append(replacement)

        if not valid_replacements:
            logger.info(
                "No valid replacements for hypothesis %d, skipping",
                hypothesis_id,
            )
            return None

        # Step 4: Compute unified diff for human display
        # Apply all valid replacements in-memory
        first_rep = valid_replacements[0]
        resolved_path = (
            self._repo_path_resolved / first_rep.file_path
        ).resolve()
        original = resolved_path.read_text()
        modified = original
        for rep in valid_replacements:
            modified = modified.replace(rep.old_text, rep.new_text, 1)

        diff_lines = difflib.unified_diff(
            original.splitlines(keepends=True),
            modified.splitlines(keepends=True),
            fromfile=first_rep.file_path,
            tofile=first_rep.file_path,
        )
        diff_patch = "".join(diff_lines)

        # Step 5: Return FixSuggestion
        return FixSuggestion(
            file_path=first_rep.file_path,
            diff_patch=diff_patch,
            explanation=llm_response.explanation,
            hypothesis_id=hypothesis_id,
            replacements=valid_replacements,
        )

    # -- Internal: code re-reading ------------------------------------------

    def _read_code_context(self, hypothesis) -> str:
        """Read code context from hypothesis evidence using _read_function_body.

        For each evidence item, resolve the file path relative to the repo,
        and extract the function body at the target line with surrounding context.

        Args:
            hypothesis: Hypothesis instance with evidence list.

        Returns:
            A formatted string with code context parts joined by double newlines,
            or empty string if no context could be read.
        """
        # Local import to avoid circular dependency
        from ascend_agent.diagnosis.engine import _read_function_body

        context_parts: list[str] = []
        for evidence in hypothesis.evidence:
            full_path = (
                self._repo_path_resolved / evidence.file_path
            ).resolve()

            # Path traversal protection
            if not str(full_path).startswith(str(self._repo_path_resolved)):
                logger.warning(
                    "Path traversal blocked: %s resolves outside repo",
                    evidence.file_path,
                )
                continue

            snippet = _read_function_body(
                str(full_path), evidence.line_number, context_lines=5
            )
            if snippet:
                context_parts.append(
                    f"--- {evidence.file_path}:{evidence.line_number} ---\n"
                    f"{snippet}"
                )

        return "\n\n".join(context_parts)

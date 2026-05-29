"""Core diagnosis engine — LLM-driven search loop with code exploration.

The Engine orchestrates up to 3 LLM search iterations, calls the
code_search tool for source code lookups, reads function bodies at
±5 lines scope, and produces ranked hypotheses with evidence.
"""

import asyncio
import ast
import logging
import re
from pathlib import Path
from typing import Awaitable, Callable

from ascend_agent.diagnosis.models import (
    DiagnosisResult,
    Hypothesis,
    PartialFailure,
    SearchDecision,
)
from ascend_agent.diagnosis.router import ModelRouter

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 3
MAX_TRACE_SOURCE_SNIPPETS = 5
SearchTool = Callable[[str, str], Awaitable[str]]

# ---------------------------------------------------------------------------
# Utility: function body extraction
# ---------------------------------------------------------------------------


def _read_function_body(
    file_path: str, target_line: int, context_lines: int = 5
) -> str | None:
    """Read a function body ±N lines of surrounding context.

    Uses Python AST to find the exact function containing *target_line*,
    then extracts source lines for that function's body plus *context_lines*
    of surrounding context above and below.

    Args:
        file_path: Path to the Python source file.
        target_line: The line number (1-indexed) of interest.
        context_lines: Number of extra lines above/below the function body.

    Returns:
        A newline-joined string with ``{line_no}:{code}`` prefix per line,
        or *None* if the file cannot be read.
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        lines = source.splitlines()
    except (FileNotFoundError, OSError):
        return None

    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Fallback: line-based window when AST parsing fails
        return _line_window(lines, target_line, context_lines)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.lineno <= target_line <= node.end_lineno:
                start = max(0, node.lineno - 1 - context_lines)
                end = min(len(lines), node.end_lineno + context_lines)
                return _format_lines(lines, start, end)

    # Fallback: target line is not inside any function
    return _line_window(lines, target_line, context_lines)


def _line_window(lines: list[str], target_line: int, context_lines: int) -> str:
    """Return a ±N line window around *target_line*."""
    start = max(0, target_line - 1 - context_lines)
    end = min(len(lines), target_line + context_lines)
    return _format_lines(lines, start, end)


def _format_lines(lines: list[str], start: int, end: int) -> str:
    """Format a slice of lines with ``{line_no}:{code}`` prefix."""
    return "\n".join(
        f"{i + 1}:{lines[i]}" for i in range(start, end)
    )


def _relative_to_repo(path: Path, repo_path: Path) -> str:
    try:
        return path.relative_to(repo_path).as_posix()
    except ValueError:
        return path.as_posix()


def _resolve_frame_file(frame_file: str | None, repo_path: Path) -> Path | None:
    """Resolve a trace frame path into a file inside the repository.

    Tracebacks often contain absolute paths from another checkout or container.
    If the exact path is unavailable, try suffixes against the current repo.
    """
    if not frame_file:
        return None

    raw_path = Path(frame_file)
    candidates: list[Path] = []

    if raw_path.is_absolute():
        try:
            resolved = raw_path.resolve()
            if resolved.exists() and str(resolved).startswith(str(repo_path)):
                return resolved
        except OSError:
            pass
        parts = raw_path.parts
        for idx in range(1, len(parts)):
            suffix = Path(*parts[idx:])
            candidates.append(repo_path / suffix)
    else:
        candidates.append(repo_path / raw_path)

    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.exists() and str(resolved).startswith(str(repo_path)):
            return resolved

    basename_matches = list(repo_path.rglob(raw_path.name))
    existing_matches = [
        match.resolve()
        for match in basename_matches
        if match.is_file() and str(match.resolve()).startswith(str(repo_path))
    ]
    if len(existing_matches) == 1:
        return existing_matches[0]

    return None


def _collect_trace_source_context(context_doc, repo_path: Path) -> str:
    """Read source snippets for stack frames before the first LLM call."""
    trace = getattr(context_doc, "trace", None)
    if not trace or not getattr(trace, "frames", None):
        return ""

    snippets: list[str] = []
    seen: set[tuple[str, int]] = set()
    for frame in trace.frames:
        if frame.line is None:
            continue
        resolved = _resolve_frame_file(frame.file, repo_path)
        if resolved is None:
            continue
        key = (resolved.as_posix(), frame.line)
        if key in seen:
            continue
        seen.add(key)

        snippet = _read_function_body(str(resolved), frame.line)
        if not snippet:
            continue
        rel_path = _relative_to_repo(resolved, repo_path)
        snippets.append(
            f"--- {rel_path}:{frame.line} in {frame.function or '?'} ---\n{snippet}"
        )
        if len(snippets) >= MAX_TRACE_SOURCE_SNIPPETS:
            break

    if not snippets:
        return ""
    return "Source Context From Stack Trace:\n" + "\n\n".join(snippets)


def _normalize_evidence_snippet(snippet: str) -> str:
    """Normalize LLM snippets for comparison against source text."""
    lines = []
    for line in snippet.splitlines():
        lines.append(re.sub(r"^\s*\d+:\s?", "", line).rstrip())
    return "\n".join(lines).strip()


def _snippet_exists_in_source(snippet: str, source: str) -> bool:
    normalized = _normalize_evidence_snippet(snippet)
    if not normalized:
        return False
    if normalized in source:
        return True

    source_lines = [line.strip() for line in source.splitlines()]
    snippet_lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    return all(line in source_lines for line in snippet_lines)


def _validate_evidence_item(evidence, repo_path: Path) -> tuple[bool, str | None]:
    resolved = _resolve_frame_file(evidence.file_path, repo_path)
    if resolved is None:
        return False, "evidence file not found in repository"

    try:
        source = resolved.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return False, f"evidence file unreadable: {exc}"

    lines = source.splitlines()
    if evidence.line_number > len(lines):
        return False, "evidence line number is outside the file"

    if not _snippet_exists_in_source(evidence.code_snippet, source):
        return False, "evidence snippet not found in file"

    return True, None


def _validate_diagnosis_evidence(
    result: DiagnosisResult, repo_path: Path
) -> DiagnosisResult:
    """Drop hypotheses whose evidence cannot be verified locally."""
    if not result.hypotheses:
        return result

    valid_hypotheses: list[Hypothesis] = []
    errors = list(result.errors)
    for index, hypothesis in enumerate(result.hypotheses):
        valid_evidence = []
        if not hypothesis.evidence:
            errors.append(
                PartialFailure(
                    stage="evidence_validation",
                    reason="hypothesis has no evidence",
                    details=f"Hypothesis {index}: {hypothesis.root_cause[:120]}",
                )
            )
            continue

        for evidence in hypothesis.evidence:
            is_valid, reason = _validate_evidence_item(evidence, repo_path)
            if is_valid:
                valid_evidence.append(evidence)
                continue
            errors.append(
                PartialFailure(
                    stage="evidence_validation",
                    reason=reason or "invalid evidence",
                    details=f"{evidence.file_path}:{evidence.line_number}",
                )
            )

        if valid_evidence:
            valid_hypotheses.append(
                hypothesis.model_copy(update={"evidence": valid_evidence})
            )

    return result.model_copy(
        update={"hypotheses": valid_hypotheses, "errors": errors}
    )


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def _build_system_prompt() -> str:
    """Construct the system prompt for the LLM."""
    return (
        "You are a Python debugging expert. Analyze the following stack trace "
        "and source code to diagnose the root cause of the error.\n\n"
        "Do not ask clarifying questions. You have up to 3 searches to gather "
        "code context. After each search result, decide: search again with a "
        "more specific pattern, or produce your top 3 hypotheses ranked by "
        "confidence.\n\n"
        "Each hypothesis must include:\n"
        "- A concise root cause statement\n"
        "- Supporting evidence with file:line references and code snippets\n"
        "- A confidence score between 0.0 and 1.0\n\n"
        "When you have enough information, output 'hypothesize' to produce "
        "the final diagnosis. If you need more information, output 'search' "
        "with specific patterns to explore."
    )


def _build_user_prompt(context_doc) -> str:
    """Format the user message from a ContextDocument."""
    trace = context_doc.trace
    repo = context_doc.repo

    lines = []
    if trace:
        lines.append(f"Error type: {trace.error_type or 'unknown'}")
        lines.append(f"Error message: {trace.error_message or 'unknown'}")
        lines.append("")
        lines.append("Stack trace frames:")
        for i, frame in enumerate(trace.frames, 1):
            file_str = frame.file or "?"
            line_str = str(frame.line) if frame.line else "?"
            func_str = frame.function or "?"
            lines.append(f"  {i}. {file_str}:{line_str} in {func_str}")
            lines.append(f"     {frame.text}")
    else:
        lines.append("No trace information available.")

    if repo:
        lines.append("")
        lines.append(f"Repository path: {repo.path}")
        lines.append(f"Repository language: {repo.language}")

    return "\n".join(lines)


def _format_search_history(search_history: list[dict]) -> str:
    """Format accumulated search results into a readable text block."""
    if not search_history:
        return ""

    parts = ["\n\n--- Search History ---"]
    for i, entry in enumerate(search_history, 1):
        parts.append(f"\nSearch {i}: pattern=\"{entry['pattern']}\"")
        if "error" in entry.get("result", {}):
            parts.append(f"  [FAILED] {entry['result']['error']}")
        elif isinstance(entry.get("result"), str):
            result_str = entry["result"]
            # Truncate very long results
            if len(result_str) > 2000:
                result_str = result_str[:2000] + "\n... (truncated)"
            parts.append(f"  {result_str}")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class Engine:
    """Orchestrates the LLM-driven diagnosis search loop.

    The Engine receives a ContextDocument, runs up to *MAX_ITERATIONS*
    LLM-directed code searches, and produces a DiagnosisResult with
    ranked hypotheses and evidence.
    """

    def __init__(
        self,
        router: ModelRouter,
        repo_path: str,
        search_tool: SearchTool | None = None,
    ):
        self._router = router
        self._repo_path_resolved = Path(repo_path).resolve()
        if search_tool is None:
            from ascend_agent.tools.code_search import search_code

            self._search_tool = search_code
        else:
            self._search_tool = search_tool

    # -- Public API ----------------------------------------------------------

    def diagnose(self, context_doc) -> DiagnosisResult:
        """Run the diagnosis loop. Returns a structured result."""
        messages = [
            {"role": "system", "content": _build_system_prompt()},
            {"role": "user", "content": _build_user_prompt(context_doc)},
        ]
        trace_source_context = _collect_trace_source_context(
            context_doc, self._repo_path_resolved
        )
        if trace_source_context:
            messages.append({"role": "user", "content": trace_source_context})
        search_history: list[dict] = []
        iterations_used = 0

        for iteration in range(1, MAX_ITERATIONS + 1):
            iterations_used = iteration
            logger.info(
                "Diagnosis iteration %d/%d", iteration, MAX_ITERATIONS
            )

            search_context = _format_search_history(search_history)
            decision_messages = messages
            if search_context:
                decision_messages = messages + [
                    {"role": "user", "content": search_context}
                ]

            try:
                decision: SearchDecision = self._router.completion(
                    messages=decision_messages,
                    response_model=SearchDecision,
                    max_tokens=4096,
                )
            except Exception as exc:
                logger.warning(
                    "LLM call failed at iteration %d: %s", iteration, exc
                )
                # Continue with budget exhaustion path
                iterations_used = iteration
                break

            if decision.action == "hypothesize":
                logger.info(
                    "LLM decided to produce diagnosis after %d iterations",
                    iteration,
                )
                return self._generate_hypotheses(
                    messages, search_history, iterations_used
                )

            # Execute searches up to safety limit per iteration
            for search in decision.searches[:3]:
                result = self._execute_search(search.pattern)
                search_history.append(
                    {"pattern": search.pattern, "result": result}
                )

        # Budget exhausted — force hypothesis with available data
        logger.info("Search budget exhausted, producing final diagnosis")
        return self._generate_hypotheses(
            messages, search_history, iterations_used, exhausted=True
        )

    # -- Internal helpers ----------------------------------------------------

    def _generate_hypotheses(
        self,
        initial_messages: list[dict],
        search_history: list[dict],
        iterations_used: int,
        exhausted: bool = False,
    ) -> DiagnosisResult:
        """Generate the final diagnosis from accumulated context."""
        extra = (
            "Generate your best hypotheses with available information."
            if exhausted
            else ""
        )
        prompt = (
            f"Generate your top 3 ranked hypotheses with evidence. {extra}"
        ).strip()

        search_context = _format_search_history(search_history)
        hypothesis_messages = list(initial_messages)
        if search_context:
            hypothesis_messages.append(
                {"role": "user", "content": search_context}
            )
        hypothesis_messages.append(
            {"role": "user", "content": prompt}
        )

        try:
            result: DiagnosisResult = self._router.completion(
                messages=hypothesis_messages,
                response_model=DiagnosisResult,
                max_tokens=8192,
            )
            result = _validate_diagnosis_evidence(
                result, self._repo_path_resolved
            )
        except Exception as exc:
            logger.error("Hypothesis generation failed: %s", exc)
            result = DiagnosisResult(
                hypotheses=[],
                errors=[
                    PartialFailure(
                        stage="hypothesis_generation",
                        reason="LLM call failed",
                        details=str(exc),
                    )
                ],
                iterations_used=iterations_used,
            )

        return result

    def _execute_search(self, pattern: str) -> dict:
        """Execute a code search in the repository.

        Returns a dict with either ``{"result": str}`` on success or
        ``{"error": str}`` on failure.
        """
        try:
            # Safely run async code: prefer asyncio.run() unless already in an event loop
            async def _do_search():
                return await self._search_tool(
                    pattern, str(self._repo_path_resolved)
                )
            try:
                result_str = asyncio.run(_do_search())
            except RuntimeError:
                # Already in a running event loop — create a new task and wait
                loop = asyncio.get_running_loop()
                result_str = loop.run_until_complete(asyncio.ensure_future(_do_search()))
            # Try to enrich with function body context
            enriched = self._enrich_with_function_bodies(
                result_str, pattern
            )
            return {"result": enriched}
        except Exception as exc:
            logger.warning(
                "Search failed for '%s': %s", pattern, exc
            )
            return {"error": str(exc)}

    def _enrich_with_function_bodies(
        self, search_result: str, pattern: str
    ) -> str:
        """Try to read function bodies for matched lines in search results."""
        # Parse search result for file:line entries
        lines = search_result.split("\n")
        enriched_lines = list(lines)
        extra_snippets: list[str] = []

        for line in lines:
            if not line.strip():
                continue
            # Search result format: "path/file.py:line_no:code_content"
            parts = line.split(":", 2)
            if len(parts) >= 2:
                file_path_candidate = parts[0]
                try:
                    line_no = int(parts[1])
                except ValueError:
                    continue

                full_path = (
                    self._repo_path_resolved / file_path_candidate
                )
                snippet = _read_function_body(
                    str(full_path), line_no
                )
                if snippet and snippet not in extra_snippets:
                    extra_snippets.append(
                        f"\n--- Context for {file_path_candidate}:{line_no} ---\n{snippet}"
                    )

        if extra_snippets:
            enriched_lines.append("\n\n### Function body context:")
            enriched_lines.extend(extra_snippets)

        return "\n".join(enriched_lines)

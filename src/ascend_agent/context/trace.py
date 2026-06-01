import pathlib
import re
import sys

from ascend_agent.context.models import TraceCause, TraceEntry, TraceInfo

_frame_pattern = re.compile(
    r'File "(?P<file>[^"]+)", line (?P<line>\d+)(?:, in (?P<function>\S+))?'
)

_python_error_pattern = re.compile(
    r"(?P<type>(?:\w+(?:\.\w+)*\.)?(?:ExceptionGroup|\w*(?:Error|Exception|Warning|Interrupt|Exit))):?\s*(?P<message>.*)"
)

_generic_log_error_pattern = re.compile(
    r"^(?:\[[^\]]*(?:ERROR|FATAL|CRITICAL)[^\]]*\]|(?:ERROR|FATAL|CRITICAL)\b)[:\]\s-]*(?P<message>.*)$",
    flags=re.IGNORECASE,
)

_generic_error_phrase_pattern = re.compile(
    r"\b(?P<kind>error|failed|failure|fatal|critical)\b[:\s-]*(?P<message>.*)",
    flags=re.IGNORECASE,
)

_ascend_error_pattern = re.compile(
    r"(?P<message>.*(?:error code is|retCode=|error_code=)\s*[A-Za-z0-9_-]+.*)",
    flags=re.IGNORECASE,
)

_pytest_failed_pattern = re.compile(
    r"^FAILED\s+(?P<file>[^:\s]+)::(?P<function>[^\s]+)\s+-\s+(?P<rest>.*)$"
)


def parse_stack_trace(raw_text: str) -> TraceInfo:
    frames = []
    python_errors: list[tuple[str, str]] = []
    pytest_errors: list[tuple[str, str]] = []
    ascend_errors: list[tuple[str, str]] = []
    log_errors: list[tuple[str, str]] = []
    phrase_errors: list[tuple[str, str]] = []
    parse_warnings: list[str] = []

    for match in _frame_pattern.finditer(raw_text):
        frames.append(TraceEntry(
            file=match.group("file"),
            line=int(match.group("line")),
            function=match.group("function"),
            text=match.group(0),
        ))

    for line in raw_text.strip().split("\n"):
        failed_match = _pytest_failed_pattern.match(line.strip())
        if failed_match:
            rest = failed_match.group("rest")
            line_no = _extract_pytest_line_number(rest)
            parsed_pytest_error = _parse_pytest_failure_error(rest)
            if parsed_pytest_error:
                pytest_errors.append(parsed_pytest_error)
            frames.append(
                TraceEntry(
                    file=failed_match.group("file"),
                    line=line_no,
                    function=failed_match.group("function"),
                    text=line.strip(),
                )
            )

        parsed_python_error = _parse_python_error_line(line)
        if parsed_python_error:
            python_errors.append(parsed_python_error)
            continue

        parsed_ascend_error = _parse_ascend_error_line(line)
        if parsed_ascend_error:
            ascend_errors.append(parsed_ascend_error)
            continue

        parsed_log_error = _parse_log_error_line(line)
        if parsed_log_error:
            log_errors.append(parsed_log_error)
            continue

        parsed_phrase_error = _parse_error_phrase_line(line)
        if parsed_phrase_error:
            phrase_errors.append(parsed_phrase_error)

    errors = _select_error_layer(
        python_errors=python_errors,
        pytest_errors=pytest_errors,
        ascend_errors=ascend_errors,
        log_errors=log_errors,
        phrase_errors=phrase_errors,
    )
    error_type, error_message = _select_primary_error(errors)
    causes = _extract_causes(python_errors, error_type, error_message)
    runtime_signals = _extract_runtime_signals(raw_text)

    if raw_text and not errors:
        parse_warnings.append("no_error_line_detected")

    return TraceInfo(
        error_type=error_type,
        error_message=error_message,
        frames=frames,
        causes=causes,
        runtime_signals=runtime_signals,
        parse_warnings=parse_warnings,
        raw_text=raw_text,
    )


def _clean_error_line(line: str) -> str:
    cleaned = line.strip()
    cleaned = re.sub(r"^[\s|+\\-]*", "", cleaned)
    cleaned = re.sub(r"^E\s+", "", cleaned)
    return cleaned


def _parse_python_error_line(line: str) -> tuple[str, str] | None:
    cleaned = _clean_error_line(line)
    if cleaned.startswith("raise ") or "Traceback" in cleaned:
        return None

    match = _python_error_pattern.match(cleaned)
    if not match:
        return None
    return match.group("type"), match.group("message").strip()


def _parse_pytest_failure_error(text: str) -> tuple[str, str] | None:
    parsed = _parse_python_error_line(text)
    if parsed:
        return parsed
    if "AssertionError" in text:
        return "AssertionError", text.strip()
    return None


def _parse_ascend_error_line(line: str) -> tuple[str, str] | None:
    cleaned = _clean_error_line(line)
    match = _ascend_error_pattern.search(cleaned)
    if not match:
        return None
    return "AscendRuntimeError", match.group("message").strip()


def _parse_log_error_line(line: str) -> tuple[str, str] | None:
    cleaned = _clean_error_line(line)
    match = _generic_log_error_pattern.match(cleaned)
    if not match:
        return None
    message = match.group("message").strip() or cleaned
    return "LogError", message


def _parse_error_phrase_line(line: str) -> tuple[str, str] | None:
    cleaned = _clean_error_line(line)
    if not cleaned or cleaned.startswith("Traceback"):
        return None
    match = _generic_error_phrase_pattern.search(cleaned)
    if not match:
        return None
    message = match.group("message").strip() or cleaned
    kind = match.group("kind").lower()
    if kind in {"failed", "failure"}:
        return "Failure", message
    return "LogError", message


def _select_error_layer(
    *,
    python_errors: list[tuple[str, str]],
    pytest_errors: list[tuple[str, str]],
    ascend_errors: list[tuple[str, str]],
    log_errors: list[tuple[str, str]],
    phrase_errors: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    for layer in (
        python_errors,
        pytest_errors,
        ascend_errors,
        log_errors,
        phrase_errors,
    ):
        if layer:
            return layer
    return []


def _select_primary_error(errors: list[tuple[str, str]]) -> tuple[str | None, str | None]:
    if not errors:
        return None, None

    for error_type, error_message in errors:
        if error_type == "ExceptionGroup":
            return error_type, error_message

    return errors[-1]


def _extract_causes(
    errors: list[tuple[str, str]],
    primary_type: str | None,
    primary_message: str | None,
) -> list[TraceCause]:
    causes = []
    for error_type, error_message in errors:
        if error_type == primary_type and error_message == primary_message:
            continue
        if error_type == "ExceptionGroup":
            continue
        causes.append(
            TraceCause(error_type=error_type, error_message=error_message)
        )
    return causes


def _extract_runtime_signals(raw_text: str) -> dict[str, str]:
    signals = {}
    patterns = {
        "error_code": r"(?:error code is|retCode=|error_code=)\s*(?P<value>[A-Za-z0-9_-]+)",
        "rank_id": r"(?:rank_id=|rank\[)\s*(?P<value>\d+)",
        "device_id": r"(?:device_id=|device\[)\s*(?P<value>\d+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, raw_text, flags=re.IGNORECASE)
        if match:
            signals[key] = match.group("value")
    return signals


def _extract_pytest_line_number(text: str) -> int:
    match = re.search(r":(?P<line>\d+):", text)
    if match:
        return int(match.group("line"))
    return 1


def trace_from_file(path: str | pathlib.Path) -> TraceInfo:
    resolved = pathlib.Path(path).resolve()
    text = resolved.read_text(encoding="utf-8", errors="replace")
    return parse_stack_trace(text)


def trace_from_stdin() -> TraceInfo:
    text = sys.stdin.read()
    return parse_stack_trace(text)


def trace_from_text(text: str) -> TraceInfo:
    return parse_stack_trace(text)

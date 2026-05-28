import pathlib
import re
import sys

from ascend_agent.context.models import TraceCause, TraceEntry, TraceInfo

_frame_pattern = re.compile(
    r'File "(?P<file>[^"]+)", line (?P<line>\d+)(?:, in (?P<function>\S+))?'
)

_error_pattern = re.compile(
    r"(?P<type>(?:\w+(?:\.\w+)*\.)?(?:ExceptionGroup|\w*(?:Error|Exception|Warning|Interrupt|Exit))):?\s*(?P<message>.*)"
)

_pytest_failed_pattern = re.compile(
    r"^FAILED\s+(?P<file>[^:\s]+)::(?P<function>[^\s]+)\s+-\s+(?P<rest>.*)$"
)


def parse_stack_trace(raw_text: str) -> TraceInfo:
    frames = []
    errors: list[tuple[str, str]] = []
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
            frames.append(
                TraceEntry(
                    file=failed_match.group("file"),
                    line=line_no,
                    function=failed_match.group("function"),
                    text=line.strip(),
                )
            )

        parsed_error = _parse_error_line(line)
        if parsed_error:
            errors.append(parsed_error)

    error_type, error_message = _select_primary_error(errors)
    causes = _extract_causes(errors, error_type, error_message)
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


def _parse_error_line(line: str) -> tuple[str, str] | None:
    cleaned = line.strip()
    cleaned = re.sub(r"^[\s|+\\-]*", "", cleaned)
    cleaned = re.sub(r"^E\s+", "", cleaned)
    if cleaned.startswith("raise ") or "Traceback" in cleaned:
        return None

    match = _error_pattern.match(cleaned)
    if not match:
        return None
    return match.group("type"), match.group("message").strip()


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

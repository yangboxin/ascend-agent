import pathlib
import re
import sys

from ascend_agent.context.models import TraceEntry, TraceInfo

_frame_pattern = re.compile(
    r'File "(?P<file>[^"]+)", line (?P<line>\d+)(?:, in (?P<function>\S+))?'
)

_error_pattern = re.compile(
    r'(?P<type>\w+(?:\.\w+)*)(Error|Exception|Warning|Interrupt|Exit):?\s*(?P<message>.*)'
)


def parse_stack_trace(raw_text: str) -> TraceInfo:
    frames = []
    error_type = None
    error_message = None

    for match in _frame_pattern.finditer(raw_text):
        frames.append(TraceEntry(
            file=match.group("file"),
            line=int(match.group("line")),
            function=match.group("function"),
            text=match.group(0),
        ))

    for line in raw_text.strip().split("\n"):
        match = _error_pattern.search(line)
        if match:
            base = match.group("type")
            suffix = match.group(2)
            if base.endswith(suffix):
                error_type = base
            else:
                error_type = base + suffix
            error_message = match.group("message").strip()
            break

    return TraceInfo(
        error_type=error_type,
        error_message=error_message,
        frames=frames,
        raw_text=raw_text,
    )


def trace_from_file(path: str | pathlib.Path) -> TraceInfo:
    resolved = pathlib.Path(path).resolve()
    text = resolved.read_text(encoding="utf-8", errors="replace")
    return parse_stack_trace(text)


def trace_from_stdin() -> TraceInfo:
    text = sys.stdin.read()
    return parse_stack_trace(text)


def trace_from_text(text: str) -> TraceInfo:
    return parse_stack_trace(text)

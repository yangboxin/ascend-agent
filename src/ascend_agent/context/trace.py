import pathlib
import re
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher

from ascend_agent.context.models import (
    TraceCause,
    TraceEntry,
    TraceErrorEvent,
    TraceInfo,
    TraceSignalCandidate,
)

_frame_pattern = re.compile(
    r'File "(?P<file>[^"]+)", line (?P<line>\d+)(?:, in (?P<function>\S+))?'
)

_ocr_frame_pattern = re.compile(
    r"File\s+[\"'“”’‘]?(?P<file>/[^\"'“”’‘\t]+?\.py)[\"'“”’‘]?"
    r"[,，\]\s]*(?:line|Line|\[ine|tine)\s+(?P<line>\d+)"
    r"(?:[,，\s]+in\s+(?P<function>[A-Za-z_][\w ]{0,80}))?",
    flags=re.IGNORECASE,
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

_ascend_actionable_pattern = re.compile(
    r"(?:rt\w*(?:mencpy|memcpy|stream|event|query)|acl\w*|synchroni[sz]e|"
    r"current capture (?:mode|node)|model stream execute failed|"
    r"does not support this operation|runtime result|ErrCode|InnerCode|EE9999)",
    flags=re.IGNORECASE,
)

_generic_exception_noise_pattern = re.compile(
    r"^(?:Error:\s*Exception|Exception raised from query\b)",
    flags=re.IGNORECASE,
)


@dataclass
class _ParsedError:
    kind: str
    error_type: str
    message: str
    confidence: float
    source_line: int
    source_text: str

_FUZZY_ERROR_TYPES = (
    "RuntimeError",
    "ValueError",
    "AssertionError",
    "TypeError",
    "ImportError",
    "ModuleNotFoundError",
    "ExceptionGroup",
)

_FUZZY_RUNTIME_SYMBOLS = (
    "aclrtSynchronize",
    "rtStreamSynchronize",
    "aclrtMemcpy",
    "HCCL",
    "CANN",
    "Ascend",
    "retCode",
)

_OCR_ALPHA_TRANSLATION = str.maketrans(
    {
        "0": "o",
        "1": "l",
        "3": "e",
        "5": "s",
        "7": "t",
        "8": "b",
        "|": "l",
    }
)
_OCR_DIGIT_TRANSLATION = str.maketrans(
    {
        "O": "0",
        "o": "0",
        "I": "1",
        "l": "1",
        "S": "5",
        "s": "5",
        "B": "8",
    }
)


def parse_stack_trace(raw_text: str) -> TraceInfo:
    frames = _extract_frames(raw_text)
    python_errors: list[_ParsedError] = []
    pytest_errors: list[_ParsedError] = []
    ascend_errors: list[_ParsedError] = []
    log_errors: list[_ParsedError] = []
    phrase_errors: list[_ParsedError] = []
    parse_warnings: list[str] = []

    for line_no, line in enumerate(raw_text.strip().split("\n"), 1):
        failed_match = _pytest_failed_pattern.match(line.strip())
        if failed_match:
            rest = failed_match.group("rest")
            test_line_no = _extract_pytest_line_number(rest)
            parsed_pytest_error = _parse_pytest_failure_error(rest)
            if parsed_pytest_error:
                pytest_errors.append(
                    _make_error(
                        "pytest_failure",
                        parsed_pytest_error[0],
                        parsed_pytest_error[1],
                        0.9,
                        line_no,
                        line,
                    )
                )
            frames.append(
                TraceEntry(
                    file=failed_match.group("file"),
                    line=test_line_no,
                    function=failed_match.group("function"),
                    text=line.strip(),
                )
            )

        parsed_python_error = _parse_python_error_line(line)
        if parsed_python_error:
            confidence = 0.45 if _is_generic_exception_noise(line) else 0.85
            python_errors.append(
                _make_error(
                    "python_exception",
                    parsed_python_error[0],
                    parsed_python_error[1],
                    confidence,
                    line_no,
                    line,
                )
            )
            continue

        parsed_ascend_error = _parse_ascend_error_line(line)
        if parsed_ascend_error:
            ascend_errors.append(
                _make_error(
                    "ascend_runtime",
                    parsed_ascend_error[0],
                    parsed_ascend_error[1],
                    0.95,
                    line_no,
                    line,
                )
            )
            continue

        parsed_log_error = _parse_log_error_line(line)
        if parsed_log_error:
            log_errors.append(
                _make_error(
                    "log_error",
                    parsed_log_error[0],
                    parsed_log_error[1],
                    0.65,
                    line_no,
                    line,
                )
            )
            continue

        parsed_phrase_error = _parse_error_phrase_line(line)
        if parsed_phrase_error:
            phrase_errors.append(
                _make_error(
                    "error_phrase",
                    parsed_phrase_error[0],
                    parsed_phrase_error[1],
                    0.55,
                    line_no,
                    line,
                )
            )

    errors = _select_error_layer(
        python_errors=python_errors,
        pytest_errors=pytest_errors,
        ascend_errors=ascend_errors,
        log_errors=log_errors,
        phrase_errors=phrase_errors,
    )
    error_type, error_message = _select_primary_error(errors)
    causes = _extract_causes(
        [(error.error_type, error.message) for error in python_errors],
        error_type,
        error_message,
    )
    runtime_signals = _extract_runtime_signals(raw_text)
    error_events = _to_trace_error_events(errors)
    signal_candidates = _extract_signal_candidates(
        raw_text,
        runtime_signals=runtime_signals,
        known_error_type=error_type,
    )

    if raw_text and not errors:
        parse_warnings.append("no_error_line_detected")
    if signal_candidates:
        parse_warnings.append("uncertain_signal_candidates")

    return TraceInfo(
        error_type=error_type,
        error_message=error_message,
        frames=frames,
        causes=causes,
        runtime_signals=runtime_signals,
        signal_candidates=signal_candidates,
        error_events=error_events,
        parse_warnings=parse_warnings,
        raw_text=raw_text,
    )


def _extract_frames(raw_text: str) -> list[TraceEntry]:
    frames: list[TraceEntry] = []
    seen: set[tuple[str | None, int | None, str | None, str]] = set()
    standard_spans: list[tuple[int, int]] = []

    def add(file: str | None, line: int | None, function: str | None, text: str):
        normalized_function = _normalize_function_name(function)
        key = (file, line, normalized_function, text)
        if key in seen:
            return
        seen.add(key)
        frames.append(
            TraceEntry(
                file=file,
                line=line,
                function=normalized_function,
                text=text,
            )
        )

    for match in _frame_pattern.finditer(raw_text):
        standard_spans.append(match.span())
        add(
            match.group("file"),
            int(match.group("line")),
            match.group("function"),
            match.group(0),
        )

    for match in _ocr_frame_pattern.finditer(raw_text):
        if any(
            match.start() >= start and match.end() <= end
            for start, end in standard_spans
        ):
            continue
        add(
            _normalize_ocr_path(match.group("file")),
            int(match.group("line")),
            match.group("function"),
            match.group(0),
        )

    return frames


def _normalize_ocr_path(path: str) -> str:
    cleaned = path.strip()
    cleaned = cleaned.replace(" ", "_")
    cleaned = cleaned.replace("/vllm_workspace/", "/vllm-workspace/")
    cleaned = cleaned.replace("/vltm_workspace/", "/vllm-workspace/")
    cleaned = cleaned.replace("/vilm-workspace/", "/vllm-workspace/")
    cleaned = cleaned.replace("/vlla-workspace/", "/vllm-workspace/")
    cleaned = cleaned.replace("/LLm_workspace/", "/vllm-workspace/")
    cleaned = cleaned.replace("/Vlla-ascend/", "/vllm-ascend/")
    cleaned = cleaned.replace("/VlIn_ascend/", "/vllm_ascend/")
    cleaned = cleaned.replace("/vilm_ascend/", "/vllm_ascend/")
    cleaned = cleaned.replace("/vlla_ascend/", "/vllm_ascend/")
    cleaned = cleaned.replace("/vllm-workspace/vllm_ascend/", "/vllm-workspace/vllm-ascend/")
    cleaned = cleaned.replace("/vllm-workspace/vlla_ascend/", "/vllm-workspace/vllm-ascend/")
    cleaned = cleaned.replace("/Vllm_ascend/", "/vllm_ascend/")
    cleaned = cleaned.replace("/Vlla_ascend/", "/vllm_ascend/")
    cleaned = cleaned.replace("/vlla_ascend/", "/vllm_ascend/")
    cleaned = cleaned.replace("/Vllm/", "/vllm/")
    cleaned = cleaned.replace("/Vlla/", "/vllm/")
    cleaned = cleaned.replace("/VlLa/", "/vllm/")
    return cleaned


def _normalize_function_name(function: str | None) -> str | None:
    if not function:
        return function
    cleaned = function.strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned[:80] or None


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


def _is_generic_exception_noise(line: str) -> bool:
    return _generic_exception_noise_pattern.search(_clean_error_line(line)) is not None


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
    if match:
        return "AscendRuntimeError", match.group("message").strip()

    if not _ascend_actionable_pattern.search(cleaned):
        return None
    if re.search(r"\b(?:INFO|metrics|throughput|cache hit)\b", cleaned, re.IGNORECASE):
        return None
    return "AscendRuntimeError", cleaned


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
    python_errors: list[_ParsedError],
    pytest_errors: list[_ParsedError],
    ascend_errors: list[_ParsedError],
    log_errors: list[_ParsedError],
    phrase_errors: list[_ParsedError],
) -> list[_ParsedError]:
    actionable_python = [
        error for error in python_errors
        if error.confidence >= 0.7 and not _is_low_value_event(error)
    ]
    if actionable_python and (
        not ascend_errors
        or min(error.source_line for error in actionable_python)
        < min(error.source_line for error in ascend_errors)
    ):
        return python_errors

    actionable_ascend = [
        error for error in ascend_errors
        if error.confidence >= 0.7 and not _is_low_value_event(error)
    ]
    if actionable_ascend:
        earliest_line = min(error.source_line for error in actionable_ascend)
        return [
            error
            for error in actionable_ascend
            if error.source_line == earliest_line
        ]
    if pytest_errors:
        return pytest_errors
    if python_errors:
        return python_errors
    candidates = log_errors + phrase_errors
    if candidates:
        best = max(candidates, key=lambda error: (error.confidence, -error.source_line))
        return [best]
    return []


def _select_primary_error(errors: list[_ParsedError]) -> tuple[str | None, str | None]:
    if not errors:
        return None, None

    for error in errors:
        if error.error_type == "ExceptionGroup":
            return error.error_type, error.message

    if all(error.kind == "python_exception" for error in errors):
        primary = errors[-1]
        return primary.error_type, primary.message

    primary = max(errors, key=lambda error: (error.confidence, -error.source_line))
    return primary.error_type, primary.message


def _make_error(
    kind: str,
    error_type: str,
    message: str,
    confidence: float,
    source_line: int,
    source_text: str,
) -> _ParsedError:
    return _ParsedError(
        kind=kind,
        error_type=error_type,
        message=message.strip(),
        confidence=confidence,
        source_line=source_line,
        source_text=source_text.strip()[:500],
    )


def _is_low_value_event(error: _ParsedError) -> bool:
    text = f"{error.error_type}: {error.message}"
    return _generic_exception_noise_pattern.search(text) is not None


def _to_trace_error_events(errors: list[_ParsedError]) -> list[TraceErrorEvent]:
    return [
        TraceErrorEvent(
            kind=error.kind,
            message=error.message,
            confidence=round(error.confidence, 2),
            source_line=error.source_line,
            source_text=error.source_text,
        )
        for error in errors
    ]


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


def _normalize_for_fuzzy_alpha(text: str) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "",
        text.lower().translate(_OCR_ALPHA_TRANSLATION),
    )


def _normalize_for_fuzzy_digits(text: str) -> str:
    return text.translate(_OCR_DIGIT_TRANSLATION)


def _similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left, right).ratio()


def _best_substring_similarity(needle: str, haystack: str) -> float:
    if not needle or not haystack:
        return 0.0
    if needle in haystack:
        return 1.0
    if len(haystack) <= len(needle):
        return _similarity(needle, haystack)

    best = 0.0
    window = len(needle)
    for index in range(0, len(haystack) - window + 1):
        best = max(best, _similarity(needle, haystack[index : index + window]))
        if best >= 0.98:
            break
    return best


def _extract_signal_candidates(
    raw_text: str,
    *,
    runtime_signals: dict[str, str],
    known_error_type: str | None,
) -> list[TraceSignalCandidate]:
    candidates: list[TraceSignalCandidate] = []
    seen: set[tuple[str, str, str]] = set()

    def add(kind: str, value: str, confidence: float, source_text: str, reason: str):
        key = (kind, value, source_text)
        if key in seen:
            return
        seen.add(key)
        candidates.append(
            TraceSignalCandidate(
                kind=kind,
                value=value,
                confidence=round(confidence, 2),
                source_text=source_text[:240],
                reason=reason,
            )
        )

    for line in raw_text.splitlines():
        cleaned = _clean_error_line(line)
        if not cleaned:
            continue
        normalized = _normalize_for_fuzzy_alpha(cleaned)

        for error_type in _FUZZY_ERROR_TYPES:
            if error_type == known_error_type:
                continue
            score = _best_substring_similarity(
                _normalize_for_fuzzy_alpha(error_type), normalized
            )
            if score >= 0.86:
                add(
                    "error_type",
                    error_type,
                    score,
                    cleaned,
                    "fuzzy OCR-tolerant error type match",
                )

        for symbol in _FUZZY_RUNTIME_SYMBOLS:
            if symbol.lower() in cleaned.lower():
                continue
            score = _best_substring_similarity(
                _normalize_for_fuzzy_alpha(symbol), normalized
            )
            if score >= 0.84:
                confidence = score if symbol.lower() in cleaned.lower() else min(score, 0.9)
                add(
                    "runtime_symbol",
                    symbol,
                    confidence,
                    cleaned,
                    "fuzzy OCR-tolerant runtime symbol match",
                )

        digit_normalized = _normalize_for_fuzzy_digits(cleaned)
        for match in re.finditer(
            r"(?:retC[o0]de|error[_ ]?c[o0]de(?: is)?|c[o0]de)\s*[=:]?\s*(?P<value>[A-Za-z0-9_-]{4,})",
            digit_normalized,
            flags=re.IGNORECASE,
        ):
            value = match.group("value")
            if value == runtime_signals.get("error_code"):
                continue
            confidence = 0.82 if re.search(r"[A-Za-z]", match.group(0)) else 0.9
            add(
                "error_code",
                value,
                confidence,
                cleaned,
                "OCR-normalized error code candidate",
            )

    return candidates


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

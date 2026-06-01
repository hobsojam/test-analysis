import json
from pathlib import Path
import re
from typing import Any, Iterable

from tqa.models import (
    ComponentReport,
    FileReport,
    LineData,
    MutantData,
    normalise_status,
)
from tqa.parsers.base import Parser
from tqa.parsers.registry import register_parser


@register_parser("mutant")
class MutantParser(Parser):
    def parse(self, path: str, report: ComponentReport) -> ComponentReport:
        """Parse native Mutant session JSON from a file or .mutant/results directory."""
        for session_path in _session_paths(path):
            try:
                with open(session_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Failed to parse Mutant report '{session_path}': {exc}"
                ) from exc
            except OSError as exc:
                raise FileNotFoundError(
                    f"Mutant report not found: '{session_path}'"
                ) from exc
            for result, parents in _mutation_results(data):
                mutant = _extract_mutant(result, parents)
                if mutant is None:
                    continue
                file_path, line, mutant_data = mutant
                file_path = _normalize_path(file_path)
                if file_path not in report.files:
                    report.files[file_path] = FileReport(file_path=file_path)
                file_report = report.files[file_path]
                if line not in file_report.lines:
                    file_report.lines[line] = LineData(line_number=line)
                file_report.lines[line].mutants.append(mutant_data)
        return report


def _session_paths(path: str) -> Iterable[Path]:
    root = Path(path)
    if root.is_dir():
        yield from sorted(p for p in root.glob("*.json") if p.is_file())
    else:
        yield root


def _normalize_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    if normalized.startswith("/work/"):
        return normalized.removeprefix("/work/")
    return normalized


def _mutation_results(
    data: Any,
    parents: tuple[dict[str, Any], ...] = (),
) -> Iterable[tuple[dict[str, Any], tuple[dict[str, Any], ...]]]:
    if isinstance(data, dict):
        if _looks_like_mutation_result(data):
            yield data, parents
            return
        next_parents = parents + (data,)
        for value in data.values():
            yield from _mutation_results(value, next_parents)
    elif isinstance(data, list):
        for item in data:
            yield from _mutation_results(item, parents)


def _looks_like_mutation_result(data: dict[str, Any]) -> bool:
    if isinstance(data.get("mutation_result"), dict) and isinstance(
        data.get("criteria_result"), dict
    ):
        return True
    if "mutation" in data or "mutant" in data:
        return _status_from(data) is not None
    keys = set(data)
    return (
        bool({"operator", "operator_name", "mutator", "diff"} & keys)
        and _status_from(data) is not None
    )


def _extract_mutant(
    result: dict[str, Any],
    parents: tuple[dict[str, Any], ...],
) -> tuple[str, int, MutantData] | None:
    mutation = _first_dict(
        result.get("mutation_result"),
        result.get("mutation"),
        result.get("mutant"),
        result,
    )
    contexts = (mutation, result, *reversed(parents))
    file_path = _first_string(
        contexts,
        "source_path",
        "path",
        "file",
        "filename",
        "source_file",
    )
    line = _first_int(contexts, "source_line", "line", "line_number", "lineno")
    if file_path is None or line is None:
        return None

    raw_status = _status_from(result)
    if raw_status is None:
        return None
    status = normalise_status(raw_status)
    mutant_id = (
        _first_string(
            (mutation, result),
            "id",
            "index",
            "uuid",
            "mutation_identification",
        )
        or f"mutant-{file_path}:{line}:{raw_status}"
    )
    description = _description(mutation, result, parents)

    return (
        file_path,
        line,
        MutantData(
            id=str(mutant_id),
            status=status,
            line=line,
            description=description,
        ),
    )


def _first_dict(*values: Any) -> dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def _first_string(contexts: Iterable[dict[str, Any]], *keys: str) -> str | None:
    for context in contexts:
        for key in keys:
            value = context.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _first_int(contexts: Iterable[dict[str, Any]], *keys: str) -> int | None:
    for context in contexts:
        for key in keys:
            value = context.get(key)
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)
        result = _line_from_location(context) or _line_from_identification(context)
        if result is not None:
            return result
    return None


def _line_from_location(context: dict[str, Any]) -> int | None:
    location = context.get("location")
    if not isinstance(location, dict):
        return None
    start = location.get("start")
    if not isinstance(start, dict):
        return None
    value = start.get("line")
    return value if isinstance(value, int) else None


def _line_from_identification(context: dict[str, Any]) -> int | None:
    identification = context.get("mutation_identification") or context.get(
        "identification"
    )
    if not isinstance(identification, str):
        return None
    match = re.search(r":(\d+):[^:]+$", identification)
    return int(match.group(1)) if match else None


def _status_from_criteria(criteria: dict[str, Any]) -> str:
    if criteria.get("test_result"):
        return "killed"
    if criteria.get("timeout"):
        return "timeout"
    if criteria.get("process_abort"):
        return "error"
    return "survived"


def _status_from(result: dict[str, Any]) -> str | None:
    criteria = result.get("criteria_result")
    if isinstance(criteria, dict):
        return _status_from_criteria(criteria)

    for key in ("status", "result", "state", "outcome"):
        value = result.get(key)
        if isinstance(value, str):
            return value
    for key in ("test_result", "tests", "runtime_result"):
        nested = result.get(key)
        if isinstance(nested, dict):
            status = _status_from(nested)
            if status is not None:
                return status
    return None


def _description(
    mutation: dict[str, Any],
    result: dict[str, Any],
    parents: tuple[dict[str, Any], ...],
) -> str | None:
    parts = []
    operator = _first_string(
        (mutation, result),
        "operator_name",
        "operator",
        "mutator",
        "mutator_name",
        "mutation_type",
        "name",
    )
    if operator:
        parts.append(operator)

    subject = _subject_description(result, parents)
    if subject and subject not in parts:
        parts.append(subject)

    diff_summary = _diff_summary(
        _first_string((mutation, result), "diff", "source_diff", "mutation_diff")
    )
    if diff_summary:
        parts.append(diff_summary)

    if not parts:
        return None
    return " | ".join(parts)


def _diff_summary(diff: str | None) -> str | None:
    if not diff:
        return None
    changes = [
        line.strip()
        for line in diff.splitlines()
        if line.startswith(("-", "+")) and not line.startswith(("---", "+++"))
    ]
    if not changes:
        return None
    return " ".join(changes[:2])


def _subject_description(
    result: dict[str, Any],
    parents: tuple[dict[str, Any], ...],
) -> str | None:
    for context in (*reversed(parents), result):
        subject = context.get("subject")
        if isinstance(subject, str) and subject:
            return subject
        if isinstance(subject, dict):
            value = _first_string((subject,), "identification", "name")
            if value:
                return value
    return _first_string((*reversed(parents), result), "identification", "name")


def parse_mutant(json_path: str, report: ComponentReport) -> ComponentReport:
    return MutantParser().parse(json_path, report)

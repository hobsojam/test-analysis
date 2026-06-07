"""JSON formatter for TQA analysis results.

Emits machine-readable JSON suitable for scripting and downstream tooling.
"""

import json
from datetime import datetime, timezone
from typing import Any

from tqa.engine import AnalysisEngine
from tqa.formatters.surviving_mutants import source_line_text
from tqa.models import ComponentReport, FileReport, MutantStatus, ProjectReport


def _file_lines(file_report: FileReport) -> list[dict[str, Any]]:
    """Return per-line data only for lines that have mutation data."""
    result = []
    for line_num in sorted(file_report.lines):
        line_data = file_report.lines[line_num]
        if not line_data.mutants:
            continue
        killed = sum(1 for m in line_data.mutants if m.status in (MutantStatus.KILLED, MutantStatus.TIMED_OUT))
        survived = len(line_data.mutants) - killed
        result.append(
            {
                "line": line_num,
                "is_covered": line_data.is_covered,
                "killed": killed,
                "survived": survived,
                "mutators": [
                    m.description
                    for m in line_data.mutants
                    if m.description is not None
                ],
            }
        )
    return result


def _file_entry(file_path: str, file_report: FileReport) -> dict[str, Any]:
    return {
        "path": file_path,
        "line_coverage": file_report.line_coverage,
        "test_strength": file_report.test_strength
        if file_report.has_mutation_data
        else None,
        "lines": _file_lines(file_report),
    }


def _component_entry(component: ComponentReport) -> dict[str, Any]:
    return {
        "tsi": component.total_test_strength if component.has_mutation_data else None,
        "has_mutation_data": component.has_mutation_data,
        "files": {
            file_path: _file_entry(file_path, file_report)
            for file_path, file_report in component.files.items()
        },
    }


def _surviving_mutant_entry(finding: dict) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "component": finding["component"],
        "file": finding["file"],
        "line": finding["line"],
        "is_covered": finding["covered"],
        "killed": finding["killed"],
        "survived": finding["survived"],
        "total": finding["total"],
        "all_survived": finding["all_survived"],
        "mutators": [
            m.get("description")
            for m in finding["mutants"]
            if m.get("description") is not None
        ],
        "suggestion": finding.get("suggestion"),
    }
    source = source_line_text(finding)
    if source is not None:
        entry["source_line"] = source
    return entry


def generate_json_report(report: ProjectReport) -> dict[str, Any]:
    """Return a dict representing the full analysis result in machine-readable form."""
    engine = AnalysisEngine()
    surviving_mutants = engine.get_surviving_mutants(report)
    critical_gaps = [
        {"file": f["file"], "line": f["line"], "survived": f["survived"]}
        for f in surviving_mutants
        if f["covered"] and f["all_survived"]
    ]

    return {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "tsi": report.total_test_strength if report.has_mutation_data else None,
        "components": {
            name: _component_entry(component)
            for name, component in report.components.items()
        },
        "surviving_mutants": [_surviving_mutant_entry(f) for f in surviving_mutants],
        "critical_gaps": critical_gaps,
    }


def print_json_report(report: ProjectReport) -> str:
    """Serialise the analysis result to a JSON string and return it."""
    data = generate_json_report(report)
    return json.dumps(data, indent=2, sort_keys=True)

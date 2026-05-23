import json
from pathlib import Path
from typing import Any

from tqa.engine import AnalysisEngine
from tqa.formatters.surviving_mutants import (
    mutant_count_label,
    mutator_descriptions,
    sorted_surviving_findings,
    suggestion_label,
)
from tqa.models import ProjectReport

SONARCLOUD_REPORT_PATH = "sonar-generic-issues.json"
TQA_ENGINE_ID = "tqa"
SURVIVING_MUTANT_RULE_ID = "surviving-mutant"


def generate_sonarcloud_report(report: ProjectReport) -> dict[str, Any]:
    """Return SonarCloud generic issue data for surviving mutant findings."""
    findings = AnalysisEngine().get_surviving_mutants(report)
    return {
        "rules": [_surviving_mutant_rule()],
        "issues": [
            _issue_for_finding(finding)
            for finding in sorted_surviving_findings(findings)
        ],
    }


def write_sonarcloud_report(
    report: ProjectReport,
    path: str = SONARCLOUD_REPORT_PATH,
) -> None:
    data = generate_sonarcloud_report(report)
    Path(path).write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _surviving_mutant_rule() -> dict[str, Any]:
    return {
        "id": SURVIVING_MUTANT_RULE_ID,
        "name": "Surviving mutant",
        "description": (
            "A mutation survived the test suite. Add or strengthen tests so the "
            "mutated behavior is detected."
        ),
        "engineId": TQA_ENGINE_ID,
        "cleanCodeAttribute": "TESTED",
        "impacts": [
            {
                "softwareQuality": "MAINTAINABILITY",
                "severity": "HIGH",
            }
        ],
    }


def _issue_for_finding(finding: dict) -> dict[str, Any]:
    return {
        "ruleId": SURVIVING_MUTANT_RULE_ID,
        "effortMinutes": _effort_minutes(finding),
        "primaryLocation": {
            "message": _issue_message(finding),
            "filePath": finding["file"],
            "textRange": {
                "startLine": finding["line"],
                "endLine": finding["line"],
            },
        },
    }


def _effort_minutes(finding: dict) -> int:
    return 20 if finding["all_survived"] else 10


def _issue_message(finding: dict) -> str:
    return (
        f"Surviving mutant: {mutant_count_label(finding)}. "
        f"Mutator: {mutator_descriptions(finding)}. "
        f"Suggested test focus: {suggestion_label(finding)}"
    )

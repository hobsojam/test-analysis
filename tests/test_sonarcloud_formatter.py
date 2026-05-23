import json
from pathlib import Path

from click.testing import CliRunner

from tqa.cli import main
from tqa.formatters.sonarcloud import (
    SONARCLOUD_REPORT_PATH,
    generate_sonarcloud_report,
)
from tqa.models import ComponentReport, FileReport, LineData, MutantData, ProjectReport


def _report_with_survivors() -> ProjectReport:
    report = ProjectReport()
    component = ComponentReport()
    component.files["src/api.py"] = FileReport(file_path="src/api.py")
    component.files["src/api.py"].lines[12] = LineData(
        line_number=12,
        is_covered=True,
        mutants=[
            MutantData(id="1", status="Killed", line=12, description="ArithmeticOperator"),
            MutantData(id="2", status="Survived", line=12, description="ConditionalBoundary"),
        ],
    )
    report.components["default"] = component
    return report


def test_sonarcloud_report_contains_rules_and_issues():
    data = generate_sonarcloud_report(_report_with_survivors())

    assert data["rules"] == [
        {
            "id": "surviving-mutant",
            "name": "Surviving mutant",
            "description": (
                "A mutation survived the test suite. Add or strengthen tests so the "
                "mutated behavior is detected."
            ),
            "engineId": "tqa",
            "cleanCodeAttribute": "TESTED",
            "impacts": [
                {
                    "softwareQuality": "MAINTAINABILITY",
                    "severity": "HIGH",
                }
            ],
        }
    ]
    assert data["issues"] == [
        {
            "ruleId": "surviving-mutant",
            "effortMinutes": 10,
            "primaryLocation": {
                "message": (
                    "Surviving mutant: 1 killed, 1/2 survived. "
                    "Mutator: ConditionalBoundary. "
                    "Suggested test focus: Add branch or boundary-value tests "
                    "that distinguish each side of this condition."
                ),
                "filePath": "src/api.py",
                "textRange": {
                    "startLine": 12,
                    "endLine": 12,
                },
            },
        }
    ]


def test_sonarcloud_report_is_empty_when_no_survivors():
    report = ProjectReport()
    component = ComponentReport()
    component.files["src/api.py"] = FileReport(file_path="src/api.py")
    component.files["src/api.py"].lines[12] = LineData(
        line_number=12,
        is_covered=True,
        mutants=[MutantData(id="1", status="Killed", line=12)],
    )
    report.components["default"] = component

    data = generate_sonarcloud_report(report)

    assert len(data["rules"]) == 1
    assert data["issues"] == []


def test_cli_sonarcloud_format_writes_json_and_markdown(tmp_path):
    runner = CliRunner()
    coverage = Path.cwd() / "tests" / "sample_cobertura.xml"
    stryker = Path.cwd() / "tests" / "sample_stryker.json"

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            main,
            [
                "analyze",
                "--coverage",
                str(coverage),
                "--stryker",
                str(stryker),
                "--format",
                "sonarcloud",
            ],
        )
        written = Path(SONARCLOUD_REPORT_PATH)
        data = json.loads(written.read_text(encoding="utf-8"))

    assert result.exit_code == 0
    assert "TQA Report Summary" in result.output
    assert "Wrote sonar-generic-issues.json" in result.stderr
    assert written.name == "sonar-generic-issues.json"
    assert data["rules"][0]["engineId"] == "tqa"
    assert data["issues"][0]["primaryLocation"]["filePath"] == "src/auth.py"

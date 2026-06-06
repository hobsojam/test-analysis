"""Tests for the JSON formatter."""

import json

import pytest
from click.testing import CliRunner

from tqa.cli import main
from tqa.formatters.json_formatter import generate_json_report, print_json_report
from tqa.models import (
    ComponentReport,
    FileReport,
    LineData,
    MutantData,
    MutantStatus,
    ProjectReport,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _report_with_survivors() -> ProjectReport:
    report = ProjectReport()
    component = ComponentReport()
    component.files["src/api.py"] = FileReport(file_path="src/api.py")
    component.files["src/api.py"].lines[12] = LineData(
        line_number=12,
        is_covered=True,
        mutants=[
            MutantData(
                id="1", status="Killed", line=12, description="ArithmeticOperator"
            ),
            MutantData(
                id="2", status="Survived", line=12, description="ConditionalBoundary"
            ),
        ],
    )
    report.components["default"] = component
    return report


def _coverage_only_report() -> ProjectReport:
    """A report that has coverage data but no mutation data."""
    report = ProjectReport()
    component = ComponentReport()
    component.files["src/utils.py"] = FileReport(file_path="src/utils.py")
    component.files["src/utils.py"].lines[1] = LineData(line_number=1, is_covered=True)
    component.files["src/utils.py"].lines[2] = LineData(line_number=2, is_covered=False)
    report.components["default"] = component
    return report


# ---------------------------------------------------------------------------
# generate_json_report – structure
# ---------------------------------------------------------------------------


def test_json_report_top_level_keys():
    data = generate_json_report(_report_with_survivors())
    for key in (
        "generated_at",
        "tsi",
        "components",
        "surviving_mutants",
        "critical_gaps",
    ):
        assert key in data


def test_json_report_tsi_is_float_when_mutation_data_present():
    data = generate_json_report(_report_with_survivors())
    assert isinstance(data["tsi"], float)


def test_json_report_tsi_is_null_without_mutation_data():
    data = generate_json_report(_coverage_only_report())
    assert data["tsi"] is None


def test_json_report_generated_at_is_iso_string():
    data = generate_json_report(_report_with_survivors())
    ts = data["generated_at"]
    # Should parse without error and contain timezone info
    from datetime import datetime

    parsed = datetime.fromisoformat(ts)
    assert parsed.tzinfo is not None


# ---------------------------------------------------------------------------
# generate_json_report – components
# ---------------------------------------------------------------------------


def test_json_report_component_keys():
    data = generate_json_report(_report_with_survivors())
    comp = data["components"]["default"]
    assert "tsi" in comp
    assert "has_mutation_data" in comp
    assert "files" in comp


def test_json_report_component_has_mutation_data_true():
    data = generate_json_report(_report_with_survivors())
    assert data["components"]["default"]["has_mutation_data"] is True


def test_json_report_component_tsi_null_without_mutation_data():
    data = generate_json_report(_coverage_only_report())
    assert data["components"]["default"]["tsi"] is None


def test_json_report_file_keys():
    data = generate_json_report(_report_with_survivors())
    file_entry = data["components"]["default"]["files"]["src/api.py"]
    for key in ("path", "line_coverage", "test_strength", "lines"):
        assert key in file_entry


def test_json_report_file_path_matches_dict_key():
    data = generate_json_report(_report_with_survivors())
    file_entry = data["components"]["default"]["files"]["src/api.py"]
    assert file_entry["path"] == "src/api.py"


def test_json_report_line_coverage_value():
    data = generate_json_report(_report_with_survivors())
    # src/api.py has exactly one line (line 12) and it is covered → 100%
    assert data["components"]["default"]["files"]["src/api.py"][
        "line_coverage"
    ] == pytest.approx(1.0)


def test_json_report_test_strength_null_without_mutation_data():
    data = generate_json_report(_coverage_only_report())
    file_entry = data["components"]["default"]["files"]["src/utils.py"]
    assert file_entry["test_strength"] is None


# ---------------------------------------------------------------------------
# generate_json_report – lines (mutation-only)
# ---------------------------------------------------------------------------


def test_json_report_lines_only_includes_mutation_lines():
    """Lines without mutation data must not appear in 'lines'."""
    report = ProjectReport()
    component = ComponentReport()
    component.files["f.py"] = FileReport(file_path="f.py")
    # Line 1: covered, no mutations
    component.files["f.py"].lines[1] = LineData(line_number=1, is_covered=True)
    # Line 2: covered, has mutations
    component.files["f.py"].lines[2] = LineData(
        line_number=2,
        is_covered=True,
        mutants=[MutantData(id="m1", status="Survived", line=2, description="ArithOp")],
    )
    report.components["default"] = component

    data = generate_json_report(report)
    lines = data["components"]["default"]["files"]["f.py"]["lines"]
    assert len(lines) == 1
    assert lines[0]["line"] == 2


def test_json_report_line_entry_keys():
    data = generate_json_report(_report_with_survivors())
    line = data["components"]["default"]["files"]["src/api.py"]["lines"][0]
    for key in ("line", "is_covered", "killed", "survived", "mutators"):
        assert key in line


def test_json_report_line_killed_and_survived_counts():
    data = generate_json_report(_report_with_survivors())
    line = data["components"]["default"]["files"]["src/api.py"]["lines"][0]
    assert line["killed"] == 1
    assert line["survived"] == 1
    assert line["line"] == 12


def test_json_report_line_mutators_list():
    data = generate_json_report(_report_with_survivors())
    line = data["components"]["default"]["files"]["src/api.py"]["lines"][0]
    # Both mutants have descriptions; ArithmeticOperator is killed (excluded from survivors),
    # but _file_lines includes all mutators regardless of status.
    assert (
        "ArithmeticOperator" in line["mutators"]
        or "ConditionalBoundary" in line["mutators"]
    )


def test_json_report_line_mutators_excludes_none_descriptions():
    report = ProjectReport()
    component = ComponentReport()
    component.files["f.py"] = FileReport(file_path="f.py")
    component.files["f.py"].lines[1] = LineData(
        line_number=1,
        is_covered=True,
        mutants=[
            MutantData(id="1", status="Survived", line=1, description=None),
            MutantData(id="2", status="Survived", line=1, description="ComparisonOp"),
        ],
    )
    report.components["default"] = component

    data = generate_json_report(report)
    line = data["components"]["default"]["files"]["f.py"]["lines"][0]
    assert line["mutators"] == ["ComparisonOp"]


# ---------------------------------------------------------------------------
# generate_json_report – surviving_mutants
# ---------------------------------------------------------------------------


def test_json_report_surviving_mutants_is_list():
    data = generate_json_report(_report_with_survivors())
    assert isinstance(data["surviving_mutants"], list)


def test_json_report_surviving_mutants_entry_keys():
    data = generate_json_report(_report_with_survivors())
    assert len(data["surviving_mutants"]) == 1
    entry = data["surviving_mutants"][0]
    for key in (
        "component",
        "file",
        "line",
        "is_covered",
        "killed",
        "survived",
        "total",
        "all_survived",
        "mutators",
        "suggestion",
    ):
        assert key in entry


def test_json_report_surviving_mutants_values():
    data = generate_json_report(_report_with_survivors())
    entry = data["surviving_mutants"][0]
    assert entry["file"] == "src/api.py"
    assert entry["line"] == 12
    assert entry["is_covered"] is True
    assert entry["killed"] == 1
    assert entry["survived"] == 1
    assert entry["total"] == 2
    assert entry["all_survived"] is False
    assert entry["component"] == "default"


def test_json_report_surviving_mutants_empty_when_all_killed():
    report = ProjectReport()
    component = ComponentReport()
    component.files["f.py"] = FileReport(file_path="f.py")
    component.files["f.py"].lines[1] = LineData(
        line_number=1,
        is_covered=True,
        mutants=[MutantData(id="1", status="Killed", line=1)],
    )
    report.components["default"] = component

    data = generate_json_report(report)
    assert data["surviving_mutants"] == []


# ---------------------------------------------------------------------------
# generate_json_report – critical_gaps
# ---------------------------------------------------------------------------


def test_json_report_critical_gaps_is_list():
    data = generate_json_report(_report_with_survivors())
    assert isinstance(data["critical_gaps"], list)


def test_json_report_critical_gap_present_when_all_survived_and_covered():
    report = ProjectReport()
    component = ComponentReport()
    component.files["f.py"] = FileReport(file_path="f.py")
    component.files["f.py"].lines[1] = LineData(
        line_number=1,
        is_covered=True,
        mutants=[MutantData(id="1", status="Survived", line=1)],
    )
    report.components["default"] = component

    data = generate_json_report(report)
    assert len(data["critical_gaps"]) == 1
    assert data["critical_gaps"][0]["file"] == "f.py"
    assert data["critical_gaps"][0]["line"] == 1


# ---------------------------------------------------------------------------
# print_json_report – round-trip
# ---------------------------------------------------------------------------


def test_print_json_report_returns_valid_json():
    output = print_json_report(_report_with_survivors())
    parsed = json.loads(output)
    assert "tsi" in parsed


def test_print_json_report_is_indented():
    output = print_json_report(_report_with_survivors())
    # Indented JSON has newlines beyond the first
    assert "\n" in output


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


def test_cli_json_format_produces_valid_json():
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "analyze",
            "--coverage",
            "tests/sample_cobertura.xml",
            "--stryker",
            "tests/sample_stryker.json",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "tsi" in data
    assert "components" in data
    assert "surviving_mutants" in data
    assert "critical_gaps" in data
    assert "generated_at" in data


def test_cli_json_format_includes_file_data():
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "analyze",
            "--coverage",
            "tests/sample_cobertura.xml",
            "--stryker",
            "tests/sample_stryker.json",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    default = data["components"]["default"]
    assert "src/auth.py" in default["files"]


def test_cli_json_format_no_reports_produces_valid_json():
    """--format json with no input files should still emit valid JSON."""
    runner = CliRunner()
    result = runner.invoke(main, ["analyze", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["tsi"] is None
    assert data["components"] == {}


# ---------------------------------------------------------------------------
# _surviving_mutant_entry: source_line included when source_context present
# ---------------------------------------------------------------------------


def test_surviving_mutant_entry_includes_source_line_when_context_present():
    from tqa.formatters.json_formatter import _surviving_mutant_entry

    finding = {
        "component": "default",
        "file": "f.py",
        "line": 1,
        "covered": True,
        "killed": 0,
        "survived": 1,
        "total": 1,
        "all_survived": True,
        "mutants": [{"description": "ArithmeticOperator", "status": "Survived"}],
        "suggestion": "Add a test",
        "source_context": {"text": "return x + 1", "line": 1},
    }
    entry = _surviving_mutant_entry(finding)
    assert entry["source_line"] == "return x + 1"


# ---------------------------------------------------------------------------
# TimedOut mutants counted as killed (regression tests for the bug fix)
# ---------------------------------------------------------------------------


def test_timedout_mutant_counted_as_killed_in_file_lines():
    """A TimedOut mutant must appear in killed, not survived, in the per-line JSON output."""
    report = ProjectReport()
    component = ComponentReport()
    component.files["src/calc.py"] = FileReport(file_path="src/calc.py")
    component.files["src/calc.py"].lines[5] = LineData(
        line_number=5,
        is_covered=True,
        mutants=[
            MutantData(id="1", status=MutantStatus.TIMED_OUT, line=5, description="BoundaryCheck"),
            MutantData(id="2", status=MutantStatus.SURVIVED, line=5, description="ArithmeticOperator"),
        ],
    )
    report.components["default"] = component

    data = generate_json_report(report)
    line = data["components"]["default"]["files"]["src/calc.py"]["lines"][0]
    assert line["killed"] == 1, "TimedOut mutant should be counted as killed"
    assert line["survived"] == 1, "Only the Survived mutant should be in survived"


def test_timedout_killed_count_consistent_with_tsi():
    """The per-line killed/total ratio must be consistent with the top-level TSI."""
    report = ProjectReport()
    component = ComponentReport()
    component.files["src/calc.py"] = FileReport(file_path="src/calc.py")
    component.files["src/calc.py"].lines[5] = LineData(
        line_number=5,
        is_covered=True,
        mutants=[
            MutantData(id="1", status=MutantStatus.TIMED_OUT, line=5, description="BoundaryCheck"),
            MutantData(id="2", status=MutantStatus.SURVIVED, line=5, description="ArithmeticOperator"),
        ],
    )
    report.components["default"] = component

    data = generate_json_report(report)
    line = data["components"]["default"]["files"]["src/calc.py"]["lines"][0]

    killed = line["killed"]
    total = killed + line["survived"]
    per_line_ratio = killed / total  # 0.5

    top_level_tsi = data["tsi"]
    assert top_level_tsi == pytest.approx(per_line_ratio), (
        "Top-level TSI must match per-line killed/total ratio when TimedOut is counted as killed"
    )

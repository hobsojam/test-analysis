from pathlib import Path

import pytest
from click.testing import CliRunner
from tqa.cli import main
from tqa.models import (
    ProjectReport,
    ComponentReport,
    FileReport,
    LineData,
    MutantData,
    MutantStatus,
)
from tqa.engine import AnalysisEngine
from tqa.formatters.github import generate_markdown_summary
from tqa.formatters.console import print_summary_table
from tqa.parsers.cobertura import parse_cobertura, CoberturaParser
from tqa.parsers.stryker import parse_stryker, StrykerParser
from tqa.parsers.pit import parse_pit, PitParser
from tqa.parsers.mutmut import parse_mutmut, MutmutParser
from tqa.parsers.mutant import parse_mutant, MutantParser
from tqa.parsers.lcov import parse_lcov, LcovParser
from tqa.parsers.registry import registry
from tqa.parsers.base import Parser


# --- Test helpers ---


def _make_file(killed: int, survived: int, covered: bool) -> FileReport:
    fr = FileReport(file_path="f.py")
    fr.lines[1] = LineData(line_number=1, is_covered=covered)
    for i in range(killed):
        fr.lines[1].mutants.append(MutantData(id=str(i), status="Killed", line=1))
    for i in range(survived):
        fr.lines[1].mutants.append(
            MutantData(id=str(killed + i), status="Survived", line=1)
        )
    return fr


def _make_component(killed: int, survived: int, covered: bool) -> ComponentReport:
    comp = ComponentReport()
    comp.files["f.py"] = _make_file(killed, survived, covered)
    return comp


def _make_report(killed: int, survived: int, covered: bool) -> ProjectReport:
    report = ProjectReport()
    report.components["default"] = _make_component(killed, survived, covered)
    return report


# --- Model defaults ---


def test_mutant_data_description_defaults_to_none():
    m = MutantData(id="1", status="Killed", line=5)
    assert m.description is None


def test_line_data_is_covered_defaults_to_false():
    line_data = LineData(line_number=1)
    assert line_data.is_covered is False


# --- Model properties ---


def test_has_mutation_data_true_when_mutants_present():
    comp = _make_component(killed=1, survived=0, covered=True)
    assert comp.files["f.py"].has_mutation_data is True


def test_has_mutation_data_false_when_no_mutants():
    comp = ComponentReport()
    comp.files["f.py"] = FileReport(file_path="f.py")
    comp.files["f.py"].lines[1] = LineData(line_number=1, is_covered=True)
    assert comp.files["f.py"].has_mutation_data is False


def test_test_strength_all_killed():
    comp = _make_component(killed=2, survived=0, covered=True)
    assert comp.files["f.py"].test_strength == 1.0


def test_test_strength_none_killed():
    comp = _make_component(killed=0, survived=2, covered=True)
    assert comp.files["f.py"].test_strength == 0.0


def test_test_strength_uncovered_lines_ignored():
    comp = _make_component(killed=0, survived=2, covered=False)
    assert comp.files["f.py"].test_strength == 0.0


def test_total_test_strength_empty_report():
    assert ProjectReport().total_test_strength == 0.0


def test_project_has_mutation_data_false_when_empty():
    assert ProjectReport().has_mutation_data is False


def test_project_total_strength_weighted_by_mutation_file_count():
    report = ProjectReport()
    # backend: 1 file with mutation data, TSI 1.0
    backend = ComponentReport()
    backend.files["a.py"] = _make_file(killed=1, survived=0, covered=True)
    report.components["backend"] = backend
    # frontend: 3 files with no mutation data — excluded from aggregate
    frontend = ComponentReport()
    for name in ("a.js", "b.js", "c.js"):
        frontend.files[name] = FileReport(file_path=name)
        frontend.files[name].lines[1] = LineData(line_number=1, is_covered=False)
    report.components["frontend"] = frontend
    # only the 1 backend mutation file counts → 1.0
    assert report.total_test_strength == pytest.approx(1.0)


def test_project_total_strength_excludes_coverage_only_files():
    """Files with coverage but no mutation data must not inflate the aggregate."""
    report = ProjectReport()
    comp = ComponentReport()
    # one file with real mutation data: 80% kill rate
    comp.files["tested.py"] = _make_file(killed=4, survived=1, covered=True)
    # two files that only have coverage data (no mutants) — would return TSI 1.0 each
    for name in ("a.py", "b.py"):
        comp.files[name] = FileReport(file_path=name)
        comp.files[name].lines[1] = LineData(line_number=1, is_covered=True)
    report.components["default"] = comp
    assert report.total_test_strength == pytest.approx(0.8)


# --- Parser: cobertura ---


def test_parse_cobertura():
    component = ComponentReport()
    parse_cobertura("tests/sample_cobertura.xml", component)

    assert "src/auth.py" in component.files
    auth_report = component.files["src/auth.py"]
    assert auth_report.lines[1].is_covered is True
    assert auth_report.lines[2].is_covered is False


# --- Parser: stryker ---


def test_parse_stryker():
    component = ComponentReport()
    parse_stryker("tests/sample_stryker.json", component)

    assert "src/auth.py" in component.files
    auth_report = component.files["src/auth.py"]
    assert len(auth_report.lines[2].mutants) == 2
    assert auth_report.lines[2].mutants[0].status == "Survived"
    assert auth_report.lines[2].mutants[1].status == "Killed"


# --- Parser: pit ---


def test_parse_pit():
    component = ComponentReport()
    parse_pit("tests/sample_pit.xml", component)

    assert "Calculator.java" in component.files
    calc_report = component.files["Calculator.java"]
    assert len(calc_report.lines[10].mutants) == 2
    assert calc_report.lines[10].mutants[0].status == MutantStatus.KILLED
    assert calc_report.lines[10].mutants[1].status == MutantStatus.SURVIVED


def test_parse_pit_line_number():
    component = ComponentReport()
    parse_pit("tests/sample_pit.xml", component)
    assert 10 in component.files["Calculator.java"].lines


def test_parse_pit_mutator_field():
    component = ComponentReport()
    parse_pit("tests/sample_pit.xml", component)
    mutant = component.files["Calculator.java"].lines[10].mutants[0]
    assert (
        mutant.description
        == "org.pitest.mutationtest.engine.gregor.mutators.MathMutator"
    )


# --- Parser: mutmut ---


def test_parse_mutmut():
    component = ComponentReport()
    parse_mutmut("tests/sample_mutmut.xml", component)

    assert "main.py" in component.files
    main_report = component.files["main.py"]
    assert main_report.lines[5].mutants[0].status == "Killed"
    assert main_report.lines[10].mutants[0].status == "Survived"


def test_parse_mutmut_description_is_none():
    # Without diff text, mutmut descriptions stay empty so recommendations
    # fall back instead of using a misleading placeholder.
    component = ComponentReport()
    parse_mutmut("tests/sample_mutmut.xml", component)
    for line_data in component.files["main.py"].lines.values():
        for mutant in line_data.mutants:
            assert mutant.description is None


def test_parse_mutmut_infers_descriptions_from_survived_diffs():
    component = ComponentReport()
    parse_mutmut("tests/sample_mutmut_with_diffs.xml", component)
    main_report = component.files["main.py"]

    assert main_report.lines[5].mutants[0].description is None
    assert main_report.lines[10].mutants[0].description == "ArithmeticOperator"
    assert main_report.lines[20].mutants[0].description == "ComparisonOperator"
    assert main_report.lines[30].mutants[0].description == "BooleanLiteral"
    assert main_report.lines[40].mutants[0].description == "ReturnValue"
    assert main_report.lines[50].mutants[0].description == "VoidMethodCall"


def test_parse_mutmut_line_numbers():
    component = ComponentReport()
    parse_mutmut("tests/sample_mutmut.xml", component)
    main_report = component.files["main.py"]
    assert 5 in main_report.lines
    assert 10 in main_report.lines


# --- Parser: mutant ---


def test_parse_mutant_session_json():
    component = ComponentReport()
    parse_mutant("tests/sample_mutant_session.json", component)

    assert "lib/person.rb" in component.files
    line = component.files["lib/person.rb"].lines[7]
    assert len(line.mutants) == 2
    assert line.mutants[0].status == "Survived"
    assert line.mutants[1].status == "Killed"


def test_parse_mutant_session_json_preserves_useful_survivor_details():
    component = ComponentReport()
    parse_mutant("tests/sample_mutant_session.json", component)

    mutant = component.files["lib/person.rb"].lines[7].mutants[0]
    assert mutant.description == (
        "Mutant::Mutator::Node::Gte | Person#adult? | -  @age >= 18 +  @age > 18"
    )


def test_parse_mutant_results_directory(tmp_path):
    results_dir = tmp_path / ".mutant" / "results"
    results_dir.mkdir(parents=True)
    fixture = Path("tests/sample_mutant_session.json")
    (results_dir / "session.json").write_text(
        fixture.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    component = ComponentReport()
    parse_mutant(str(results_dir), component)

    assert "lib/person.rb" in component.files
    assert len(component.files["lib/person.rb"].lines[7].mutants) == 2


# --- Parser: lcov ---


def test_parse_lcov():
    component = ComponentReport()
    parse_lcov("tests/sample_lcov.info", component)

    assert "src/auth.js" in component.files
    auth_report = component.files["src/auth.js"]
    assert auth_report.lines[1].is_covered is True
    assert auth_report.lines[2].is_covered is False
    assert auth_report.lines[3].is_covered is True

    assert "src/utils.js" in component.files
    assert component.files["src/utils.js"].line_coverage == 1.0


# --- Correlation ---


def test_correlation():
    component = ComponentReport()
    parse_cobertura("tests/sample_cobertura.xml", component)
    parse_stryker("tests/sample_stryker.json", component)

    auth_report = component.files["src/auth.py"]
    assert auth_report.line_coverage == 0.5
    assert auth_report.test_strength == 1.0


# --- Engine: path reconciliation ---


@pytest.mark.parametrize(
    "killed,survived,covered,expected",
    [
        (0, 2, True, {"killed": 0, "survived": 2, "total": 2, "all_survived": True}),
        (1, 2, True, {"killed": 1, "survived": 2, "total": 3, "all_survived": False}),
        (0, 1, False, {"killed": 0, "survived": 1, "total": 1, "all_survived": True}),
    ],
)
def test_engine_surviving_mutants_reports_survivor_metadata(
    killed: int,
    survived: int,
    covered: bool,
    expected: dict,
):
    findings = AnalysisEngine().get_surviving_mutants(
        _make_report(killed=killed, survived=survived, covered=covered)
    )

    assert len(findings) == 1
    for key, value in expected.items():
        assert findings[0][key] == value
    assert findings[0]["component"] == "default"
    assert findings[0]["file"] == "f.py"
    assert findings[0]["line"] == 1
    assert findings[0]["covered"] is covered
    assert len(findings[0]["mutants"]) == survived


@pytest.mark.parametrize(
    "report",
    [
        _make_report(killed=2, survived=0, covered=True),
    ],
)
def test_engine_surviving_mutants_excludes_lines_without_survivors(
    report: ProjectReport,
):
    assert AnalysisEngine().get_surviving_mutants(report) == []


def test_engine_surviving_mutants_excludes_lines_without_mutants():
    component = ComponentReport()
    component.files["f.py"] = FileReport(file_path="f.py")
    component.files["f.py"].lines[1] = LineData(line_number=1, is_covered=True)
    report = ProjectReport()
    report.components["default"] = component

    assert AnalysisEngine().get_surviving_mutants(report) == []


def test_engine_surviving_mutants_includes_component_name_and_description():
    report = _report_with_line(
        "backend",
        "api.py",
        7,
        True,
        [
            MutantData(
                id="mut-1",
                status=MutantStatus.SURVIVED,
                line=7,
                description="ConditionalBoundary",
            )
        ],
    )

    findings = AnalysisEngine().get_surviving_mutants(report)

    assert findings[0]["component"] == "backend"
    assert findings[0]["mutants"] == [
        {
            "id": "mut-1",
            "status": MutantStatus.SURVIVED,
            "description": "ConditionalBoundary",
        }
    ]


def _report_with_line(
    component_name: str,
    file_path: str,
    line_number: int,
    covered: bool,
    mutants: list[MutantData],
) -> ProjectReport:
    report = ProjectReport()
    component = ComponentReport()
    component.files[file_path] = FileReport(file_path=file_path)
    component.files[file_path].lines[line_number] = LineData(
        line_number=line_number,
        is_covered=covered,
        mutants=mutants,
    )
    report.components[component_name] = component
    return report


def test_engine_critical_gaps_uses_only_covered_fully_survived_lines():
    report = _report_with_line(
        "default",
        "f.py",
        1,
        True,
        [MutantData(id="1", status="Survived", line=1)],
    )
    report.components["default"].files["f.py"].lines[2] = LineData(
        line_number=2,
        is_covered=True,
        mutants=[
            MutantData(id="2", status="Killed", line=2),
            MutantData(id="3", status="Survived", line=2),
        ],
    )
    report.components["default"].files["f.py"].lines[3] = LineData(
        line_number=3,
        is_covered=False,
        mutants=[MutantData(id="4", status="Survived", line=3)],
    )

    assert AnalysisEngine().get_critical_gaps(report) == [
        {
            "file": "f.py",
            "line": 1,
            "survived": 1,
        }
    ]


def test_path_reconciliation():
    component = ComponentReport()
    parse_cobertura("tests/sample_cobertura.xml", component)
    component.files["auth.py"] = component.files.pop("src/auth.py")
    component.files["auth.py"].file_path = "auth.py"
    parse_stryker("tests/sample_stryker.json", component)
    component.reconcile_paths()
    assert "auth.py" not in component.files
    assert "src/auth.py" in component.files
    merged = component.files["src/auth.py"]
    assert merged.lines[1].is_covered is True
    assert len(merged.lines[2].mutants) > 0


def test_path_reconciliation_skips_ambiguous():
    component = ComponentReport()
    component.files["__init__.py"] = FileReport(file_path="__init__.py")
    component.files["pkg/__init__.py"] = FileReport(file_path="pkg/__init__.py")
    component.files["sub/__init__.py"] = FileReport(file_path="sub/__init__.py")
    component.reconcile_paths()
    assert "__init__.py" in component.files
    assert "pkg/__init__.py" in component.files
    assert "sub/__init__.py" in component.files


# --- Formatter: github ---


def _make_healthy_report() -> ProjectReport:
    return _make_report(killed=4, survived=1, covered=True)


def test_github_formatter_contains_header():
    report = _make_healthy_report()
    md = generate_markdown_summary(report)
    assert "## TQA Report Summary" in md
    # Verify it is H2, not H1 — use line-start anchor to avoid substring false-positive
    assert not any(
        line == "# TQA Report Summary" for line in md.splitlines()
    ), "Header must be H2 (##), not H1 (#)"


def test_github_formatter_shows_tsi_percentage():
    report = _make_healthy_report()
    md = generate_markdown_summary(report)
    assert "80.0%" in md  # 4 killed / 5 total


def test_github_formatter_healthy_status():
    report = _make_report(killed=9, survived=1, covered=True)
    md = generate_markdown_summary(report)
    assert "Healthy" in md


def test_github_formatter_weak_status():
    report = _make_report(killed=6, survived=4, covered=True)
    md = generate_markdown_summary(report)
    assert "Weak" in md


def test_github_formatter_blind_status():
    report = _make_report(killed=1, survived=9, covered=True)
    md = generate_markdown_summary(report)
    assert "Blind" in md


def test_github_formatter_na_without_mutation_data():
    component = ComponentReport()
    component.files["f.py"] = FileReport(file_path="f.py")
    component.files["f.py"].lines[1] = LineData(line_number=1, is_covered=True)
    report = ProjectReport()
    report.components["default"] = component
    md = generate_markdown_summary(report)
    assert "N/A" in md


def test_github_formatter_total_strength():
    report = _make_report(killed=4, survived=1, covered=True)
    md = generate_markdown_summary(report)
    assert "Total Project Test Strength" in md


def test_github_formatter_multi_component_shows_headers():
    report = ProjectReport()
    report.components["backend"] = _make_component(killed=4, survived=1, covered=True)
    report.components["frontend"] = _make_component(killed=2, survived=2, covered=True)
    md = generate_markdown_summary(report)
    assert "### Backend" in md
    assert "### Frontend" in md
    assert "Total Project Test Strength" in md


def test_github_formatter_single_named_component_shows_header():
    report = ProjectReport()
    report.components["backend"] = _make_component(killed=4, survived=1, covered=True)
    md = generate_markdown_summary(report)
    assert "### Backend" in md


def test_github_formatter_default_component_no_header():
    report = _make_report(killed=4, survived=1, covered=True)
    md = generate_markdown_summary(report)
    assert "### " not in md


def test_github_formatter_plain_filename_without_actions_env(monkeypatch):
    monkeypatch.delenv("GITHUB_SERVER_URL", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    report = _make_report(killed=4, survived=1, covered=True)
    md = generate_markdown_summary(report)
    assert "`f.py`" in md
    assert "](https://" not in md


def test_github_formatter_linked_filename_with_actions_env(monkeypatch):
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_SHA", "abc1234")
    report = _make_report(killed=4, survived=1, covered=True)
    md = generate_markdown_summary(report)
    assert "[`f.py`](https://github.com/owner/repo/blob/abc1234/f.py)" in md


# --- Formatter: console ---


def test_console_formatter_runs_without_error():
    report = _make_report(killed=1, survived=1, covered=True)
    print_summary_table(report)


def test_console_formatter_runs_with_no_mutation_data():
    component = ComponentReport()
    component.files["f.py"] = FileReport(file_path="f.py")
    component.files["f.py"].lines[1] = LineData(line_number=1, is_covered=True)
    report = ProjectReport()
    report.components["default"] = component
    print_summary_table(report)


def test_console_formatter_multi_component_runs_without_error():
    report = ProjectReport()
    report.components["backend"] = _make_component(killed=1, survived=1, covered=True)
    report.components["frontend"] = _make_component(killed=0, survived=2, covered=True)
    print_summary_table(report)


# --- CLI ---


def test_cli_analyze_with_coverage_and_stryker():
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "analyze",
            "--coverage",
            "tests/sample_cobertura.xml",
            "--stryker",
            "tests/sample_stryker.json",
        ],
    )
    assert result.exit_code == 0
    assert "src/auth.py" in result.output


def test_cli_analyze_github_format():
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
            "github",
        ],
    )
    assert result.exit_code == 0
    assert "# TQA Report Summary" in result.output


def test_cli_analyze_fail_under_triggers_exit():
    # mutmut-only: no coverage data means all lines is_covered=False → TSI 0%
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "analyze",
            "--mutmut",
            "tests/sample_mutmut.xml",
            "--fail-under",
            "50",
        ],
    )
    assert result.exit_code == 1


def test_cli_analyze_with_mutant_session_json():
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "analyze",
            "--mutant",
            "tests/sample_mutant_session.json",
            "--format",
            "github",
        ],
    )
    assert result.exit_code == 0
    assert "lib/person.rb" in result.output
    assert "Mutant::Mutator::Node::Gte" in result.output


def test_cli_analyze_no_reports():
    runner = CliRunner()
    result = runner.invoke(main, ["analyze"])
    assert result.exit_code == 0


def test_cli_analyze_with_config_file(tmp_path):
    config = tmp_path / "tqa.toml"
    config.write_text(
        "[components.backend]\n"
        'cobertura = "tests/sample_cobertura.xml"\n'
        "[components.frontend]\n"
        'lcov = "tests/sample_lcov.info"\n',
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(
        main, ["analyze", "--config", str(config), "--format", "github"]
    )
    assert result.exit_code == 0
    assert "## Backend" in result.output
    assert "## Frontend" in result.output


def test_cli_analyze_config_single_component_shows_header(tmp_path):
    config = tmp_path / "tqa.toml"
    config.write_text(
        '[components.backend]\ncobertura = "tests/sample_cobertura.xml"\n',
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(
        main, ["analyze", "--config", str(config), "--format", "github"]
    )
    assert result.exit_code == 0
    assert "## Backend" in result.output


def test_cli_analyze_with_project_root_flag(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "analyze",
            "--coverage", "tests/sample_cobertura.xml",
            "--stryker", "tests/sample_stryker.json",
            "--project-root", str(tmp_path),
            "--context-lines", "1",
        ],
    )
    assert result.exit_code == 0


def test_cli_analyze_context_lines_without_project_root_warns():
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "analyze",
            "--coverage", "tests/sample_cobertura.xml",
            "--context-lines", "3",
        ],
    )
    assert result.exit_code == 0
    assert "--context-lines" in result.output and "--project-root" in result.output


# --- Input validation: empty/missing coverage data ---


def test_parse_cobertura_empty_xml():
    component = ComponentReport()
    parse_cobertura("tests/sample_cobertura_empty.xml", component)
    assert component.files == {}


def test_cli_warns_when_coverage_xml_has_no_files():
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "analyze",
            "--coverage",
            "tests/sample_cobertura_empty.xml",
            "--format",
            "github",
        ],
    )
    assert result.exit_code == 0
    assert "No coverage or mutation reports were detected" in result.output


def test_cli_warns_when_coverage_xml_has_no_files_with_mutation_data():
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "analyze",
            "--coverage",
            "tests/sample_cobertura_empty.xml",
            "--mutmut",
            "tests/sample_mutmut.xml",
            "--format",
            "github",
        ],
    )
    assert result.exit_code == 0
    assert "coverage" in result.output.lower()


# --- Parser registry ---


def test_registry_contains_all_parsers():
    for key in ("cobertura", "stryker", "pit", "mutmut", "mutant", "lcov"):
        assert key in registry


def test_registry_returns_correct_types():
    assert isinstance(registry.get("cobertura"), CoberturaParser)
    assert isinstance(registry.get("stryker"), StrykerParser)
    assert isinstance(registry.get("pit"), PitParser)
    assert isinstance(registry.get("mutmut"), MutmutParser)
    assert isinstance(registry.get("mutant"), MutantParser)
    assert isinstance(registry.get("lcov"), LcovParser)


def test_registry_parsers_implement_base():
    for name in registry.names():
        assert isinstance(registry.get(name), Parser)


def test_registry_get_returns_fresh_instance():
    p1 = registry.get("cobertura")
    p2 = registry.get("cobertura")
    assert p1 is not p2


def test_engine_run_accepts_inputs_dict():
    engine = AnalysisEngine()
    report = engine.run({"cobertura": "tests/sample_cobertura.xml"})
    assert "src/auth.py" in report.components["default"].files


def test_engine_run_ignores_unknown_parser():
    engine = AnalysisEngine()
    report = engine.run({"unknown_format": "tests/sample_cobertura.xml"})
    assert report.components == {}


def test_engine_run_ignores_none_paths():
    engine = AnalysisEngine()
    report = engine.run({"cobertura": None, "stryker": None})
    assert report.components == {}


def test_engine_run_uses_multiple_parsers():
    engine = AnalysisEngine()
    report = engine.run(
        {
            "cobertura": "tests/sample_cobertura.xml",
            "stryker": "tests/sample_stryker.json",
        }
    )
    assert "src/auth.py" in report.components["default"].files
    assert report.components["default"].files["src/auth.py"].has_mutation_data


def test_engine_run_multi_creates_named_components():
    engine = AnalysisEngine()
    report = engine.run_multi(
        {
            "backend": {"cobertura": "tests/sample_cobertura.xml"},
            "frontend": {"lcov": "tests/sample_lcov.info"},
        }
    )
    assert "backend" in report.components
    assert "frontend" in report.components
    assert "src/auth.py" in report.components["backend"].files
    assert "src/auth.js" in report.components["frontend"].files


def test_engine_run_multi_reconciles_paths_per_component():
    engine = AnalysisEngine()
    report = engine.run_multi(
        {
            "backend": {
                "cobertura": "tests/sample_cobertura.xml",
                "stryker": "tests/sample_stryker.json",
            },
        }
    )
    backend = report.components["backend"]
    assert "src/auth.py" in backend.files
    assert backend.files["src/auth.py"].has_mutation_data


# --- CLI: sonarcloud format with no reports ---


def test_cli_sonarcloud_format_with_no_reports(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["analyze", "--format", "sonarcloud"])
    assert result.exit_code == 0
    assert "Quality Unknown" in result.output


# --- CLI: export-svg ---


def test_cli_export_svg(tmp_path):
    svg_path = str(tmp_path / "out.svg")
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "analyze",
            "--coverage",
            "tests/sample_cobertura.xml",
            "--format",
            "console",
            "--export-svg",
            svg_path,
        ],
    )
    assert result.exit_code == 0
    assert Path(svg_path).exists()
    assert "<svg" in Path(svg_path).read_text(encoding="utf-8")


# --- Models: FileReport.line_coverage when no lines ---


def test_file_report_line_coverage_when_no_lines():
    assert FileReport(file_path="empty.py").line_coverage == 0.0


# --- Models: reconcile_paths continue when ambiguous (multiple longer matches) ---


def test_reconcile_paths_skips_when_ambiguous():
    comp = ComponentReport()
    comp.files["a.py"] = FileReport(file_path="a.py")
    comp.files["b/a.py"] = FileReport(file_path="b/a.py")
    comp.files["c/a.py"] = FileReport(file_path="c/a.py")
    comp.reconcile_paths()
    # "a.py" matches both "b/a.py" and "c/a.py" — ambiguous, nothing merged
    assert "a.py" in comp.files
    assert "b/a.py" in comp.files
    assert "c/a.py" in comp.files


# --- Models: reconcile_paths sets is_covered=True from src line ---


def test_reconcile_paths_merges_covered_status():
    comp = ComponentReport()
    comp.files["auth.py"] = FileReport(file_path="auth.py")
    comp.files["auth.py"].lines[5] = LineData(line_number=5, is_covered=True)
    comp.files["tqa/auth.py"] = FileReport(file_path="tqa/auth.py")
    comp.files["tqa/auth.py"].lines[5] = LineData(line_number=5, is_covered=False)
    comp.reconcile_paths()
    assert "auth.py" not in comp.files
    assert comp.files["tqa/auth.py"].lines[5].is_covered is True


# --- mutmut parser: testcase with no name and no file/line is skipped ---


def test_mutmut_parser_skips_nameless_locationless_testcase(tmp_path):
    xml = (
        '<?xml version="1.0"?>'
        '<testsuites><testsuite name="mutmut">'
        "<testcase/>"
        "</testsuite></testsuites>"
    )
    p = tmp_path / "mutmut.xml"
    p.write_text(xml, encoding="utf-8")
    component = ComponentReport()
    parse_mutmut(str(p), component)
    assert component.files == {}


def test_cli_version_flag():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "tqa" in result.output
    assert "0.1.0" in result.output


# --- PIT parser: stable sequential mutant IDs ---


def test_pit_mutant_ids_are_stable_across_parses():
    c1 = ComponentReport()
    parse_pit("tests/sample_pit.xml", c1)
    c2 = ComponentReport()
    parse_pit("tests/sample_pit.xml", c2)
    ids1 = sorted(m.id for fr in c1.files.values() for ld in fr.lines.values() for m in ld.mutants)
    ids2 = sorted(m.id for fr in c2.files.values() for ld in fr.lines.values() for m in ld.mutants)
    assert ids1 == ids2


def test_pit_mutant_ids_have_expected_format():
    component = ComponentReport()
    parse_pit("tests/sample_pit.xml", component)
    for fr in component.files.values():
        for ld in fr.lines.values():
            for m in ld.mutants:
                assert m.id.startswith("pit-")
                assert m.id[4:].isdigit()

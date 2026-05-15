from click.testing import CliRunner
from tqa.cli import main
from tqa.models import ProjectReport, FileReport, LineData, MutantData
from tqa.engine import AnalysisEngine
from tqa.formatters.github import generate_markdown_summary
from tqa.formatters.console import print_summary_table
from tqa.parsers.cobertura import parse_cobertura
from tqa.parsers.stryker import parse_stryker
from tqa.parsers.pit import parse_pit
from tqa.parsers.mutmut import parse_mutmut
from tqa.parsers.lcov import parse_lcov


# --- Model defaults ---

def test_mutant_data_description_defaults_to_none():
    m = MutantData(id="1", status="Killed", line=5)
    assert m.description is None

def test_line_data_is_covered_defaults_to_false():
    l = LineData(line_number=1)
    assert l.is_covered is False


# --- Model properties ---

def _make_report(killed: int, survived: int, covered: bool) -> ProjectReport:
    report = ProjectReport()
    report.files["f.py"] = FileReport(file_path="f.py")
    report.files["f.py"].lines[1] = LineData(line_number=1, is_covered=covered)
    for i in range(killed):
        report.files["f.py"].lines[1].mutants.append(
            MutantData(id=str(i), status="Killed", line=1)
        )
    for i in range(survived):
        report.files["f.py"].lines[1].mutants.append(
            MutantData(id=str(killed + i), status="Survived", line=1)
        )
    return report

def test_has_mutation_data_true_when_mutants_present():
    report = _make_report(killed=1, survived=0, covered=True)
    assert report.files["f.py"].has_mutation_data is True

def test_has_mutation_data_false_when_no_mutants():
    report = ProjectReport()
    report.files["f.py"] = FileReport(file_path="f.py")
    report.files["f.py"].lines[1] = LineData(line_number=1, is_covered=True)
    assert report.files["f.py"].has_mutation_data is False

def test_test_strength_all_killed():
    report = _make_report(killed=2, survived=0, covered=True)
    assert report.files["f.py"].test_strength == 1.0

def test_test_strength_none_killed():
    report = _make_report(killed=0, survived=2, covered=True)
    assert report.files["f.py"].test_strength == 0.0

def test_test_strength_uncovered_lines_ignored():
    report = _make_report(killed=0, survived=2, covered=False)
    assert report.files["f.py"].test_strength == 0.0

def test_total_test_strength_empty_report():
    assert ProjectReport().total_test_strength == 0.0

def test_project_has_mutation_data_false_when_empty():
    assert ProjectReport().has_mutation_data is False


# --- Parser: cobertura ---

def test_parse_cobertura():
    report = ProjectReport()
    parse_cobertura("tests/sample_cobertura.xml", report)

    assert "src/auth.py" in report.files
    auth_report = report.files["src/auth.py"]
    assert auth_report.lines[1].is_covered is True
    assert auth_report.lines[2].is_covered is False


# --- Parser: stryker ---

def test_parse_stryker():
    report = ProjectReport()
    parse_stryker("tests/sample_stryker.json", report)

    assert "src/auth.py" in report.files
    auth_report = report.files["src/auth.py"]
    assert len(auth_report.lines[2].mutants) == 2
    assert auth_report.lines[2].mutants[0].status == "Survived"
    assert auth_report.lines[2].mutants[1].status == "Killed"


# --- Parser: pit ---

def test_parse_pit():
    report = ProjectReport()
    parse_pit("tests/sample_pit.xml", report)

    assert "Calculator.java" in report.files
    calc_report = report.files["Calculator.java"]
    assert len(calc_report.lines[10].mutants) == 2
    assert calc_report.lines[10].mutants[0].status == "KILLED"
    assert calc_report.lines[10].mutants[1].status == "SURVIVED"

def test_parse_pit_line_number():
    report = ProjectReport()
    parse_pit("tests/sample_pit.xml", report)
    assert 10 in report.files["Calculator.java"].lines

def test_parse_pit_mutator_field():
    report = ProjectReport()
    parse_pit("tests/sample_pit.xml", report)
    mutant = report.files["Calculator.java"].lines[10].mutants[0]
    assert mutant.description == "org.pitest.mutationtest.engine.gregor.mutators.MathMutator"


# --- Parser: mutmut ---

def test_parse_mutmut():
    report = ProjectReport()
    parse_mutmut("tests/sample_mutmut.xml", report)

    assert "main.py" in report.files
    main_report = report.files["main.py"]
    assert main_report.lines[5].mutants[0].status == "Killed"
    assert main_report.lines[10].mutants[0].status == "Survived"

def test_parse_mutmut_line_numbers():
    report = ProjectReport()
    parse_mutmut("tests/sample_mutmut.xml", report)
    main_report = report.files["main.py"]
    assert 5 in main_report.lines
    assert 10 in main_report.lines


# --- Parser: lcov ---

def test_parse_lcov():
    report = ProjectReport()
    parse_lcov("tests/sample_lcov.info", report)

    assert "src/auth.js" in report.files
    auth_report = report.files["src/auth.js"]
    assert auth_report.lines[1].is_covered is True
    assert auth_report.lines[2].is_covered is False
    assert auth_report.lines[3].is_covered is True

    assert "src/utils.js" in report.files
    assert report.files["src/utils.js"].line_coverage == 1.0


# --- Correlation ---

def test_correlation():
    report = ProjectReport()
    parse_cobertura("tests/sample_cobertura.xml", report)
    parse_stryker("tests/sample_stryker.json", report)

    auth_report = report.files["src/auth.py"]
    assert auth_report.line_coverage == 0.5
    assert auth_report.test_strength == 1.0


# --- Engine: path reconciliation ---

def test_path_reconciliation():
    report = ProjectReport()
    parse_cobertura("tests/sample_cobertura.xml", report)
    report.files["auth.py"] = report.files.pop("src/auth.py")
    report.files["auth.py"].file_path = "auth.py"
    parse_stryker("tests/sample_stryker.json", report)
    engine = AnalysisEngine()
    engine._reconcile_paths(report)
    assert "auth.py" not in report.files
    assert "src/auth.py" in report.files
    merged = report.files["src/auth.py"]
    assert merged.lines[1].is_covered is True
    assert len(merged.lines[2].mutants) > 0

def test_path_reconciliation_skips_ambiguous():
    # Two files both named __init__.py in different dirs — neither should be merged
    report = ProjectReport()
    report.files["__init__.py"] = FileReport(file_path="__init__.py")
    report.files["pkg/__init__.py"] = FileReport(file_path="pkg/__init__.py")
    report.files["sub/__init__.py"] = FileReport(file_path="sub/__init__.py")
    engine = AnalysisEngine()
    engine._reconcile_paths(report)
    assert "__init__.py" in report.files
    assert "pkg/__init__.py" in report.files
    assert "sub/__init__.py" in report.files


# --- Formatter: github ---

def _make_healthy_report() -> ProjectReport:
    report = _make_report(killed=4, survived=1, covered=True)
    return report

def test_github_formatter_contains_header():
    report = _make_healthy_report()
    md = generate_markdown_summary(report)
    assert "# TQA Report Summary" in md

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
    report = ProjectReport()
    report.files["f.py"] = FileReport(file_path="f.py")
    report.files["f.py"].lines[1] = LineData(line_number=1, is_covered=True)
    md = generate_markdown_summary(report)
    assert "N/A" in md

def test_github_formatter_total_strength():
    report = _make_report(killed=4, survived=1, covered=True)
    md = generate_markdown_summary(report)
    assert "Total Project Test Strength" in md


# --- Formatter: console ---

def test_console_formatter_runs_without_error():
    report = _make_report(killed=1, survived=1, covered=True)
    print_summary_table(report)  # should not raise

def test_console_formatter_runs_with_no_mutation_data():
    report = ProjectReport()
    report.files["f.py"] = FileReport(file_path="f.py")
    report.files["f.py"].lines[1] = LineData(line_number=1, is_covered=True)
    print_summary_table(report)  # should not raise


# --- CLI ---

def test_cli_analyze_with_coverage_and_stryker():
    runner = CliRunner()
    result = runner.invoke(main, [
        "analyze",
        "--coverage", "tests/sample_cobertura.xml",
        "--stryker", "tests/sample_stryker.json",
    ])
    assert result.exit_code == 0
    assert "src/auth.py" in result.output

def test_cli_analyze_github_format():
    runner = CliRunner()
    result = runner.invoke(main, [
        "analyze",
        "--coverage", "tests/sample_cobertura.xml",
        "--stryker", "tests/sample_stryker.json",
        "--format", "github",
    ])
    assert result.exit_code == 0
    assert "# TQA Report Summary" in result.output

def test_cli_analyze_fail_under_triggers_exit():
    # mutmut-only: no coverage data means all lines is_covered=False → TSI 0%
    runner = CliRunner()
    result = runner.invoke(main, [
        "analyze",
        "--mutmut", "tests/sample_mutmut.xml",
        "--fail-under", "50",
    ])
    assert result.exit_code == 1

def test_cli_analyze_no_reports():
    runner = CliRunner()
    result = runner.invoke(main, ["analyze"])
    assert result.exit_code == 0

from tqa.models import ProjectReport
from tqa.engine import AnalysisEngine
from tqa.parsers.cobertura import parse_cobertura
from tqa.parsers.stryker import parse_stryker
from tqa.parsers.pit import parse_pit
from tqa.parsers.mutmut import parse_mutmut
from tqa.parsers.lcov import parse_lcov

def test_parse_cobertura():
    report = ProjectReport()
    parse_cobertura("tests/sample_cobertura.xml", report)
    
    assert "src/auth.py" in report.files
    auth_report = report.files["src/auth.py"]
    assert auth_report.lines[1].is_covered is True
    assert auth_report.lines[2].is_covered is False

def test_parse_stryker():
    report = ProjectReport()
    parse_stryker("tests/sample_stryker.json", report)
    
    assert "src/auth.py" in report.files
    auth_report = report.files["src/auth.py"]
    assert len(auth_report.lines[2].mutants) == 2
    assert auth_report.lines[2].mutants[0].status == "Survived"
    assert auth_report.lines[2].mutants[1].status == "Killed"

def test_correlation():
    report = ProjectReport()
    parse_cobertura("tests/sample_cobertura.xml", report)
    parse_stryker("tests/sample_stryker.json", report)
    
    auth_report = report.files["src/auth.py"]
    # Line 2 is NOT covered in cobertura, but has mutants in stryker
    # Test Strength should be based only on covered lines.
    # Line 1 is covered, has 0 mutants -> score 1.0
    # Line 2 is NOT covered -> ignored for TSI
    assert auth_report.line_coverage == 0.5
    assert auth_report.test_strength == 1.0 

def test_parse_pit():
    report = ProjectReport()
    parse_pit("tests/sample_pit.xml", report)
    
    assert "Calculator.java" in report.files
    calc_report = report.files["Calculator.java"]
    assert len(calc_report.lines[10].mutants) == 2
    assert calc_report.lines[10].mutants[0].status == "KILLED"
    assert calc_report.lines[10].mutants[1].status == "SURVIVED"

def test_parse_mutmut():
    report = ProjectReport()
    parse_mutmut("tests/sample_mutmut.xml", report)

    assert "main.py" in report.files
    main_report = report.files["main.py"]
    assert main_report.lines[5].mutants[0].status == "Killed"
    assert main_report.lines[10].mutants[0].status == "Survived"

def test_path_reconciliation():
    report = ProjectReport()
    # Coverage uses short path (pytest-cov strips package prefix)
    parse_cobertura("tests/sample_cobertura.xml", report)
    # Rename coverage entry to simulate short path: "src/auth.py" -> "auth.py"
    report.files["auth.py"] = report.files.pop("src/auth.py")
    report.files["auth.py"].file_path = "auth.py"
    # Mutation data uses full path
    parse_stryker("tests/sample_stryker.json", report)
    # Now reconcile
    engine = AnalysisEngine()
    engine._reconcile_paths(report)
    # Short path should be merged into long path and removed
    assert "auth.py" not in report.files
    assert "src/auth.py" in report.files
    merged = report.files["src/auth.py"]
    # Coverage + mutation data both present
    assert merged.lines[1].is_covered is True
    assert len(merged.lines[2].mutants) > 0

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

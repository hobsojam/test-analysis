from tqa.models import ProjectReport
from tqa.parsers.cobertura import parse_cobertura
from tqa.parsers.stryker import parse_stryker

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

from tqa.parsers.pit import parse_pit
from tqa.parsers.mutmut import parse_mutmut

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

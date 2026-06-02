"""Tests that parsers produce user-friendly errors on bad input.

Each parser must:
- Raise ValueError (with context) for malformed XML/JSON.
- Raise FileNotFoundError (with path) for missing files.
- Silently skip or return empty for structurally incomplete but valid content.
- Never surface raw tracebacks (KeyError, AttributeError, etc.) to callers.
"""

import json
import pytest
from click.testing import CliRunner

from tqa.cli import main
from tqa.models import ComponentReport
from tqa.parsers.cobertura import parse_cobertura
from tqa.parsers.lcov import parse_lcov
from tqa.parsers.mutant import parse_mutant
from tqa.parsers.mutmut import parse_mutmut
from tqa.parsers.pit import parse_pit
from tqa.parsers.stryker import parse_stryker


# ---------------------------------------------------------------------------
# Cobertura
# ---------------------------------------------------------------------------


def test_cobertura_malformed_xml_raises_value_error(tmp_path):
    p = tmp_path / "bad.xml"
    p.write_text("not xml at all", encoding="utf-8")
    with pytest.raises(ValueError, match="Failed to parse Cobertura report"):
        parse_cobertura(str(p), ComponentReport())


def test_cobertura_unclosed_tag_raises_value_error(tmp_path):
    p = tmp_path / "bad.xml"
    p.write_text("<coverage>", encoding="utf-8")
    with pytest.raises(ValueError, match="Failed to parse Cobertura report"):
        parse_cobertura(str(p), ComponentReport())


def test_cobertura_empty_file_raises_value_error(tmp_path):
    p = tmp_path / "empty.xml"
    p.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="Failed to parse Cobertura report"):
        parse_cobertura(str(p), ComponentReport())


def test_cobertura_missing_file_raises_file_not_found():
    with pytest.raises((FileNotFoundError, ValueError)):
        parse_cobertura("/nonexistent/path/cobertura.xml", ComponentReport())


def test_cobertura_non_int_line_number_skips_gracefully(tmp_path):
    """A <line> with a non-integer number attribute is silently skipped."""
    xml = (
        '<?xml version="1.0"?>'
        "<coverage><packages><package><classes>"
        '<class filename="f.py"><lines>'
        '<line number="abc" hits="0"/>'
        "</lines></class></classes></package></packages></coverage>"
    )
    p = tmp_path / "bad_line.xml"
    p.write_text(xml, encoding="utf-8")
    component = ComponentReport()
    parse_cobertura(str(p), component)
    # File is registered but the bad line is skipped → no lines
    if "f.py" in component.files:
        assert component.files["f.py"].lines == {}


def test_cobertura_missing_filename_skips_class(tmp_path):
    """A <class> with no filename attribute is silently skipped."""
    xml = (
        '<?xml version="1.0"?>'
        "<coverage><packages><package><classes>"
        "<class><lines>"
        '<line number="1" hits="1"/>'
        "</lines></class></classes></package></packages></coverage>"
    )
    p = tmp_path / "no_filename.xml"
    p.write_text(xml, encoding="utf-8")
    component = ComponentReport()
    parse_cobertura(str(p), component)
    assert component.files == {}


def test_cobertura_error_message_contains_path(tmp_path):
    p = tmp_path / "broken.xml"
    p.write_text(">>>broken<<<", encoding="utf-8")
    with pytest.raises(ValueError) as exc_info:
        parse_cobertura(str(p), ComponentReport())
    assert str(p) in str(exc_info.value)


# ---------------------------------------------------------------------------
# PIT
# ---------------------------------------------------------------------------


def test_pit_malformed_xml_raises_value_error(tmp_path):
    p = tmp_path / "bad.xml"
    p.write_text("not xml", encoding="utf-8")
    with pytest.raises(ValueError, match="Failed to parse PIT report"):
        parse_pit(str(p), ComponentReport())


def test_pit_empty_file_raises_value_error(tmp_path):
    p = tmp_path / "empty.xml"
    p.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="Failed to parse PIT report"):
        parse_pit(str(p), ComponentReport())


def test_pit_non_int_line_number_skips(tmp_path):
    xml = (
        '<?xml version="1.0"?>'
        "<mutations>"
        '<mutation status="SURVIVED">'
        "<sourceFile>Calc.java</sourceFile>"
        "<lineNumber>notanumber</lineNumber>"
        "<mutator>SomeMutator</mutator>"
        "</mutation>"
        "</mutations>"
    )
    p = tmp_path / "bad_line.xml"
    p.write_text(xml, encoding="utf-8")
    component = ComponentReport()
    parse_pit(str(p), component)
    assert component.files == {}


def test_pit_missing_source_file_skips(tmp_path):
    xml = (
        '<?xml version="1.0"?>'
        "<mutations>"
        '<mutation status="SURVIVED">'
        "<lineNumber>5</lineNumber>"
        "<mutator>SomeMutator</mutator>"
        "</mutation>"
        "</mutations>"
    )
    p = tmp_path / "no_sf.xml"
    p.write_text(xml, encoding="utf-8")
    component = ComponentReport()
    parse_pit(str(p), component)
    assert component.files == {}


def test_pit_error_message_contains_path(tmp_path):
    p = tmp_path / "broken.xml"
    p.write_text("<mutations>", encoding="utf-8")
    with pytest.raises(ValueError) as exc_info:
        parse_pit(str(p), ComponentReport())
    assert str(p) in str(exc_info.value)


# ---------------------------------------------------------------------------
# mutmut
# ---------------------------------------------------------------------------


def test_mutmut_malformed_xml_raises_value_error(tmp_path):
    p = tmp_path / "bad.xml"
    p.write_text("not xml", encoding="utf-8")
    with pytest.raises(ValueError, match="Failed to parse mutmut report"):
        parse_mutmut(str(p), ComponentReport())


def test_mutmut_empty_file_raises_value_error(tmp_path):
    p = tmp_path / "empty.xml"
    p.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="Failed to parse mutmut report"):
        parse_mutmut(str(p), ComponentReport())


def test_mutmut_error_message_contains_path(tmp_path):
    p = tmp_path / "broken.xml"
    p.write_text("<<not_valid>>", encoding="utf-8")
    with pytest.raises(ValueError) as exc_info:
        parse_mutmut(str(p), ComponentReport())
    assert str(p) in str(exc_info.value)


# ---------------------------------------------------------------------------
# Stryker
# ---------------------------------------------------------------------------


def test_stryker_malformed_json_raises_value_error(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("not json at all", encoding="utf-8")
    with pytest.raises(ValueError, match="Failed to parse Stryker report"):
        parse_stryker(str(p), ComponentReport())


def test_stryker_empty_file_raises_value_error(tmp_path):
    p = tmp_path / "empty.json"
    p.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="Failed to parse Stryker report"):
        parse_stryker(str(p), ComponentReport())


def test_stryker_json_array_raises_value_error(tmp_path):
    """Top-level JSON array is not a valid Stryker report."""
    p = tmp_path / "array.json"
    p.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="expected a JSON object"):
        parse_stryker(str(p), ComponentReport())


def test_stryker_null_json_raises_value_error(tmp_path):
    p = tmp_path / "null.json"
    p.write_text("null", encoding="utf-8")
    with pytest.raises(ValueError, match="expected a JSON object"):
        parse_stryker(str(p), ComponentReport())


def test_stryker_mutant_missing_location_skips(tmp_path):
    """Mutants without a valid location are silently skipped."""
    data = {
        "files": {
            "src/app.js": {
                "mutants": [
                    {"id": "1", "mutatorName": "BooleanLiteral", "status": "Killed"}
                ]
            }
        }
    }
    p = tmp_path / "no_loc.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    component = ComponentReport()
    parse_stryker(str(p), component)
    # File may or may not be present, but no mutants were added
    if "src/app.js" in component.files:
        all_mutants = [
            m for ld in component.files["src/app.js"].lines.values() for m in ld.mutants
        ]
        assert all_mutants == []


def test_stryker_null_files_returns_empty_report(tmp_path):
    p = tmp_path / "null_files.json"
    p.write_text('{"files": null}', encoding="utf-8")
    component = ComponentReport()
    parse_stryker(str(p), component)
    assert component.files == {}


def test_stryker_error_message_contains_path(tmp_path):
    p = tmp_path / "broken.json"
    p.write_text("{invalid json}", encoding="utf-8")
    with pytest.raises(ValueError) as exc_info:
        parse_stryker(str(p), ComponentReport())
    assert str(p) in str(exc_info.value)


# ---------------------------------------------------------------------------
# Mutant (JSON)
# ---------------------------------------------------------------------------


def test_mutant_malformed_json_raises_value_error(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError, match="Failed to parse Mutant report"):
        parse_mutant(str(p), ComponentReport())


def test_mutant_empty_file_raises_value_error(tmp_path):
    p = tmp_path / "empty.json"
    p.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="Failed to parse Mutant report"):
        parse_mutant(str(p), ComponentReport())


def test_mutant_error_message_contains_path(tmp_path):
    p = tmp_path / "broken.json"
    p.write_text("{bad", encoding="utf-8")
    with pytest.raises(ValueError) as exc_info:
        parse_mutant(str(p), ComponentReport())
    assert str(p) in str(exc_info.value)


# ---------------------------------------------------------------------------
# LCOV
# ---------------------------------------------------------------------------


def test_lcov_non_numeric_da_line_skips(tmp_path):
    content = "SF:src/app.js\nDA:abc,1\nend_of_record\n"
    p = tmp_path / "bad.info"
    p.write_text(content, encoding="utf-8")
    component = ComponentReport()
    parse_lcov(str(p), component)
    # File is present but the bad DA line is skipped → no lines
    assert "src/app.js" in component.files
    assert component.files["src/app.js"].lines == {}


def test_lcov_empty_file_returns_empty_report(tmp_path):
    p = tmp_path / "empty.info"
    p.write_text("", encoding="utf-8")
    component = ComponentReport()
    parse_lcov(str(p), component)
    assert component.files == {}


def test_lcov_da_with_only_one_part_skips(tmp_path):
    """A DA line with only one comma-separated part is silently skipped."""
    content = "SF:src/app.js\nDA:5\nend_of_record\n"
    p = tmp_path / "partial_da.info"
    p.write_text(content, encoding="utf-8")
    component = ComponentReport()
    parse_lcov(str(p), component)
    assert "src/app.js" in component.files
    assert component.files["src/app.js"].lines == {}


# ---------------------------------------------------------------------------
# CLI — error messages shown as user-friendly output, not tracebacks
# ---------------------------------------------------------------------------


def test_cli_malformed_coverage_xml_exits_with_error(tmp_path):
    bad = tmp_path / "bad.xml"
    bad.write_text("not xml", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(main, ["analyze", "--coverage", str(bad)])
    assert result.exit_code != 0
    # Should show a friendly error, not a raw traceback keyword
    assert "Error:" in result.output or "Error:" in (result.stderr or "")
    assert "Traceback" not in (result.output or "")


def test_cli_malformed_stryker_json_exits_with_error(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(main, ["analyze", "--stryker", str(bad)])
    assert result.exit_code != 0
    assert "Traceback" not in (result.output or "")


def test_cli_malformed_pit_xml_exits_with_error(tmp_path):
    bad = tmp_path / "bad.xml"
    bad.write_text("<unclosed>", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(main, ["analyze", "--pit", str(bad)])
    assert result.exit_code != 0
    assert "Traceback" not in (result.output or "")


def test_cli_malformed_mutmut_xml_exits_with_error(tmp_path):
    bad = tmp_path / "bad.xml"
    bad.write_text("garbage", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(main, ["analyze", "--mutmut", str(bad)])
    assert result.exit_code != 0
    assert "Traceback" not in (result.output or "")


def test_cli_malformed_mutant_json_exits_with_error(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{bad json}", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(main, ["analyze", "--mutant", str(bad)])
    assert result.exit_code != 0
    assert "Traceback" not in (result.output or "")

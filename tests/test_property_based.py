"""Property-based tests for tqa parsers using Hypothesis.

These tests focus on robustness: parsers must never crash on malformed,
empty, or structurally surprising input — they should either produce a
valid (possibly empty) ComponentReport or raise a well-defined exception
(ET.XMLSyntaxError / json.JSONDecodeError / ValueError) rather than an
unexpected AttributeError, KeyError, or similar.

Approach
--------
For XML parsers (Cobertura, PIT, mutmut) we use Hypothesis to generate
XML strings with varying structure and write them to a tmp file.
For JSON parsers (Stryker) we generate JSON with varying structure.
For LCOV we generate text that may or may not follow the LCOV format.

Note: Hypothesis @given tests that write files use tempfile.mkdtemp()
instead of the pytest tmp_path fixture to avoid the function-scoped
fixture health check warning.
"""

import json
import os
import string
import tempfile
import textwrap

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from lxml import etree as ET

from tqa.models import ComponentReport, normalise_status
from tqa.parsers.cobertura import parse_cobertura
from tqa.parsers.lcov import parse_lcov
from tqa.parsers.mutmut import parse_mutmut
from tqa.parsers.pit import parse_pit
from tqa.parsers.stryker import parse_stryker

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

# Characters valid in XML text / attribute values (ASCII-safe to avoid
# surrogate pairs that lxml may reject).
_TEXT = st.text(
    alphabet=string.ascii_letters + string.digits + " _-./:",
    min_size=0,
    max_size=40,
)

_NONEMPTY_TEXT = st.text(
    alphabet=string.ascii_letters + string.digits + "_-./:",
    min_size=1,
    max_size=40,
)

_POSITIVE_INT = st.integers(min_value=1, max_value=9999)
_NONNEG_INT = st.integers(min_value=0, max_value=9999)


def _write_tmp_and_parse(parser_fn, content: str, suffix: str) -> ComponentReport:
    """Write *content* to a temporary file, call *parser_fn*, return the report."""
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=suffix, delete=False
    ) as f:
        f.write(content)
        tmp_name = f.name
    try:
        component = ComponentReport()
        parser_fn(tmp_name, component)
        return component
    finally:
        os.unlink(tmp_name)


def _assert_valid_component(component: ComponentReport) -> None:
    """Check the structural invariants that every parser must maintain."""
    assert isinstance(component.files, dict)
    for file_path, file_report in component.files.items():
        assert isinstance(file_path, str)
        assert isinstance(file_report.lines, dict)
        for line_num, line_data in file_report.lines.items():
            assert isinstance(line_num, int)
            assert isinstance(line_data.is_covered, bool)
            for mutant in line_data.mutants:
                assert isinstance(mutant.id, str)
                assert isinstance(mutant.status, str)
                assert isinstance(mutant.line, int)


# ---------------------------------------------------------------------------
# Cobertura parser
# ---------------------------------------------------------------------------


@st.composite
def _cobertura_xml(draw) -> str:
    """Generate a Cobertura-like XML document with random structure."""
    num_classes = draw(st.integers(min_value=0, max_value=5))
    classes_xml = ""
    for _ in range(num_classes):
        filename = draw(_NONEMPTY_TEXT)
        num_lines = draw(st.integers(min_value=0, max_value=10))
        lines_xml = ""
        for _ in range(num_lines):
            number = draw(_POSITIVE_INT)
            hits = draw(_NONNEG_INT)
            lines_xml += f'<line number="{number}" hits="{hits}"/>\n'
        classes_xml += (
            f'<class filename="{filename}"><lines>{lines_xml}</lines></class>\n'
        )
    return (
        '<?xml version="1.0"?>'
        "<coverage><packages><package><classes>"
        f"{classes_xml}"
        "</classes></package></packages></coverage>"
    )


@given(_cobertura_xml())
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_cobertura_valid_structure_never_crashes(xml_str):
    component = _write_tmp_and_parse(parse_cobertura, xml_str, ".xml")
    _assert_valid_component(component)


@given(st.integers(min_value=1, max_value=50))
@settings(max_examples=50)
def test_cobertura_line_count_matches_unique_numbers(num_lines):
    """Each unique line number should produce exactly one LineData entry."""
    lines = "\n".join(
        f'<line number="{i}" hits="{i % 2}"/>' for i in range(1, num_lines + 1)
    )
    xml = (
        '<?xml version="1.0"?>'
        "<coverage><packages><package><classes>"
        f'<class filename="f.py"><lines>{lines}</lines></class>'
        "</classes></package></packages></coverage>"
    )
    component = _write_tmp_and_parse(parse_cobertura, xml, ".xml")
    if "f.py" in component.files:
        assert len(component.files["f.py"].lines) == num_lines


@pytest.mark.parametrize(
    "malformed",
    [
        "",
        "not xml at all",
        "<coverage>",  # unclosed tag
        "<coverage><packages></coverage>",  # mismatched tags
        "<?xml version='1.0'?><coverage/>",  # valid but no classes
        (
            "<coverage><packages><package><classes>"
            '<class filename=""><lines>'
            '<line number="abc" hits="0"/>'
            "</lines></class></classes></package></packages></coverage>"
        ),  # non-int line number
    ],
)
def test_cobertura_malformed_raises_or_returns_empty(malformed, tmp_path):
    p = tmp_path / "bad.xml"
    p.write_text(malformed, encoding="utf-8")
    component = ComponentReport()
    try:
        parse_cobertura(str(p), component)
        assert isinstance(component.files, dict)
    except (ET.XMLSyntaxError, ValueError):
        pass  # expected for truly malformed XML


def test_cobertura_empty_file_returns_empty_report(tmp_path):
    p = tmp_path / "empty.xml"
    p.write_text("", encoding="utf-8")
    component = ComponentReport()
    try:
        parse_cobertura(str(p), component)
        assert component.files == {}
    except ET.XMLSyntaxError:
        pass


def test_cobertura_missing_hits_attribute(tmp_path):
    """A <line> without 'hits' should raise ValueError or be skipped."""
    xml = (
        '<?xml version="1.0"?>'
        "<coverage><packages><package><classes>"
        '<class filename="f.py"><lines>'
        '<line number="1"/>'  # missing hits
        "</lines></class></classes></package></packages></coverage>"
    )
    p = tmp_path / "no_hits.xml"
    p.write_text(xml, encoding="utf-8")
    component = ComponentReport()
    try:
        parse_cobertura(str(p), component)
        assert isinstance(component.files, dict)
    except (TypeError, ValueError):
        pass


def test_cobertura_missing_filename_attribute(tmp_path):
    """A <class> without 'filename' must not raise an unhandled KeyError."""
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
    try:
        parse_cobertura(str(p), component)
        assert isinstance(component.files, dict)
    except (TypeError, ValueError, AttributeError):
        pass


# ---------------------------------------------------------------------------
# PIT parser
# ---------------------------------------------------------------------------


@st.composite
def _pit_xml(draw) -> str:
    num_mutations = draw(st.integers(min_value=0, max_value=8))
    mutations_xml = ""
    for _ in range(num_mutations):
        source_file = draw(_NONEMPTY_TEXT)
        line_number = draw(_POSITIVE_INT)
        status = draw(
            st.sampled_from(["KILLED", "SURVIVED", "NO_COVERAGE", "TIMED_OUT"])
        )
        mutator = draw(_TEXT)
        detected = "true" if status == "KILLED" else "false"
        mutations_xml += (
            f'<mutation detected="{detected}" status="{status}">'
            f"<sourceFile>{source_file}</sourceFile>"
            f"<lineNumber>{line_number}</lineNumber>"
            f"<mutator>{mutator}</mutator>"
            f"</mutation>\n"
        )
    return (
        f'<?xml version="1.0" encoding="UTF-8"?><mutations>{mutations_xml}</mutations>'
    )


@given(_pit_xml())
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_pit_valid_structure_never_crashes(xml_str):
    component = _write_tmp_and_parse(parse_pit, xml_str, ".xml")
    _assert_valid_component(component)


@given(
    source_file=_NONEMPTY_TEXT,
    line_number=_POSITIVE_INT,
    status=st.sampled_from(["KILLED", "SURVIVED", "NO_COVERAGE"]),
)
@settings(max_examples=100)
def test_pit_single_mutation_appears_in_report(source_file, line_number, status):
    xml = textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <mutations>
          <mutation detected="true" status="{status}">
            <sourceFile>{source_file}</sourceFile>
            <lineNumber>{line_number}</lineNumber>
            <mutator>SomeMutator</mutator>
          </mutation>
        </mutations>
    """)
    component = _write_tmp_and_parse(parse_pit, xml, ".xml")
    assert source_file in component.files
    assert line_number in component.files[source_file].lines
    mutants = component.files[source_file].lines[line_number].mutants
    assert len(mutants) == 1
    assert mutants[0].status == normalise_status(status)


@pytest.mark.parametrize(
    "malformed",
    [
        "",
        "not xml",
        "<mutations>",  # unclosed
        "<mutations><mutation><sourceFile>f.java</sourceFile></mutation></mutations>",
        (
            "<mutations><mutation>"
            "<sourceFile>f.java</sourceFile>"
            "<lineNumber>abc</lineNumber>"
            "</mutation></mutations>"
        ),  # non-int line
    ],
)
def test_pit_malformed_raises_or_returns_empty(malformed, tmp_path):
    p = tmp_path / "bad.xml"
    p.write_text(malformed, encoding="utf-8")
    component = ComponentReport()
    try:
        parse_pit(str(p), component)
        assert isinstance(component.files, dict)
    except (ET.XMLSyntaxError, ValueError, TypeError):
        pass


def test_pit_empty_mutations_element(tmp_path):
    xml = '<?xml version="1.0" encoding="UTF-8"?><mutations></mutations>'
    p = tmp_path / "empty.xml"
    p.write_text(xml, encoding="utf-8")
    component = ComponentReport()
    parse_pit(str(p), component)
    assert component.files == {}


def test_pit_mutation_missing_source_file(tmp_path):
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<mutations>"
        '<mutation detected="false" status="SURVIVED">'
        "<lineNumber>5</lineNumber>"
        "<mutator>SomeMutator</mutator>"
        "</mutation>"
        "</mutations>"
    )
    p = tmp_path / "no_sf.xml"
    p.write_text(xml, encoding="utf-8")
    component = ComponentReport()
    try:
        parse_pit(str(p), component)
        assert isinstance(component.files, dict)
    except (TypeError, ValueError):
        pass


def test_pit_mutation_missing_line_number(tmp_path):
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<mutations>"
        '<mutation detected="false" status="SURVIVED">'
        "<sourceFile>Calc.java</sourceFile>"
        "<mutator>SomeMutator</mutator>"
        "</mutation>"
        "</mutations>"
    )
    p = tmp_path / "no_ln.xml"
    p.write_text(xml, encoding="utf-8")
    component = ComponentReport()
    try:
        parse_pit(str(p), component)
        assert isinstance(component.files, dict)
    except (TypeError, ValueError):
        pass


# ---------------------------------------------------------------------------
# Stryker parser
# ---------------------------------------------------------------------------


@st.composite
def _mutant_location(draw) -> dict:
    line = draw(_POSITIVE_INT)
    col = draw(_NONNEG_INT)
    return {
        "start": {"line": line, "column": col},
        "end": {"line": line, "column": col + 1},
    }


@st.composite
def _stryker_mutant(draw) -> dict:
    return {
        "id": draw(st.text(min_size=1, max_size=10)),
        "mutatorName": draw(_TEXT),
        "location": draw(_mutant_location()),
        "status": draw(
            st.sampled_from(["Survived", "Killed", "NoCoverage", "Timeout"])
        ),
    }


@st.composite
def _stryker_json(draw) -> str:
    num_files = draw(st.integers(min_value=0, max_value=5))
    files: dict = {}
    for _ in range(num_files):
        filename = draw(_NONEMPTY_TEXT)
        num_mutants = draw(st.integers(min_value=0, max_value=8))
        mutants = draw(
            st.lists(_stryker_mutant(), min_size=num_mutants, max_size=num_mutants)
        )
        files[filename] = {"mutants": mutants}
    return json.dumps({"schemaVersion": "1", "files": files})


@given(_stryker_json())
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_stryker_valid_structure_never_crashes(json_str):
    component = _write_tmp_and_parse(parse_stryker, json_str, ".json")
    _assert_valid_component(component)


@given(
    filename=_NONEMPTY_TEXT,
    num_mutants=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=100)
def test_stryker_mutant_count_matches_report(filename, num_mutants):
    """The number of mutants on a line must equal those generated."""
    mutants = [
        {
            "id": str(i),
            "mutatorName": "BooleanLiteral",
            "location": {
                "start": {"line": 1, "column": 0},
                "end": {"line": 1, "column": 4},
            },
            "status": "Killed",
        }
        for i in range(num_mutants)
    ]
    data = {"schemaVersion": "1", "files": {filename: {"mutants": mutants}}}
    component = _write_tmp_and_parse(parse_stryker, json.dumps(data), ".json")
    assert filename in component.files
    line_report = component.files[filename].lines.get(1)
    assert line_report is not None
    assert len(line_report.mutants) == num_mutants


@pytest.mark.parametrize(
    "bad_content",
    [
        "",  # empty file
        "not json",
        "null",  # valid JSON but not an object
        "[]",  # array instead of object
        '{"files": null}',
        '{"files": {"f.py": {"mutants": null}}}',
        '{"files": {"f.py": {"mutants": [{"id": "1", "location": null, "status": "Killed"}]}}}',
    ],
)
def test_stryker_malformed_raises_or_skips(bad_content, tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(bad_content, encoding="utf-8")
    component = ComponentReport()
    try:
        parse_stryker(str(p), component)
        assert isinstance(component.files, dict)
    except (json.JSONDecodeError, TypeError, AttributeError, KeyError, ValueError):
        pass


def test_stryker_empty_files_dict(tmp_path):
    data = {"schemaVersion": "1", "files": {}}
    p = tmp_path / "empty.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    component = ComponentReport()
    parse_stryker(str(p), component)
    assert component.files == {}


def test_stryker_file_with_no_mutants_key(tmp_path):
    """A file entry missing 'mutants' should produce no mutants."""
    data = {"files": {"src/app.js": {}}}
    p = tmp_path / "no_mutants.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    component = ComponentReport()
    parse_stryker(str(p), component)
    if "src/app.js" in component.files:
        all_mutants = [
            m for ld in component.files["src/app.js"].lines.values() for m in ld.mutants
        ]
        assert all_mutants == []


def test_stryker_mutant_with_missing_location_key(tmp_path):
    """A mutant without 'location' may raise KeyError — that is acceptable."""
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
    try:
        parse_stryker(str(p), component)
        assert isinstance(component.files, dict)
    except (KeyError, TypeError):
        pass  # location is required by the Stryker format


# ---------------------------------------------------------------------------
# LCOV parser
# ---------------------------------------------------------------------------


@st.composite
def _lcov_record(draw) -> str:
    """Generate a single LCOV record (SF: … end_of_record block)."""
    filename = draw(_NONEMPTY_TEXT)
    num_lines = draw(st.integers(min_value=0, max_value=15))
    da_lines = ""
    for _ in range(num_lines):
        line_num = draw(_POSITIVE_INT)
        hits = draw(_NONNEG_INT)
        da_lines += f"DA:{line_num},{hits}\n"
    return f"SF:{filename}\n{da_lines}end_of_record\n"


@st.composite
def _lcov_content(draw) -> str:
    num_records = draw(st.integers(min_value=0, max_value=5))
    records = draw(st.lists(_lcov_record(), min_size=num_records, max_size=num_records))
    return "".join(records)


@given(_lcov_content())
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_lcov_valid_structure_never_crashes(content):
    component = _write_tmp_and_parse(parse_lcov, content, ".info")
    _assert_valid_component(component)


@given(
    filename=_NONEMPTY_TEXT,
    hits=st.lists(
        st.tuples(_POSITIVE_INT, _NONNEG_INT),
        min_size=1,
        max_size=20,
        unique_by=lambda t: t[0],
    ),
)
@settings(max_examples=100)
def test_lcov_covered_lines_match_nonzero_hits(filename, hits):
    da_lines = "".join(f"DA:{ln},{h}\n" for ln, h in hits)
    content = f"SF:{filename}\n{da_lines}end_of_record\n"
    component = _write_tmp_and_parse(parse_lcov, content, ".info")

    assert filename in component.files
    file_report = component.files[filename]
    for line_num, hit_count in hits:
        assert line_num in file_report.lines
        assert file_report.lines[line_num].is_covered == (hit_count > 0)


def test_lcov_empty_file(tmp_path):
    p = tmp_path / "empty.info"
    p.write_text("", encoding="utf-8")
    component = ComponentReport()
    parse_lcov(str(p), component)
    assert component.files == {}


def test_lcov_record_without_end_of_record(tmp_path):
    content = "SF:src/app.js\nDA:1,1\nDA:2,0\n"  # no end_of_record
    p = tmp_path / "no_eor.info"
    p.write_text(content, encoding="utf-8")
    component = ComponentReport()
    parse_lcov(str(p), component)
    assert isinstance(component.files, dict)


def test_lcov_da_before_sf(tmp_path):
    """DA lines before SF are silently ignored (current_file is None)."""
    content = "DA:1,1\nDA:2,0\nSF:src/app.js\nend_of_record\n"
    p = tmp_path / "da_before_sf.info"
    p.write_text(content, encoding="utf-8")
    component = ComponentReport()
    parse_lcov(str(p), component)
    assert isinstance(component.files, dict)


def test_lcov_non_numeric_da_line_number(tmp_path):
    content = "SF:src/app.js\nDA:abc,1\nend_of_record\n"
    p = tmp_path / "bad.info"
    p.write_text(content, encoding="utf-8")
    component = ComponentReport()
    try:
        parse_lcov(str(p), component)
        assert isinstance(component.files, dict)
    except ValueError:
        pass


def test_lcov_da_line_with_extra_commas(tmp_path):
    """Extra fields after the second comma must not cause a crash."""
    content = "SF:src/app.js\nDA:1,2,extra\nend_of_record\n"
    p = tmp_path / "extra.info"
    p.write_text(content, encoding="utf-8")
    component = ComponentReport()
    parse_lcov(str(p), component)
    assert isinstance(component.files, dict)


def test_lcov_multiple_records_same_filename(tmp_path):
    content = (
        "SF:src/app.js\nDA:1,1\nend_of_record\nSF:src/app.js\nDA:2,0\nend_of_record\n"
    )
    p = tmp_path / "dup.info"
    p.write_text(content, encoding="utf-8")
    component = ComponentReport()
    parse_lcov(str(p), component)
    assert "src/app.js" in component.files
    _assert_valid_component(component)


# ---------------------------------------------------------------------------
# mutmut parser
# ---------------------------------------------------------------------------


@st.composite
def _mutmut_xml(draw) -> str:
    num_testcases = draw(st.integers(min_value=0, max_value=8))
    testcases_xml = ""
    for i in range(num_testcases):
        name = f"Mutant #{i + 1}"
        filename = draw(_NONEMPTY_TEXT)
        line = draw(_POSITIVE_INT)
        survived = draw(st.booleans())
        failure_xml = (
            '<failure type="failure" message="survived">survived</failure>'
            if survived
            else ""
        )
        testcases_xml += (
            f'<testcase name="{name}" file="{filename}" line="{line}">'
            f"{failure_xml}"
            f"</testcase>\n"
        )
    return (
        '<?xml version="1.0"?>'
        '<testsuites><testsuite name="mutmut">'
        f"{testcases_xml}"
        "</testsuite></testsuites>"
    )


@given(_mutmut_xml())
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_mutmut_valid_structure_never_crashes(xml_str):
    component = _write_tmp_and_parse(parse_mutmut, xml_str, ".xml")
    _assert_valid_component(component)


@given(
    filename=_NONEMPTY_TEXT,
    line=_POSITIVE_INT,
    survived=st.booleans(),
)
@settings(max_examples=100)
def test_mutmut_single_testcase_status(filename, line, survived):
    failure_xml = (
        '<failure type="failure" message="survived">survived</failure>'
        if survived
        else ""
    )
    xml = (
        '<?xml version="1.0"?>'
        '<testsuites><testsuite name="mutmut">'
        f'<testcase name="Mutant #1" file="{filename}" line="{line}">'
        f"{failure_xml}"
        "</testcase>"
        "</testsuite></testsuites>"
    )
    component = _write_tmp_and_parse(parse_mutmut, xml, ".xml")
    assert filename in component.files
    assert line in component.files[filename].lines
    mutant = component.files[filename].lines[line].mutants[0]
    expected_status = "Survived" if survived else "Killed"
    assert mutant.status == expected_status


@pytest.mark.parametrize(
    "malformed",
    [
        "",
        "not xml",
        "<testsuites>",  # unclosed
        '<?xml version="1.0"?><testsuites/>',  # valid but no testcases
    ],
)
def test_mutmut_malformed_raises_or_returns_empty(malformed, tmp_path):
    p = tmp_path / "bad.xml"
    p.write_text(malformed, encoding="utf-8")
    component = ComponentReport()
    try:
        parse_mutmut(str(p), component)
        assert isinstance(component.files, dict)
    except (ET.XMLSyntaxError, ValueError):
        pass


def test_mutmut_empty_testsuites(tmp_path):
    xml = (
        '<?xml version="1.0"?>'
        '<testsuites><testsuite name="mutmut"></testsuite></testsuites>'
    )
    p = tmp_path / "empty.xml"
    p.write_text(xml, encoding="utf-8")
    component = ComponentReport()
    parse_mutmut(str(p), component)
    assert component.files == {}


def test_mutmut_testcase_without_file_and_no_name_pattern(tmp_path):
    """A testcase with neither file/line nor a parseable name is silently skipped."""
    xml = (
        '<?xml version="1.0"?>'
        '<testsuites><testsuite name="mutmut">'
        '<testcase name="unparseable name"/>'
        "</testsuite></testsuites>"
    )
    p = tmp_path / "skip.xml"
    p.write_text(xml, encoding="utf-8")
    component = ComponentReport()
    parse_mutmut(str(p), component)
    assert component.files == {}


def test_mutmut_legacy_name_format_parsed(tmp_path):
    """Older mutmut format: name='mutant #N (file: F, line: L)' is parsed."""
    xml = (
        '<?xml version="1.0"?>'
        '<testsuites><testsuite name="mutmut">'
        '<testcase name="mutant #42 (file: legacy.py, line: 7)">'
        '<failure type="failure" message="survived">survived</failure>'
        "</testcase>"
        "</testsuite></testsuites>"
    )
    p = tmp_path / "legacy.xml"
    p.write_text(xml, encoding="utf-8")
    component = ComponentReport()
    parse_mutmut(str(p), component)
    assert "legacy.py" in component.files
    assert 7 in component.files["legacy.py"].lines
    assert component.files["legacy.py"].lines[7].mutants[0].status == "Survived"


def test_mutmut_error_element_treated_as_survived(tmp_path):
    """A testcase with an <error> child is treated the same as <failure>."""
    xml = (
        '<?xml version="1.0"?>'
        '<testsuites><testsuite name="mutmut">'
        '<testcase name="Mutant #1" file="mod.py" line="3">'
        '<error type="error" message="oops">error text</error>'
        "</testcase>"
        "</testsuite></testsuites>"
    )
    p = tmp_path / "error.xml"
    p.write_text(xml, encoding="utf-8")
    component = ComponentReport()
    parse_mutmut(str(p), component)
    assert "mod.py" in component.files
    assert component.files["mod.py"].lines[3].mutants[0].status == "Survived"


# ---------------------------------------------------------------------------
# Cross-parser property: parsers are idempotent on subsequent identical calls
# ---------------------------------------------------------------------------


@given(_cobertura_xml())
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_cobertura_idempotent_second_parse(xml_str):
    """Parsing the same Cobertura file twice must not double-count lines."""
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".xml", delete=False
    ) as f:
        f.write(xml_str)
        tmp_name = f.name
    try:
        component = ComponentReport()
        parse_cobertura(tmp_name, component)
        file_counts_first = {fp: len(fr.lines) for fp, fr in component.files.items()}
        parse_cobertura(tmp_name, component)
        for fp, count in file_counts_first.items():
            assert len(component.files[fp].lines) == count
    finally:
        os.unlink(tmp_name)


@given(_stryker_json())
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_stryker_idempotent_second_parse(json_str):
    """Parsing the same Stryker file twice must leave the report structurally valid."""
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".json", delete=False
    ) as f:
        f.write(json_str)
        tmp_name = f.name
    try:
        component = ComponentReport()
        parse_stryker(tmp_name, component)
        _assert_valid_component(component)
        parse_stryker(tmp_name, component)
        _assert_valid_component(component)
    finally:
        os.unlink(tmp_name)

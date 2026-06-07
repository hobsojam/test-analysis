import json
from tqa.models import ComponentReport, MutantStatus, normalise_status
from tqa.parsers.mutant import (
    _description,
    _diff_summary,
    _extract_mutant,
    _first_dict,
    _first_int,
    _first_string,
    _line_from_identification,
    _line_from_location,
    _looks_like_mutation_result,
    _normalize_path,
    _status_from,
    _status_from_criteria,
    _subject_description,
    parse_mutant,
)


# --- _normalize_path ---


def test_normalize_path_leaves_absolute_path_unchanged():
    assert _normalize_path("/work/lib/foo.rb") == "/work/lib/foo.rb"


def test_normalize_path_leaves_plain_path_unchanged():
    assert _normalize_path("lib/foo.rb") == "lib/foo.rb"


def test_normalize_path_converts_backslashes():
    assert _normalize_path("lib\\foo.rb") == "lib/foo.rb"


# --- _looks_like_mutation_result ---


def test_looks_like_mutation_result_new_format():
    assert (
        _looks_like_mutation_result({"mutation_result": {}, "criteria_result": {}})
        is True
    )


def test_looks_like_mutation_result_requires_both_dicts():
    assert (
        _looks_like_mutation_result(
            {"mutation_result": "not a dict", "criteria_result": {}}
        )
        is False
    )


# --- _line_from_location ---


def test_line_from_location_happy_path():
    assert _line_from_location({"location": {"start": {"line": 42}}}) == 42


def test_line_from_location_no_location_key():
    assert _line_from_location({}) is None


def test_line_from_location_location_not_dict():
    assert _line_from_location({"location": "string"}) is None


def test_line_from_location_start_not_dict():
    assert _line_from_location({"location": {"start": 5}}) is None


def test_line_from_location_line_not_int():
    assert _line_from_location({"location": {"start": {"line": "five"}}}) is None


# --- _line_from_identification ---


def test_line_from_identification_mutation_identification_key():
    assert (
        _line_from_identification({"mutation_identification": "lib/foo.rb:15:Add"})
        == 15
    )


def test_line_from_identification_identification_key():
    assert _line_from_identification({"identification": "lib/bar.rb:20:Sub"}) == 20


def test_line_from_identification_no_match():
    assert (
        _line_from_identification({"mutation_identification": "no-colons-here"}) is None
    )


def test_line_from_identification_not_string():
    assert _line_from_identification({"mutation_identification": 99}) is None


def test_line_from_identification_missing_key():
    assert _line_from_identification({}) is None


# --- _status_from_criteria ---


def test_status_from_criteria_test_result_true():
    assert _status_from_criteria({"test_result": True}) == "killed"


def test_status_from_criteria_timeout():
    assert _status_from_criteria({"timeout": True}) == "timeout"


def test_status_from_criteria_process_abort():
    assert _status_from_criteria({"process_abort": True}) == "error"


def test_status_from_criteria_no_flags():
    assert _status_from_criteria({}) == "survived"


# --- _status_from ---


def test_status_from_uses_criteria_result():
    assert _status_from({"criteria_result": {"test_result": True}}) == "killed"


def test_status_from_returns_none_with_empty_dict():
    assert _status_from({}) is None


# --- _first_int ---


def test_first_int_accepts_string_digit():
    assert _first_int([{"line": "42"}], "line") == 42


def test_first_int_uses_location_start_line():
    assert _first_int([{"location": {"start": {"line": 7}}}], "missing_key") == 7


def test_first_int_uses_mutation_identification():
    assert (
        _first_int([{"mutation_identification": "lib/foo.rb:33:Add"}], "missing_key")
        == 33
    )


# --- _first_dict ---


def test_first_dict_returns_empty_when_no_dicts():
    assert _first_dict("string", 42, None) == {}


# --- _first_string ---


def test_first_string_returns_none_when_nothing_found():
    assert _first_string([{"x": 1}], "missing") is None


# --- _diff_summary ---


def test_diff_summary_none_returns_none():
    assert _diff_summary(None) is None


def test_diff_summary_empty_returns_none():
    assert _diff_summary("") is None


def test_diff_summary_only_context_lines_returns_none():
    assert _diff_summary(" context line\n another context line\n") is None


# --- normalise_status ---


def test_normalise_status_unknown_returns_unknown():
    assert normalise_status("SomeUnknownStatus") == MutantStatus.UNKNOWN


def test_normalise_status_killed_variants():
    assert normalise_status("KILLED") == MutantStatus.KILLED
    assert normalise_status("killed") == MutantStatus.KILLED
    assert normalise_status("dead") == MutantStatus.KILLED


def test_normalise_status_survived_variants():
    assert normalise_status("SURVIVED") == MutantStatus.SURVIVED
    assert normalise_status("alive") == MutantStatus.SURVIVED


def test_normalise_status_timeout_variants():
    assert normalise_status("TIMED_OUT") == MutantStatus.TIMED_OUT
    assert normalise_status("timeout") == MutantStatus.TIMED_OUT


def test_normalise_status_no_coverage_variants():
    assert normalise_status("NO_COVERAGE") == MutantStatus.NO_COVERAGE
    assert normalise_status("NoCoverage") == MutantStatus.NO_COVERAGE


# --- _description ---


def test_description_returns_none_when_no_parts():
    assert _description({}, {}, ()) is None


# --- _subject_description ---


def test_subject_description_string_subject():
    assert _subject_description({"subject": "MyClass#method"}, ()) == "MyClass#method"


def test_subject_description_falls_back_to_identification():
    assert (
        _subject_description({"identification": "MyClass#method"}, ())
        == "MyClass#method"
    )


# --- _extract_mutant ---


def test_extract_mutant_returns_none_when_no_file_path():
    assert _extract_mutant({"status": "alive"}, ()) is None


def test_extract_mutant_returns_none_when_no_status():
    assert _extract_mutant({"source_path": "lib/foo.rb", "source_line": 5}, ()) is None


# --- parse_mutant: criteria_result session format ---


def _write_session(tmp_path, results):
    p = tmp_path / "session.json"
    p.write_text(json.dumps({"results": results}), encoding="utf-8")
    return str(p)


def test_parse_mutant_criteria_result_survived(tmp_path):
    path = _write_session(
        tmp_path,
        [
            {
                "mutation_result": {
                    "source_path": "lib/calc.rb",
                    "mutation_identification": "lib/calc.rb:10:Add",
                },
                "criteria_result": {"test_result": False},
            }
        ],
    )
    component = ComponentReport()
    parse_mutant(path, component)
    assert component.files["lib/calc.rb"].lines[10].mutants[0].status == "Survived"


def test_parse_mutant_criteria_result_killed(tmp_path):
    path = _write_session(
        tmp_path,
        [
            {
                "mutation_result": {
                    "source_path": "lib/calc.rb",
                    "mutation_identification": "lib/calc.rb:10:Add",
                },
                "criteria_result": {"test_result": True},
            }
        ],
    )
    component = ComponentReport()
    parse_mutant(path, component)
    assert component.files["lib/calc.rb"].lines[10].mutants[0].status == "Killed"


def test_parse_mutant_criteria_result_timeout(tmp_path):
    path = _write_session(
        tmp_path,
        [
            {
                "mutation_result": {
                    "source_path": "lib/calc.rb",
                    "mutation_identification": "lib/calc.rb:10:Add",
                },
                "criteria_result": {"timeout": True},
            }
        ],
    )
    component = ComponentReport()
    parse_mutant(path, component)
    assert (
        component.files["lib/calc.rb"].lines[10].mutants[0].status
        == MutantStatus.TIMED_OUT
    )


def test_parse_mutant_criteria_result_process_abort(tmp_path):
    path = _write_session(
        tmp_path,
        [
            {
                "mutation_result": {
                    "source_path": "lib/calc.rb",
                    "mutation_identification": "lib/calc.rb:10:Add",
                },
                "criteria_result": {"process_abort": True},
            }
        ],
    )
    component = ComponentReport()
    parse_mutant(path, component)
    assert component.files["lib/calc.rb"].lines[10].mutants[0].status == "Killed"


def test_parse_mutant_criteria_result_survived_no_flags(tmp_path):
    path = _write_session(
        tmp_path,
        [
            {
                "mutation_result": {
                    "source_path": "lib/calc.rb",
                    "mutation_identification": "lib/calc.rb:10:Add",
                },
                "criteria_result": {},
            }
        ],
    )
    component = ComponentReport()
    parse_mutant(path, component)
    assert component.files["lib/calc.rb"].lines[10].mutants[0].status == "Survived"


def test_parse_mutant_absolute_path_preserved(tmp_path):
    path = _write_session(
        tmp_path,
        [
            {
                "mutation_result": {
                    "source_path": "/work/lib/foo.rb",
                    "mutation_identification": "/work/lib/foo.rb:5:Add",
                },
                "criteria_result": {"test_result": False},
            }
        ],
    )
    component = ComponentReport()
    parse_mutant(path, component)
    assert "/work/lib/foo.rb" in component.files


def test_parse_mutant_skips_unparseable_results(tmp_path):
    path = _write_session(tmp_path, [{"mutation_result": {}, "criteria_result": {}}])
    component = ComponentReport()
    parse_mutant(path, component)
    assert component.files == {}


def test_parse_mutant_mutation_diff_included_in_description(tmp_path):
    path = _write_session(
        tmp_path,
        [
            {
                "mutation_result": {
                    "source_path": "lib/calc.rb",
                    "mutation_identification": "lib/calc.rb:10:Add",
                    "mutation_type": "Add",
                    "mutation_diff": "-  a + b\n+  a - b\n",
                },
                "criteria_result": {"test_result": False},
            }
        ],
    )
    component = ComponentReport()
    parse_mutant(path, component)
    mutant = component.files["lib/calc.rb"].lines[10].mutants[0]
    assert mutant.description is not None
    assert "a + b" in mutant.description


def test_parse_mutant_line_extracted_from_mutation_identification(tmp_path):
    path = _write_session(
        tmp_path,
        [
            {
                "mutation_result": {
                    "source_path": "lib/calc.rb",
                    "mutation_identification": "lib/calc.rb:99:Negate",
                },
                "criteria_result": {"test_result": False},
            }
        ],
    )
    component = ComponentReport()
    parse_mutant(path, component)
    assert 99 in component.files["lib/calc.rb"].lines

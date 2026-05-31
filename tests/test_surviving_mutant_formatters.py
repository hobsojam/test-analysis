import pytest
from io import StringIO
from rich.console import Console
from tqa.formatters.console import print_summary_table
from tqa.formatters.github import generate_markdown_summary
from tqa.formatters.surviving_mutants import (
    coverage_label,
    mutant_count_label,
    mutator_descriptions,
    sorted_surviving_findings,
    SURVIVING_MUTANT_LIMIT,
)
from tqa.models import ComponentReport, FileReport, LineData, MutantData, ProjectReport


@pytest.fixture(autouse=True)
def clear_github_actions_env(monkeypatch):
    """Ensure GitHub Actions env vars are absent so file links don't appear in output."""
    monkeypatch.delenv("GITHUB_SERVER_URL", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("GITHUB_SHA", raising=False)


def _report_with_lines(
    lines: list[tuple[str, int, bool, list[tuple[str, str, str | None]]]],
) -> ProjectReport:
    report = ProjectReport()
    component = ComponentReport()

    for file_path, line_number, covered, mutants in lines:
        if file_path not in component.files:
            component.files[file_path] = FileReport(file_path=file_path)
        component.files[file_path].lines[line_number] = LineData(
            line_number=line_number,
            is_covered=covered,
            mutants=[
                MutantData(
                    id=mutant_id,
                    status=status,
                    line=line_number,
                    description=description,
                )
                for mutant_id, status, description in mutants
            ],
        )

    report.components["default"] = component
    return report


def test_github_formatter_reports_surviving_mutants_with_line_counts_and_mutators():
    report = _report_with_lines(
        [
            (
                "src/api.py",
                12,
                True,
                [
                    ("1", "Killed", "ArithmeticOperator"),
                    ("2", "Survived", "ConditionalBoundary"),
                    ("3", "Survived", "ConditionalBoundary"),
                ],
            ),
            (
                "src/model.py",
                3,
                True,
                [("4", "Survived", "ReturnValue")],
            ),
        ]
    )

    markdown = generate_markdown_summary(report)

    assert "**Surviving Mutants**" in markdown
    assert (
        "| `src/model.py` | 3 | Covered | 1/1 survived | ReturnValue | "
        "Assert the exact returned value for this path. |"
    ) in markdown
    assert (
        "| `src/api.py` | 12 | Covered | 1 killed, 2/3 survived | "
        "ConditionalBoundary | Add branch or boundary-value tests that distinguish "
        "each side of this condition. |"
    ) in markdown


def test_github_formatter_orders_fully_survived_before_partial_survived():
    report = _report_with_lines(
        [
            (
                "src/partial.py",
                20,
                True,
                [
                    ("1", "Killed", "MathMutator"),
                    ("2", "Survived", "MathMutator"),
                    ("3", "Survived", "MathMutator"),
                ],
            ),
            (
                "src/full.py",
                10,
                True,
                [("4", "Survived", "ReturnValue")],
            ),
        ]
    )

    markdown = generate_markdown_summary(report)
    surviving_section = markdown.split("**Surviving Mutants**", 1)[1]

    assert surviving_section.index("`src/full.py`") < surviving_section.index(
        "`src/partial.py`"
    )


def test_github_formatter_limits_surviving_mutants_to_top_10():
    report = _report_with_lines(
        [
            (
                f"src/file_{i}.py",
                i,
                True,
                [(str(i), "Survived", f"Mutator{i}")],
            )
            for i in range(1, 12)
        ]
    )

    markdown = generate_markdown_summary(report)

    assert markdown.count(" survived | Mutator") == 10
    assert "Showing top 10 of 11 findings" in markdown


def test_console_formatter_reports_surviving_mutants(capsys):
    report = _report_with_lines(
        [
            (
                "src/api.py",
                12,
                True,
                [
                    ("1", "Killed", "ArithmeticOperator"),
                    ("2", "Survived", "ConditionalBoundary"),
                ],
            )
        ]
    )

    print_summary_table(report)

    output = capsys.readouterr().out
    assert "Surviving Mutants" in output
    assert "src/api.py" in output
    assert "1 killed, 1/2 survived" in output
    assert "ConditionalBoundary" in output
    assert "boundary-value tests" in output


# --- GitHub formatter: surviving mutant section details ---


def test_github_formatter_omits_section_when_no_surviving_mutants():
    report = _report_with_lines(
        [
            (
                "src/clean.py",
                5,
                True,
                [("1", "Killed", "ArithmeticOperator")],
            )
        ]
    )

    markdown = generate_markdown_summary(report)

    assert "**Surviving Mutants**" not in markdown


def test_github_formatter_shows_uncovered_label_for_uncovered_lines():
    report = _report_with_lines(
        [
            (
                "src/uncovered.py",
                7,
                False,
                [("1", "Survived", "ReturnValue")],
            )
        ]
    )

    markdown = generate_markdown_summary(report)

    assert "Uncovered" in markdown


def test_github_formatter_shows_na_when_no_mutator_descriptions():
    report = _report_with_lines(
        [
            (
                "src/nodesc.py",
                3,
                True,
                [("1", "Survived", None)],
            )
        ]
    )

    markdown = generate_markdown_summary(report)

    assert "**Surviving Mutants**" in markdown
    assert "| N/A |" in markdown


def test_github_formatter_covered_before_uncovered_in_surviving_section():
    report = _report_with_lines(
        [
            (
                "src/uncovered.py",
                1,
                False,
                [("1", "Survived", "ReturnValue")],
            ),
            (
                "src/covered.py",
                1,
                True,
                [("2", "Survived", "ReturnValue")],
            ),
        ]
    )

    markdown = generate_markdown_summary(report)
    surviving_section = markdown.split("**Surviving Mutants**", 1)[1]

    assert surviving_section.index("`src/covered.py`") < surviving_section.index(
        "`src/uncovered.py`"
    )


def test_github_formatter_truncates_many_mutator_descriptions():
    report = _report_with_lines(
        [
            (
                "src/multi.py",
                1,
                True,
                [
                    ("1", "Survived", "MutatorA"),
                    ("2", "Survived", "MutatorB"),
                    ("3", "Survived", "MutatorC"),
                    ("4", "Survived", "MutatorD"),
                ],
            )
        ]
    )

    markdown = generate_markdown_summary(report)

    assert "MutatorA, MutatorB, MutatorC, +1 more" in markdown


def test_github_formatter_deduplicates_mutator_descriptions():
    report = _report_with_lines(
        [
            (
                "src/dup.py",
                1,
                True,
                [
                    ("1", "Survived", "ConditionalBoundary"),
                    ("2", "Survived", "ConditionalBoundary"),
                ],
            )
        ]
    )

    markdown = generate_markdown_summary(report)

    # Should appear only once, not "ConditionalBoundary, ConditionalBoundary"
    assert "ConditionalBoundary, ConditionalBoundary" not in markdown
    assert "ConditionalBoundary" in markdown


def test_github_formatter_surviving_section_ordered_by_most_survived_first():
    report = _report_with_lines(
        [
            (
                "src/few.py",
                1,
                True,
                [("1", "Survived", "X")],
            ),
            (
                "src/many.py",
                1,
                True,
                [
                    ("2", "Survived", "X"),
                    ("3", "Survived", "X"),
                    ("4", "Survived", "X"),
                ],
            ),
        ]
    )

    markdown = generate_markdown_summary(report)
    surviving_section = markdown.split("**Surviving Mutants**", 1)[1]

    assert surviving_section.index("`src/many.py`") < surviving_section.index(
        "`src/few.py`"
    )


# --- Console formatter: surviving mutant section ---


def _capture_console_output(report: ProjectReport) -> str:
    buf = StringIO()
    console = Console(file=buf, legacy_windows=False, width=160, highlight=False)
    print_summary_table(report, console)
    return buf.getvalue()


def test_console_formatter_omits_surviving_section_when_all_killed():
    report = _report_with_lines(
        [
            (
                "src/clean.py",
                5,
                True,
                [("1", "Killed", "ArithmeticOperator")],
            )
        ]
    )

    output = _capture_console_output(report)

    assert "Surviving Mutants" not in output


def test_console_formatter_shows_uncovered_label():
    report = _report_with_lines(
        [
            (
                "src/uncovered.py",
                7,
                False,
                [("1", "Survived", "ReturnValue")],
            )
        ]
    )

    output = _capture_console_output(report)

    assert "Uncovered" in output


def test_console_formatter_shows_na_when_no_mutator_descriptions():
    report = _report_with_lines(
        [
            (
                "src/nodesc.py",
                3,
                True,
                [("1", "Survived", None)],
            )
        ]
    )

    output = _capture_console_output(report)

    assert "Surviving Mutants" in output
    assert "N/A" in output


def test_console_formatter_limits_surviving_mutants_and_shows_count():
    report = _report_with_lines(
        [
            (
                f"src/file_{i}.py",
                i,
                True,
                [(str(i), "Survived", f"Mutator{i}")],
            )
            for i in range(1, SURVIVING_MUTANT_LIMIT + 2)
        ]
    )

    output = _capture_console_output(report)

    total = SURVIVING_MUTANT_LIMIT + 1
    assert f"Showing top {SURVIVING_MUTANT_LIMIT} of {total} findings" in output


def test_console_formatter_surviving_mutants_shows_suggestion():
    report = _report_with_lines(
        [
            (
                "src/api.py",
                10,
                True,
                [("1", "Survived", "ReturnValue")],
            )
        ]
    )

    output = _capture_console_output(report)

    assert "Assert the exact returned value" in output


# --- surviving_mutants helpers ---


def _make_finding(
    survived: int,
    total: int,
    covered: bool,
    descriptions: list[str | None],
) -> dict:
    killed = total - survived
    return {
        "file": "f.py",
        "line": 1,
        "covered": covered,
        "killed": killed,
        "survived": survived,
        "total": total,
        "all_survived": killed == 0,
        "mutants": [
            {"id": str(i), "status": "Survived", "description": d}
            for i, d in enumerate(descriptions)
        ],
    }


def test_coverage_label_covered():
    finding = _make_finding(1, 1, True, ["X"])
    assert coverage_label(finding) == "Covered"


def test_coverage_label_uncovered():
    finding = _make_finding(1, 1, False, ["X"])
    assert coverage_label(finding) == "Uncovered"


def test_mutant_count_label_all_survived():
    finding = _make_finding(2, 2, True, ["X", "Y"])
    assert mutant_count_label(finding) == "2/2 survived"


def test_mutant_count_label_partial_survived():
    finding = _make_finding(1, 3, True, ["X"])
    assert mutant_count_label(finding) == "2 killed, 1/3 survived"


def test_mutator_descriptions_returns_na_for_all_none():
    finding = _make_finding(2, 2, True, [None, None])
    assert mutator_descriptions(finding) == "N/A"


def test_mutator_descriptions_deduplicates():
    finding = _make_finding(2, 2, True, ["Foo", "Foo"])
    assert mutator_descriptions(finding) == "Foo"


def test_mutator_descriptions_truncates_beyond_three():
    finding = _make_finding(4, 4, True, ["A", "B", "C", "D"])
    assert mutator_descriptions(finding) == "A, B, C, +1 more"


def test_sorted_surviving_findings_covered_all_survived_first():
    findings = [
        _make_finding(1, 1, False, ["X"]),  # uncovered, all survived
        _make_finding(1, 2, True, ["X"]),  # covered, partial survived
        _make_finding(1, 1, True, ["X"]),  # covered, all survived
    ]
    result = sorted_surviving_findings(findings)
    # covered all-survived first, then covered partial, then uncovered
    assert result[0]["covered"] is True and result[0]["all_survived"] is True
    assert result[1]["covered"] is True and result[1]["all_survived"] is False
    assert result[2]["covered"] is False

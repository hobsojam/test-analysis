from tqa.formatters.console import print_summary_table
from tqa.formatters.github import generate_markdown_summary
from tqa.models import ComponentReport, FileReport, LineData, MutantData, ProjectReport


def _report_with_lines(lines: list[tuple[str, int, bool, list[tuple[str, str, str | None]]]]) -> ProjectReport:
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
    report = _report_with_lines([
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
    ])

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
    report = _report_with_lines([
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
    ])

    markdown = generate_markdown_summary(report)
    surviving_section = markdown.split("**Surviving Mutants**", 1)[1]

    assert surviving_section.index("`src/full.py`") < surviving_section.index("`src/partial.py`")


def test_github_formatter_limits_surviving_mutants_to_top_10():
    report = _report_with_lines([
        (
            f"src/file_{i}.py",
            i,
            True,
            [(str(i), "Survived", f"Mutator{i}")],
        )
        for i in range(1, 12)
    ])

    markdown = generate_markdown_summary(report)

    assert markdown.count(" survived | Mutator") == 10
    assert "Showing top 10 of 11 findings" in markdown


def test_console_formatter_reports_surviving_mutants(capsys):
    report = _report_with_lines([
        (
            "src/api.py",
            12,
            True,
            [
                ("1", "Killed", "ArithmeticOperator"),
                ("2", "Survived", "ConditionalBoundary"),
            ],
        )
    ])

    print_summary_table(report)

    output = capsys.readouterr().out
    assert "Surviving Mutants" in output
    assert "src/api.py" in output
    assert "1 killed, 1/2 survived" in output
    assert "ConditionalBoundary" in output
    assert "boundary-value tests" in output

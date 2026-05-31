import os
import sys
from tqa.engine import AnalysisEngine
from tqa.formatters.surviving_mutants import (
    SURVIVING_MUTANT_LIMIT,
    coverage_label,
    mutant_count_label,
    mutator_descriptions,
    source_line_text,
    suggestion_label,
    sorted_surviving_findings,
)
from tqa.models import ProjectReport, ComponentReport


def _blob_base_url() -> str | None:
    """Return the GitHub blob URL prefix for the current commit, or None when not in Actions."""
    server = os.environ.get("GITHUB_SERVER_URL", "").rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    sha = os.environ.get("GITHUB_SHA", "")
    if server and repo and sha:
        return f"{server}/{repo}/blob/{sha}"
    return None


def _file_link(file_path: str, base_url: str | None) -> str:
    if base_url:
        return f"[`{file_path}`]({base_url}/{file_path})"
    return f"`{file_path}`"


def _detect_language(component: ComponentReport) -> str:
    extensions = [os.path.splitext(f)[1] for f in component.files]
    if any(e in (".js", ".ts", ".jsx", ".tsx") for e in extensions):
        return "js"
    if any(e == ".java" for e in extensions):
        return "java"
    return "python"


def _mutation_tip(component: ComponentReport) -> str:
    lang = _detect_language(component)
    if lang == "js":
        return (
            "> **Tip:** TSI requires a mutation report alongside coverage.\n"
            "> Run [Stryker](https://stryker-mutator.io): `stryker run`"
            " and add `--stryker reports/mutation/mutation.json` to the `tqa analyze` command."
        )
    if lang == "java":
        return (
            "> **Tip:** TSI requires a mutation report alongside coverage.\n"
            "> Run [PIT](https://pitest.org): `mvn test-compile pitest:mutationCoverage`"
            " and add `--pit target/pit-reports/mutations.xml` to the `tqa analyze` command."
        )
    return (
        "> **Tip:** TSI requires a mutation report alongside coverage.\n"
        "> Run [mutmut](https://mutmut.readthedocs.io): `mutmut run && mutmut junitxml > mutmut.xml`"
        " and add `--mutmut mutmut.xml` to the `tqa analyze` command."
    )


def _status_emoji(tsi: float) -> str:
    if tsi >= 80:
        return "✅ Healthy"
    if tsi >= 50:
        return "🟡 Weak"
    return "🔴 Blind"


# NOTE: Column structure and thresholds must stay in sync with _render_component_table() in console.py.
# GitHub Markdown does not support ANSI color, so the TSI value is plain text here; color is carried
# by the Status emoji instead.
def _component_table(component: ComponentReport) -> list[str]:
    rows = [
        "| File | Coverage | Test Strength (TSI) | Status |",
        "| :--- | :---: | :---: | :---: |",
    ]
    base_url = _blob_base_url()
    for file_path, file_report in component.files.items():
        cov = file_report.line_coverage * 100
        if file_report.has_mutation_data:
            tsi = file_report.test_strength * 100
            tsi_str = f"{tsi:.1f}%"
            status = _status_emoji(tsi)
        else:
            tsi_str = "N/A"
            status = "—"
        rows.append(
            f"| {_file_link(file_path, base_url)} | {cov:.1f}% | {tsi_str} | {status} |"
        )
    return rows


def _comp_display_name(name: str) -> str:
    return name.replace("-", " ").replace("_", " ").title()


def _source_cell(finding: dict) -> str:
    """Format source line text as an inline code span, or empty string."""
    text = source_line_text(finding)
    if text is None:
        return ""
    # Escape backticks inside the code span so the cell renders correctly.
    escaped = text.strip().replace("`", "&#96;")
    return f"`{escaped}`"


def _surviving_mutant_rows(findings: list[dict]) -> list[str]:
    limited = sorted_surviving_findings(findings)[:SURVIVING_MUTANT_LIMIT]
    has_source = any(source_line_text(f) is not None for f in limited)
    if has_source:
        rows = [
            "| File | Line | Coverage | Mutants | Source | Mutator Details | Suggested Test Focus |",
            "| :--- | :---: | :---: | :---: | :--- | :--- | :--- |",
        ]
    else:
        rows = [
            "| File | Line | Coverage | Mutants | Mutator Details | Suggested Test Focus |",
            "| :--- | :---: | :---: | :---: | :--- | :--- |",
        ]
    base_url = _blob_base_url()
    for finding in limited:
        if has_source:
            rows.append(
                f"| {_file_link(finding['file'], base_url)} | {finding['line']} | {coverage_label(finding)} | "
                f"{mutant_count_label(finding)} | {_source_cell(finding)} | "
                f"{mutator_descriptions(finding)} | {suggestion_label(finding)} |"
            )
        else:
            rows.append(
                f"| {_file_link(finding['file'], base_url)} | {finding['line']} | {coverage_label(finding)} | "
                f"{mutant_count_label(finding)} | {mutator_descriptions(finding)} | "
                f"{suggestion_label(finding)} |"
            )
    return rows


def generate_markdown_summary(report: ProjectReport) -> str:
    lines = ["## TQA Report Summary", ""]
    # Show per-component headers when there are multiple components, or when
    # a single component has an explicit name (i.e. came from a config file).
    multi = len(report.components) > 1 or (
        len(report.components) == 1 and "default" not in report.components
    )

    # Headline metrics first
    if multi and report.has_mutation_data:
        lines.append(
            f"**Total Project Test Strength: {report.total_test_strength * 100:.1f}%**"
        )
        lines.append("")

    for comp_name, component in report.components.items():
        if multi:
            lines.append(f"### {_comp_display_name(comp_name)}")
            lines.append("")

        if component.has_mutation_data:
            label = "Test Strength" if multi else "Total Project Test Strength"
            lines.append(f"**{label}: {component.total_test_strength * 100:.1f}%**")
        else:
            label = "Test Strength" if multi else "Total Project Test Strength"
            lines.append(f"**{label}: N/A**")
            lines.append("")
            lines.append(_mutation_tip(component))

        lines.append("")
        lines.append("<details>")
        lines.append("<summary>Per-file breakdown</summary>")
        lines.append("")
        lines.extend(_component_table(component))
        lines.append("")
        lines.append("</details>")
        lines.append("")

    engine = AnalysisEngine()
    surviving_mutants = engine.get_surviving_mutants(report)
    if surviving_mutants:
        lines.append("**Surviving Mutants**")
        lines.append("")
        lines.extend(_surviving_mutant_rows(surviving_mutants))
        if len(surviving_mutants) > SURVIVING_MUTANT_LIMIT:
            lines.append("")
            lines.append(
                f"_Showing top {SURVIVING_MUTANT_LIMIT} of {len(surviving_mutants)} findings._"
            )
        lines.append("")

    gaps = engine.get_critical_gaps(report)
    if gaps:
        lines.append("## Critical Gaps (covered but 0% killed)")
        lines.append("| File | Line | Survived Mutants |")
        lines.append("| :--- | :---: | :---: |")
        for gap in gaps[:10]:
            lines.append(f"| `{gap['file']}` | {gap['line']} | {gap['survived']} |")
        lines.append("")

    return "\n".join(lines)


def print_github_annotations(report: ProjectReport) -> None:
    engine = AnalysisEngine()
    gaps = engine.get_critical_gaps(report)
    for gap in gaps:
        print(
            f"::warning file={gap['file']},line={gap['line']}::"
            f"Critical Gap: Line is covered but all {gap['survived']} mutants survived. "
            "Stronger assertions needed.",
            file=sys.stderr,
        )

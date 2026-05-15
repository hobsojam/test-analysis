import os
import sys
from tqa.models import ProjectReport, ComponentReport
from tqa.engine import AnalysisEngine


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


def _component_table(component: ComponentReport) -> list[str]:
    rows = [
        "| File | Coverage | Test Strength (TSI) | Status |",
        "| :--- | :---: | :---: | :---: |",
    ]
    for file_path, file_report in component.files.items():
        cov = file_report.line_coverage * 100
        if file_report.has_mutation_data:
            tsi = file_report.test_strength * 100
            tsi_str = f"{tsi:.1f}%"
            status = "Healthy" if tsi >= 80 else ("Weak" if tsi >= 50 else "Blind")
        else:
            tsi_str = "N/A"
            status = "—"
        rows.append(f"| `{file_path}` | {cov:.1f}% | {tsi_str} | {status} |")
    return rows


def _comp_display_name(name: str) -> str:
    return name.replace("-", " ").replace("_", " ").title()


def generate_markdown_summary(report: ProjectReport) -> str:
    lines = ["# TQA Report Summary", ""]
    # Show per-component headers when there are multiple components, or when
    # a single component has an explicit name (i.e. came from a config file).
    multi = len(report.components) > 1 or (
        len(report.components) == 1 and "default" not in report.components
    )

    for comp_name, component in report.components.items():
        if multi:
            lines.append(f"## {_comp_display_name(comp_name)}")
            lines.append("")

        lines.extend(_component_table(component))
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

    if multi and report.has_mutation_data:
        lines.append(f"**Total Project Test Strength: {report.total_test_strength * 100:.1f}%**")
        lines.append("")

    engine = AnalysisEngine()
    gaps = engine.get_critical_gaps(report)
    if gaps:
        lines.append("\n## Critical Gaps (covered but 0% killed)")
        lines.append("| File | Line | Survived Mutants |")
        lines.append("| :--- | :---: | :---: |")
        for gap in gaps[:10]:
            lines.append(f"| `{gap['file']}` | {gap['line']} | {gap['survived']} |")

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

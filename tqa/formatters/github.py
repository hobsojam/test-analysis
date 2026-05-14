from tqa.models import ProjectReport
from tqa.engine import AnalysisEngine

def generate_markdown_summary(report: ProjectReport) -> str:
    lines = [
        "# TQA Report Summary",
        "",
        "| File | Coverage | Test Strength (TSI) | Status |",
        "| :--- | :---: | :---: | :---: |"
    ]

    for file_path, file_report in report.files.items():
        cov = file_report.line_coverage * 100

        if file_report.has_mutation_data:
            tsi = file_report.test_strength * 100
            tsi_str = f"{tsi:.1f}%"
            if tsi >= 80:
                status = "Healthy"
            elif tsi >= 50:
                status = "Weak"
            else:
                status = "Blind"
        else:
            tsi_str = "N/A"
            status = "—"

        lines.append(f"| `{file_path}` | {cov:.1f}% | {tsi_str} | {status} |")

    lines.append("")

    if report.has_mutation_data:
        lines.append(f"**Total Project Test Strength: {report.total_test_strength * 100:.1f}%**")
    else:
        lines.append("**Total Project Test Strength: N/A**")
        lines.append("")
        lines.append("> **Tip:** TSI requires a mutation report alongside coverage.")
        lines.append("> For this project, run [Stryker](https://stryker-mutator.io) and add `--stryker reports/mutation/mutation.json` to the `tqa analyze` command.")

    # Add Critical Gaps section
    engine = AnalysisEngine()
    gaps = engine.get_critical_gaps(report)
    if gaps:
        lines.append("\n## Critical Gaps (covered but 0% killed)")
        lines.append("| File | Line | Survived Mutants |")
        lines.append("| :--- | :---: | :---: |")
        for gap in gaps[:10]:
            lines.append(f"| `{gap['file']}` | {gap['line']} | {gap['survived']} |")

    return "\n".join(lines)

def print_github_annotations(report: ProjectReport):
    engine = AnalysisEngine()
    gaps = engine.get_critical_gaps(report)
    for gap in gaps:
        print(f"::warning file={gap['file']},line={gap['line']}::Critical Gap: Line is covered but all {gap['survived']} mutants survived. Stronger assertions needed.")

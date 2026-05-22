from rich.console import Console
from rich.table import Table
from tqa.engine import AnalysisEngine
from tqa.formatters.surviving_mutants import (
    SURVIVING_MUTANT_LIMIT,
    coverage_label,
    mutant_count_label,
    mutator_descriptions,
    suggestion_label,
    sorted_surviving_findings,
)
from tqa.models import ProjectReport, ComponentReport


def _render_component_table(console: Console, component: ComponentReport, title: str) -> None:
    table = Table(title=title)
    table.add_column("File", style="cyan")
    table.add_column("Coverage", justify="right")
    table.add_column("Test Strength (TSI)", justify="right")
    table.add_column("Status", justify="center")

    for file_path, file_report in component.files.items():
        cov = file_report.line_coverage * 100
        if file_report.has_mutation_data:
            tsi = file_report.test_strength * 100
            status = "[green]Healthy[/]"
            if tsi < 80:
                status = "[yellow]Weak[/]"
            if tsi < 50:
                status = "[red]Blind[/]"
            tsi_str = f"{tsi:.1f}%"
        else:
            tsi_str = "N/A"
            status = "[dim]No mutants[/]"
        table.add_row(file_path, f"{cov:.1f}%", tsi_str, status)

    console.print(table)


def _render_surviving_mutants(console: Console, findings: list[dict]) -> None:
    if not findings:
        return

    table = Table(title="Surviving Mutants")
    table.add_column("File", style="cyan")
    table.add_column("Line", justify="right")
    table.add_column("Coverage", justify="center")
    table.add_column("Mutants", justify="right", no_wrap=True)
    table.add_column("Mutator Details", no_wrap=True)
    table.add_column("Suggested Test Focus")

    for finding in sorted_surviving_findings(findings)[:SURVIVING_MUTANT_LIMIT]:
        table.add_row(
            finding["file"],
            str(finding["line"]),
            coverage_label(finding),
            mutant_count_label(finding),
            mutator_descriptions(finding),
            suggestion_label(finding),
        )

    console.print("")
    console.print(table)
    if len(findings) > SURVIVING_MUTANT_LIMIT:
        console.print(f"[dim]Showing top {SURVIVING_MUTANT_LIMIT} of {len(findings)} findings.[/]")


def print_summary_table(report: ProjectReport) -> None:
    console = Console(legacy_windows=False, width=160)
    multi = len(report.components) > 1 or (
        len(report.components) == 1 and "default" not in report.components
    )

    for comp_name, component in report.components.items():
        display = comp_name.replace("-", " ").replace("_", " ").title()
        title = f"TQA - {display}" if multi else "TQA - Test Quality Summary"
        _render_component_table(console, component, title)

        if component.has_mutation_data:
            label = f"{display} Test Strength" if multi else "Total Project Test Strength"
            console.print(f"\n[bold]{label}:[/] [green]{component.total_test_strength * 100:.1f}%[/]")
        else:
            label = f"{display} Test Strength" if multi else "Total Project Test Strength"
            console.print(f"\n[bold]{label}:[/] [dim]N/A — no mutation data[/]")
            if not multi:
                console.print("\n[yellow]Tip:[/] TSI requires a mutation report. Add one with:")
                console.print("  JS:     [bold]stryker run[/] → [bold]--stryker reports/mutation/mutation.json[/]")
                console.print("  Python: [bold]mutmut run[/]  → [bold]--mutmut mutmut.xml[/]")
                console.print("  Java:   [bold]mvn pitest:mutationCoverage[/] → [bold]--pit mutations.xml[/]")

    if multi and report.has_mutation_data:
        console.print(f"\n[bold]Total Project Test Strength:[/] [green]{report.total_test_strength * 100:.1f}%[/]")

    _render_surviving_mutants(console, AnalysisEngine().get_surviving_mutants(report))

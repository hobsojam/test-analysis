from rich.console import Console
from rich.table import Table
from tqa.models import ProjectReport

def print_summary_table(report: ProjectReport):
    console = Console(legacy_windows=False)

    table = Table(title="TQA - Test Quality Summary")
    table.add_column("File", style="cyan")
    table.add_column("Coverage", justify="right")
    table.add_column("Test Strength (TSI)", justify="right")
    table.add_column("Status", justify="center")

    for file_path, file_report in report.files.items():
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

    if report.has_mutation_data:
        console.print(f"\n[bold]Total Project Test Strength:[/] [green]{report.total_test_strength * 100:.1f}%[/]")
    else:
        console.print("\n[bold]Total Project Test Strength:[/] [dim]N/A — no mutation data[/]")
        console.print("\n[yellow]Tip:[/] TSI requires a mutation report. Add one with:")
        console.print("  JS:     [bold]stryker run[/] → [bold]--stryker reports/mutation/mutation.json[/]")
        console.print("  Python: [bold]mutmut run[/]  → [bold]--mutmut mutmut.xml[/]")
        console.print("  Java:   [bold]mvn pitest:mutationCoverage[/] → [bold]--pit mutations.xml[/]")

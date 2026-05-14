from rich.console import Console
from rich.table import Table
from tqa.models import ProjectReport

def print_summary_table(report: ProjectReport):
    console = Console()
    
    table = Table(title="TQA - Test Quality Summary")
    table.add_column("File", style="cyan")
    table.add_column("Coverage", justify="right")
    table.add_column("Test Strength (TSI)", justify="right")
    table.add_column("Status", justify="center")

    for file_path, file_report in report.files.items():
        cov = file_report.line_coverage * 100
        tsi = file_report.test_strength * 100
        
        status = "✅ Healthy"
        if tsi < 80:
            status = "⚠️ Weak"
        if tsi < 50:
            status = "❌ Blind"
            
        table.add_row(
            file_path,
            f"{cov:.1f}%",
            f"{tsi:.1f}%",
            status
        )

    console.print(table)
    console.print(f"\n[bold]Total Project Test Strength:[/] [green]{report.total_test_strength * 100:.1f}%[/]")

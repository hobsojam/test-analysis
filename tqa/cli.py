import click
import sys
from rich.console import Console
from tqa.engine import AnalysisEngine
from tqa.formatters.console import print_summary_table
from tqa.formatters.github import generate_markdown_summary, print_github_annotations

@click.group()
def main() -> None:
    """TQA - Test Quality Analyzer"""
    pass

@main.command()
@click.option("--coverage", "coverage_path", type=click.Path(), help="Path to Cobertura XML")
@click.option("--lcov", "lcov_path", type=click.Path(), help="Path to lcov.info (Jest, Vitest, NYC)")
@click.option("--stryker", "stryker_path", type=click.Path(), help="Path to Stryker JSON")
@click.option("--pit", "pit_path", type=click.Path(), help="Path to PIT mutations.xml")
@click.option("--mutmut", "mutmut_path", type=click.Path(), help="Path to mutmut junit.xml")
@click.option("--format", type=click.Choice(["console", "github"]), default="console")
@click.option("--fail-under", type=float, default=0.0, help="Fail if total TSI is below this threshold")
def analyze(coverage_path: str, lcov_path: str, stryker_path: str, pit_path: str, mutmut_path: str, format: str, fail_under: float) -> None:
    """Analyze test quality by correlating reports."""
    engine = AnalysisEngine()
    report = engine.run({
        "cobertura": coverage_path,
        "lcov": lcov_path,
        "stryker": stryker_path,
        "pit": pit_path,
        "mutmut": mutmut_path,
    })
    
    if not report.files:
        if format == "console":
            console = Console()
            console.print("\n[bold yellow]⚠️ No quality data found.[/]")
            console.print("To see results, please ensure you have generated coverage or mutation reports.")
            console.print("\n[bold]Suggested Setup:[/]")
            console.print("1. Coverage: Use `pytest-cov --cov-report=xml` (Python) or `nyc report --reporter=cobertura` (JS)")
            console.print("2. Mutation: Use `stryker run` (JS), `pitest` (Java), or `mutmut run` (Python)")
        elif format == "github":
            click.echo("# 🛡️ TQA: Quality Unknown")
            click.echo("\nNo coverage or mutation reports were detected. Quality metrics cannot be calculated.")
            click.echo("\n### 🛠️ Suggested Setup")
            click.echo("- **Coverage:** Ensure a Cobertura XML report is generated.")
            click.echo("- **Mutation:** Ensure a Stryker, PIT, or mutmut report is generated.")
        return
        
    if format == "console":
        print_summary_table(report)
    elif format == "github":
        click.echo(generate_markdown_summary(report))
        print_github_annotations(report)
        
    if report.total_test_strength * 100 < fail_under:
        click.echo(f"\nError: Test Strength {report.total_test_strength * 100:.1f}% is below threshold {fail_under}%", err=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

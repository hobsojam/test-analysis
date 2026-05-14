import click
import sys
from tqa.engine import AnalysisEngine
from tqa.formatters.console import print_summary_table
from tqa.formatters.github import generate_markdown_summary, print_github_annotations

@click.group()
def main():
    """TQA - Test Quality Analyzer"""
    pass

@main.command()
@click.option("--coverage", "coverage_path", type=click.Path(), help="Path to Cobertura XML")
@click.option("--stryker", "stryker_path", type=click.Path(), help="Path to Stryker JSON")
@click.option("--pit", "pit_path", type=click.Path(), help="Path to PIT mutations.xml")
@click.option("--mutmut", "mutmut_path", type=click.Path(), help="Path to mutmut junit.xml")
@click.option("--format", type=click.Choice(["console", "github"]), default="console")
@click.option("--fail-under", type=float, default=0.0, help="Fail if total TSI is below this threshold")
def analyze(coverage_path, stryker_path, pit_path, mutmut_path, format, fail_under):
    """Analyze test quality by correlating reports."""
    engine = AnalysisEngine()
    report = engine.run(
        coverage_path=coverage_path,
        stryker_path=stryker_path,
        pit_path=pit_path,
        mutmut_path=mutmut_path
    )
    
    if not report.files:
        if format == "console":
            click.echo("\n[bold yellow]⚠️ No quality data found.[/]")
            click.echo("To see results, please ensure you have generated coverage or mutation reports.")
            click.echo("\n[bold]Suggested Setup:[/]")
            click.echo("1. Coverage: Use `pytest-cov --cov-report=xml` (Python) or `nyc report --reporter=cobertura` (JS)")
            click.echo("2. Mutation: Use `stryker run` (JS), `pitest` (Java), or `mutmut run` (Python)")
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

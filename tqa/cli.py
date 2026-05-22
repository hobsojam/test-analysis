import sys
try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]
import click
from rich.console import Console
from tqa.engine import AnalysisEngine
from tqa.formatters.console import print_summary_table
from tqa.formatters.github import generate_markdown_summary, print_github_annotations


@click.group()
def main() -> None:
    """TQA - Test Quality Analyzer"""
    pass


@main.command()
@click.option("--config", "config_path", type=click.Path(), help="Path to tqa.toml config file")
@click.option("--coverage", "coverage_path", type=click.Path(), help="Path to Cobertura XML")
@click.option("--lcov", "lcov_path", type=click.Path(), help="Path to lcov.info (Jest, Vitest, NYC)")
@click.option("--stryker", "stryker_path", type=click.Path(), help="Path to Stryker JSON")
@click.option("--pit", "pit_path", type=click.Path(), help="Path to PIT mutations.xml")
@click.option("--mutmut", "mutmut_path", type=click.Path(), help="Path to mutmut junit.xml")
@click.option("--format", type=click.Choice(["console", "github"]), default="console")
@click.option("--fail-under", type=float, default=0.0, help="Fail if total TSI is below this threshold")
@click.option("--export-svg", "export_svg", type=click.Path(), default=None, help="Export console output as SVG")
def analyze(
    config_path: str,
    coverage_path: str,
    lcov_path: str,
    stryker_path: str,
    pit_path: str,
    mutmut_path: str,
    format: str,
    fail_under: float,
    export_svg: str,
) -> None:
    """Analyze test quality by correlating reports."""
    engine = AnalysisEngine()

    if config_path:
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        report = engine.run_multi(config.get("components", {}))
    else:
        report = engine.run({
            "cobertura": coverage_path,
            "lcov": lcov_path,
            "stryker": stryker_path,
            "pit": pit_path,
            "mutmut": mutmut_path,
        })

    if not report.components:
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
        if export_svg:
            recording = Console(record=True, legacy_windows=False, width=160)
            print_summary_table(report, console=recording)
            recording.save_svg(export_svg, title="TQA — Test Quality Summary")
        else:
            print_summary_table(report)
    elif format == "github":
        click.echo(generate_markdown_summary(report))
        print_github_annotations(report)

    if report.total_test_strength * 100 < fail_under:
        click.echo(f"\nError: Test Strength {report.total_test_strength * 100:.1f}% is below threshold {fail_under}%", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

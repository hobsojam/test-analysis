import sys
from importlib.metadata import version as _pkg_version

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]
import click
from rich.console import Console
from tqa.engine import AnalysisEngine
from tqa.formatters.console import print_summary_table
from tqa.formatters.github import generate_markdown_summary, print_github_annotations
from tqa.formatters.json_formatter import format_json_report
from tqa.formatters.sonarcloud import SONARCLOUD_REPORT_PATH, write_sonarcloud_report
from tqa.models import SurvivingMutantFinding


@click.group()
@click.version_option(version=_pkg_version("tqa"), prog_name="tqa")
def main() -> None:
    """TQA - Test Quality Analyzer"""
    pass


@main.command()
@click.option(
    "--config", "config_path", type=click.Path(), help="Path to tqa.toml config file"
)
@click.option(
    "--coverage", "coverage_path", type=click.Path(), help="Path to Cobertura XML"
)
@click.option(
    "--lcov",
    "lcov_path",
    type=click.Path(),
    help="Path to lcov.info (Jest, Vitest, NYC)",
)
@click.option(
    "--stryker", "stryker_path", type=click.Path(), help="Path to Stryker JSON"
)
@click.option("--pit", "pit_path", type=click.Path(), help="Path to PIT mutations.xml")
@click.option(
    "--mutmut", "mutmut_path", type=click.Path(), help="Path to mutmut junit.xml"
)
@click.option(
    "--mutant",
    "mutant_path",
    type=click.Path(),
    help="Path to Mutant session JSON or .mutant/results",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["console", "github", "sonarcloud", "json"]),
    default="console",
)
@click.option(
    "--fail-under",
    type=float,
    default=0.0,
    help="Fail if total TSI is below this threshold",
)
@click.option(
    "--export-svg",
    "export_svg",
    type=click.Path(),
    default=None,
    help="Export console output as SVG",
)
@click.option(
    "--project-root",
    "project_root",
    type=click.Path(),
    default=None,
    help="Project root directory for source context in surviving mutant findings",
)
@click.option(
    "--context-lines",
    "context_lines",
    type=int,
    default=0,
    help="Number of source lines of context to show around each surviving mutant (requires --project-root)",
)
def analyze(
    config_path: str,
    coverage_path: str,
    lcov_path: str,
    stryker_path: str,
    pit_path: str,
    mutmut_path: str,
    mutant_path: str,
    output_format: str,
    fail_under: float,
    export_svg: str,
    project_root: str,
    context_lines: int,
) -> None:
    """Analyze test quality by correlating reports."""
    engine = AnalysisEngine()

    try:
        if config_path:
            with open(config_path, "rb") as f:
                config = tomllib.load(f)
            report = engine.run_multi(config.get("components", {}))
        else:
            report = engine.run(
                {
                    "cobertura": coverage_path,
                    "lcov": lcov_path,
                    "stryker": stryker_path,
                    "pit": pit_path,
                    "mutmut": mutmut_path,
                    "mutant": mutant_path,
                }
            )
    except (ValueError, FileNotFoundError) as exc:
        console = Console(stderr=True)
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(2) from exc

    if context_lines > 0 and project_root is None:
        click.echo(
            "Warning: --context-lines has no effect without --project-root.", err=True
        )

    if not report.components:
        if output_format == "console":
            console = Console()
            console.print("\n[bold yellow]⚠️ No quality data found.[/]")
            console.print(
                "To see results, please ensure you have generated coverage or mutation reports."
            )
            console.print("\n[bold]Suggested Setup:[/]")
            console.print(
                "1. Coverage: Use `pytest-cov --cov-report=xml` (Python) or `nyc report --reporter=cobertura` (JS)"
            )
            console.print(
                "2. Mutation: Use `stryker run` (JS), `pitest` (Java), or `mutmut run` (Python)"
            )
        elif output_format == "json":
            click.echo(format_json_report(report))
        elif output_format in ("github", "sonarcloud"):
            if output_format == "sonarcloud":
                write_sonarcloud_report(report)
                click.echo(f"Wrote {SONARCLOUD_REPORT_PATH}", err=True)
            click.echo("# 🛡️ TQA: Quality Unknown")
            click.echo(
                "\nNo coverage or mutation reports were detected. Quality metrics cannot be calculated."
            )
            click.echo("\n### 🛠️ Suggested Setup")
            click.echo("- **Coverage:** Ensure a Cobertura XML report is generated.")
            click.echo(
                "- **Mutation:** Ensure a Stryker, PIT, or mutmut report is generated."
            )
        return

    # Pre-compute surviving mutant findings with optional source context
    surviving_findings: list[SurvivingMutantFinding] | None
    if project_root is not None:
        surviving_findings = engine.get_surviving_mutants(
            report, project_root=project_root, context_lines=context_lines
        )
    else:
        surviving_findings = None  # formatters will compute their own

    if output_format == "console":
        if export_svg:
            recording = Console(record=True, legacy_windows=False, width=160)
            print_summary_table(report, console=recording, findings=surviving_findings)
            recording.save_svg(export_svg, title="TQA — Test Quality Summary")
        else:
            print_summary_table(report, findings=surviving_findings)
    elif output_format == "github":
        click.echo(generate_markdown_summary(report, findings=surviving_findings))
        print_github_annotations(report, findings=surviving_findings)
    elif output_format == "sonarcloud":
        write_sonarcloud_report(report)
        click.echo(f"Wrote {SONARCLOUD_REPORT_PATH}", err=True)
        click.echo(generate_markdown_summary(report, findings=surviving_findings))
    elif output_format == "json":
        click.echo(format_json_report(report, findings=surviving_findings))

    if report.total_test_strength * 100 < fail_under:
        click.echo(
            f"\nError: Test Strength {report.total_test_strength * 100:.1f}% is below threshold {fail_under}%",
            err=True,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()

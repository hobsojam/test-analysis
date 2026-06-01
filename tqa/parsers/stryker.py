import json
from tqa.models import (
    ComponentReport,
    FileReport,
    LineData,
    MutantData,
    normalise_status,
)
from tqa.parsers.base import Parser
from tqa.parsers.registry import register_parser


@register_parser("stryker")
class StrykerParser(Parser):
    def parse(self, path: str, report: ComponentReport) -> ComponentReport:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed to parse Stryker report '{path}': {exc}") from exc
        except OSError as exc:
            raise FileNotFoundError(f"Stryker report not found: '{path}'") from exc
        if not isinstance(data, dict):
            raise ValueError(
                f"Failed to parse Stryker report '{path}': expected a JSON object, "
                f"got {type(data).__name__}"
            )
        try:
            files_data = data.get("files", {})
            if not isinstance(files_data, dict):
                return report
            for file_path, file_data in files_data.items():
                if not isinstance(file_data, dict):
                    continue
                if file_path not in report.files:
                    report.files[file_path] = FileReport(file_path=file_path)
                file_report = report.files[file_path]
                mutants_list = file_data.get("mutants", [])
                if not isinstance(mutants_list, list):
                    continue
                for m in mutants_list:
                    if not isinstance(m, dict):
                        continue
                    location = m.get("location")
                    if not isinstance(location, dict):
                        continue
                    start = location.get("start")
                    if not isinstance(start, dict):
                        continue
                    line = start.get("line")
                    if not isinstance(line, int):
                        continue
                    if line not in file_report.lines:
                        file_report.lines[line] = LineData(line_number=line)
                    file_report.lines[line].mutants.append(
                        MutantData(
                            id=str(m.get("id")),
                            status=normalise_status(str(m.get("status") or "")),
                            line=line,
                            description=m.get("mutatorName"),
                        )
                    )
        except Exception as exc:
            raise ValueError(
                f"Unexpected error reading Stryker report '{path}': {exc}"
            ) from exc
        return report


def parse_stryker(json_path: str, report: ComponentReport) -> ComponentReport:
    return StrykerParser().parse(json_path, report)

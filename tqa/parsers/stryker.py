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
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for file_path, file_data in data.get("files", {}).items():
            if file_path not in report.files:
                report.files[file_path] = FileReport(file_path=file_path)
            file_report = report.files[file_path]
            for m in file_data.get("mutants", []):
                line = m["location"]["start"]["line"]
                if line not in file_report.lines:
                    file_report.lines[line] = LineData(line_number=line)
                file_report.lines[line].mutants.append(
                    MutantData(
                        id=str(m.get("id")),
                        status=normalise_status(m.get("status") or ""),
                        line=line,
                        description=m.get("mutatorName"),
                    )
                )
        return report


def parse_stryker(json_path: str, report: ComponentReport) -> ComponentReport:
    return StrykerParser().parse(json_path, report)

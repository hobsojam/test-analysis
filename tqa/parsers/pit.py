import lxml.etree as ET
from tqa.models import (
    ComponentReport,
    FileReport,
    LineData,
    MutantData,
    normalise_status,
)
from tqa.parsers.base import Parser
from tqa.parsers.registry import register_parser


@register_parser("pit")
class PitParser(Parser):
    def parse(self, path: str, report: ComponentReport) -> ComponentReport:
        try:
            tree = ET.parse(path)
        except ET.XMLSyntaxError as exc:
            raise ValueError(f"Failed to parse PIT report '{path}': {exc}") from exc
        except OSError as exc:
            raise FileNotFoundError(f"PIT report not found: '{path}'") from exc
        root = tree.getroot()
        try:
            for mutation in root.xpath("//mutation"):
                file_path = mutation.findtext("sourceFile")
                line_text = mutation.findtext("lineNumber")
                if file_path is None or line_text is None:
                    continue
                try:
                    line = int(line_text)
                except (ValueError, TypeError):
                    continue
                status = normalise_status(mutation.get("status") or "")
                mutator = mutation.findtext("mutator")
                if file_path not in report.files:
                    report.files[file_path] = FileReport(file_path=file_path)
                file_report = report.files[file_path]
                if line not in file_report.lines:
                    file_report.lines[line] = LineData(line_number=line)
                file_report.lines[line].mutants.append(
                    MutantData(
                        id=f"pit-{hash(mutation)}",
                        status=status,
                        line=line,
                        description=mutator,
                    )
                )
        except Exception as exc:
            raise ValueError(
                f"Unexpected error reading PIT report '{path}': {exc}"
            ) from exc
        return report


def parse_pit(xml_path: str, report: ComponentReport) -> ComponentReport:
    return PitParser().parse(xml_path, report)

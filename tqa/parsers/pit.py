import lxml.etree as ET
from tqa.models import ComponentReport, FileReport, LineData, MutantData
from tqa.parsers.base import Parser
from tqa.parsers.registry import register_parser


@register_parser("pit")
class PitParser(Parser):
    def parse(self, path: str, report: ComponentReport) -> ComponentReport:
        tree = ET.parse(path)
        root = tree.getroot()
        for mutation in root.xpath("//mutation"):
            file_path = mutation.findtext("sourceFile")
            line = int(mutation.findtext("lineNumber"))
            status = mutation.get("status")
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
        return report


def parse_pit(xml_path: str, report: ComponentReport) -> ComponentReport:
    return PitParser().parse(xml_path, report)

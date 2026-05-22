import lxml.etree as ET
import re
from tqa.models import ComponentReport, FileReport, LineData, MutantData
from tqa.parsers.base import Parser
from tqa.parsers.registry import register_parser


@register_parser("mutmut")
class MutmutParser(Parser):
    def parse(self, path: str, report: ComponentReport) -> ComponentReport:
        """
        Parses a mutmut JUnit XML report and updates the ProjectReport.

        mutmut 2.x format: file and line are XML attributes on <testcase>.
        Older format fallback: name="mutant #N (file: F, line: L)".
        Killed = no <failure> element. Survived = <failure> present.
        """
        tree = ET.parse(path)
        root = tree.getroot()

        for testcase in root.xpath("//testcase"):
            file_path = testcase.get("file")
            line_str = testcase.get("line")
            mutant_id = testcase.get("name", "")

            if not file_path or not line_str:
                name = testcase.get("name")
                if not name:
                    continue
                match = re.search(r"mutant #(\d+) \(file: (.*), line: (\d+)\)", name, re.IGNORECASE)
                if not match:
                    continue
                mutant_id, file_path, line_str = match.groups()

            line = int(line_str)
            status = "Killed"
            if testcase.xpath("./failure") or testcase.xpath("./error"):
                status = "Survived"

            if file_path not in report.files:
                report.files[file_path] = FileReport(file_path=file_path)

            file_report = report.files[file_path]

            if line not in file_report.lines:
                file_report.lines[line] = LineData(line_number=line)

            file_report.lines[line].mutants.append(
                MutantData(
                    id=str(mutant_id),
                    status=status,
                    line=line,
                    # mutmut JUnit XML does not include mutation-type info, so
                    # description is left None; recommendation rules cannot fire.
                    description=None,
                )
            )

        return report


def parse_mutmut(xml_path: str, report: ComponentReport) -> ComponentReport:
    return MutmutParser().parse(xml_path, report)

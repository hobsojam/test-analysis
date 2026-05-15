import lxml.etree as ET
from tqa.models import ComponentReport, FileReport, LineData
from tqa.parsers.base import Parser
from tqa.parsers.registry import register_parser


@register_parser("cobertura")
class CoberturaParser(Parser):
    def parse(self, path: str, report: ComponentReport) -> ComponentReport:
        tree = ET.parse(path)
        root = tree.getroot()
        for class_node in root.xpath("//class"):
            file_path = class_node.get("filename")
            if file_path not in report.files:
                report.files[file_path] = FileReport(file_path=file_path)
            file_report = report.files[file_path]
            for line_node in class_node.xpath("./lines/line"):
                line_num = int(line_node.get("number"))
                hits = int(line_node.get("hits"))
                if line_num not in file_report.lines:
                    file_report.lines[line_num] = LineData(line_number=line_num)
                file_report.lines[line_num].is_covered = hits > 0
        return report


def parse_cobertura(xml_path: str, report: ComponentReport) -> ComponentReport:
    return CoberturaParser().parse(xml_path, report)

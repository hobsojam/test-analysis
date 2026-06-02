import lxml.etree as ET
from tqa.models import ComponentReport, FileReport, LineData
from tqa.parsers.base import Parser
from tqa.parsers.registry import register_parser


@register_parser("cobertura")
class CoberturaParser(Parser):
    def parse(self, path: str, report: ComponentReport) -> ComponentReport:
        try:
            tree = ET.parse(path)
        except ET.XMLSyntaxError as exc:
            raise ValueError(
                f"Failed to parse Cobertura report '{path}': {exc}"
            ) from exc
        except OSError as exc:
            raise FileNotFoundError(f"Cobertura report not found: '{path}'") from exc
        root = tree.getroot()
        for class_node in root.xpath("//class"):
            self._process_class_node(class_node, report)
        return report

    def _process_class_node(self, class_node, report: ComponentReport) -> None:
        file_path = class_node.get("filename")
        if file_path is None:
            return
        if file_path not in report.files:
            report.files[file_path] = FileReport(file_path=file_path)
        file_report = report.files[file_path]
        for line_node in class_node.xpath("./lines/line"):
            self._process_line_node(line_node, file_report)

    def _process_line_node(self, line_node, file_report: FileReport) -> None:
        number_str = line_node.get("number")
        hits_str = line_node.get("hits")
        if number_str is None or hits_str is None:
            return
        try:
            line_num = int(number_str)
            hits = int(hits_str)
        except (ValueError, TypeError):
            return
        if line_num not in file_report.lines:
            file_report.lines[line_num] = LineData(line_number=line_num)
        file_report.lines[line_num].is_covered = hits > 0


def parse_cobertura(xml_path: str, report: ComponentReport) -> ComponentReport:
    return CoberturaParser().parse(xml_path, report)

from tqa.models import ComponentReport, FileReport, LineData
from tqa.parsers.base import Parser
from tqa.parsers.registry import register_parser


@register_parser("lcov")
class LcovParser(Parser):
    def parse(self, path: str, report: ComponentReport) -> ComponentReport:
        try:
            f_handle = open(path, "r", encoding="utf-8")
        except OSError as exc:
            raise FileNotFoundError(f"LCOV report not found: '{path}'") from exc
        current_file = None
        with f_handle:
            for raw in f_handle:
                current_file = self._process_line(raw.strip(), report, current_file)
        return report

    def _process_line(self, line: str, report: ComponentReport, current_file):
        if line.startswith("SF:"):
            file_path = line[3:]
            if file_path not in report.files:
                report.files[file_path] = FileReport(file_path=file_path)
            return report.files[file_path]
        if line.startswith("DA:") and current_file is not None:
            self._parse_da_line(line[3:], current_file)
        elif line == "end_of_record":
            return None
        return current_file

    def _parse_da_line(self, data: str, current_file: FileReport) -> None:
        parts = data.split(",")
        if len(parts) < 2:
            return
        try:
            line_num = int(parts[0])
            hits = int(parts[1])
        except (ValueError, TypeError):
            return
        if line_num not in current_file.lines:
            current_file.lines[line_num] = LineData(line_number=line_num)
        current_file.lines[line_num].is_covered = hits > 0


def parse_lcov(lcov_path: str, report: ComponentReport) -> ComponentReport:
    return LcovParser().parse(lcov_path, report)

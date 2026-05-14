from tqa.models import ProjectReport, FileReport, LineData

def parse_lcov(lcov_path: str, report: ProjectReport) -> ProjectReport:
    current_file = None
    with open(lcov_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if line.startswith("SF:"):
                file_path = line[3:]
                if file_path not in report.files:
                    report.files[file_path] = FileReport(file_path=file_path)
                current_file = report.files[file_path]
            elif line.startswith("DA:") and current_file is not None:
                parts = line[3:].split(",")
                line_num = int(parts[0])
                hits = int(parts[1])
                if line_num not in current_file.lines:
                    current_file.lines[line_num] = LineData(line_number=line_num)
                current_file.lines[line_num].is_covered = hits > 0
            elif line == "end_of_record":
                current_file = None
    return report

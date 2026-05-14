import lxml.etree as ET
import re
from tqa.models import ProjectReport, FileReport, LineData, MutantData

def parse_mutmut(xml_path: str, report: ProjectReport) -> ProjectReport:
    """
    Parses a mutmut JUnit XML report and updates the ProjectReport.
    In mutmut's JUnit output:
    - Passed test = Killed mutant
    - Failed/Errored test = Survived mutant (or other error)
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    for testcase in root.xpath("//testcase"):
        # mutmut encodes info in the name: "mutant #123 (file: path/to/file.py, line: 45)"
        name = testcase.get("name")
        match = re.search(r"mutant #(\d+) \(file: (.*), line: (\d+)\)", name)
        
        if not match:
            continue
            
        mutant_id, file_path, line = match.groups()
        line = int(line)
        
        # Determine status
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
                id=mutant_id,
                status=status,
                line=line,
                description="mutmut mutation"
            )
        )

    return report

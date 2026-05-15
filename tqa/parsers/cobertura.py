import lxml.etree as ET
from tqa.models import ProjectReport, FileReport, LineData

def parse_cobertura(xml_path: str, report: ProjectReport) -> ProjectReport:
    """
    Parses a Cobertura XML report and updates the ProjectReport with coverage data.
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Iterate over all classes (files) in the report
    for class_node in root.xpath("//class"):
        file_path = class_node.get("filename")
        
        if file_path not in report.files:
            report.files[file_path] = FileReport(file_path=file_path)
        
        file_report = report.files[file_path]
        
        # Parse line hits
        for line_node in class_node.xpath("./lines/line"):
            line_num = int(line_node.get("number"))
            hits = int(line_node.get("hits"))
            
            if line_num not in file_report.lines:
                file_report.lines[line_num] = LineData(line_number=line_num)
            
            file_report.lines[line_num].is_covered = hits > 0

    return report

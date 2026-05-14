import lxml.etree as ET
from tqa.models import ProjectReport, FileReport, LineData, MutantData

def parse_pit(xml_path: str, report: ProjectReport) -> ProjectReport:
    """
    Parses a PIT mutation report (mutations.xml) and updates the ProjectReport.
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    for mutation in root.xpath("//mutation"):
        # PIT usually provides the source file and class name
        file_path = mutation.findtext("sourceFile")
        line = int(mutation.findtext("lineNumber"))
        status = mutation.get("status")
        mutator = mutation.findtext("mutator")
        
        # PIT XML doesn't always have a full path, might need mapping logic later
        # For now, we use the sourceFile name as the key
        if file_path not in report.files:
            report.files[file_path] = FileReport(file_path=file_path)
            
        file_report = report.files[file_path]
        
        if line not in file_report.lines:
            file_report.lines[line] = LineData(line_number=line)
            
        file_report.lines[line].mutants.append(
            MutantData(
                id=f"pit-{hash(mutation)}", # PIT doesn't have unique IDs in XML
                status=status,
                line=line,
                description=mutator
            )
        )

    return report

import json
from tqa.models import ProjectReport, FileReport, LineData, MutantData

def parse_stryker(json_path: str, report: ProjectReport) -> ProjectReport:
    """
    Parses a Stryker JSON report (Mutation Testing Elements schema) 
    and updates the ProjectReport with mutation data.
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    files = data.get("files", {})
    
    for file_path, file_data in files.items():
        if file_path not in report.files:
            report.files[file_path] = FileReport(file_path=file_path)
        
        file_report = report.files[file_path]
        mutants = file_data.get("mutants", [])
        
        for m in mutants:
            line = m["location"]["start"]["line"]
            mutant_id = str(m.get("id"))
            status = m.get("status")
            
            if line not in file_report.lines:
                file_report.lines[line] = LineData(line_number=line)
            
            file_report.lines[line].mutants.append(
                MutantData(
                    id=mutant_id,
                    status=status,
                    line=line,
                    description=m.get("mutatorName")
                )
            )

    return report

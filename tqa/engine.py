import os
from typing import Dict, List
from tqa.models import ProjectReport
from tqa.parsers import registry


class AnalysisEngine:
    def run(self, inputs: Dict[str, str]) -> ProjectReport:
        """
        Ingests all provided reports and returns the correlated ProjectReport.

        inputs maps parser key (e.g. "cobertura", "stryker") to file path.
        """
        report = ProjectReport()
        for parser_name, path in inputs.items():
            if path and os.path.exists(path) and parser_name in registry:
                registry.get(parser_name).parse(path, report)
        report.reconcile_paths()
        return report

    def get_critical_gaps(self, report: ProjectReport) -> List[dict]:
        """
        Identifies lines with 100% coverage but 0% mutation kill rate.
        """
        gaps = []
        for file_path, file_report in report.files.items():
            for line_num, line_data in file_report.lines.items():
                if line_data.is_covered and line_data.mutants:
                    killed = sum(1 for m in line_data.mutants if m.status.lower() == "killed")
                    if killed == 0:
                        gaps.append({
                            "file": file_path,
                            "line": line_num,
                            "survived": len(line_data.mutants),
                        })
        return gaps

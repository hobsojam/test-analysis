import os
from typing import List, Optional
from tqa.models import ProjectReport
from tqa.parsers.cobertura import parse_cobertura
from tqa.parsers.stryker import parse_stryker
from tqa.parsers.pit import parse_pit
from tqa.parsers.mutmut import parse_mutmut
from tqa.parsers.lcov import parse_lcov

class AnalysisEngine:
    def run(
        self,
        coverage_path: Optional[str] = None,
        lcov_path: Optional[str] = None,
        stryker_path: Optional[str] = None,
        pit_path: Optional[str] = None,
        mutmut_path: Optional[str] = None
    ) -> ProjectReport:
        """
        Ingests all provided reports and returns the correlated ProjectReport.
        """
        report = ProjectReport()

        if coverage_path and os.path.exists(coverage_path):
            parse_cobertura(coverage_path, report)

        if lcov_path and os.path.exists(lcov_path):
            parse_lcov(lcov_path, report)

        if stryker_path and os.path.exists(stryker_path):
            parse_stryker(stryker_path, report)

        if pit_path and os.path.exists(pit_path):
            parse_pit(pit_path, report)

        if mutmut_path and os.path.exists(mutmut_path):
            parse_mutmut(mutmut_path, report)

        return report

    def get_critical_gaps(self, report: ProjectReport) -> List[dict]:
        """
        Identifies lines with 100% coverage but 0% mutation kill rate.
        """
        gaps = []
        for file_path, file_report in report.files.items():
            for line_num, line_data in file_report.lines.items():
                if line_data.is_covered and line_data.mutants:
                    # Check if all mutants survived
                    killed = sum(1 for m in line_data.mutants if m.status.lower() == "killed")
                    if killed == 0:
                        gaps.append({
                            "file": file_path,
                            "line": line_num,
                            "survived": len(line_data.mutants)
                        })
        return gaps

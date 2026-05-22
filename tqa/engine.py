import os
from typing import Dict, List
from tqa.models import ProjectReport, ComponentReport
from tqa.parsers import registry


class AnalysisEngine:
    def run(self, inputs: Dict[str, str]) -> ProjectReport:
        """Single-component analysis. Wraps inputs in a 'default' component."""
        return self.run_multi({"default": inputs})

    def run_multi(self, components: Dict[str, Dict[str, str]]) -> ProjectReport:
        """Multi-component analysis. components maps name to parser-key → file-path."""
        report = ProjectReport()
        for comp_name, inputs in components.items():
            component = ComponentReport()
            for parser_name, path in inputs.items():
                if path and os.path.exists(path) and parser_name in registry:
                    registry.get(parser_name).parse(path, component)
            component.reconcile_paths()
            if component.files:
                report.components[comp_name] = component
        return report

    def get_surviving_mutants(self, report: ProjectReport) -> List[dict]:
        """Return structured findings for lines with unkilled mutants."""
        findings = []
        for component_name, component in report.components.items():
            for file_path, file_report in component.files.items():
                for line_num, line_data in file_report.lines.items():
                    if not line_data.mutants:
                        continue
                    killed = sum(
                        1 for m in line_data.mutants
                        if m.status.lower() == "killed"
                    )
                    survived = len(line_data.mutants) - killed
                    if survived == 0:
                        continue
                    findings.append({
                        "component": component_name,
                        "file": file_path,
                        "line": line_num,
                        "covered": line_data.is_covered,
                        "killed": killed,
                        "survived": survived,
                        "total": len(line_data.mutants),
                        "all_survived": killed == 0,
                        "mutants": [
                            {
                                "id": mutant.id,
                                "status": mutant.status,
                                "description": mutant.description,
                            }
                            for mutant in line_data.mutants
                            if mutant.status.lower() != "killed"
                        ],
                    })
        return findings

    def get_critical_gaps(self, report: ProjectReport) -> List[dict]:
        """Identifies covered lines with mutation data but 0% mutation kill rate."""
        gaps = []
        for finding in self.get_surviving_mutants(report):
            if finding["covered"] and finding["all_survived"]:
                gaps.append({
                    "file": finding["file"],
                    "line": finding["line"],
                    "survived": finding["survived"],
                })
        return gaps

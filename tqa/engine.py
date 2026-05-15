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

    def get_critical_gaps(self, report: ProjectReport) -> List[dict]:
        """Identifies lines with coverage but 0% mutation kill rate."""
        gaps = []
        for component in report.components.values():
            for file_path, file_report in component.files.items():
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

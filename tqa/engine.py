import os
from pathlib import Path
from typing import Dict, List, Optional
from tqa.models import ProjectReport, ComponentReport, LineData
from tqa.parsers import registry
from tqa.recommendations import recommendation_for_finding


class AnalysisEngine:
    def run(self, inputs: Dict[str, str]) -> ProjectReport:
        """Single-component analysis. Wraps inputs in a 'default' component."""
        return self.run_multi({"default": inputs})

    def run_multi(self, components: Dict[str, Dict[str, str]]) -> ProjectReport:
        """Multi-component analysis. components maps name to parser-key -> file-path."""
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

    def _surviving_mutant_finding(
        self,
        component_name: str,
        file_path: str,
        line_num: int,
        line_data: LineData,
    ) -> dict | None:
        killed = sum(1 for mutant in line_data.mutants if self._is_killed(mutant.status))
        survived = len(line_data.mutants) - killed
        if survived == 0:
            return None
        return {
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
                if not self._is_killed(mutant.status)
            ],
        }

    @staticmethod
    def _is_killed(status: str) -> bool:
        return status.lower() == "killed"

    def get_surviving_mutants(
        self,
        report: ProjectReport,
        project_root: Optional[str] = None,
        context_lines: int = 0,
    ) -> List[dict]:
        """Return structured findings for lines with unkilled mutants."""
        findings = []
        for component_name, component in report.components.items():
            for file_path, file_report in component.files.items():
                for line_num, line_data in file_report.lines.items():
                    if not line_data.mutants:
                        continue
                    finding = self._surviving_mutant_finding(
                        component_name,
                        file_path,
                        line_num,
                        line_data,
                    )
                    if not finding:
                        continue
                    if project_root is not None:
                        finding["source_context"] = self.get_source_context(
                            file_path,
                            line_num,
                            project_root,
                            context_lines,
                        )
                    finding["suggestion"] = recommendation_for_finding(finding)
                    findings.append(finding)
        return findings

    def get_source_context(
        self,
        file_path: str,
        line_number: int,
        project_root: str,
        context_lines: int = 0,
    ) -> Optional[dict]:
        """Return source text around a line, constrained to project_root."""
        source_path = self._resolve_source_path(file_path, project_root)
        if source_path is None:
            return None

        try:
            lines = source_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return None

        if line_number < 1 or line_number > len(lines):
            return None

        extra_lines = max(context_lines, 0)
        start_line = max(line_number - extra_lines, 1)
        end_line = min(line_number + extra_lines, len(lines))
        context = [
            {
                "line": current_line,
                "text": lines[current_line - 1],
                "is_target": current_line == line_number,
            }
            for current_line in range(start_line, end_line + 1)
        ]

        return {
            "path": str(source_path),
            "line": line_number,
            "text": lines[line_number - 1],
            "start_line": start_line,
            "end_line": end_line,
            "context": context,
        }

    def _resolve_source_path(self, file_path: str, project_root: str) -> Optional[Path]:
        root = Path(project_root).resolve()
        candidate = Path(file_path)
        if not candidate.is_absolute():
            candidate = root / candidate

        try:
            source_path = candidate.resolve()
            source_path.relative_to(root)
        except (OSError, ValueError):
            return None

        if not source_path.is_file():
            return None
        return source_path

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

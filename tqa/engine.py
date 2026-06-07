import logging
import os
from typing import Dict, List, Optional
from tqa.models import (
    ProjectReport,
    ComponentReport,
    LineData,
    MutantStatus,
    CriticalGap,
    SurvivingMutantFinding,
    SurvivingMutantEntry,
)
from tqa.parsers import registry
from tqa.recommendations import recommendation_for_finding
from tqa.source_context import read_source_context

logger = logging.getLogger(__name__)


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
                    try:
                        registry.get(parser_name).parse(path, component)
                    except (ValueError, FileNotFoundError) as exc:
                        logger.exception("Parser error [%s]: %s", parser_name, exc)
                        raise
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
    ) -> SurvivingMutantFinding | None:
        killed = sum(
            1 for mutant in line_data.mutants if self._is_killed(mutant.status)
        )
        survived = len(line_data.mutants) - killed
        if survived == 0:
            return None
        surviving_mutants: List[SurvivingMutantEntry] = [
            SurvivingMutantEntry(
                id=mutant.id,
                status=mutant.status,
                description=mutant.description,
            )
            for mutant in line_data.mutants
            if not self._is_killed(mutant.status)
        ]
        return SurvivingMutantFinding(
            component=component_name,
            file=file_path,
            line=line_num,
            covered=line_data.is_covered,
            killed=killed,
            survived=survived,
            total=len(line_data.mutants),
            all_survived=killed == 0,
            mutants=surviving_mutants,
            suggestion=None,
        )

    @staticmethod
    def _is_killed(status: str) -> bool:
        return status in (MutantStatus.KILLED, MutantStatus.TIMED_OUT)

    def get_surviving_mutants(
        self,
        report: ProjectReport,
        project_root: Optional[str] = None,
        context_lines: int = 0,
    ) -> List[SurvivingMutantFinding]:
        """Return structured findings for lines with unkilled mutants."""
        findings: List[SurvivingMutantFinding] = []
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
        return read_source_context(file_path, line_number, project_root, context_lines)

    def get_critical_gaps(
        self,
        report: ProjectReport,
        findings: Optional[List[SurvivingMutantFinding]] = None,
    ) -> List[CriticalGap]:
        """Identifies covered lines with mutation data but 0% mutation kill rate."""
        source = findings if findings is not None else self.get_surviving_mutants(report)
        return [
            CriticalGap(file=f["file"], line=f["line"], survived=f["survived"])
            for f in source
            if f["covered"] and f["all_survived"]
        ]

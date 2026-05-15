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
        self._reconcile_paths(report)
        return report

    def _reconcile_paths(self, report: ProjectReport) -> None:
        """Merge file entries that differ only by a path prefix.

        pytest-cov with `source = ["tqa"]` strips the package prefix from
        filenames (e.g. tqa/models.py -> models.py), while mutation tools
        keep the full path. For each shorter path, find the one longer path
        that ends with /<shorter> — if there is exactly one match it is safe
        to merge; ambiguous cases (e.g. __init__.py matching multiple dirs)
        are left as-is rather than merging incorrectly.
        """
        paths = list(report.files.keys())
        to_delete: List[str] = []

        for shorter in paths:
            if shorter in to_delete:
                continue
            candidates = [
                p for p in paths
                if p not in to_delete and p != shorter and p.endswith("/" + shorter)
            ]
            if len(candidates) != 1:
                continue
            longer = candidates[0]
            src = report.files[shorter]
            dst = report.files[longer]
            for line_num, line_data in src.lines.items():
                if line_num not in dst.lines:
                    dst.lines[line_num] = line_data
                else:
                    if line_data.is_covered:
                        dst.lines[line_num].is_covered = True
                    dst.lines[line_num].mutants.extend(line_data.mutants)
            to_delete.append(shorter)

        for path in to_delete:
            del report.files[path]

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

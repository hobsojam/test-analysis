from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class MutantData(BaseModel):
    id: str
    status: str
    line: int
    description: Optional[str] = None


class LineData(BaseModel):
    line_number: int
    is_covered: bool = False
    mutants: List[MutantData] = Field(default_factory=list)

    @property
    def mutation_score(self) -> float:
        if not self.mutants:
            return 1.0
        killed = sum(1 for m in self.mutants if m.status.lower() == "killed")
        return killed / len(self.mutants)


class FileReport(BaseModel):
    file_path: str
    lines: Dict[int, LineData] = Field(default_factory=dict)

    @property
    def has_mutation_data(self) -> bool:
        return any(bool(line.mutants) for line in self.lines.values())

    @property
    def line_coverage(self) -> float:
        if not self.lines:
            return 0.0
        covered = sum(1 for line in self.lines.values() if line.is_covered)
        return covered / len(self.lines)

    @property
    def test_strength(self) -> float:
        """Calculates the Test Strength Index (TSI). Only considers covered lines."""
        covered_lines = [line for line in self.lines.values() if line.is_covered]
        if not covered_lines:
            return 0.0
        scores = [line.mutation_score for line in covered_lines]
        return sum(scores) / len(scores)


class ComponentReport(BaseModel):
    """Parsed data for a single technology stack within the project."""
    files: Dict[str, FileReport] = Field(default_factory=dict)

    @property
    def has_mutation_data(self) -> bool:
        return any(f.has_mutation_data for f in self.files.values())

    @property
    def total_test_strength(self) -> float:
        mutation_files = [f for f in self.files.values() if f.has_mutation_data]
        if not mutation_files:
            return 0.0
        return sum(f.test_strength for f in mutation_files) / len(mutation_files)

    def reconcile_paths(self) -> None:
        """Merge file entries that differ only by a path prefix.

        pytest-cov with `source = ["tqa"]` strips the package prefix from
        filenames (e.g. tqa/models.py -> models.py), while mutation tools
        keep the full path. For each shorter path, find the one longer path
        that ends with /<shorter> — if there is exactly one match it is safe
        to merge; ambiguous cases (e.g. __init__.py matching multiple dirs)
        are left as-is rather than merging incorrectly.
        """
        paths = list(self.files.keys())
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
            src = self.files[shorter]
            dst = self.files[longer]
            for line_num, line_data in src.lines.items():
                if line_num not in dst.lines:
                    dst.lines[line_num] = line_data
                else:
                    if line_data.is_covered:
                        dst.lines[line_num].is_covered = True
                    dst.lines[line_num].mutants.extend(line_data.mutants)
            to_delete.append(shorter)

        for path in to_delete:
            del self.files[path]


class ProjectReport(BaseModel):
    """Top-level report aggregating one or more ComponentReports."""
    components: Dict[str, ComponentReport] = Field(default_factory=dict)

    @property
    def has_mutation_data(self) -> bool:
        return any(c.has_mutation_data for c in self.components.values())

    @property
    def total_test_strength(self) -> float:
        if not self.components:
            return 0.0
        mutation_counts = {
            name: sum(1 for f in c.files.values() if f.has_mutation_data)
            for name, c in self.components.items()
        }
        total = sum(mutation_counts.values())
        if total == 0:
            return 0.0
        return sum(
            c.total_test_strength * mutation_counts[name]
            for name, c in self.components.items()
        ) / total

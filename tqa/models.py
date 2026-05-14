from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class MutantData(BaseModel):
    id: str
    status: str  # Killed, Survived, NoCoverage, etc.
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
        covered = sum(1 for l in self.lines.values() if l.is_covered)
        return covered / len(self.lines)

    @property
    def test_strength(self) -> float:
        """
        Calculates the Test Strength Index (TSI) for the file.
        Only considers lines that are actually covered.
        """
        covered_lines = [l for l in self.lines.values() if l.is_covered]
        if not covered_lines:
            return 0.0
        
        # Average mutation score across covered lines
        # If a line has no mutants, we treat it as 1.0 (no weakness found)
        scores = [l.mutation_score for l in covered_lines]
        return sum(scores) / len(scores)

class ProjectReport(BaseModel):
    files: Dict[str, FileReport] = Field(default_factory=dict)

    @property
    def has_mutation_data(self) -> bool:
        return any(f.has_mutation_data for f in self.files.values())

    @property
    def total_test_strength(self) -> float:
        if not self.files:
            return 0.0
        return sum(f.test_strength for f in self.files.values()) / len(self.files)

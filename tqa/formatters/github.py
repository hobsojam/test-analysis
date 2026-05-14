from tqa.models import ProjectReport
from tqa.engine import AnalysisEngine

def generate_markdown_summary(report: ProjectReport) -> str:
    lines = [
        "# 🛡️ TQA Report Summary",
        "",
        "| File | Coverage | Test Strength (TSI) | Status |",
        "| :--- | :---: | :---: | :---: |"
    ]
    
    for file_path, file_report in report.files.items():
        cov = file_report.line_coverage * 100
        tsi = file_report.test_strength * 100
        
        status = "✅"
        if tsi < 80: status = "⚠️"
        if tsi < 50: status = "❌"
        
        lines.append(f"| `{file_path}` | {cov:.1f}% | {tsi:.1f}% | {status} |")
        
    lines.append("")
    lines.append(f"**Total Project Test Strength: {report.total_test_strength * 100:.1f}%**")
    
    # Add Critical Gaps section
    engine = AnalysisEngine()
    gaps = engine.get_critical_gaps(report)
    if gaps:
        lines.append("\n## 🚨 Critical Gaps (100% Coverage, 0% Killed)")
        lines.append("| File | Line | Survived Mutants |")
        lines.append("| :--- | :---: | :---: |")
        for gap in gaps[:10]: # Limit to top 10
            lines.append(f"| `{gap['file']}` | {gap['line']} | {gap['survived']} |")
            
    return "\n".join(lines)

def print_github_annotations(report: ProjectReport):
    engine = AnalysisEngine()
    gaps = engine.get_critical_gaps(report)
    for gap in gaps:
        print(f"::warning file={gap['file']},line={gap['line']}::Critical Gap: Line is covered but all {gap['survived']} mutants survived. Stronger assertions needed.")

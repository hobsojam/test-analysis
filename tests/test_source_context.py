from tqa.engine import AnalysisEngine
from tqa.models import ComponentReport, FileReport, LineData, MutantData, ProjectReport


def _report_for(file_path: str, line_number: int = 2) -> ProjectReport:
    report = ProjectReport()
    component = ComponentReport()
    component.files[file_path] = FileReport(file_path=file_path)
    component.files[file_path].lines[line_number] = LineData(
        line_number=line_number,
        is_covered=True,
    )
    component.files[file_path].lines[line_number].mutants.append(
        MutantData(
            id="mut-1",
            status="Survived",
            line=line_number,
            description="ConditionalBoundary",
        )
    )
    report.components["default"] = component
    return report


def test_surviving_mutants_include_source_context_when_project_root_is_given(tmp_path):
    source_file = tmp_path / "src" / "auth.py"
    source_file.parent.mkdir()
    source_file.write_text(
        "def allowed(user):\n"
        "    return user.is_admin\n"
        "print(allowed(user))\n",
        encoding="utf-8",
    )

    findings = AnalysisEngine().get_surviving_mutants(
        _report_for("src/auth.py"),
        project_root=str(tmp_path),
        context_lines=1,
    )

    context = findings[0]["source_context"]
    assert context == {
        "path": str(source_file.resolve()),
        "line": 2,
        "text": "    return user.is_admin",
        "start_line": 1,
        "end_line": 3,
        "context": [
            {"line": 1, "text": "def allowed(user):", "is_target": False},
            {"line": 2, "text": "    return user.is_admin", "is_target": True},
            {"line": 3, "text": "print(allowed(user))", "is_target": False},
        ],
    }


def test_surviving_mutants_do_not_include_source_context_without_project_root():
    findings = AnalysisEngine().get_surviving_mutants(_report_for("src/auth.py"))

    assert "source_context" not in findings[0]


def test_surviving_mutants_use_none_source_context_for_missing_files(tmp_path):
    findings = AnalysisEngine().get_surviving_mutants(
        _report_for("src/missing.py"),
        project_root=str(tmp_path),
    )

    assert findings[0]["source_context"] is None


def test_source_context_rejects_paths_outside_project_root(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    outside_file = tmp_path / "outside.py"
    outside_file.write_text("print('outside')\n", encoding="utf-8")

    findings = AnalysisEngine().get_surviving_mutants(
        _report_for("../outside.py", line_number=1),
        project_root=str(project_root),
    )

    assert findings[0]["source_context"] is None

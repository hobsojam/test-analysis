from tqa.engine import AnalysisEngine
from tqa.models import ComponentReport, FileReport, LineData, MutantData, ProjectReport
from tqa.source_context import read_source_context, resolve_source_path


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
        "def allowed(user):\n    return user.is_admin\nprint(allowed(user))\n",
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


# --- Standalone unit tests for tqa.source_context ---


def test_read_source_context_returns_correct_line(tmp_path):
    src = tmp_path / "mod.py"
    src.write_text("line one\nline two\nline three\n", encoding="utf-8")

    result = read_source_context("mod.py", 2, str(tmp_path))

    assert result is not None
    assert result["line"] == 2
    assert result["text"] == "line two"
    assert result["start_line"] == 2
    assert result["end_line"] == 2
    assert result["context"] == [{"line": 2, "text": "line two", "is_target": True}]


def test_read_source_context_includes_surrounding_lines(tmp_path):
    src = tmp_path / "mod.py"
    src.write_text("a\nb\nc\nd\ne\n", encoding="utf-8")

    result = read_source_context("mod.py", 3, str(tmp_path), context_lines=1)

    assert result["start_line"] == 2
    assert result["end_line"] == 4
    assert len(result["context"]) == 3
    assert result["context"][1]["is_target"] is True


def test_read_source_context_clamps_context_at_file_boundaries(tmp_path):
    src = tmp_path / "mod.py"
    src.write_text("only\n", encoding="utf-8")

    result = read_source_context("mod.py", 1, str(tmp_path), context_lines=5)

    assert result["start_line"] == 1
    assert result["end_line"] == 1


def test_read_source_context_returns_none_for_missing_file(tmp_path):
    result = read_source_context("nonexistent.py", 1, str(tmp_path))
    assert result is None


def test_read_source_context_returns_none_for_out_of_bounds_line(tmp_path):
    src = tmp_path / "mod.py"
    src.write_text("one\ntwo\n", encoding="utf-8")

    assert read_source_context("mod.py", 0, str(tmp_path)) is None
    assert read_source_context("mod.py", 99, str(tmp_path)) is None


def test_read_source_context_rejects_path_traversal(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    outside = tmp_path / "secret.py"
    outside.write_text("secret\n", encoding="utf-8")

    result = read_source_context("../secret.py", 1, str(project_root))
    assert result is None


def test_read_source_context_ignores_negative_context_lines(tmp_path):
    src = tmp_path / "mod.py"
    src.write_text("x\ny\nz\n", encoding="utf-8")

    result = read_source_context("mod.py", 2, str(tmp_path), context_lines=-10)

    assert result["start_line"] == 2
    assert result["end_line"] == 2


def test_resolve_source_path_returns_path_for_valid_file(tmp_path):
    src = tmp_path / "file.py"
    src.write_text("x\n", encoding="utf-8")

    resolved = resolve_source_path("file.py", str(tmp_path))

    assert resolved is not None
    assert resolved.is_file()


def test_resolve_source_path_returns_none_for_missing_file(tmp_path):
    assert resolve_source_path("missing.py", str(tmp_path)) is None


def test_resolve_source_path_returns_none_for_traversal(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("x\n", encoding="utf-8")

    assert resolve_source_path("../outside.py", str(project_root)) is None

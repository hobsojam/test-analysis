"""Source-context reader for surviving-mutant findings.

Resolves a file path safely against a project root and returns the source text
for a given line number, plus optional surrounding context lines.  All
error paths (missing file, out-of-bounds line, path traversal) return None
rather than raising.
"""

from pathlib import Path
from typing import Optional


def resolve_source_path(file_path: str, project_root: str) -> Optional[Path]:
    """Resolve *file_path* relative to *project_root*, rejecting traversals.

    Returns the resolved :class:`~pathlib.Path` when it exists inside
    *project_root*, or ``None`` if:

    - the resolved path is outside *project_root*,
    - the path does not exist or is not a regular file, or
    - any OS error occurs during resolution.
    """
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


def read_source_context(
    file_path: str,
    line_number: int,
    project_root: str,
    context_lines: int = 0,
) -> Optional[dict]:
    """Return source text around *line_number* in *file_path*.

    Parameters
    ----------
    file_path:
        Path to the source file, typically relative to *project_root*.
    line_number:
        1-based line number of the mutated line.
    project_root:
        Absolute path used as the safety boundary.  *file_path* must resolve
        to a descendant of this directory.
    context_lines:
        Number of lines to include before and after the target line.
        Clamped to 0 if negative.

    Returns
    -------
    dict or None
        ``None`` when the file cannot be resolved, read, or the line number is
        out of range.  Otherwise a dict with keys:

        - ``path`` – resolved absolute path string
        - ``line`` – the requested 1-based line number
        - ``text`` – stripped text of the target line
        - ``start_line`` / ``end_line`` – inclusive 1-based range returned
        - ``context`` – list of ``{"line": int, "text": str, "is_target": bool}``
    """
    source_path = resolve_source_path(file_path, project_root)
    if source_path is None:
        return None

    try:
        raw_lines = source_path.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()
    except OSError:
        return None

    if line_number < 1 or line_number > len(raw_lines):
        return None

    extra = max(context_lines, 0)
    start_line = max(line_number - extra, 1)
    end_line = min(line_number + extra, len(raw_lines))

    context = [
        {
            "line": current_line,
            "text": raw_lines[current_line - 1],
            "is_target": current_line == line_number,
        }
        for current_line in range(start_line, end_line + 1)
    ]

    return {
        "path": str(source_path),
        "line": line_number,
        "text": raw_lines[line_number - 1],
        "start_line": start_line,
        "end_line": end_line,
        "context": context,
    }

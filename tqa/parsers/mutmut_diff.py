import re


MAX_DIFF_LINES = 100

_ARITHMETIC_PAIRS = (("+", "-"), ("-", "+"), ("*", "/"), ("/", "*"))
_COMPARISON_PAIRS = (
    ("==", "!="),
    ("!=", "=="),
    (">=", ">"),
    (">", ">="),
    ("<=", "<"),
    ("<", "<="),
    (">", "<"),
    ("<", ">"),
)
_BOOLEAN_PAIRS = (("True", "False"), ("False", "True"), ("and", "or"), ("or", "and"))
_EMPTY_RETURN_VALUES = ("None", "''", '""', "0", "False")


def infer_mutmut_description(diff_text: str | None) -> str | None:
    """Infer a broad mutation category from mutmut's survived-mutant diff."""
    if not diff_text:
        return None

    removed, added = _changed_lines(diff_text)
    if not removed and not added:
        return None

    for before in removed:
        for after in added:
            classification = _classify_change(before, after)
            if classification:
                return classification

    if removed and not any(added) and any(_looks_like_call(line) for line in removed):
        return "VoidMethodCall"

    return None


def _changed_lines(diff_text: str) -> tuple[list[str], list[str]]:
    removed: list[str] = []
    added: list[str] = []
    for raw_line in diff_text.splitlines():
        if len(removed) + len(added) >= MAX_DIFF_LINES:
            break
        if raw_line.startswith(("---", "+++", "@@")):
            continue
        if raw_line.startswith("-"):
            removed.append(raw_line[1:].strip())
        elif raw_line.startswith("+"):
            added.append(raw_line[1:].strip())
    return removed, added


def _classify_change(before: str, after: str) -> str | None:
    if _has_token_swap(before, after, _BOOLEAN_PAIRS):
        return "BooleanLiteral"

    if before.startswith("return ") and after.startswith("return "):
        returned = after.removeprefix("return ").strip()
        if returned in _EMPTY_RETURN_VALUES:
            return "ReturnValue"

    if _has_token_swap(before, after, _COMPARISON_PAIRS):
        return "ComparisonOperator"
    if _has_token_swap(before, after, _ARITHMETIC_PAIRS):
        return "ArithmeticOperator"
    return None


def _has_token_swap(before: str, after: str, pairs: tuple[tuple[str, str], ...]) -> bool:
    for old, new in pairs:
        if old in before and new in after:
            before_without_old = before.replace(old, "", 1)
            after_without_new = after.replace(new, "", 1)
            if before_without_old == after_without_new:
                return True
    return False


def _looks_like_call(line: str) -> bool:
    return bool(re.search(r"\b[\w.]+\([^)]*\)", line)) and not line.startswith("def ")

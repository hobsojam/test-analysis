from collections.abc import Iterable


FALLBACK_SUGGESTION = (
    "Add a test that fails when this mutation changes the observable behavior."
)


_RULES = [
    (
        ("conditional", "conditionals", "boundary"),
        "Add branch or boundary-value tests that distinguish each side of this condition.",
    ),
    (
        ("equality", "equal", "comparison"),
        "Add cases that distinguish equality from inequality and assert the result.",
    ),
    (
        ("boolean", "negate", "negation", "invert"),
        "Add true and false path tests with assertions on the observable result.",
    ),
    (
        ("return",),
        "Assert the exact returned value for this path.",
    ),
    (
        ("math", "arithmetic", "operator"),
        "Use inputs where this operation changes the result and assert that result.",
    ),
    (
        ("method", "call", "void"),
        "Assert the side effect or collaborator interaction from this call.",
    ),
    (
        ("constant", "string", "number", "literal"),
        "Assert behavior that depends on this literal or constant value.",
    ),
    (
        ("exception", "throws", "throw"),
        "Add an error-path test that asserts the expected exception or failure result.",
    ),
]


def recommendation_for_finding(finding: dict) -> str:
    """Return deterministic test guidance for a surviving-mutant finding."""
    if not finding.get("covered", False):
        return "Add coverage for this line before strengthening assertions."

    descriptions = list(_mutator_descriptions(finding))
    for keywords, suggestion in _RULES:
        if any(
            keyword in description
            for description in descriptions
            for keyword in keywords
        ):
            return _with_source_focus(suggestion, finding)
    return _with_source_focus(FALLBACK_SUGGESTION, finding)


def _mutator_descriptions(finding: dict) -> Iterable[str]:
    for mutant in finding.get("mutants", []):
        description = mutant.get("description")
        if description:
            yield description.lower()


def _with_source_focus(suggestion: str, finding: dict) -> str:
    source_context = finding.get("source_context")
    if not source_context:
        return suggestion

    text = source_context.get("text", "").strip()
    if not text:
        return suggestion
    return f"{suggestion} Focus line: `{text}`."

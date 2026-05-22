import pytest

from tqa.recommendations import recommendation_for_finding


def _finding(description: str | None, covered: bool = True) -> dict:
    return {
        "covered": covered,
        "mutants": [
            {
                "id": "1",
                "status": "Survived",
                "description": description,
            }
        ],
    }


@pytest.mark.parametrize(
    "description,expected",
    [
        ("ConditionalBoundary", "boundary-value tests"),
        ("EqualityOperator", "equality from inequality"),
        ("BooleanLiteral", "true and false path"),
        ("ReturnValue", "exact returned value"),
        ("MathMutator", "operation changes the result"),
        ("VoidMethodCall", "side effect or collaborator interaction"),
        ("StringLiteral", "literal or constant value"),
        ("ExceptionMutator", "error-path test"),
    ],
)
def test_recommendation_for_known_mutator_families(description: str, expected: str):
    assert expected in recommendation_for_finding(_finding(description))


def test_recommendation_prioritizes_coverage_for_uncovered_findings():
    assert recommendation_for_finding(_finding("ReturnValue", covered=False)) == (
        "Add coverage for this line before strengthening assertions."
    )


def test_recommendation_uses_generic_fallback_for_unknown_mutators():
    assert recommendation_for_finding(_finding("UnknownMutator")) == (
        "Add a test that fails when this mutation changes the observable behavior."
    )


def test_recommendation_uses_generic_fallback_when_description_is_none():
    # mutmut JUnit XML provides no mutation type; None description must not crash
    # and must produce the generic fallback (not a placeholder like "mutmut mutation").
    assert recommendation_for_finding(_finding(None)) == (
        "Add a test that fails when this mutation changes the observable behavior."
    )


def test_recommendation_can_include_source_focus():
    finding = _finding("ReturnValue")
    finding["source_context"] = {"text": "return user.is_admin"}

    assert recommendation_for_finding(finding) == (
        "Assert the exact returned value for this path. "
        "Focus line: `return user.is_admin`."
    )


def test_recommendation_skips_blank_source_focus():
    finding = _finding("ReturnValue")
    finding["source_context"] = {"text": "   "}

    assert recommendation_for_finding(finding) == (
        "Assert the exact returned value for this path."
    )

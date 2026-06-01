import pytest

from tqa.parsers.mutmut_diff import infer_mutmut_description


@pytest.mark.parametrize(
    "before,after,expected",
    [
        ("return a + b", "return a - b", "ArithmeticOperator"),
        ("return user == owner", "return user != owner", "ComparisonOperator"),
        ("return True", "return False", "BooleanLiteral"),
        ("return result", "return None", "ReturnValue"),
    ],
)
def test_infer_mutmut_description_from_replaced_line(
    before: str,
    after: str,
    expected: str,
):
    diff = f"""--- main.py
+++ main.py (copy)
@@ -1,1 +1,1 @@
-    {before}
+    {after}
"""

    assert infer_mutmut_description(diff) == expected


def test_infer_mutmut_description_from_deleted_call():
    diff = """--- main.py
+++ main.py (copy)
@@ -1,1 +1,0 @@
-    service.notify(user)
"""

    assert infer_mutmut_description(diff) == "VoidMethodCall"


def test_infer_mutmut_description_from_call_replaced_with_blank_line():
    diff = """--- main.py
+++ main.py (copy)
@@ -1,1 +1,1 @@
-    service.notify(user)
+
"""

    assert infer_mutmut_description(diff) == "VoidMethodCall"


@pytest.mark.parametrize(
    "diff_text",
    [
        None,
        "",
        "survived",
        "--- main.py\n+++ main.py\n@@ -1,1 +1,1 @@\n-    x = foo\n+    y = bar\n",
    ],
)
def test_infer_mutmut_description_returns_none_for_ambiguous_diff(
    diff_text: str | None,
):
    assert infer_mutmut_description(diff_text) is None


def test_infer_mutmut_description_caps_scanned_diff_lines():
    diff = "\n".join(f"-    value_{index}" for index in range(101))

    assert infer_mutmut_description(diff) is None

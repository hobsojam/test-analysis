# tqa - Test Quality Analyzer

`tqa` is a language-agnostic CLI tool designed to bridge the gap between **Code Coverage** and **Mutation Testing**. It provides a "Test Strength Index" (TSI) by correlating which lines of code are executed by tests versus which lines actually have effective assertions.

## 🚀 Key Features

- **Multi-Ecosystem Support**: Built-in parsers for Java (PIT), Python (mutmut), and JavaScript/TypeScript (Stryker).
- **Unified Coverage**: Supports Cobertura XML as the universal coverage format.
- **Blind Spot Detection**: Automatically identifies "False Positives"—lines with 100% coverage but 0% mutation kill rate.
- **CI/CD Native**: Optimized for GitHub Actions with automated Markdown summaries and inline PR annotations.
- **Actionable Insights**: Detailed reports showing exactly which lines need stronger assertions.

## 🛠️ Technologies

- **Python 3.10+**: Chosen for its rich ecosystem, ease of CI integration, and excellent XML/JSON handling.
- **Pydantic**: For robust, type-safe data modeling of report schemas.
- **Click**: For a professional, intuitive command-line interface.
- **Rich**: For beautiful, colorized terminal output.
- **Pytest**: For ensuring the analyzer itself is rock-solid.

## 🧪 Testing

We use `pytest` for unit testing. The tests verify that the parsers correctly handle various report formats and that the correlation engine accurately calculates the Test Strength Index.

### Running Tests

1.  **Install dev dependencies**:
    ```bash
    pip install .[dev]
    ```

2.  **Run the test suite**:
    ```bash
    python -m pytest tests/
    ```

### Adding New Test Cases
Place sample report files in `tests/` and add corresponding test functions in `tests/test_tqa.py` to verify parser behavior on new edge cases.

## 📈 Implementation Plan

1.  **Phase 1: Foundation**: Project initialization and core Pydantic models to represent the "Unified Test Quality Report."
2.  **Phase 2: Data Ingestion**: Implementation of parsers for Cobertura (coverage), Stryker (JS/TS), PIT (Java), and mutmut (Python).
3.  **Phase 4: Output & Integration**: Development of the console table formatter and the GitHub Actions Markdown/Annotation generator.

## 📖 Usage Guide (Preview)

Once installed, you can analyze your project by pointing `tqa` to your report files:

```bash
# Analyze a JavaScript project using Stryker and Cobertura
tqa analyze \
  --coverage ./coverage/cobertura-coverage.xml \
  --mutation ./reports/stryker-report.json \
  --format github

# Analyze a Python project using mutmut and pytest-cov
tqa analyze \
  --coverage ./coverage.xml \
  --mutation ./mutmut-junit.xml \
  --format console
```

### GitHub Actions Integration

Add `tqa` to your workflow to get automated PR comments:

```yaml
- name: Run TQA
  run: |
    pip install tqa
    tqa analyze --coverage coverage.xml --mutation report.json --format github > tqa-summary.md
```

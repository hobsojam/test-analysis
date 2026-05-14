# tqa — Test Quality Analyzer

`tqa` correlates code coverage with mutation testing to produce a **Test Strength Index (TSI)**: the percentage of covered lines where mutants are actually killed. A line with coverage but no killed mutants means your tests execute the code but don't verify its behaviour.

## Installation

```bash
pip install tqa
```

## Quick start

```bash
tqa analyze --coverage coverage.xml --mutmut mutmut.xml
```

## Generating the input reports

### Python (pytest-cov + mutmut)

```bash
# Coverage — outputs coverage.xml in the current directory
python -m pytest --cov --cov-report=xml:coverage.xml tests/

# Mutation — outputs .mutmut-cache in the current directory
mutmut run
mutmut junitxml > mutmut.xml   # export to mutmut.xml
```

```bash
tqa analyze --coverage coverage.xml --mutmut mutmut.xml
```

### JavaScript / TypeScript (Jest/Vitest + Stryker)

```bash
# Coverage — Jest writes coverage/lcov.info by default
jest --coverage

# Mutation — Stryker writes reports/mutation/mutation.json by default
stryker run
```

```bash
tqa analyze --lcov coverage/lcov.info --stryker reports/mutation/mutation.json
```

If you use NYC instead of Jest:

```bash
nyc report --reporter=lcov   # writes coverage/lcov.info
```

### Java (JaCoCo + PIT)

```bash
# Coverage + mutation — both produced by a single Maven build
mvn test jacoco:report org.pitest:pitest-maven:mutationCoverage
# Coverage: target/site/jacoco/jacoco.xml
# Mutations: target/pit-reports/<timestamp>/mutations.xml
```

```bash
tqa analyze \
  --coverage target/site/jacoco/jacoco.xml \
  --pit target/pit-reports/*/mutations.xml
```

## Report file locations at a glance

| Tool | Default output path |
| :--- | :--- |
| pytest-cov | `coverage.xml` (configure with `--cov-report=xml:<path>`) |
| mutmut | `.mutmut-cache` (DB); export with `mutmut junitxml > mutmut.xml` |
| Jest | `coverage/lcov.info` |
| Vitest | `coverage/lcov.info` (requires `@vitest/coverage-v8`) |
| NYC | `coverage/lcov.info` |
| Stryker | `reports/mutation/mutation.json` |
| JaCoCo | `target/site/jacoco/jacoco.xml` |
| PIT | `target/pit-reports/<timestamp>/mutations.xml` |

## CLI reference

```
tqa analyze [OPTIONS]

  --coverage PATH     Cobertura XML (pytest-cov, JaCoCo)
  --lcov PATH         lcov.info (Jest, Vitest, NYC)
  --stryker PATH      Stryker JSON report
  --mutmut PATH       mutmut JUnit XML (mutmut junitxml)
  --pit PATH          PIT mutations.xml
  --format [console|github]  Output format (default: console)
  --fail-under FLOAT  Exit 1 if TSI is below this percentage
```

Multiple flags can be combined — tqa merges coverage and mutation data by file path.

## GitHub Actions integration

```yaml
- name: Run tests with coverage
  run: python -m pytest --cov --cov-report=xml:coverage.xml tests/

- name: Run mutation tests
  run: mutmut run
  continue-on-error: true   # don't block CI on surviving mutants

- name: Export mutation results
  run: mutmut junitxml > mutmut.xml

- name: Run TQA
  run: |
    tqa analyze \
      --coverage coverage.xml \
      --mutmut mutmut.xml \
      --format github > tqa-summary.md

- name: Comment on PR
  if: github.event_name == 'pull_request'
  run: gh pr comment ${{ github.event.number }} --body-file tqa-summary.md
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

Use `--fail-under 80` on the `tqa analyze` line to enforce a minimum TSI quality gate.

## Output

### Console (default)

```
          TQA - Test Quality Summary
┌─────────────┬──────────┬─────────────────────┬─────────┐
│ File        │ Coverage │ Test Strength (TSI)  │ Status  │
├─────────────┼──────────┼─────────────────────┼─────────┤
│ models.py   │   95.0%  │              88.5%   │ Healthy │
│ engine.py   │   80.0%  │              62.0%   │ Weak    │
│ index.js    │   39.2%  │                N/A   │ No data │
└─────────────┴──────────┴─────────────────────┴─────────┘

Total Project Test Strength: 84.2%
```

`N/A` in the TSI column means no mutation data was loaded for that file — coverage alone cannot measure test strength.

### GitHub (`--format github`)

Produces a Markdown table suitable for a PR comment, plus `::warning` annotations for lines with 100% coverage but 0% mutants killed.

## Development

```bash
pip install .[dev]
python -m pytest tests/
```

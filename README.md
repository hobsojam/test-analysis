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
| Vitest | `coverage/lcov.info` (requires `@vitest/coverage-v8` and `reporter: ['lcov']` in config) |
| NYC | `coverage/lcov.info` |
| Stryker | `reports/mutation/mutation.json` |
| JaCoCo | `target/site/jacoco/jacoco.xml` |
| PIT | `target/pit-reports/<timestamp>/mutations.xml` |

## CLI reference

```
tqa analyze [OPTIONS]

  --config PATH       tqa.toml config file (multi-technology projects)
  --coverage PATH     Cobertura XML (pytest-cov, JaCoCo)
  --lcov PATH         lcov.info (Jest, Vitest, NYC)
  --stryker PATH      Stryker JSON report
  --mutmut PATH       mutmut JUnit XML (mutmut junitxml)
  --pit PATH          PIT mutations.xml
  --format [console|github]  Output format (default: console)
  --fail-under FLOAT  Exit 1 if TSI is below this percentage
```

Multiple flags can be combined — tqa merges coverage and mutation data by file path.

## Multi-technology projects

When a project has more than one technology stack (e.g. a Node.js server and a Svelte/React frontend), use a `tqa.toml` config file to define named components. Each component is analyzed independently and gets its own section in the report.

### tqa.toml format

```toml
[components.server]
lcov    = "reports/server/lcov.info"
stryker = "reports/server/mutation.json"

[components.client]
lcov    = "reports/client/lcov.info"
stryker = "reports/client/mutation.json"
```

Then invoke tqa with:

```bash
tqa analyze --config tqa.toml --format github
```

The flat flags (`--lcov`, `--coverage`, etc.) remain available as a shorthand for single-stack projects and produce the same output as before. Use `--config` whenever you need separate per-component metrics.

### Enabling coverage for Vitest

Vitest does not produce coverage by default. You need the `@vitest/coverage-v8` package and a coverage config:

```bash
npm install --save-dev @vitest/coverage-v8
```

In `vite.config.js` (or `vitest.config.js`):

```js
export default {
  test: {
    coverage: {
      provider: 'v8',
      reporter: ['lcov'],
      reportsDirectory: 'reports/coverage',
    },
  },
}
```

Add a separate script for coverage so plain `npm test` stays fast in local development:

```json
"scripts": {
  "test": "vitest run",
  "test:coverage": "vitest run --coverage"
}
```

Run coverage:

```bash
npm run test:coverage
# writes: reports/coverage/lcov.info
```

Without this, the client component will show no coverage data and TSI will be N/A for all client files.

### GitHub Actions — multi-technology example

Four things must be true for both stacks to appear in the report:

1. **The `tqa` job must `needs` both upstream jobs** — otherwise it may run before one stack finishes.
2. **Both artifact sets must be downloaded** — one `download-artifact` step per stack.
3. **A `tqa.toml` must be committed** to the repo pointing at the downloaded paths.
4. **Artifact uploads must flatten the directory structure** — `actions/download-artifact` preserves the path relative to the repo root, so uploading `server/coverage/lcov.info` and downloading to `reports/server` lands at `reports/server/server/coverage/lcov.info`. Add a collect step to copy reports to a flat staging directory before uploading.

```yaml
jobs:
  server-test:
    steps:
      - uses: actions/checkout@v4
      - run: npx c8 --reporter=lcov node --test
        working-directory: server
      - run: npx stryker run
        working-directory: server
      - name: Collect server reports
        run: |
          mkdir -p artifacts
          cp server/coverage/lcov.info artifacts/lcov.info
          cp server/reports/mutation/mutation.json artifacts/mutation.json
      - uses: actions/upload-artifact@v4
        with:
          name: server-reports
          path: artifacts/

  client-test:
    steps:
      - uses: actions/checkout@v4
      - run: npm install
        working-directory: client
      - run: npm run test:coverage           # see Vitest section above
        working-directory: client
      - run: npx stryker run
        working-directory: client
      - name: Collect client reports
        run: |
          mkdir -p artifacts
          cp client/reports/coverage/lcov.info artifacts/lcov.info
          cp client/reports/mutation/mutation.json artifacts/mutation.json
      - uses: actions/upload-artifact@v4
        with:
          name: client-reports
          path: artifacts/

  tqa:
    needs: [server-test, client-test]      # wait for BOTH jobs
    permissions:
      pull-requests: write
    steps:
      - uses: actions/checkout@v4          # needed to read tqa.toml
      - uses: actions/download-artifact@v4
        with:
          name: server-reports
          path: reports/server
      - uses: actions/download-artifact@v4
        with:
          name: client-reports
          path: reports/client
      - run: pip install tqa
      - run: tqa analyze --config tqa.toml --format github > tqa-summary.md
      # ... comment step as in the single-job example
```

With a `tqa.toml` in the repo root (paths match the flattened artifact structure above):

```toml
[components.server]
lcov    = "reports/server/lcov.info"
stryker = "reports/server/mutation.json"

[components.client]
lcov    = "reports/client/lcov.info"
stryker = "reports/client/mutation.json"
```

## GitHub Actions integration

### Single-job example (Python)

```yaml
- name: Run tests with coverage
  run: python -m pytest --cov --cov-report=xml:coverage.xml tests/

- name: Verify coverage data was collected
  run: |
    python -c "
    import xml.etree.ElementTree as ET
    assert ET.parse('coverage.xml').findall('.//class'), \
      'coverage.xml has no file entries — coverage collected no data'
    "

- name: Run mutation tests
  run: mutmut run
  continue-on-error: true   # mutmut exits non-zero when mutants survive

- name: Export mutation results
  run: mutmut junitxml > mutmut.xml   # run even if the step above failed

- name: Run TQA
  run: |
    tqa analyze \
      --coverage coverage.xml \
      --mutmut mutmut.xml \
      --format github > tqa-summary.md

- name: Comment on PR
  if: github.event_name == 'pull_request'
  run: |
    COMMENT_ID=$(gh api repos/${{ github.repository }}/issues/${{ github.event.number }}/comments \
      --jq '[.[] | select(.user.login == "github-actions[bot]" and (.body | startswith("## TQA Report Summary"))) | .id] | last // empty')
    if [ -n "$COMMENT_ID" ]; then
      gh api repos/${{ github.repository }}/issues/comments/"$COMMENT_ID" \
        -X PATCH -f body="$(cat tqa-summary.md)"
    else
      gh api repos/${{ github.repository }}/issues/${{ github.event.number }}/comments \
        -X POST -f body="$(cat tqa-summary.md)"
    fi
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

The comment step updates the existing TQA comment in place rather than appending a new one on every push.

### Multi-job example (JavaScript — tests and TQA in separate jobs)

When coverage and mutation reports are produced in one job and consumed in another, upload them as an artifact and locate them with `find` rather than hardcoding the download path:

```yaml
jobs:
  test:
    steps:
      - run: npx c8 --reporter=lcov node --test
      - run: npx stryker run
      - uses: actions/upload-artifact@v4
        with:
          name: reports
          path: |
            coverage/lcov.info
            reports/mutation/mutation.json

  tqa:
    needs: test
    permissions:
      pull-requests: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: reports
          path: reports
      - run: pip install tqa
      - run: |
          LCOV=$(find reports -name "lcov.info" | head -1)
          STRYKER=$(find reports -name "mutation.json" | head -1)
          tqa analyze \
            ${LCOV:+--lcov "$LCOV"} \
            ${STRYKER:+--stryker "$STRYKER"} \
            --format github > tqa-summary.md
      # ... comment step as above
```

Using `find` avoids depending on the exact directory structure that `download-artifact` produces.

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

**TSI status thresholds**

| Status | TSI | Meaning |
| :--- | :--- | :--- |
| Healthy | ≥ 80% | Tests catch most mutations — good signal |
| Weak | 50–79% | Tests run the code but miss many mutations |
| Blind | < 50% | Tests cover lines but verify almost nothing |

### GitHub (`--format github`)

Produces a Markdown report suitable for a PR comment or a GitHub Actions job summary, plus `::warning` annotations for lines with 100% coverage but 0% mutants killed.

The report structure is:
- **Headline metric** (Total Project Test Strength) at the top
- Per-file breakdown in a collapsible `<details>` block
- Status column uses emoji: ✅ Healthy / 🟡 Weak / 🔴 Blind
- Surviving mutants table with file, line, mutator details, and rule-based test suggestions
- Critical gaps table (if any) at the bottom

Suggestions are deterministic heuristics based on the mutator name and optional source-line context. They are meant to point at the missing test signal, not to guarantee a complete test case.

#### Writing to the job summary

Pipe the output to `$GITHUB_STEP_SUMMARY` to make the report visible in the Actions UI on every run, including pushes to `main` where there is no PR to comment on:

```yaml
- run: tqa analyze --config tqa.toml --format github > tqa-summary.md
- run: cat tqa-summary.md >> $GITHUB_STEP_SUMMARY
- name: Comment on PR
  if: github.event_name == 'pull_request'
  # ... comment step as below
```

The two outputs are independent — write to both, or either one alone.

## Development

```bash
pip install -e .[dev]   # editable install required for coverage to trace local source files
python -m pytest tests/
```

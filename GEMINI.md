# Security Guidelines for Gemini CLI

These rules are foundational mandates for working in this repository. Follow them without exception unless explicitly overridden.

## Dependencies

- Do not add new `pip` dependencies without a clear reason tied to an existing feature requirement.
- Audit dependencies for CVEs before inclusion (e.g., using `pip-audit`).
- Production environments must use audited lockfiles.

## Docker

- The Docker image must run as a non-root user (e.g., `USER appuser`).
- Do not copy `.env` files, secrets, or credential files into the Docker image.
- The `.dockerignore` must exclude `__pycache__`, `.git`, and any local config files.

## Git

- **NEVER commit directly to `main`.** Always create a feature branch for any changes.
- **Never force-push to `main`.**
- **Never commit secrets, tokens, or credentials** of any kind.
- The `.gitignore` must exclude `.env` and `*.local` files.
- Do not amend published commits on shared branches without user confirmation.

## What to do if uncertain

If an action could be destructive, irreversible, or exposes user data, **stop and ask the user for confirmation** before proceeding. The cost of pausing is always lower than the cost of a security incident.

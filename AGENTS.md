# Repository Guidelines

## Project Structure & Module Organization
The core specification lives in `docs/meta_prompting_protocol_spec.md`, with a
static landing page in `docs/index.html`. Python integration code sits in
`mpp_dspy/` (see `mpp_dspy/README.md` for usage). Tests live in `tests/`
organized by test type. Repo-level docs and configuration are in `README.md`,
`CONTRIBUTING.md`, `pyproject.toml`, and `requirements.txt`.

## Build, Test, and Development Commands
- `python -m pip install -r requirements.txt`: install runtime dependencies.
- `python -m pip install -r requirements-test.txt`: install test + formatting deps.
- `make format`: run Black and Ruff on `mpp_dspy/` and `tests/`.
- `make test`: run the pytest suite in `tests/`.

## Coding Style & Naming Conventions
Python formatting follows Black with a line length of 88 and target version
Python 3.9. Ruff enforces E/F/I checks, so keep imports sorted and unused
symbols removed. Use snake_case for modules/functions, PascalCase for classes,
and UPPER_SNAKE_CASE for constants.

## Testing Guidelines
Tests live under `tests/` with `unit/` and `integration/` folders plus shared
fixtures in `tests/fixtures/`. Follow the AAA pattern, use `test_methodname_*`
naming, and include a brief docstring describing the expected behavior in each
test.

## Commit & Pull Request Guidelines
Commit messages in history are short and imperative, often sentence case or
lower-case (for example: "simplify spec path", "Update version badge to v1.1.4").
Follow the branching guidance in `CONTRIBUTING.md` (for example,
`feature/amazing-idea`). Pull requests should include a clear description of
the change, rationale, and any linked issues; update the spec or examples when
behavioral details change.

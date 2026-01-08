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
- Python: 4-space indentation, type hints on public APIs, no wildcard imports.
- Naming: `snake_case` for functions/modules, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants.
- Keep code slim: avoid inline comments and verbose model metadata unless it reduces cognitive load or improves generated docs.
- Prefer structural pattern matching (`match`/destructuring, including Pydantic models) for parsing and branching when it clarifies intent and the target Python version allows it.
- Prefer explicit config over hidden defaults; validate at the boundary.
- Formatting: run Black (line length 88) and Ruff (E/F/I) on changed code.

## Testing Guidelines
- Use `pytest`; name files `test_*.py`.
- Unit tests must not call external services; mock LLM/HTTP requests.
- Keep fixtures in `tests/fixtures/` when shared across suites.

## Commit & Pull Request Guidelines
Commit messages in history are short and imperative, often sentence case or
lower-case (for example: "simplify spec path", "Update version badge to v1.1.4").
Follow the branching guidance in `CONTRIBUTING.md` (for example,
`feature/amazing-idea`). Pull requests should include a clear description of
the change, rationale, and any linked issues; update the spec or examples when
behavioral details change.

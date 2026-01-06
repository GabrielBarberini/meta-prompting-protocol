# Testing Guidelines

This project follows RocketPy's testing philosophy and conventions:
https://docs.rocketpy.org/en/latest/development/testing.html. Keep tests fast,
focused, and descriptive so contributors can understand intent at a glance.

## Philosophy and Structure
- Unit tests are the minimum requirement for new features.
- Prefer the AAA pattern: Arrange, Act, Assert.
- Use parameterization for multiple scenarios.
- Tests live under `tests/` with:
  - `tests/unit/` for method-level or tightly scoped behavior.
  - `tests/integration/` for cross-module behavior or I/O-heavy paths.
  - `tests/acceptance/` for user-facing, end-to-end validation (add if needed).
  - `tests/fixtures/` for shared fixtures.

## Naming Conventions
Test functions should follow one of these patterns:
- `test_methodname`
- `test_methodname_stateundertest`
- `test_methodname_expectedbehaviour`

Every test must include a docstring that explicitly states the expected
behavior or state being validated.

## Unit vs. Integration
- Unit tests are method-level and should stay small; sociable tests are allowed
  when dependencies are necessary to validate real behavior, but prefer mocks
  when feasible.
- Integration tests cover interactions across modules or external inputs,
  including file or network I/O, or broad API surfaces.

## Fixtures
Place shared fixtures in `tests/fixtures/` and expose them in
`tests/conftest.py`. Keep fixture modules specific (e.g., bundle fixtures).

## Running Tests
- `make test`

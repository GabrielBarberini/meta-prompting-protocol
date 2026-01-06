VENV_BIN ?= ./.venv/bin

ifneq (,$(wildcard $(VENV_BIN)/black))
BLACK := $(VENV_BIN)/black
else
BLACK := black
endif

ifneq (,$(wildcard $(VENV_BIN)/ruff))
RUFF := $(VENV_BIN)/ruff
else
RUFF := ruff
endif

ifneq (,$(wildcard $(VENV_BIN)/pytest))
PYTEST := $(VENV_BIN)/pytest
else
PYTEST := pytest
endif

format: black ruff

black:
	$(BLACK) ./mpp_dspy || true
	$(BLACK) ./tests || true

ruff:
	$(RUFF) check --fix ./mpp_dspy || true
	$(RUFF) check --fix ./tests || true

test:
	$(PYTEST) ./tests

.PHONY: black ruff format test

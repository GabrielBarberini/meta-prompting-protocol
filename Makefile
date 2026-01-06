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

format: black ruff

black:
	$(BLACK) ./mpp_dspy || true
	$(BLACK) ./scripts || true

ruff:
	$(RUFF) check --fix ./mpp_dspy || true
	$(RUFF) check --fix ./scripts || true

.PHONY: black ruff format

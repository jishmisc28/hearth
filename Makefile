.PHONY: check test contract bench report format install

VENV ?= .venv
PYTHON ?= $(VENV)/bin/python
RUFF ?= $(VENV)/bin/ruff
MYPY ?= $(VENV)/bin/mypy
PYTEST ?= $(VENV)/bin/pytest

install:
	uv pip install -e ".[dev]"

format:
	$(RUFF) format src tests bench
	$(RUFF) check --fix src tests bench

check:
	$(RUFF) check src tests bench
	$(RUFF) format --check src tests bench
	$(MYPY) --strict src/hearth
	$(PYTEST) -m "not contract" tests/

test:
	$(PYTEST) tests/

contract:
	$(PYTEST) -m contract tests/

bench:
	$(PYTHON) -m hearth.bench.runner

report:
	$(PYTHON) -m hearth.bench.report

PYTHON ?= .venv/bin/python

.PHONY: install test evals

install:
	python3 -m venv .venv
	$(PYTHON) -m pip install -r requirements-dev.txt

test:
	$(PYTHON) -m pytest -m "not live and not evals"

evals:
	$(PYTHON) -m pytest -m evals harness/evals

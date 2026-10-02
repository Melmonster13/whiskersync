PYTHON ?= .venv/bin/python

.PHONY: install test evals airline agent talk chat

install:
	python3 -m venv .venv
	$(PYTHON) -m pip install -r requirements-dev.txt

test:
	$(PYTHON) -m pytest -m "not live and not evals"

evals:
	$(PYTHON) -m pytest -m evals harness/evals

# Mock airline API on http://127.0.0.1:8000
airline:
	$(PYTHON) -m uvicorn sandbox.mock_airline.app:create_default_app --factory

# Create or update the ElevenLabs agent (live API call)
agent:
	$(PYTHON) -m modules.m4_agent.provision

# Voice session (needs pyaudio) / text-only session; run `make airline` first
talk:
	$(PYTHON) -m modules.m4_agent.session

chat:
	$(PYTHON) -m modules.m4_agent.session --text

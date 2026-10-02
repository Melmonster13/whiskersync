PYTHON ?= .venv/bin/python

.PHONY: install test evals latency airline agent talk chat

install:
	python3 -m venv .venv
	$(PYTHON) -m pip install -r requirements-dev.txt

test:
	$(PYTHON) -m pytest -m "not live and not evals"

# Live agent evals (cost credits); report in harness/evals/results/
# Run a subset: make evals ONLY=out_of_scope,different_route
evals:
	EVAL_SCENARIOS="$(ONLY)" $(PYTHON) -m pytest -m evals -s harness/evals

# Latency p50/p95 for existing conversations: make latency IDS="conv_1 conv_2"
latency:
	$(PYTHON) -m harness.evals.runner $(IDS)

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

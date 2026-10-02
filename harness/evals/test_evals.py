"""Live agent evals. Cost credits; run with `make evals`, never in CI."""

import os

import pytest
from dotenv import load_dotenv

from harness.evals.runner import CostGuardError, check_low_cost_tts, new_results_dir, run_scenario, write_report
from harness.evals.scenarios import SCENARIOS

pytestmark = pytest.mark.evals


@pytest.fixture(scope="module")
def eval_results():
    load_dotenv()
    api_key, agent_id = os.environ.get("ELEVENLABS_API_KEY"), os.environ.get("ELEVENLABS_AGENT_ID")
    if not (api_key and agent_id):
        pytest.skip("ELEVENLABS_API_KEY and ELEVENLABS_AGENT_ID required")
    from elevenlabs import ElevenLabs

    client = ElevenLabs(api_key=api_key)
    try:
        model = check_low_cost_tts(client, agent_id)
    except CostGuardError as e:
        pytest.fail(f"cost guard: {e}", pytrace=False)
    print(f"\nagent TTS model: {model}")
    out_dir = new_results_dir()
    results = {s.name: run_scenario(client, agent_id, s, out_dir) for s in SCENARIOS}
    print("\n" + write_report(list(results.values()), out_dir))
    print(f"\nresults: {out_dir}")
    return results


@pytest.mark.parametrize("name", [s.name for s in SCENARIOS])
def test_scenario(eval_results, name):
    result = eval_results[name]
    assert result.passed, "\n".join(result.failures)

import typing
from types import SimpleNamespace

import pytest
from elevenlabs.types import AgentPlatformSettingsRequestModel, ConversationalConfig
from elevenlabs.types.tts_conversational_model import TtsConversationalModel

from modules.m4_agent.agent import TOOL_PARAMS
from modules.m4_agent.config import (
    AGENT_NAME,
    EVALUATION_CRITERIA,
    LOW_COST_TTS_MODELS,
    PARAM_DESCRIPTIONS,
    SYSTEM_PROMPT,
    TTS_MODEL,
    build_conversation_config,
    build_platform_settings,
)
from modules.m4_agent.provision import provision


def test_config_parses_with_sdk_models():
    config = ConversationalConfig.model_validate(build_conversation_config("voice_stock_1"))
    assert config.tts.voice_id == "voice_stock_1"
    tools = config.agent.prompt.tools
    assert [t.name for t in tools] == list(TOOL_PARAMS)
    for tool in tools:
        assert tool.type == "client"
        assert tool.expects_response is True
        assert set(tool.parameters.required) == set(TOOL_PARAMS[tool.name])
        assert set(tool.parameters.properties) == set(TOOL_PARAMS[tool.name])


def test_tts_uses_low_cost_model_without_expressive_tags():
    tts = ConversationalConfig.model_validate(build_conversation_config("voice_stock_1")).tts
    assert tts.model_id == TTS_MODEL
    assert tts.model_id in LOW_COST_TTS_MODELS
    assert tts.expressive_mode is False


def test_low_cost_models_are_known_to_the_sdk():
    sdk_models = set(typing.get_args(typing.get_args(TtsConversationalModel)[0]))
    assert LOW_COST_TTS_MODELS <= sdk_models


def test_platform_settings_parse_with_sdk_models():
    settings = AgentPlatformSettingsRequestModel.model_validate(build_platform_settings())
    criteria = settings.evaluation.criteria
    assert [c.id for c in criteria] == list(EVALUATION_CRITERIA)
    assert all(c.conversation_goal_prompt == EVALUATION_CRITERIA[c.id] for c in criteria)


def test_param_descriptions_match_tool_params():
    used = {p for params in TOOL_PARAMS.values() for p in params}
    assert set(PARAM_DESCRIPTIONS) == used


def test_prompt_mentions_every_tool():
    for name in TOOL_PARAMS:
        assert name in SYSTEM_PROMPT


class FakeAgents:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(("create", None, kwargs))
        return SimpleNamespace(agent_id="agent_new")

    def update(self, agent_id, **kwargs):
        self.calls.append(("update", agent_id, kwargs))


def fake_client(category):
    return SimpleNamespace(
        voices=SimpleNamespace(get=lambda voice_id: SimpleNamespace(category=category)),
        conversational_ai=SimpleNamespace(agents=FakeAgents()),
    )


def test_provision_creates_agent():
    client = fake_client("premade")
    assert provision(client, "voice_stock_1") == "agent_new"
    [(op, _, kwargs)] = client.conversational_ai.agents.calls
    assert op == "create"
    assert kwargs["name"] == AGENT_NAME
    assert isinstance(kwargs["conversation_config"], ConversationalConfig)
    assert isinstance(kwargs["platform_settings"], AgentPlatformSettingsRequestModel)


def test_provision_updates_existing_agent():
    client = fake_client("premade")
    assert provision(client, "voice_stock_1", agent_id="agent_42") == "agent_42"
    [(op, agent_id, _)] = client.conversational_ai.agents.calls
    assert (op, agent_id) == ("update", "agent_42")


@pytest.mark.parametrize("category", ["cloned", "professional", "generated", "famous", None])
def test_provision_refuses_non_stock_voice(category):
    client = fake_client(category)
    with pytest.raises(ValueError):
        provision(client, "voice_x")
    assert client.conversational_ai.agents.calls == []

"""Create or update the ElevenLabs agent from config.py. Live API calls; never run in CI.

    python -m modules.m4_agent.provision
"""

import os

from dotenv import load_dotenv
from elevenlabs import ElevenLabs
from elevenlabs.types import ConversationalConfig

from modules.m4_agent.config import AGENT_NAME, build_conversation_config

STOCK_VOICE_CATEGORY = "premade"


def check_stock_voice(client, voice_id: str) -> None:
    voice = client.voices.get(voice_id)
    if voice.category != STOCK_VOICE_CATEGORY:
        raise ValueError(
            f"voice {voice_id} is '{voice.category}', not a stock voice; refusing to use it"
        )


def provision(client, voice_id: str, agent_id: str | None = None) -> str:
    check_stock_voice(client, voice_id)
    config = ConversationalConfig.model_validate(build_conversation_config(voice_id))
    if agent_id:
        client.conversational_ai.agents.update(agent_id, conversation_config=config, name=AGENT_NAME)
        return agent_id
    return client.conversational_ai.agents.create(conversation_config=config, name=AGENT_NAME).agent_id


def main() -> None:
    load_dotenv()
    client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
    existing = os.environ.get("ELEVENLABS_AGENT_ID") or None
    agent_id = provision(client, os.environ["ELEVENLABS_VOICE_ID"], existing)
    if existing:
        print(f"Updated agent {agent_id}")
    else:
        print(f"Created agent {agent_id}. Set ELEVENLABS_AGENT_ID={agent_id} in .env")


if __name__ == "__main__":
    main()

"""Run a live conversation with the agent; tool calls execute locally against the airline.

    python -m modules.m4_agent.session          # voice (needs pyaudio)
    python -m modules.m4_agent.session --text   # text only
"""

import asyncio
import json
import os
import sys
import uuid

import httpx
from dotenv import load_dotenv
from elevenlabs import ElevenLabs
from elevenlabs.conversational_ai.conversation import ClientTools, Conversation

from modules.m4_agent.agent import TOOL_PARAMS, handle_tool_call
from modules.m4_agent.audit import AuditLog
from modules.m4_agent.tools import AirlineTools, dry_run_from_env

SDK_INJECTED_PARAMS = {"tool_call_id"}


class ToolBridge:
    """Registers every agent tool with the SDK's ClientTools and routes calls to the dispatcher.

    The SDK runs handlers on its own event loop thread; the airline client is only used there.
    """

    def __init__(self, tools: AirlineTools, audit: AuditLog, session_id: str):
        self.tools = tools
        self.audit = audit
        self.session_id = session_id
        self._loop: asyncio.AbstractEventLoop | None = None

    def register(self, client_tools: ClientTools) -> None:
        for name in TOOL_PARAMS:
            client_tools.register(name, self._handler(name), is_async=True)

    def _handler(self, name: str):
        async def handle(parameters: dict) -> str:
            return await self.call(name, parameters)
        return handle

    async def call(self, name: str, parameters: dict) -> str:
        self._loop = asyncio.get_running_loop()
        params = {k: v for k, v in parameters.items() if k not in SDK_INJECTED_PARAMS}
        resp = await handle_tool_call(self.tools, self.audit, name, params, self.session_id)
        return json.dumps(resp)

    def close(self, client: httpx.AsyncClient) -> None:
        if self._loop is not None and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(client.aclose(), self._loop).result(timeout=5)


def _audio_interface():
    try:
        from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
        return DefaultAudioInterface()
    except ImportError:
        sys.exit("Voice mode needs pyaudio: pip install 'elevenlabs[pyaudio]'. Or use --text.")


def main() -> None:
    load_dotenv()
    text_mode = "--text" in sys.argv
    session_id = f"local-{uuid.uuid4().hex[:12]}"
    audit = AuditLog(os.environ.get("AUDIT_LOG_PATH", "logs/audit.jsonl"))
    airline = httpx.AsyncClient(
        base_url=os.environ.get("MOCK_AIRLINE_URL", "http://127.0.0.1:8000"), timeout=5
    )
    tools = AirlineTools(airline, dry_run=dry_run_from_env())
    bridge = ToolBridge(tools, audit, session_id)
    client_tools = ClientTools()
    bridge.register(client_tools)

    conversation = Conversation(
        ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"]),
        os.environ["ELEVENLABS_AGENT_ID"],
        requires_auth=True,
        audio_interface=None if text_mode else _audio_interface(),
        client_tools=client_tools,
        callback_agent_response=lambda text: print(f"Agent: {text}"),
        callback_user_transcript=lambda text: print(f"You: {text}"),
    )
    print(f"Session {session_id} (dry_run={tools.dry_run}). Ctrl-C or 'quit' to end.")
    conversation.start_session()
    try:
        if text_mode:
            while (line := input()).strip().lower() != "quit":
                conversation.send_user_message(line)
        else:
            conversation.wait_for_session_end()
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        bridge.close(airline)   # before end_session, which stops the tools event loop
        conversation.end_session()
        conversation_id = conversation.wait_for_session_end()
        audit.record(
            conversation_id=session_id,
            tool="session_end",
            args={"elevenlabs_conversation_id": conversation_id},
            outcome="ok",
            dry_run=tools.dry_run,
        )
        print(f"Ended. ElevenLabs conversation id: {conversation_id}")


if __name__ == "__main__":
    main()

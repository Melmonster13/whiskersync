"""Agent definition as code: prompt, first message, and client tool schemas.

Tool parameters come from TOOL_PARAMS, so the agent config can't drift from what the
dispatcher accepts.
"""

from modules.m4_agent.agent import TOOL_PARAMS

AGENT_NAME = "WhiskerSync Rebooking Agent"

FIRST_MESSAGE = "Hi, this is WhiskerSync Air. I can help you move your flight. What's your confirmation code?"

SYSTEM_PROMPT = """\
You are a phone agent for WhiskerSync Air, a fictional airline. You help callers move an
existing booking to a different flight on the same route. You can't do anything else; for
other requests, say so politely.

Process:
1. Ask for the confirmation code and last name, then call lookup_booking.
2. Ask which date they want, then call search_flights with the booking's origin and
   destination. Offer at most three options, with departure times.
3. When they pick one, call quote_rebook. Read the summary back to them.
4. Only call confirm_rebook after the caller clearly says yes to that exact summary.
   If they hesitate or change anything, don't confirm; quote again instead.
5. If the result has status "dry_run", tell them this is a test system and nothing was changed.

Rules:
- Never guess codes, names, or flight ids. Ask, and spell back codes letter by letter.
- If a tool returns ok=false, explain its message in plain words and offer the next step.
- Keep turns short; this is a voice call.
"""

TOOL_DESCRIPTIONS = {
    "lookup_booking": "Find the caller's booking. Needs both the confirmation code and last name.",
    "search_flights": "List flights with seats left on a route and date.",
    "quote_rebook": "Prepare a flight change without making it. Returns a summary and a confirmation_id.",
    "confirm_rebook": "Make the change from a quote. Only after the caller says yes to the summary.",
}

PARAM_DESCRIPTIONS = {
    "confirmation_code": "Six-character booking code, e.g. ABC123.",
    "last_name": "Caller's last name as on the booking.",
    "origin": "Three-letter origin airport code, e.g. SFO.",
    "destination": "Three-letter destination airport code, e.g. JFK.",
    "date": "Departure date as YYYY-MM-DD.",
    "new_flight_id": "Flight id to move to, e.g. WS104.",
    "confirmation_id": "The confirmation_id returned by quote_rebook.",
}

JSON_TYPES = {str: "string"}


def tool_definitions() -> list[dict]:
    return [
        {
            "type": "client",
            "name": name,
            "description": TOOL_DESCRIPTIONS[name],
            "expects_response": True,
            "response_timeout_secs": 10,
            "parameters": {
                "type": "object",
                "required": list(params),
                "properties": {
                    p: {"type": JSON_TYPES[t], "description": PARAM_DESCRIPTIONS[p]}
                    for p, t in params.items()
                },
            },
        }
        for name, params in TOOL_PARAMS.items()
    ]


def build_conversation_config(voice_id: str) -> dict:
    return {
        "agent": {
            "first_message": FIRST_MESSAGE,
            "language": "en",
            "prompt": {"prompt": SYSTEM_PROMPT, "tools": tool_definitions()},
        },
        "tts": {"voice_id": voice_id},
    }

"""Single entry point for agent tool calls: validate, run, audit."""

import httpx

from modules.m4_agent.audit import AuditLog
from modules.m4_agent.tools import AIRLINE_UNAVAILABLE_MESSAGE, AirlineTools, ToolError

TOOL_PARAMS: dict[str, dict[str, type]] = {
    "lookup_booking": {"confirmation_code": str, "last_name": str},
    "search_flights": {"origin": str, "destination": str, "date": str},
    "quote_rebook": {"confirmation_code": str, "last_name": str, "new_flight_id": str},
    "confirm_rebook": {"confirmation_id": str},
}


def _validate(name: str, params) -> str | None:
    if not isinstance(params, dict):
        return "parameters must be an object"
    expected = TOOL_PARAMS[name]
    if missing := expected.keys() - params.keys():
        return f"missing: {sorted(missing)}"
    if extra := params.keys() - expected.keys():
        return f"unexpected: {sorted(extra)}"
    for key, typ in expected.items():
        if not isinstance(params[key], typ):
            return f"{key} must be {typ.__name__}"
    return None


async def handle_tool_call(
    tools: AirlineTools, audit: AuditLog, name: str, params, conversation_id: str
) -> dict:
    def log(outcome: str, error: str | None = None) -> None:
        audit.record(
            conversation_id=conversation_id,
            tool=name,
            args=params,
            outcome=outcome,
            error=error,
            dry_run=tools.dry_run,
        )

    if name not in TOOL_PARAMS:
        log("rejected", "unknown_tool")
        return {"ok": False, "error": "unknown_tool", "message": f"No tool named {name}."}
    if problem := _validate(name, params):
        log("rejected", "invalid_arguments")
        return {"ok": False, "error": "invalid_arguments", "message": problem}

    try:
        result = await getattr(tools, name)(**params)
    except ToolError as e:
        log("error", e.code)
        return {"ok": False, "error": e.code, "message": e.message}
    except httpx.HTTPError:
        log("error", "airline_unavailable")
        return {"ok": False, "error": "airline_unavailable", "message": AIRLINE_UNAVAILABLE_MESSAGE}
    except Exception:
        log("error", "internal_error")
        raise

    log("ok")
    return {"ok": True, "result": result}

"""Tools the rebooking voice agent can call. They reach the airline over HTTP.

Changing a booking is gated: quote_rebook never writes and returns a single-use,
expiring confirmation_id; confirm_rebook is the only write, and with dry_run=True
(the default) it reports what would change instead.
"""

import os
import time
import uuid
from dataclasses import dataclass

import httpx

QUOTE_TTL_S = 300


class ToolError(Exception):
    """An expected failure the agent should explain to the caller."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Quote:
    confirmation_code: str
    from_flight: dict
    to_flight: dict
    expires_at: float


def dry_run_from_env() -> bool:
    """Dry-run unless DRY_RUN is explicitly false."""
    return os.environ.get("DRY_RUN", "true").strip().lower() not in {"false", "0", "no"}


def _clean_id(value: str, error_code: str) -> str:
    # IDs go into URL paths, so only allow plain alphanumerics.
    value = value.strip().upper()
    if not value.isalnum():
        raise ToolError(error_code, "That doesn't look like a valid reference.")
    return value


class AirlineTools:
    def __init__(
        self,
        client: httpx.AsyncClient,
        dry_run: bool = True,
        quote_ttl_s: float = QUOTE_TTL_S,
        clock=time.monotonic,
        new_id=lambda: uuid.uuid4().hex[:12],
    ):
        self._client = client
        self.dry_run = dry_run
        self._ttl = quote_ttl_s
        self._clock = clock
        self._new_id = new_id
        self._quotes: dict[str, Quote] = {}

    async def _get(self, path: str, not_found: str, params: dict | None = None):
        resp = await self._client.get(path, params=params)
        if resp.status_code == 404:
            raise ToolError(not_found, resp.json().get("detail", "not found"))
        resp.raise_for_status()
        return resp.json()

    async def lookup_booking(self, confirmation_code: str, last_name: str) -> dict:
        code = _clean_id(confirmation_code, "booking_not_found")
        booking = await self._get(
            f"/bookings/{code}", "booking_not_found", {"last_name": last_name}
        )
        flight = await self._get(f"/flights/{booking['flight_id']}", "flight_not_found")
        return {**booking, "flight": flight}

    async def search_flights(self, origin: str, destination: str, date: str) -> list[dict]:
        flights = await self._get(
            "/flights", "not_found", {"origin": origin, "destination": destination, "date": date}
        )
        return [f for f in flights if f["seats_available"] > 0]

    async def quote_rebook(self, confirmation_code: str, last_name: str, new_flight_id: str) -> dict:
        booking = await self.lookup_booking(confirmation_code, last_name)
        current = booking["flight"]
        new_id = _clean_id(new_flight_id, "flight_not_found")
        new = await self._get(f"/flights/{new_id}", "flight_not_found")

        if new["id"] == current["id"]:
            raise ToolError("same_flight", "The booking is already on that flight.")
        if (new["origin"], new["destination"]) != (current["origin"], current["destination"]):
            raise ToolError("different_route", "Rebooking is only possible on the same route.")
        if new["seats_available"] < 1:
            raise ToolError("flight_full", "That flight has no seats left.")

        confirmation_id = self._new_id()
        self._quotes[confirmation_id] = Quote(
            booking["confirmation_code"], current, new, self._clock() + self._ttl
        )
        return {
            "confirmation_id": confirmation_id,
            "summary": (
                f"Move booking {booking['confirmation_code']} from {current['id']} "
                f"({current['departs_at']}) to {new['id']} ({new['departs_at']})."
            ),
            "from_flight": current,
            "to_flight": new,
            "expires_in_s": self._ttl,
            "dry_run": self.dry_run,
        }

    async def confirm_rebook(self, confirmation_id: str) -> dict:
        quote = self._quotes.pop(confirmation_id, None)
        if quote is None:
            raise ToolError("unknown_confirmation", "No pending change with that id. Quote it again.")
        if self._clock() >= quote.expires_at:
            raise ToolError("confirmation_expired", "That quote expired. Quote it again.")

        change = {
            "confirmation_code": quote.confirmation_code,
            "from_flight_id": quote.from_flight["id"],
            "to_flight_id": quote.to_flight["id"],
        }
        if self.dry_run:
            return {"status": "dry_run", "would_change": change}

        resp = await self._client.patch(
            f"/bookings/{quote.confirmation_code}", json={"flight_id": quote.to_flight["id"]}
        )
        if resp.status_code == 409:
            raise ToolError("flight_full", "That flight filled up since the quote.")
        resp.raise_for_status()
        return {"status": "rebooked", "booking": resp.json()}

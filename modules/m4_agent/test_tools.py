import pytest

from modules.m4_agent.tools import QUOTE_TTL_S, ToolError

pytestmark = pytest.mark.asyncio


def booked_flight(conn, code):
    return conn.execute(
        "SELECT flight_id FROM bookings WHERE confirmation_code = ?", (code,)
    ).fetchone()[0]


def seats(conn, flight_id):
    return conn.execute("SELECT seats_available FROM flights WHERE id = ?", (flight_id,)).fetchone()[0]


async def test_lookup_booking(tools):
    booking = await tools.lookup_booking("abc123", "sample")
    assert booking["confirmation_code"] == "ABC123"
    assert booking["flight"]["id"] == "WS100"


@pytest.mark.parametrize(
    "code, last_name",
    [
        ("ABC123", "Wrong"),
        ("NOPE00", "Sample"),
        ("../flights/WS100", "Sample"),   # path injection rejected before any request
    ],
)
async def test_lookup_booking_not_found(tools, code, last_name):
    with pytest.raises(ToolError) as exc:
        await tools.lookup_booking(code, last_name)
    assert exc.value.code == "booking_not_found"


async def test_search_flights_hides_full_flights(tools):
    flights = await tools.search_flights("SFO", "JFK", "2026-11-02")
    assert [f["id"] for f in flights] == ["WS100", "WS104"]


async def test_search_flights_no_route(tools):
    assert await tools.search_flights("SFO", "LAX", "2026-11-02") == []


async def test_quote_does_not_write(tools, conn):
    quote = await tools.quote_rebook("ABC123", "Sample", "WS104")
    assert quote["confirmation_id"]
    assert quote["dry_run"] is True
    assert quote["to_flight"]["id"] == "WS104"
    assert booked_flight(conn, "ABC123") == "WS100"
    assert seats(conn, "WS104") == 5


@pytest.mark.parametrize(
    "code, last_name, new_flight, error",
    [
        ("ABC123", "Sample", "WS100", "same_flight"),
        ("ABC123", "Sample", "WS102", "flight_full"),
        ("ABC123", "Sample", "WS200", "different_route"),
        ("ABC123", "Sample", "WS999", "flight_not_found"),
        ("ABC123", "Sample", "../x", "flight_not_found"),
        ("ABC123", "Wrong", "WS104", "booking_not_found"),
    ],
)
async def test_quote_errors(tools, code, last_name, new_flight, error):
    with pytest.raises(ToolError) as exc:
        await tools.quote_rebook(code, last_name, new_flight)
    assert exc.value.code == error


async def test_confirm_dry_run_does_not_write(tools, conn):
    quote = await tools.quote_rebook("ABC123", "Sample", "WS104")
    result = await tools.confirm_rebook(quote["confirmation_id"])
    assert result == {
        "status": "dry_run",
        "would_change": {
            "confirmation_code": "ABC123",
            "from_flight_id": "WS100",
            "to_flight_id": "WS104",
        },
    }
    assert booked_flight(conn, "ABC123") == "WS100"
    assert seats(conn, "WS104") == 5


async def test_confirm_live_rebooks(live_tools, conn):
    quote = await live_tools.quote_rebook("ABC123", "Sample", "WS104")
    result = await live_tools.confirm_rebook(quote["confirmation_id"])
    assert result["status"] == "rebooked"
    assert result["booking"]["flight_id"] == "WS104"
    assert booked_flight(conn, "ABC123") == "WS104"
    assert seats(conn, "WS100") == 4
    assert seats(conn, "WS104") == 4


async def test_confirm_unknown_id(tools):
    with pytest.raises(ToolError) as exc:
        await tools.confirm_rebook("nope")
    assert exc.value.code == "unknown_confirmation"


async def test_confirm_is_single_use(live_tools, conn):
    quote = await live_tools.quote_rebook("ABC123", "Sample", "WS104")
    await live_tools.confirm_rebook(quote["confirmation_id"])
    with pytest.raises(ToolError) as exc:
        await live_tools.confirm_rebook(quote["confirmation_id"])
    assert exc.value.code == "unknown_confirmation"
    assert seats(conn, "WS104") == 4


@pytest.mark.parametrize("elapsed", [QUOTE_TTL_S, QUOTE_TTL_S + 1])
async def test_confirm_expired(live_tools, clock, conn, elapsed):
    quote = await live_tools.quote_rebook("ABC123", "Sample", "WS104")
    clock.now += elapsed
    with pytest.raises(ToolError) as exc:
        await live_tools.confirm_rebook(quote["confirmation_id"])
    assert exc.value.code == "confirmation_expired"
    assert booked_flight(conn, "ABC123") == "WS100"


async def test_confirm_flight_filled_after_quote(live_tools, conn):
    quote = await live_tools.quote_rebook("ABC123", "Sample", "WS106")
    conn.execute("UPDATE flights SET seats_available = 0 WHERE id = 'WS106'")
    with pytest.raises(ToolError) as exc:
        await live_tools.confirm_rebook(quote["confirmation_id"])
    assert exc.value.code == "flight_full"
    assert booked_flight(conn, "ABC123") == "WS100"

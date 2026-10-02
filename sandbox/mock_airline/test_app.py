import pytest
from fastapi.testclient import TestClient

from sandbox.mock_airline.app import create_app
from sandbox.mock_airline.db import connect, init_db


@pytest.fixture
def conn():
    conn = connect()
    init_db(conn)
    yield conn
    conn.close()


@pytest.fixture
def api(conn):
    return TestClient(create_app(conn))


def seats(conn, flight_id):
    return conn.execute("SELECT seats_available FROM flights WHERE id = ?", (flight_id,)).fetchone()[0]


def test_read_booking(api):
    resp = api.get("/bookings/abc123", params={"last_name": " sample "})
    assert resp.status_code == 200
    assert resp.json() == {
        "confirmation_code": "ABC123",
        "first_name": "Avery",
        "last_name": "Sample",
        "flight_id": "WS100",
    }


@pytest.mark.parametrize(
    "code, last_name",
    [
        ("ABC123", "Wrong"),     # wrong name looks the same as unknown code
        ("NOPE00", "Sample"),
    ],
)
def test_read_booking_not_found(api, code, last_name):
    resp = api.get(f"/bookings/{code}", params={"last_name": last_name})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "booking not found"


def test_search_flights_includes_full_flights_sorted(api):
    resp = api.get("/flights", params={"origin": "sfo", "destination": "jfk", "date": "2026-11-02"})
    assert [f["id"] for f in resp.json()] == ["WS100", "WS102", "WS104"]


def test_search_flights_no_match(api):
    resp = api.get("/flights", params={"origin": "SFO", "destination": "LAX", "date": "2026-11-02"})
    assert resp.json() == []


def test_read_flight_not_found(api):
    assert api.get("/flights/WS999").status_code == 404


def test_change_flight_moves_seat(api, conn):
    resp = api.patch("/bookings/ABC123", json={"flight_id": "WS104"})
    assert resp.status_code == 200
    assert resp.json()["flight_id"] == "WS104"
    assert seats(conn, "WS100") == 4
    assert seats(conn, "WS104") == 4


@pytest.mark.parametrize(
    "code, flight_id, status",
    [
        ("ABC123", "WS102", 409),   # full
        ("ABC123", "WS100", 400),   # already on it
        ("ABC123", "WS999", 404),   # unknown flight
        ("NOPE00", "WS104", 404),   # unknown booking
    ],
)
def test_change_flight_errors_leave_data_unchanged(api, conn, code, flight_id, status):
    resp = api.patch(f"/bookings/{code}", json={"flight_id": flight_id})
    assert resp.status_code == status
    assert seats(conn, "WS100") == 3
    assert seats(conn, "WS104") == 5
    assert api.get("/bookings/ABC123", params={"last_name": "Sample"}).json()["flight_id"] == "WS100"


def test_same_idempotency_key_applies_once(api, conn):
    headers = {"Idempotency-Key": "k1"}
    first = api.patch("/bookings/ABC123", json={"flight_id": "WS104"}, headers=headers)
    second = api.patch("/bookings/ABC123", json={"flight_id": "WS104"}, headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert seats(conn, "WS100") == 4          # moved once, not twice
    assert seats(conn, "WS104") == 4


def test_without_key_a_repeat_is_rejected(api):
    api.patch("/bookings/ABC123", json={"flight_id": "WS104"})
    assert api.patch("/bookings/ABC123", json={"flight_id": "WS104"}).status_code == 400


def test_key_reused_for_different_request_is_422(api, conn):
    api.patch("/bookings/ABC123", json={"flight_id": "WS104"}, headers={"Idempotency-Key": "k1"})
    resp = api.patch("/bookings/ABC123", json={"flight_id": "WS106"}, headers={"Idempotency-Key": "k1"})
    assert resp.status_code == 422
    assert seats(conn, "WS106") == 2


def test_failed_request_does_not_store_its_key(api, conn):
    headers = {"Idempotency-Key": "k1"}
    assert api.patch("/bookings/ABC123", json={"flight_id": "WS102"}, headers=headers).status_code == 409
    conn.execute("UPDATE flights SET seats_available = 1 WHERE id = 'WS102'")
    assert api.patch("/bookings/ABC123", json={"flight_id": "WS102"}, headers=headers).status_code == 200


def test_init_db_is_idempotent(conn):
    init_db(conn)
    assert conn.execute("SELECT COUNT(*) FROM flights").fetchone()[0] == 5

"""Mock airline API: the fake customer system the m4 agent integrates with.

Run locally:
    uvicorn sandbox.mock_airline.app:create_default_app --factory
"""

import os
import sqlite3

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from sandbox.mock_airline.db import connect, init_db


class Flight(BaseModel):
    id: str
    origin: str
    destination: str
    departs_at: str
    seats_available: int


class Booking(BaseModel):
    confirmation_code: str
    first_name: str
    last_name: str
    flight_id: str


class ChangeFlight(BaseModel):
    flight_id: str


def create_app(conn: sqlite3.Connection) -> FastAPI:
    # Endpoints are async so every SQLite call runs on the event loop thread.
    app = FastAPI(title="Mock Airline")

    def get_flight(flight_id: str) -> Flight:
        row = conn.execute("SELECT * FROM flights WHERE id = ?", (flight_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "flight not found")
        return Flight(**dict(row))

    def get_booking(code: str) -> Booking:
        row = conn.execute(
            "SELECT * FROM bookings WHERE confirmation_code = ?", (code.upper(),)
        ).fetchone()
        if row is None:
            raise HTTPException(404, "booking not found")
        return Booking(**dict(row))

    @app.get("/bookings/{code}")
    async def read_booking(code: str, last_name: str) -> Booking:
        booking = get_booking(code)
        # Same 404 as an unknown code, so a wrong name doesn't confirm the code exists.
        if booking.last_name.lower() != last_name.strip().lower():
            raise HTTPException(404, "booking not found")
        return booking

    @app.get("/flights")
    async def search_flights(origin: str, destination: str, date: str) -> list[Flight]:
        rows = conn.execute(
            "SELECT * FROM flights WHERE origin = ? AND destination = ? "
            "AND substr(departs_at, 1, 10) = ? ORDER BY departs_at",
            (origin.upper(), destination.upper(), date),
        ).fetchall()
        return [Flight(**dict(r)) for r in rows]

    @app.get("/flights/{flight_id}")
    async def read_flight(flight_id: str) -> Flight:
        return get_flight(flight_id)

    @app.patch("/bookings/{code}")
    async def change_flight(code: str, body: ChangeFlight) -> Booking:
        booking = get_booking(code)
        new = get_flight(body.flight_id)
        if new.id == booking.flight_id:
            raise HTTPException(400, "booking is already on this flight")
        if new.seats_available < 1:
            raise HTTPException(409, "flight is full")
        with conn:
            conn.execute(
                "UPDATE flights SET seats_available = seats_available - 1 WHERE id = ?", (new.id,)
            )
            conn.execute(
                "UPDATE flights SET seats_available = seats_available + 1 WHERE id = ?",
                (booking.flight_id,),
            )
            conn.execute(
                "UPDATE bookings SET flight_id = ? WHERE confirmation_code = ?",
                (new.id, booking.confirmation_code),
            )
        return get_booking(code)

    return app


def create_default_app() -> FastAPI:
    conn = connect(os.environ.get("MOCK_AIRLINE_DB_PATH", "sandbox/mock_airline/airline.db"))
    init_db(conn)
    return create_app(conn)

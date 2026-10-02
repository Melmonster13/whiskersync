import httpx
import pytest
import pytest_asyncio

from modules.m4_agent.tools import AirlineTools
from sandbox.mock_airline.app import create_app
from sandbox.mock_airline.db import connect, init_db


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


@pytest.fixture
def conn():
    conn = connect()
    init_db(conn)
    yield conn
    conn.close()


@pytest_asyncio.fixture
async def client(conn):
    transport = httpx.ASGITransport(app=create_app(conn))
    async with httpx.AsyncClient(transport=transport, base_url="http://airline") as c:
        yield c


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def tools(client, clock):
    return AirlineTools(client, dry_run=True, clock=clock)


@pytest.fixture
def live_tools(client, clock):
    return AirlineTools(client, dry_run=False, clock=clock)

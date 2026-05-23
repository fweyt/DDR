import httpx
import pytest

from src.server import app


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_signal_webhook_queues_message(client):
    payload = {
        "envelope": {
            "source": "+32456789012",
            "dataMessage": {
                "message": "Hallo, ik heb hoofdpijn."
            }
        }
    }
    resp = await client.post("/signal-webhook", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"


@pytest.mark.asyncio
async def test_signal_webhook_missing_data(client):
    resp = await client.post("/signal-webhook", json={})
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"


@pytest.mark.asyncio
async def test_signal_webhook_empty_message(client):
    payload = {"envelope": {"source": "+32456789012", "dataMessage": {}}}
    resp = await client.post("/signal-webhook", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"

import subprocess
import sys

import pytest


def test_paid_evaluation_requires_explicit_call_limit():
    result = subprocess.run(
        [sys.executable, "-m", "scripts.evaluate_mvp", "--mode", "llm", "--suite", "golden"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 2
    assert "requires --max-calls" in result.stderr


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_chat_empty_message(client):
    response = await client.post("/api/v1/chat", json={"message": ""})
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_agent_status(client):
    response = await client.get("/api/v1/status")
    assert response.status_code == 200

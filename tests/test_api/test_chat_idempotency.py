import hashlib
import json

import pytest

from src.main import app


@pytest.fixture
def stub_chat_answer(client, monkeypatch):
    calls = []

    async def answer(question, context="", scope=None):
        calls.append((question, context, scope))
        return {
            "response": f"Câu trả lời kiểm thử cho: {question}",
            "kind": "answered",
            "sources": [],
            "mode": "extractive",
            "tokens": 0,
        }

    monkeypatch.setattr(app.state.runtime["admissions"], "answer", answer)
    return calls


@pytest.mark.asyncio
async def test_chat_replay_is_idempotent_but_same_text_with_new_id_is_a_new_turn(client, stub_chat_answer):
    question = "Đăng ký xét tuyển đánh giá tư duy như thế nào?"

    first = await client.post(
        "/api/v1/chat", json={"message": question, "request_id": "normal-turn-001"}
    )
    intentional_repeat = await client.post(
        "/api/v1/chat", json={"message": question, "request_id": "repeat-turn-002"}
    )
    retry_first = await client.post(
        "/api/v1/chat", json={"message": question, "request_id": "retry-turn-003"}
    )
    retry_again = await client.post(
        "/api/v1/chat", json={"message": question, "request_id": "retry-turn-003"}
    )

    assert all(response.status_code == 200 for response in (first, intentional_repeat, retry_first, retry_again))
    assert retry_first.json() == retry_again.json()
    assert len(stub_chat_answer) == 3
    assert len({first.json()["message_ids"]["user"], intentional_repeat.json()["message_ids"]["user"], retry_first.json()["message_ids"]["user"]}) == 3
    feedback = await client.post(
        f"/api/v1/answers/{retry_first.json()['request_id']}/feedback", json={"rating": "helpful"}
    )
    assert feedback.status_code == 200
    assert (
        await client.post(
            "/api/v1/chat", json={"message": question, "request_id": "retry-turn-003"}
        )
    ).json()["feedback"] == "helpful"

    histories = [
        (await client.get("/api/v1/session")).json()["messages"]
        for _ in range(3)
    ]
    assert histories[0] == histories[1] == histories[2]
    assert len(histories[0]) == 6
    assert [message["role"] for message in histories[0]] == ["user", "assistant"] * 3
    assert [message["response"] for message in histories[0] if message["role"] == "user"] == [question] * 3
    assert len({message["id"] for message in histories[0]}) == 6
    assert {message["turn_id"] for message in histories[0]} == {
        "normal-turn-001",
        "repeat-turn-002",
        "retry-turn-003",
    }

    conflict = await client.post(
        "/api/v1/chat",
        json={"message": "Nội dung khác", "request_id": "retry-turn-003"},
    )
    assert conflict.status_code == 409
    assert len((await client.get("/api/v1/session")).json()["messages"]) == 6


@pytest.mark.asyncio
async def test_in_progress_retry_does_not_create_a_second_turn(client, monkeypatch):
    question = "Hỏi một câu duy nhất"
    request_id = "concurrent-turn-004"
    body = {"message": question, "program": None}
    request_hash = hashlib.sha256(
        json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    await client.get("/api/v1/session")
    store = app.state.runtime["store"]
    _, session = store.session(client.cookies.get("candidate"), 24)
    claim = store.claim_chat_request(session["id"], request_id, request_hash)
    assert claim["status"] == "claimed"

    calls = []

    async def answer(question, context="", scope=None):
        calls.append(question)
        return {
            "response": "Câu trả lời sau khi chờ",
            "kind": "answered",
            "sources": [],
            "mode": "extractive",
            "tokens": 0,
        }

    monkeypatch.setattr(app.state.runtime["admissions"], "answer", answer)
    body["request_id"] = request_id

    in_progress_retry = await client.post("/api/v1/chat", json=body)
    assert in_progress_retry.status_code == 409
    assert calls == []
    assert (await client.get("/api/v1/session")).json()["messages"] == []

    store.release_chat_request(session["id"], request_id, request_hash, claim["claim_token"])
    completed = await client.post("/api/v1/chat", json=body)

    assert completed.status_code == 200
    assert len(calls) == 1
    history = (await client.get("/api/v1/session")).json()["messages"]
    assert [message["role"] for message in history] == ["user", "assistant"]

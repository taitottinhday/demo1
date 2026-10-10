from pathlib import Path

import pytest

from src.config import Settings
from src.main import create_app, runtime_data_dirs
from src.services.store import Store


def test_runtime_dirs_keep_mutable_state_separate_from_knowledge(tmp_path):
    knowledge_dir = tmp_path / "bundled-sources"
    state_dir = tmp_path / "railway-volume"
    cfg = Settings(
        _env_file=None,
        app_env="test",
        mvp_data_dir=str(knowledge_dir),
        persistent_data_dir=str(state_dir),
    )

    resolved_knowledge, resolved_state = runtime_data_dirs(cfg)

    assert resolved_knowledge == knowledge_dir
    assert resolved_state == state_dir
    assert resolved_state != resolved_knowledge


def test_store_data_survives_a_new_store_instance(tmp_path):
    cfg = Settings(
        _env_file=None,
        app_env="test",
        mvp_data_dir=str(tmp_path / "sources"),
        persistent_data_dir=str(tmp_path / "state"),
    )
    _, state_dir = runtime_data_dirs(cfg)
    first_store = Store(state_dir / "mvp.db")
    session_token, session = first_store.session("candidate-session", 24)
    ticket = first_store.create_ticket(
        session["id"],
        "handover-1",
        "Học phí IT1",
        "Thiếu căn cứ",
        question="Học phí IT1 bao nhiêu?",
    )
    first_store.claim(ticket["id"], "canbo")

    restarted_store = Store(state_dir / "mvp.db")
    persisted = restarted_store.ticket(ticket["id"])

    assert session_token
    assert persisted["id"] == ticket["id"]
    assert persisted["status"] == "in_progress"
    assert persisted["owner"] == "canbo"


def test_chat_request_replay_survives_restart_and_clear_removes_its_cache(tmp_path):
    path = tmp_path / "chat-idempotency.db"
    store = Store(path)
    _, session = store.session("chat-session", 24)
    request_id = "persisted-turn-001"
    request_hash = "a" * 64
    claim = store.claim_chat_request(session["id"], request_id, request_hash)
    assert claim["status"] == "claimed"
    answer = {
        "response": "Fixture answer",
        "kind": "answered",
        "sources": [],
        "mode": "extractive",
        "tokens": 0,
        "request_id": "feedback-001",
    }

    first = store.complete_chat_request(
        session["id"], request_id, request_hash, claim["claim_token"], "Fixture question", answer
    )
    restarted = Store(path)
    replay = restarted.claim_chat_request(session["id"], request_id, request_hash)

    assert first["status"] == replay["status"] == "completed"
    assert replay["response"] == first["response"]
    assert len(restarted.messages(session["id"])) == 2
    assert len({message["id"] for message in restarted.messages(session["id"])}) == 2

    restarted.clear(session["id"])
    assert restarted.messages(session["id"]) == []
    assert restarted.claim_chat_request(session["id"], request_id, request_hash)["status"] == "claimed"


def test_production_requires_a_persistent_data_dir(tmp_path):
    cfg = Settings(
        _env_file=None,
        app_env="production",
        mvp_data_dir=str(tmp_path / "sources"),
        persistent_data_dir="",
    )

    with pytest.raises(ValueError, match="PERSISTENT_DATA_DIR"):
        runtime_data_dirs(cfg)


def test_production_does_not_allow_volume_to_hide_sources(tmp_path):
    source_dir = Path(tmp_path / "sources")
    cfg = Settings(
        _env_file=None,
        app_env="production",
        mvp_data_dir=str(source_dir),
        persistent_data_dir=str(source_dir),
    )

    with pytest.raises(ValueError, match="khác MVP_DATA_DIR"):
        runtime_data_dirs(cfg)


@pytest.mark.asyncio
async def test_app_opens_store_on_persistent_dir_and_knowledge_on_source_dir(tmp_path):
    state_dir = tmp_path / "state"
    source_dir = Path("data").resolve()
    cfg = Settings(
        _env_file=None,
        app_env="test",
        answer_mode="extractive",
        mvp_data_dir=str(source_dir),
        persistent_data_dir=str(state_dir),
    )
    instance = create_app(cfg)

    async with instance.router.lifespan_context(instance):
        assert instance.state.runtime["store"].path == state_dir / "mvp.db"
        assert instance.state.runtime["knowledge"].root == source_dir

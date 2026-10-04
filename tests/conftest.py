from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.config import Settings
from src.main import app
from src.services.admissions import Admissions
from src.services.knowledge import Knowledge
from src.services.store import Store


@pytest.fixture(scope="session")
def knowledge():
    k = Knowledge("data")
    k.ingest()
    return k


@pytest_asyncio.fixture
async def client(tmp_path, knowledge):
    """Async HTTP client for testing API endpoints."""
    cfg = Settings(_env_file=None, answer_mode="extractive", app_env="test")
    store = Store(tmp_path / "test.db")
    app.state.runtime = {
        "settings": cfg,
        "store": store,
        "knowledge": knowledge,
        "admissions": Admissions(knowledge, store, cfg),
        "source_error": None,
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_llm():
    """Mock LLM to avoid calling OpenAI during tests.

    Usage in test:
        def test_something(mock_llm):
            # LLM calls will return mock response instead of hitting OpenAI
            ...
    """
    mock = AsyncMock()
    mock.ainvoke.return_value = AsyncMock(content="Mocked LLM response")
    return mock

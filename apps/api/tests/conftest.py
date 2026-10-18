"""Shared fixtures. Pytest talks to the Compose FalkorDB, not a graph mock."""

from __future__ import annotations

import os

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("FALKORDB_HOST", "127.0.0.1")
os.environ.setdefault("FALKORDB_PORT", "6379")
os.environ.setdefault("FALKORDB_PASSWORD", "faultline-dev-password")
os.environ.setdefault("AUTH_KEYS", "dev-key:tenant-synthetic,other-key:tenant-other")
os.environ["OPENAI_API_KEY"] = ""

import pytest
from fastapi.testclient import TestClient

from faultline.config import get_settings
from faultline.graph.client import GraphStore
from faultline.graph.reset import reset_known_tenants
from faultline.graph.seed import seed_atlas
from faultline.llm.fake import FakeExtractor
from faultline.main import create_app

get_settings.cache_clear()

AUTH_A = {"Authorization": "Bearer dev-key"}
AUTH_B = {"Authorization": "Bearer other-key"}


@pytest.fixture(scope="session")
def settings():
    get_settings.cache_clear()
    loaded = get_settings()
    store = GraphStore(loaded)
    try:
        store.ping()
    except Exception as exc:
        pytest.exit(f"FalkorDB is not reachable ({exc}). Start it with make up.", returncode=1)
    return loaded


@pytest.fixture()
def store(settings):
    return GraphStore(settings)


@pytest.fixture(autouse=True)
def _clean_graphs(store, settings):
    reset_known_tenants(store, settings)
    yield


@pytest.fixture()
def client(settings, store):
    application = create_app(settings, store, FakeExtractor())
    with TestClient(application) as test_client:
        yield test_client


@pytest.fixture()
def seeded(settings, store):
    seed_atlas(settings, store)
    return store

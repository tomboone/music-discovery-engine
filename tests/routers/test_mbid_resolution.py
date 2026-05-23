import uuid
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.app import Base
from app.routers.mbid_resolution import create_mbid_resolution_router

SEED_USER_ID = uuid.UUID("d4e5f6a7-b8c9-4d0e-a1f2-b3c4d5e6f7a8")


def _make_app_and_mocks():
    app_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(app_engine)
    mb_engine = create_engine("sqlite:///:memory:")

    def _get_app_session():
        with Session(app_engine) as s:
            yield s

    def _get_mb_session():
        with Session(mb_engine) as s:
            yield s

    mock_service = MagicMock()
    app = FastAPI()
    app.include_router(
        create_mbid_resolution_router(
            mock_service,
            SEED_USER_ID,
            get_app_session=_get_app_session,
            get_mb_session=_get_mb_session,
        )
    )
    return TestClient(app), mock_service


def test_run_endpoint_returns_summary():
    client, service = _make_app_and_mocks()
    service.run.return_value = {
        "attempted": 152,
        "resolved": 131,
        "unmatched": 21,
        "run_at": "2026-04-18T22:30:00+00:00",
    }
    r = client.post("/mbid-resolution/run")
    assert r.status_code == 200
    assert r.json() == {
        "attempted": 152,
        "resolved": 131,
        "unmatched": 21,
        "run_at": "2026-04-18T22:30:00+00:00",
    }


def test_run_endpoint_passes_seed_user_id_to_service():
    client, service = _make_app_and_mocks()
    service.run.return_value = {
        "attempted": 0,
        "resolved": 0,
        "unmatched": 0,
        "run_at": "2026-04-18T00:00:00+00:00",
    }
    client.post("/mbid-resolution/run")
    call_args = service.run.call_args
    assert call_args.args[2] == SEED_USER_ID


def test_run_endpoint_zero_attempted_returns_200():
    client, service = _make_app_and_mocks()
    service.run.return_value = {
        "attempted": 0,
        "resolved": 0,
        "unmatched": 0,
        "run_at": "2026-04-18T00:00:00+00:00",
    }
    r = client.post("/mbid-resolution/run")
    assert r.status_code == 200
    assert r.json()["attempted"] == 0

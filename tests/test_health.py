from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from main import app


def test_health_returns_ok():
    with (
        patch("main.create_app_db"),
        patch("main.reflect_mb_tables"),
        patch("main.get_app_engine") as mock_app_engine,
        patch("main.get_mb_engine") as mock_mb_engine,
    ):
        mock_app_conn = MagicMock()
        mock_mb_conn = MagicMock()
        mock_app_engine.return_value.connect.return_value.__enter__ = MagicMock(
            return_value=mock_app_conn
        )
        mock_app_engine.return_value.connect.return_value.__exit__ = MagicMock(
            return_value=False
        )
        mock_mb_engine.return_value.connect.return_value.__enter__ = MagicMock(
            return_value=mock_mb_conn
        )
        mock_mb_engine.return_value.connect.return_value.__exit__ = MagicMock(
            return_value=False
        )
        mock_app_conn.execute.return_value.scalar.return_value = 1
        mock_mb_conn.execute.return_value.scalar.return_value = 1

        with TestClient(app) as client:
            response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "databases" in data
        assert data["databases"]["app"] == "ok"
        assert data["databases"]["musicbrainz"] == "ok"

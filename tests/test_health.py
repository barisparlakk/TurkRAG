import asyncio
from unittest.mock import MagicMock, patch

from api.routers.health import _check_postgres, _check_qdrant, health_check


def test_qdrant_check_closes_client():
    client = MagicMock()

    with patch("qdrant_client.QdrantClient", return_value=client):
        assert _check_qdrant() == "ok"

    client.get_collections.assert_called_once_with()
    client.close.assert_called_once_with()


def test_qdrant_check_reports_failure_and_closes_client():
    client = MagicMock()
    client.get_collections.side_effect = RuntimeError("qdrant unavailable")

    with patch("qdrant_client.QdrantClient", return_value=client):
        status = _check_qdrant()

    assert status == "error"
    client.close.assert_called_once_with()


def test_postgres_check_closes_connection():
    conn = MagicMock()

    with patch("psycopg2.connect", return_value=conn):
        assert _check_postgres() == "ok"

    conn.close.assert_called_once_with()


def test_health_response_is_degraded_when_dependency_fails():
    with (
        patch("api.routers.health._check_qdrant", return_value="error"),
        patch("api.routers.health._check_postgres", return_value="ok"),
        patch("generation.llm.is_available", return_value=False),
    ):
        response = asyncio.run(health_check())

    assert response.status == "degraded"
    assert response.qdrant == "error"
    assert response.postgres == "ok"
    assert response.llm_available is False
    assert response.details == {}

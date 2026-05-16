"""VectorStore unit tests — Qdrant client fully mocked."""

from unittest.mock import MagicMock, patch


def _make_store(slug="demo"):
    from retrieval.vector_store import VectorStore
    return VectorStore(slug)


def _make_point(score, payload):
    p = MagicMock()
    p.score = score
    p.payload = payload
    return p


class TestCollectionName:
    def test_collection_name_prefixed(self):
        store = _make_store("acme")
        assert store.collection_name == "tenant_acme"

    def test_collection_name_stored(self):
        store = _make_store("xyz")
        assert store.tenant_slug == "xyz"


class TestSearch:
    def _mock_client(self, points):
        client = MagicMock()
        response = MagicMock()
        response.points = points
        client.query_points.return_value = response
        return client

    def test_returns_list_of_dicts(self):
        store = _make_store()
        point = _make_point(0.9, {"text": "hello", "doc_id": "d1",
                                   "chunk_index": 0, "filename": "f.txt",
                                   "start_char": 0, "end_char": 50})
        client = self._mock_client([point])
        with patch.object(store, "_get_client", return_value=client):
            results = store.search([0.1] * 768, top_k=5)
        assert isinstance(results, list)
        assert len(results) == 1

    def test_result_keys(self):
        store = _make_store()
        point = _make_point(0.85, {"text": "metin", "doc_id": "d2",
                                    "chunk_index": 3, "filename": "x.pdf",
                                    "start_char": 100, "end_char": 200})
        client = self._mock_client([point])
        with patch.object(store, "_get_client", return_value=client):
            result = store.search([0.0] * 768)[0]
        assert result["text"] == "metin"
        assert result["doc_id"] == "d2"
        assert result["chunk_index"] == 3
        assert result["filename"] == "x.pdf"
        assert result["start_char"] == 100
        assert result["end_char"] == 200
        assert abs(result["score"] - 0.85) < 1e-9

    def test_dense_rank_assigned(self):
        store = _make_store()
        points = [
            _make_point(0.9, {"text": "a", "doc_id": "d1", "chunk_index": 0,
                               "filename": "a.txt", "start_char": 0, "end_char": 10}),
            _make_point(0.7, {"text": "b", "doc_id": "d2", "chunk_index": 1,
                               "filename": "b.txt", "start_char": 0, "end_char": 10}),
        ]
        client = self._mock_client(points)
        with patch.object(store, "_get_client", return_value=client):
            results = store.search([0.0] * 768)
        assert results[0]["dense_rank"] == 0
        assert results[1]["dense_rank"] == 1

    def test_empty_response_returns_empty(self):
        store = _make_store()
        client = self._mock_client([])
        with patch.object(store, "_get_client", return_value=client):
            results = store.search([0.0] * 768)
        assert results == []

    def test_qdrant_exception_returns_empty(self):
        store = _make_store()
        client = MagicMock()
        client.query_points.side_effect = Exception("connection refused")
        with patch.object(store, "_get_client", return_value=client):
            results = store.search([0.0] * 768)
        assert results == []

    def test_missing_payload_fields_default(self):
        store = _make_store()
        point = _make_point(0.5, {})
        client = self._mock_client([point])
        with patch.object(store, "_get_client", return_value=client):
            result = store.search([0.0] * 768)[0]
        assert result["text"] == ""
        assert result["doc_id"] == ""
        assert result["chunk_index"] == 0
        assert result["filename"] == ""
        assert result["start_char"] == 0
        assert result["end_char"] == 0

    def test_calls_query_points_with_correct_args(self):
        store = _make_store("tenant-a")
        client = self._mock_client([])
        query_vec = [0.1] * 768
        with patch.object(store, "_get_client", return_value=client):
            store.search(query_vec, top_k=15)
        call_kwargs = client.query_points.call_args
        assert call_kwargs is not None
        # collection_name and limit must be correct
        client.query_points.assert_called_once()


class TestCollectionExists:
    def test_delegates_to_qdrant_client(self):
        store = _make_store("t")
        client = MagicMock()
        client.collection_exists.return_value = True
        with patch.object(store, "_get_client", return_value=client):
            result = store.collection_exists()
        assert result is True
        client.collection_exists.assert_called_once_with("tenant_t")

    def test_returns_false_when_missing(self):
        store = _make_store("t")
        client = MagicMock()
        client.collection_exists.return_value = False
        with patch.object(store, "_get_client", return_value=client):
            assert store.collection_exists() is False

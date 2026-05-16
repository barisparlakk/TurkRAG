"""TenantIndexer unit tests — all external I/O mocked."""

import pickle
from unittest.mock import MagicMock, patch

import numpy as np

from ingestion.indexer import TenantIndexer


def _make_chunks(n: int = 3) -> list[dict]:
    return [
        {
            "text": f"chunk text {i}",
            "chunk_index": i,
            "start_char": i * 100,
            "end_char": i * 100 + 80,
        }
        for i in range(n)
    ]


class TestIngestEarlyReturn:
    def test_empty_chunks_returns_immediately(self, caplog):
        indexer = TenantIndexer()
        with patch("ingestion.embedder.embed") as mock_embed:
            indexer.ingest("doc-1", "tenant-x", "file.txt", [])
            mock_embed.assert_not_called()

    def test_empty_chunks_logs_warning(self, caplog):
        import logging
        indexer = TenantIndexer()
        with caplog.at_level(logging.WARNING, logger="ingestion.indexer"):
            indexer.ingest("doc-1", "tenant-x", "file.txt", [])
        assert any("No chunks" in r.message for r in caplog.records)


class TestBM25Payload:
    """Verify that BM25 payloads contain start_char and end_char."""

    def test_payload_keys_include_char_offsets(self, tmp_path):

        chunks = _make_chunks(2)
        indexer = TenantIndexer()

        with patch("ingestion.indexer.BM25_INDEX_DIR", tmp_path):
            indexer._update_bm25("slug-a", chunks, "doc-42", "myfile.txt")

        index_path = tmp_path / "bm25_slug-a.pkl"
        assert index_path.exists()

        with open(index_path, "rb") as f:
            data = pickle.load(f)

        payloads = data["payloads"]
        assert len(payloads) == 2

        for i, p in enumerate(payloads):
            assert "start_char" in p, f"Payload {i} missing start_char"
            assert "end_char" in p, f"Payload {i} missing end_char"
            assert p["start_char"] == chunks[i]["start_char"]
            assert p["end_char"] == chunks[i]["end_char"]
            assert p["doc_id"] == "doc-42"
            assert p["filename"] == "myfile.txt"

    def test_existing_index_is_appended(self, tmp_path):
        chunks_a = _make_chunks(2)
        chunks_b = _make_chunks(1)
        # chunks_b has chunk_index=0 but different content after offset shift
        chunks_b[0]["text"] = "new document text"
        chunks_b[0]["start_char"] = 500
        chunks_b[0]["end_char"] = 580

        indexer = TenantIndexer()
        with patch("ingestion.indexer.BM25_INDEX_DIR", tmp_path):
            indexer._update_bm25("slug-b", chunks_a, "doc-1", "a.txt")
            indexer._update_bm25("slug-b", chunks_b, "doc-2", "b.txt")

        index_path = tmp_path / "bm25_slug-b.pkl"
        with open(index_path, "rb") as f:
            data = pickle.load(f)

        assert len(data["texts"]) == 3  # 2 + 1
        assert len(data["payloads"]) == 3


class TestUpdatePostgresStatus:
    def test_executes_update_query(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cur

        with patch("ingestion.indexer.get_conn", return_value=mock_conn):
            TenantIndexer()._update_postgres_status("doc-abc", 7)

        mock_cur.execute.assert_called_once()
        sql, params = mock_cur.execute.call_args[0]
        assert "UPDATE documents" in sql
        assert params == (7, "doc-abc")

    def test_conn_closed_even_on_error(self):
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.side_effect = RuntimeError("DB down")

        with patch("ingestion.indexer.get_conn", return_value=mock_conn):
            # should not raise
            TenantIndexer()._update_postgres_status("doc-x", 3)

        mock_conn.close.assert_called_once()


class TestIngestFullPipeline:
    """Smoke test the full ingest() path with all I/O mocked."""

    def _run_ingest(self, tmp_path):
        chunks = _make_chunks(3)
        fake_embeddings = np.random.rand(3, 768).astype("float32")

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cur

        mock_qdrant = MagicMock()
        mock_qdrant.get_collections.return_value.collections = []

        with (
            patch("ingestion.embedder.embed", return_value=fake_embeddings),
            patch("ingestion.indexer._qdrant_client", return_value=mock_qdrant),
            patch("ingestion.indexer.get_conn", return_value=mock_conn),
            patch("ingestion.indexer.BM25_INDEX_DIR", tmp_path),
        ):
            TenantIndexer().ingest("doc-1", "tenant-z", "data.txt", chunks)

        return mock_qdrant, tmp_path

    def test_creates_qdrant_collection_if_missing(self, tmp_path):
        mock_qdrant, _ = self._run_ingest(tmp_path)
        mock_qdrant.create_collection.assert_called_once()

    def test_upserts_called(self, tmp_path):
        mock_qdrant, _ = self._run_ingest(tmp_path)
        assert mock_qdrant.upsert.called

    def test_bm25_index_created(self, tmp_path):
        _, tmp = self._run_ingest(tmp_path)
        assert (tmp / "bm25_tenant-z.pkl").exists()

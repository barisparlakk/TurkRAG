import pytest

from eval.retrieval_metrics import (
    average_precision,
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)


def test_duplicate_relevant_documents_receive_credit_once():
    retrieved = ["a.pdf", "a.pdf", "b.pdf"]
    relevant = {"a.pdf", "b.pdf"}

    assert recall_at_k(retrieved, relevant, 2) == 0.5
    assert recall_at_k(retrieved, relevant, 3) == 1.0
    assert precision_at_k(retrieved, relevant, 3) == pytest.approx(2 / 3)
    assert average_precision(retrieved, relevant) == pytest.approx((1.0 + 2 / 3) / 2)
    assert ndcg_at_k(retrieved, relevant, 3) < 1.0


@pytest.mark.parametrize(
    "metric",
    [
        lambda docs, relevant: recall_at_k(docs, relevant, 20),
        lambda docs, relevant: precision_at_k(docs, relevant, 1),
        lambda docs, relevant: average_precision(docs, relevant),
        lambda docs, relevant: ndcg_at_k(docs, relevant, 20),
        mean_reciprocal_rank,
    ],
)
def test_normalized_metrics_never_exceed_one_with_duplicate_chunks(metric):
    assert 0.0 <= metric(["policy.pdf"] * 20, {"policy.pdf"}) <= 1.0


def test_metrics_return_zero_without_relevant_documents():
    retrieved = ["a.pdf", "b.pdf"]

    assert recall_at_k(retrieved, set(), 2) == 0.0
    assert precision_at_k(retrieved, set(), 2) == 0.0
    assert average_precision(retrieved, set()) == 0.0
    assert ndcg_at_k(retrieved, set(), 2) == 0.0
    assert mean_reciprocal_rank(retrieved, set()) == 0.0

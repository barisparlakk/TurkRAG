# TurkRAG — Teknik Yol Haritası

> Hocanın proje yönergesi (proje-oneri.pdf §7-9) ve ön hazırlık belgesi (proje-onhazirlik.pdf §6-10) gereksinimlerine göre kodda yapılması gereken teknik değişiklikler.

---

## Mevcut Teknik Altyapı (Hazır)

| Modül | Durum |
|-------|-------|
| `ingestion/` — chunker, embedder, indexer, parser, queue, worker | ✅ Komple |
| `retrieval/` — bm25_store, vector_store, hybrid (RRF), reranker, semantic_cache, turkish_stemmer | ✅ Komple |
| `generation/` — llm, streamer, citations, prompt, followups, memory | ✅ Komple |
| `guardrails/` — filters | ✅ Komple |
| `eval/` — ragas_eval.py, retrieval_metrics.py, error_analysis.py, auto_eval.py, test_queries.json | ✅ Komple |
| `api/` — RBAC, sessions, analytics, eval_runs tablosu | ✅ Komple |

---

## Faz 1 — Deney Altyapısı

**Hedef:** 4 retrieval konfigürasyonunu tek komutla karşılaştırabilmek.

**Bağımlılık:** Diğer tüm fazlar bu fazı bekler.

### 1.1 `retrieval/hybrid.py` — Retrieval Mode Switch

`search()` fonksiyonuna `mode` parametresi ekle:

| Mode | Açıklama |
|------|----------|
| `sparse` | Sadece BM25 |
| `dense` | Sadece Qdrant (dense vector) |
| `hybrid` | RRF fusion (mevcut davranış) |
| `hybrid+rerank` | RRF + cross-encoder reranker (mevcut full pipeline) |

### 1.2 `eval/ragas_eval.py` — Genelleştirme

- `--retrieval-mode` CLI argümanı al
- `--run-label` argümanı al (run'ı isimlendirmek için)
- Sonuçları `eval_runs` tablosuna yaz: config JSON + 4 RAGAS metriği
- Her run'a UUID `run_id` ata

### 1.3 `scripts/run_experiments.py` — Mevcut

```
4 mode × eval seti → eval_runs tablosu
Çıktı: results/experiment_<timestamp>.csv
```

İçerik:
- 4 retrieval mode üzerinden döngü
- Her mode için `ragas_eval.py` çağrısı
- Pandas DataFrame → CSV + DB

### 1.4 `scripts/plot_results.py` — Mevcut

```
Giriş: results/*.csv
Çıktılar:
  figures/metrics_comparison.png  → bar chart (4 mode × 4 metrik)
  figures/latency_distribution.png → box plot (mode başına)
  figures/recall_at_k.png          → Recall@K eğrisi
```

Not: `eval/ragas_eval.py` artık per-query ve aggregate latency değerlerini persist ettiği için
`latency_distribution.png` gerçek deney verisiyle üretilebiliyor.

---

## Faz 2 — Ground-Truth Eval Set

**Hedef:** 50-100 soru × beklenen kaynak (doc_id, chunk_id) eşleştirmesi olan formal test seti.

### 2.1 `eval/test_queries.json` Kontrolü

- Mevcut dosyadaki soru sayısını ve ground truth formatını doğrula
- Ground truth yoksa Faz 2.2'ye geç

### 2.2 `scripts/generate_eval_set.py` — Mevcut

- BM25 index'teki her chunk için LLM ile 1-2 soru üret (synthetic Q generation)
- Format:
  ```json
  {
    "question": "...",
    "expected_doc_id": "uuid",
    "expected_chunk_idx": 3,
    "expected_answer_snippet": "..."
  }
  ```
- Manuel doğrulama için `eval/eval_set.csv` export

### 2.3 `eval/retrieval_metrics.py` — Mevcut

RAGAS (end-to-end) yanına retrieval-only metrikler:

| Metrik | Açıklama |
|--------|----------|
| Recall@K | Beklenen chunk top-K'da var mı? |
| MRR | Mean Reciprocal Rank |
| nDCG | Normalized Discounted Cumulative Gain |

Mevcut `eval/ragas_eval.py` ile entegre edilecek, aynı run'da hesaplanacak.

---

## Faz 3 — Hata Analizi

**Hedef:** Sistematik failure case kategorizasyonu (proje-oneri §9: "hangi örneklerde hata yapıldı").

### 3.1 `eval/error_analysis.py` — Mevcut

Her eval sorusu için kategori tespiti:

| Kategori | Tanım |
|----------|-------|
| `retrieval_fail` | Beklenen chunk top-K'da yok (Recall@K = 0) |
| `wrong_citation` | Cevap kaynak gösteriyor ama chunk bunu desteklemiyor |
| `no_answer` | Sistem "bilgi bulunamadı" döndürdü ama cevap mevcut |
| `hallucination` | RAGAS faithfulness < 0.5 |
| `correct` | Tüm metrikler eşik üzerinde |

Çıktılar:
- `eval/failure_cases.json` — her kategoriden örnekler
- Kategori başına örnek sayısı tablosu (CSV/stdout)

---

## Faz 4 — Özgün Katkı: Chunking + Embedder Ablation

**Hedef:** Hocanın "anlamlı özgün katkı" beklentisi için 2 boyutta ablation.

**Bu faz en güçlü akademik katkıyı sağlar.**

### 4.1 `ingestion/chunker.py` — Genişletme

Mevcut `TurkishChunker`'a ek olarak:

| Chunker | Parametre |
|---------|-----------|
| `FixedSizeChunker` | token_size ∈ {256, 512} |
| `RecursiveChunker` | separators hiyerarşisi |
| `ParagraphChunker` | `\n\n` bazlı bölme |
| `TurkishChunker` | mevcut (sentence-based, 800 char) |

### 4.2 `scripts/chunking_experiments.py` — Mevcut

```
4 chunker × eval set → Recall@K, MRR, nDCG
Geçici tenant indeksleri ile kıyaslama yapar
Çıktı: results/chunking_experiments.json
```

### 4.3 `ingestion/embedder.py` — Plug-and-Play

`EMBEDDING_MODEL` env var ile model değiştirilebilsin:

| Model | Boyut |
|-------|-------|
| `paraphrase-multilingual-mpnet-base-v2` | 768 (mevcut) |
| `intfloat/multilingual-e5-base` | 768 |
| `dbmdz/bert-base-turkish-uncased` | 768 |

### 4.4 `scripts/embedder_experiments.py` — Mevcut

```
Her embedder için:
  1. Geçici Qdrant koleksiyonu kur
  2. Dense retrieval eval set üzerinde çalıştır
  3. Recall@K + MRR + nDCG kaydet
Çıktı: results/embedder_experiments.json
```

---

## Faz 5 — Hyperparameter Tuning

**Hedef:** Sistem parametrelerini sistematik olarak optimize etmek.

### 5.1 `scripts/hyperparameter_sweep.py` — Mevcut

Taranacak aralıklar:

| Parametre | Aralık |
|-----------|--------|
| `chunk_size` | {400, 600, 800, 1000} |
| `overlap` | {0, 100, 150, 200} |
| `top_k` (retrieval) | {10, 20, 30} |
| `final_k` (reranker sonrası) | {3, 5, 7} |
| RRF `k` sabiti | {30, 60, 90} |
| `rerank_threshold` | {-3.0, -2.0, -1.0} |

Çıktı: `results/hyperparameter_sweep.json` + en iyi konfigürasyon özeti

---

## Faz 6 — XAI: Cümle Bazlı Attribution (Opsiyonel / Bonus)

**Hedef:** "Açıklanabilir yapay zeka" katkısı — cevabın hangi cümlesinin hangi chunk'tan geldiğini göster.

### 6.1 `generation/attribution.py` — Mevcut

```
Cevap üretildikten sonra:
  1. Cevabı cümlelere böl
  2. Her cümleyi embed et
  3. Retrieved chunk'larla cosine similarity hesapla
  4. threshold > 0.7 → "destekleniyor" işareti
  5. Sonuç: [{sentence, supporting_chunk_id, confidence}]
```

### 6.2 Dashboard Entegrasyonu

`dashboard/src/components/CitationPanel.jsx`'e renkli highlight eklenir:
- Desteklenen cümleler → yeşil underline
- Desteklenmeyen cümleler → sarı uyarı

---

## Öncelik ve Bağımlılık Sırası

```
[Faz 1]  → retrieval mode switch + deney script + grafikler   ← BAŞLANGIÇ
[Faz 2]  → ground-truth eval set oluştur                       ← Faz 1 sonrası
[Faz 3]  → hata analizi                                        ← Faz 2 sonrası
[Faz 4]  → chunking + embedder ablation                        ← En güçlü katkı
[Faz 5]  → hyperparameter sweep                                ← Faz 4 sonrası
[Faz 6]  → XAI attribution                                     ← Bonus/opsiyonel
```

---

## Oluşturulacak Dosyalar Özeti

| Dosya | Faz | Durum |
|-------|-----|-------|
| `retrieval/hybrid.py` (mode param) | 1.1 | Mevcut dosya güncellenir |
| `eval/ragas_eval.py` (CLI args) | 1.2 | Mevcut dosya güncellenir |
| `scripts/run_experiments.py` | 1.3 | ✅ Mevcut |
| `scripts/plot_results.py` | 1.4 | ✅ Mevcut |
| `scripts/generate_eval_set.py` | 2.2 | ✅ Mevcut |
| `eval/retrieval_metrics.py` | 2.3 | ✅ Mevcut |
| `eval/error_analysis.py` | 3.1 | ✅ Mevcut |
| `ingestion/chunker.py` (ek chunkerlar) | 4.1 | ✅ Mevcut; Türkçe chunker override'ları deney scriptleriyle uyumlu |
| `scripts/chunking_experiments.py` | 4.2 | ✅ Mevcut |
| `ingestion/embedder.py` (env var) | 4.3 | ✅ Mevcut |
| `scripts/embedder_experiments.py` | 4.4 | ✅ Mevcut |
| `scripts/hyperparameter_sweep.py` | 5.1 | ✅ Mevcut |
| `generation/attribution.py` | 6.1 | ✅ Mevcut |
| `figures/` dizini | 1.4+ | ✅ Mevcut |
| `results/` dizini | 1.3+ | ✅ Mevcut |

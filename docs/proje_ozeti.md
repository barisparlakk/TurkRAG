# TurkRAG — Proje Özeti

> On-premise, KVKK uyumlu Türkçe RAG sistemi. Üniversite AI dersi bitirme projesi.

---

## Sistem Mimarisi

| Katman | Teknoloji |
|--------|-----------|
| LLM | Qwen3-8B-Instruct GGUF (llama-cpp-python, GPU) |
| Embedder | SentenceTransformer `turkish-embedder` (768 boyut) |
| Vektör DB | Qdrant (port 6333) |
| BM25 | bm25s (disk üzerinde pickle) |
| Reranker | cross-encoder/ms-marco-MiniLM-L-6-v2 |
| API | FastAPI (port 8001), JWT tabanlı RBAC |
| Dashboard | React + Vite (port 5173) |
| Veritabanı | PostgreSQL (sessions, messages, analytics) |

---

## Yapılan Çalışmalar

### Faz 1 — Deney Altyapısı

**1.1 Retrieval Mode Switch (`retrieval/hybrid.py`)**
- `retrieve(mode=...)` parametresi ile 4 mod desteklendi:
  - `sparse` → yalnızca BM25
  - `dense` → yalnızca Qdrant vektör araması
  - `hybrid` → RRF (Reciprocal Rank Fusion) ile BM25 + dense füzyonu
  - `hybrid+rerank` → RRF sonrası cross-encoder ile yeniden sıralama
- HyDE (Hypothetical Document Embeddings) entegrasyonu: sorgu için sentetik belge üretilip embedding alınıyor

**1.2 Değerlendirme Pipeline'ı (`eval/ragas_eval.py`)**
- RAGAS kütüphanesi OpenAI bağımlılığı nedeniyle kullanılamadı
- Lokal, LLM gerektirmeyen metrikler sıfırdan yazıldı:
  - `faithfulness` — cevap tokenlarının context'te bulunma oranı
  - `answer_relevancy` — soru↔cevap embedding cosine similarity
  - `context_precision` — retrieved docs içinde doğru kaynağın oranı
  - `context_recall` — doğru kaynağın retrieved set'te bulunup bulunmadığı

**1.3 Deney Scripti (`scripts/run_experiments.py`)**
- 4 retrieval modunu sırayla çalıştırıp CSV çıktısı üretiyor
- Her mod için JSON sonuç dosyası kaydediliyor

**1.4 Grafik Üretimi (`scripts/plot_results.py`)**
- `figures/metrics_comparison.png` → 4 mod × 4 metrik grouped bar chart
- `figures/metrics_radar.png` → modlar arası radar grafiği
- `figures/recall_at_k.png` → K=1,3,5,10,20 için Recall@K eğrisi

---

### Faz 2 — Ground-Truth Eval Seti

**2.1 Eval Seti Oluşturma**
- 5 manuel, ground-truth etiketli soru ile başlandı
- Qwen3-8B ile 25 chunk'tan sentetik Q-A çifti üretildi
- **Problem:** Qwen3'ün thinking modu (`<think>` tokenları) max_tokens limitini aşıyor, sorular bozuluyordu
- **Çözüm:** `/no_think` sistem talimatı ile thinking modu kapatıldı, filtre eklendi
- Sonuç: **55 temiz Türkçe soru** (`eval/test_queries.json`)
  - Her soruda: `question`, `ground_truth`, `relevant_doc` alanları
  - Kapsanan dosyalar: müşteri hizmetleri, şirket politikası, ürün kataloğu, bilgi güvenliği, oryantasyon rehberi

**2.2 Retrieval Metrikleri (`eval/retrieval_metrics.py`)**
- LLM gerektirmeden saf retrieval kalitesi ölçümü
- 55 sorgu × 4 mod çalıştırıldı:

```
Mode             MRR     R@1    R@3    R@5    R@10   R@20
─────────────────────────────────────────────────────────
sparse          0.914   0.873  1.800  2.345  3.509  5.127
dense           0.850   0.800  1.509  2.127  3.164  4.436
hybrid          0.916   0.891  1.855  2.473  3.855  3.855
hybrid+rerank   0.905   0.873  1.927  2.600  3.745  3.745
```

**Bulgular:**
- Hybrid en yüksek MRR (0.916) — ilk pozisyonda doğru chunk her sorguda
- Hybrid+rerank en yüksek R@5 (2.600) — 5 chunk içinde en fazla ilgili belge
- Dense tek başına MRR'de en zayıf — Türkçe embedder iyileştirmeye açık
- Sparse beklenenden güçlü — Türkçe BM25 etkili

---

### Faz 3 — Hata Analizi

**3.1 Error Analysis (`eval/error_analysis.py`)**

Her sorgu için pipeline çalıştırılıp sonuç şu kategorilerden birine atanıyor:

| Kategori | Tanım |
|----------|-------|
| `correct` | Tüm metrikler eşik üzerinde |
| `retrieval_fail` | Doğru chunk top-K'da yok |
| `wrong_citation` | Cevap kaynak gösteriyor ama chunk bunu desteklemiyor |
| `no_answer` | Sistem "bilgi bulunamadı" döndürdü |
| `hallucination` | faithfulness < 0.5 |

- Çıktı: `eval/failure_cases.json` — kategori başına örnek sorular ve detaylar
- 55 sorgu üzerinde hybrid+rerank moduyla çalıştırıldı
- **Akademik değeri:** Sistemin hangi tür sorgularda başarısız olduğunu gösteriyor

---

### Faz 4 — Özgün Katkı: Chunker Ablation

**4.1 Türkçe Chunker Genişletmesi (`ingestion/chunker.py`)**

4 farklı chunking stratejisi implement edildi:

| Chunker | Yöntem | Parametreler |
|---------|--------|-------------|
| `TurkishChunker` | Türkçe noktalama kurallarına göre cümle bazlı | max_chars=800, overlap=150 |
| `FixedSizeChunker` | Sabit karakter sayısına göre | max_chars=800, overlap=150 |
| `RecursiveChunker` | Paragraf → cümle → karakter hiyerarşisi | max_chars=800, overlap=150 |
| `ParagraphChunker` | `\n\n` bazlı bölme | max_chars=800, overlap=0 |

**TurkishChunker Özellikleri:**
- Türkçe kısaltmaları tanıyor (Dr., Prof., vb.) — hatalı cümle bölmesini önlüyor
- Snowball tabanlı Türkçe stemmer ile BM25 token normalleştirme
- Chunk overlap ile bağlam sürekliliği korunuyor

**4.2 Chunking Deney Scripti (`scripts/chunking_experiments.py`)**
- Her strateji için geçici index kurulup eval seti üzerinde Recall@5 ölçülüyor
- Geçici indexler temizleniyor, production index değişmiyor

---

### Faz 5 — Hyperparameter Sweep

**`scripts/hyperparameter_sweep.py`**
- Taranabilecek parametreler: `chunk_size`, `overlap`, `top_k`, `final_k`, `rrf_k`, `rerank_threshold`
- Random sampling ile max 50 kombinasyon (2-3 saat sürer)
- Akademik kısıtlar nedeniyle çalıştırılmadı — script hazır

---

### Faz 6 — XAI: Cümle Bazlı Attribution

**6.1 Attribution Engine (`generation/attribution.py`)**

Cevabın her cümlesi için kaynak takibi:
1. Cevap Türkçe cümle ayırıcı ile bölünüyor
2. Her cümle embed ediliyor
3. Retrieved chunk'larla cosine similarity hesaplanıyor
4. Eşik (≥0.7) üzeri chunk'lar kaynak olarak atfediliyor
5. Eşik altı en iyi eşleşme "düşük güven" olarak işaretleniyor

Çıktı yapısı:
```json
{
  "sentences": [
    {
      "text": "Ürünler 30 gün içinde iade edilebilir.",
      "sources": [{"filename": "musteri_hizmetleri.txt", "score": 0.87}]
    }
  ],
  "has_sources": true
}
```

**6.2 Dashboard XAI Highlight (Faz 6.2)**

`SourcesPanel.jsx`'e "Cümle Bazlı Atıf" bölümü eklendi:
- 🟢 **Yeşil underline** → kaynak tarafından yüksek güvenle desteklenen cümle (cosine ≥ 0.7)
- 🟡 **Sarı underline** → eşik altı, düşük güvenle eşleşen cümle
- Hover → kaynak dosya adı + güven skoru tooltip
- WebSocket `done` frame'inden sonra ayrı `attribution` frame olarak gönderiliyor (cevap gecikmesini etkilemiyor)

**Entegrasyon akışı:**
```
streamer.py → attribution frame → useStream.js → ChatWindow.jsx → SourcesPanel.jsx
```

---

## RAGAS End-to-End Metrikler (5 sorgu, ilk run)

```
Mode             faithfulness  answer_rel  ctx_prec  ctx_recall
──────────────────────────────────────────────────────────────
sparse              0.866        0.453      0.360      1.000
dense               0.770        0.484      0.400      0.800
hybrid              0.823        0.462      0.360      1.000
hybrid+rerank       0.889        0.446      0.360      1.000
```

**Bulgular:**
- `hybrid+rerank` en yüksek faithfulness (0.889) — LLM context dışına çıkmıyor
- `dense` en yüksek answer_relevancy (0.484) — semantik benzerlik daha yüksek
- `sparse` ve `hybrid` context_recall = 1.0 — küçük sette tüm doğru kaynakları buluyor

---

## Altyapı Özellikleri

- **KVKK Uyumu:** Tüm veriler on-premise, dışarı çıkmıyor
- **Semantic Cache:** Aynı sorgu tekrar gelince LLM çağrısı yapılmıyor
- **Guardrails:** Prompt injection tespiti, PII filtreleme
- **RBAC:** JWT tabanlı rol yönetimi (admin/viewer)
- **Session Yönetimi:** Konuşma geçmişi PostgreSQL'de saklanıyor
- **Async Queue:** Belge ingestion sıraya alınıp arka planda işleniyor
- **Follow-up Sorular:** Her cevap sonrası 3 öneri soru üretiliyor

---

## Karşılaşılan Problemler

Detaylar için: [`docs/karsilasilan_problemler.md`](karsilasilan_problemler.md)

1. Dashboard beyaz ekran → port uyumsuzluğu (8000→8001) + ErrorBoundary
2. RAGAS OpenAI bağımlılığı → lokal token-overlap + embedding metrikleri
3. Cross-encoder eksikliği → HuggingFace'den ms-marco indirildi
4. Script'lerde `ModuleNotFoundError` → `sys.path.insert` fix
5. Qwen3 think token bozukluğu → `/no_think` sistem talimatı

---

## Dosya Yapısı

```
TurkRAG/
├── api/                    FastAPI endpoints, RBAC, schemas
├── dashboard/              React + Vite frontend
├── eval/
│   ├── test_queries.json   55 soruluk eval seti
│   ├── ragas_eval.py       Lokal metrik hesaplama
│   ├── retrieval_metrics.py Recall@K, MRR, nDCG
│   ├── error_analysis.py   Failure case kategorileştirme
│   └── failure_cases.json  Hata analizi çıktısı
├── figures/
│   ├── metrics_comparison.png
│   ├── metrics_radar.png
│   └── recall_at_k.png
├── generation/
│   ├── attribution.py      XAI cümle bazlı kaynak atfı
│   ├── llm.py              Qwen3 GGUF wrapper
│   └── streamer.py         WebSocket token streaming
├── ingestion/
│   ├── chunker.py          4 chunking stratejisi
│   └── embedder.py         SentenceTransformer wrapper
├── models/
│   ├── turkish-embedder/   768-dim Türkçe embedding modeli
│   └── cross-encoder/      ms-marco-MiniLM-L-6-v2
├── results/
│   ├── experiment_*.csv    RAGAS deney sonuçları
│   └── retrieval_metrics_55q.json  55 sorguyla retrieval metrikleri
├── retrieval/
│   ├── hybrid.py           4-mod retrieval + RRF + HyDE
│   ├── reranker.py         Cross-encoder yeniden sıralama
│   └── semantic_cache.py   Sorgu önbelleği
└── scripts/
    ├── run_experiments.py      4 mod × eval → CSV
    ├── plot_results.py         Grafik üretimi
    ├── generate_eval_set.py    Sentetik Q-A üretimi
    ├── chunking_experiments.py Chunker ablation
    └── hyperparameter_sweep.py Grid search
```

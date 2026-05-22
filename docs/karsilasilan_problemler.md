# Karşılaşılan Problemler ve Çözümler

## 1. Dashboard Beyaz Ekran (localhost:5173)

**Sorun:** Dashboard açılınca boş beyaz ekran geliyordu.

**Kök Neden:**
- `dashboard/src/api/client.js` içinde API portu 8000 olarak yazılıydı, API ise 8001'de çalışıyordu.
- Vite dev server yeniden başlatılmamıştı.

**Çözüm:**
- `API_BASE` portu 8001'e güncellendi.
- `dashboard/src/main.jsx`'e `ErrorBoundary` React bileşeni eklendi (render hatalarını yakalamak için).
- Vite yeniden başlatıldı.

---

## 2. RAGAS Lokal LLM ile Uyumsuzluğu

**Sorun:** `ragas_eval.py` RAGAS kütüphanesini kullanıyordu; RAGAS varsayılan olarak OpenAI API bekliyor.

**Kök Neden:**
- RAGAS 0.4.3, lokal LLM'i LangchainLLMWrapper ile sarmaya çalışınca `TypeError: All metrics must be initialised metric objects` hatası verdi.
- `InstructorLLM` gerektiren modern metrikler lokal LLM'i desteklemiyordu.
- Async runner + senkron LLM çakışması `TimeoutError` üretiyordu.
- 5 sorgu × 4 metrik × her metrik için birden fazla LLM çağrısı = saatler süren değerlendirme.

**Çözüm:**
- RAGAS LLM judge tamamen kaldırıldı.
- Yerine lokal, LLM gerektirmeyen metrikler yazıldı:
  - `faithfulness`: token overlap (cevap ∩ context)
  - `answer_relevancy`: cosine similarity (soru ↔ cevap embedding)
  - `context_precision`: retrieved docs içinde relevant_doc oranı
  - `context_recall`: relevant_doc retrieved set'te var mı?

---

## 3. Cross-Encoder Reranker Eksikliği

**Sorun:** `hybrid+rerank` modu çalıştırılınca "Reranker model not found at 'models/cross-encoder'" hatası.

**Kök Neden:** Cross-encoder modeli repo'ya eklenmemişti.

**Çözüm:** `huggingface_hub.snapshot_download` ile `cross-encoder/ms-marco-MiniLM-L-6-v2` modeli (~80MB) `models/cross-encoder/` dizinine indirildi.

**Not:** Model İngilizce MS-MARCO veri setiyle eğitildiği için Türkçe sorgularda MRR'yi düşürüyor. Türkçe cross-encoder ile değiştirilebilir.

---

## 4. Script'lerde ModuleNotFoundError

**Sorun:** `python3 scripts/run_experiments.py` çalıştırılınca `ModuleNotFoundError: No module named 'eval'` hatası.

**Kök Neden:** Script `scripts/` dizininden çalıştırıldığında Python `sys.path`'e proje kök dizinini eklemiyordu.

**Çözüm:** Tüm `scripts/` altındaki dosyalara şu satır eklendi:
```python
sys.path.insert(0, str(Path(__file__).parent.parent))
```

---

## 5. Eval Set Üretiminde Qwen3 Think Token Sorunu

**Sorun:** `generate_eval_set.py` ile üretilen 47 sorunun 46'sı `<think>` veya `Okay, let's see...` içeriyordu. Retrieval metrics çalıştırıldığında bu sahte sorgular yüzünden hybrid+rerank MRR=0.043'e düştü.

**Kök Neden:**
- Qwen3-8B modeli düşünme (thinking) modunda çalışıyor: önce `<think>...</think>` bloğu, sonra cevap üretiyor.
- Soru üretimi için `max_tokens=200` çok düşüktü — think bloğu token limitini aşıyordu, kapanış `</think>` tagı hiç gelmiyordu.
- `strip_think_tags()` yalnızca tam `<think>...</think>` bloklarını kaldırıyor; yarım kalan tag'leri kaldıramıyordu.
- `splitlines()[:n]` ile ilk 2 satır alınınca think/reasoning satırları soru olarak kaydediliyordu.

**Çözüm:**
- Sistem prompt'una `/no_think` eklendi (Qwen3'e özgü, düşünme modunu kapatır).
- `max_tokens` 200'den 300'e çıkarıldı.
- Parsing adımına filtre eklendi: `<` ile başlayan, `okay` veya `let me` içeren satırlar atlanıyor.
- Orijinal 5 el yapımı sorgu git'ten kurtarıldı, yeni 50 temiz soruyla birleştirildi → 55 soruluk eval seti.

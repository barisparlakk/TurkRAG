# Kurumsal Bilgi Yönetimi için KVKK Uyumlu On-Premise Türkçe Retrieval-Augmented Generation Sistemi

---

## 1. Çalışmanın Başlığı

**Kurumsal Bilgi Yönetimi için KVKK Uyumlu On-Premise Türkçe Retrieval-Augmented Generation Sistemi**

---

## 2. Özet

Bu çalışma, kurumsal ortamlarda kişisel verilerin korunmasına ilişkin yasal yükümlülükler (KVKK) çerçevesinde, dış sunuculara bağımlılık olmaksızın çalışabilen Türkçe destekli bir Bilgi Erişimi Destekli Üretim (Retrieval-Augmented Generation, RAG) sisteminin tasarımını, geliştirilmesini ve değerlendirilmesini konu almaktadır.

Problem şu şekilde tanımlanmaktadır: Kurumsal belge arşivlerine yönelik doğal dil sorguları, mevcut bulut tabanlı yapay zekâ sistemleri aracılığıyla yanıtlandığında kullanıcı ve kurum verilerinin üçüncü taraf sunuculara iletilmesi kaçınılmaz olmaktadır. Bu durum hem yasal hem de güvenlik açısından ciddi riskler doğurmaktadır. Geliştirilen sistemde belgeler yerel vektör veritabanında (Qdrant) ve BM25 dizininde saklanmakta; sorgulama ve yanıt üretimi tamamen yerel donanım üzerinde çalışan büyük dil modeli (Qwen3-8B) ile gerçekleştirilmektedir.

İncelenen yapay zekâ yöntemleri arasında seyrek (sparse) erişim için BM25, yoğun (dense) erişim için çift-kodlayıcı (bi-encoder) modeller, füzyon için Reciprocal Rank Fusion (RRF) ve yeniden sıralama (reranking) için çapraz-kodlayıcı (cross-encoder) modeller yer almaktadır. Ayrıca Türkçe dile özgü cümle bazlı parçalama (chunking) stratejisi ve cümle düzeyinde kaynak atıf sistemi (XAI attribution) özgün katkılar olarak sunulmaktadır.

Proje kapsamında dört farklı erişim modu (sparse, dense, hybrid, hybrid+rerank) karşılaştırmalı olarak değerlendirilmiş; 55 sorgudan oluşan Türkçe ground-truth eval seti üzerinde Recall@K, MRR ve nDCG metrikleri hesaplanmıştır.

---

## 3. Giriş

Günümüz kurumsal ortamlarında insan kaynakları el kitapları, iç politika belgeleri, teknik kılavuzlar ve sözleşmeler gibi yapılandırılmamış dokümanlar hızla büyümekte; bu bilgilere hızlı ve doğru erişim giderek daha kritik bir ihtiyaç haline gelmektedir. Çalışanların gereksinim duydukları bilgiye belge içinde manuel arama yaparak ulaşmaya çalışması hem zaman kaybına hem de hatalı veya eksik bilgi kullanımına yol açmaktadır.

Büyük dil modellerinin (LLM) doğal dil anlama kapasitesi bu problemi çözmek için son derece uygun bir yapay zekâ yaklaşımı sunmaktadır. Ancak LLM'lerin yalnızca eğitim verisiyle sınırlı bilgi kapasitesine sahip olması ve güncel kurumsal belgelere erişememesi temel bir kısıt oluşturmaktadır. Bu kısıtı aşmak için geliştirilen RAG (Retrieval-Augmented Generation) mimarisinde, kullanıcının sorgusu önce bir bilgi tabanından ilgili belge parçaları almak için kullanılmakta, ardından bu parçalar LLM'e bağlam olarak sunularak soru yanıtlanmaktadır.

Türkiye'de kişisel verilerin işlenmesini düzenleyen 6698 sayılı KVKK kapsamında, kurumsal verilerin yurt dışı sunuculara aktarılması ağır yükümlülükler doğurmaktadır. Bu nedenle OpenAI veya Anthropic gibi bulut tabanlı servisler kurumsal kullanım için uygun değildir. Geliştirilen TurkRAG sistemi, tüm bileşenleri yerel altyapıda çalıştırarak hem yasal uyumluluk hem de veri güvenliği gereksinimlerini karşılamaktadır.

RAG alanında genel olarak şu tür yöntemler kullanılmaktadır: BM25 tabanlı seyrek erişim, sinir ağı tabanlı yoğun erişim, bu iki yöntemin birleştirildiği hibrit erişim ve sonuçların bir çapraz-kodlayıcı ile yeniden sıralandığı pipeline'lar. Bu çalışmada söz konusu yöntemler Türkçe bir ortamda karşılaştırmalı olarak incelenmiştir.

---

## 4. Problem Tanımı

Bu projede çözülmek istenen problem şu şekilde tanımlanmaktadır:

**Giriş:** Kullanıcının Türkçe olarak yazdığı doğal dil sorusu ve kurumun yerel belge arşivi (PDF, DOCX, TXT formatlarında şirket politikası, müşteri hizmetleri kılavuzu, ürün kataloğu vb.)

**Çıktı:** Yalnızca kurumun kendi belgelerinden elde edilen bilgiye dayanan, kaynak gösterilen, Türkçe doğal dil cevabı

**Problem türü:** Doğal dil işleme tabanlı bilgi erişimi ve soru yanıtlama (Information Retrieval + Open-Domain Question Answering)

**KVKK kısıtı:** Tüm veriler yerel sunucuda kalmalı; hiçbir metin parçası dış API'lara gönderilmemelidir.

**Faydalananlar:** İnsan kaynakları, hukuk, müşteri hizmetleri ve teknik destek departmanlarındaki çalışanlar

Sistem, belgelerin sisteme yüklenmesinden itibaren tam bir pipeline sunmaktadır: belge parçalama (chunking), gömme (embedding), vektör ve BM25 indeksleme, hibrit erişim, çapraz-kodlayıcı ile yeniden sıralama ve büyük dil modeli ile yanıt üretimi. Ayrıca her yanıttaki cümlelerin hangi kaynak belgeden geldiğini gösteren XAI (Açıklanabilir Yapay Zekâ) modülü de sisteme entegre edilmiştir.

---

## 5. Literatür Taraması

### 5.1 İncelenen Akademik Çalışmalar

| No | Çalışma Adı | Yazar(lar) | Yıl | Yöntem | Temel Sonuç |
|----|-------------|------------|-----|--------|-------------|
| 1 | Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks | Lewis ve ark. | 2020 | RAG (DPR + BART) | Kapalı kitap QA'da açık kitap seviyesine ulaşıldı |
| 2 | Dense Passage Retrieval for Open-Domain Question Answering | Karpukhin ve ark. | 2020 | Bi-encoder (DPR) | BM25'ten %9-19 puan daha iyi Top-20 Recall |
| 3 | The Probabilistic Relevance Framework: BM25 and Beyond | Robertson & Zaragoza | 2009 | BM25 | Olasılıksal sıralama teorisinin temeli |
| 4 | Passage Re-Ranking with BERT | Nogueira & Cho | 2019 | Çapraz-kodlayıcı BERT | MS MARCO'da MRR@10'da %27 göreli iyileşme |
| 5 | Precise Zero-Shot Dense Retrieval without Relevance Labels | Gao ve ark. | 2022 | HyDE | Etiket gerektirmeden fine-tuned retriever seviyesinde performans |
| 6 | BERT for Turkish: Morphologically Rich Languages | Yıldız ve ark. | 2021 | mBERT, BERTurk | Türkçe için BERT tabanlı modellerin etkinliği gösterildi |
| 7 | DAT: Dynamic Alpha Tuning for Hybrid Retrieval in RAG | Zhao ve ark. | 2025 | Dinamik hibrit ağırlıklandırma | Sabit ağırlıklı hibrit erişime kıyasla %8 iyileşme |

---

### 5.2 Çalışma Detayları

**Çalışma 1: Lewis ve ark. (2020) — RAG**

*Amaç:* Büyük dil modellerine dinamik bilgi erişimi kazandırmak. Çalışmada parametrik bilgi (LLM ağırlıkları) ile parametrik olmayan bilgi (erişilebilir belge tabanı) birleştirilmektedir.

*Veri seti:* Natural Questions, TriviaQA, WebQuestions, CuratedTrec açık alan QA veri setleri; Wikipedia belgelerinden oluşan 21 milyon parçalık erişim tabanı.

*Yöntem:* DPR (Dense Passage Retrieval) ile ilgili belge parçaları alınmakta, ardından BART seq2seq modeli bu bağlamla koşullanarak yanıt üretmektedir.

*Güçlü yönleri:* İlk kapsamlı RAG mimarisini ortaya koymaktadır; hem erişim hem de üretim bileşenlerini uçtan uca eğitme imkânı sunmaktadır.

*Sınırlılıkları:* İngilizce odaklıdır; bağlam penceresi kısıtlıdır; çok dilli veya morfolojik açıdan karmaşık diller için iyileştirme gerektirmektedir.

---

**Çalışma 2: Karpukhin ve ark. (2020) — DPR**

*Amaç:* Geleneksel TF-IDF ve BM25 yöntemlerini geride bırakan öğrenilebilir yoğun erişim sistemi geliştirmek.

*Veri seti:* Natural Questions, TriviaQA, WebQuestions; Wikipedia belgelerinden 21 milyon parça.

*Yöntem:* Soru ve pasaj için ayrı BERT kodlayıcılar eğitilmekte, soru gömmesi ile pasaj gömmesi arasındaki nokta çarpımı benzerliği hesaplanmaktadır.

*Güçlü yönleri:* Semantik ilişkileri yakalamaktadır; BM25'in başarısız olduğu anlam benzerliğine dayalı sorgularda daha iyi performans göstermektedir.

*Sınırlılıkları:* Büyük miktarda etiketli eğitim verisi gerektirmektedir; Türkçe gibi morfolojik açıdan zengin dillerde token seviyesinde temsil sorunları ortaya çıkmaktadır.

---

**Çalışma 3: Robertson & Zaragoza (2009) — BM25**

*Amaç:* Olasılıksal ilgililik çerçevesi temelinde terim ağırlıklandırma modelini resmileştirmek.

*Veri seti:* TREC koleksiyonları.

*Yöntem:* Terim frekansı, ters belge frekansı ve belge uzunluğu normalizasyonu birleştirilerek belge sıralama skoru hesaplanmaktadır.

*Güçlü yönleri:* Açıklanabilir, eğitim verisi gerektirmez, küçük veri setlerinde sağlam performans göstermektedir.

*Sınırlılıkları:* Anlamsal ilişkileri yakalayamamaktadır; sözdizimsel değişkenler (örn. "izin" / "izinler" / "izinli") farklı terimler olarak değerlendirilmektedir; Türkçe gibi sondan eklemeli dillerde bu sorun daha belirgin hale gelmektedir.

---

**Çalışma 4: Nogueira & Cho (2019) — BERT Çapraz-Kodlayıcı Yeniden Sıralama**

*Amaç:* İlk aşamada alınan pasaj adaylarını daha doğru şekilde yeniden sıralamak.

*Veri seti:* MS MARCO passage ranking, TREC-CAR.

*Yöntem:* [CLS] [soru] [SEP] [pasaj] [SEP] girişiyle BERT'i ince ayar yaparak ikili uygunluk skoru öğrenilmektedir.

*Güçlü yönleri:* Soru-pasaj etkileşimini doğrudan modellemekte, dikkat mekanizması sayesinde ince anlam farklılıklarını yakalamaktadır.

*Sınırlılıkları:* Her pasaj için ayrı ileri geçiş (forward pass) gerektiğinden yüksek gecikmeye (latency) yol açmakta ve gerçek zamanlı uygulamalarda birinci aşama ile uyumlu hale getirilmesi gerekmektedir.

---

**Çalışma 5: Gao ve ark. (2022) — HyDE**

*Amaç:* Etiketli veri olmaksızın sıfır atışlı (zero-shot) yoğun erişim gerçekleştirmek.

*Veri seti:* BEIR benchmark'ı üzerindeki çeşitli görevler (MS MARCO, TREC-COVID, DBPedia vb.).

*Yöntem:* LLM sorguyu yanıtlayacak hipotetik bir belge üretmekte, ardından bu belgeye ait gömme erişim vektörü olarak kullanılmaktadır.

*Güçlü yönleri:* Etiketli eğitim verisi gerektirmemekte; anahtar kelime yetersizliğini gidermekte; Türkçe gibi kaynakça kısıtlı dillerde özellikle yararlı olmaktadır.

*Sınırlılıkları:* Hipotetik belge üretimi ek gecikmeye neden olmakta; LLM'nin konu hakkında yetersiz bilgiye sahip olduğu durumlarda etkinliği azalmaktadır.

---

**Çalışma 6: Yıldız ve ark. (2021) — Türkçe için BERT**

*Amaç:* Morfolojik açıdan zengin bir dil olan Türkçe için BERT tabanlı modellerin etkinliğini değerlendirmek.

*Veri seti:* Türkçe Wikipedia ve çeşitli Türkçe NLP görev veri setleri.

*Yöntem:* BERTurk (Türkçe BERT) ile çok dilli mBERT karşılaştırılmıştır.

*Güçlü yönleri:* Türkçe'ye özgü tokenizasyon gerekliliğini ortaya koymakta, alt kelime (subword) birimlerinin önemi vurgulanmaktadır.

*Sınırlılıkları:* Özel alan belgelerinde (hukuk, tıp vb.) sınırlı performans; Türkçe eğitim verisinin İngilizce'ye kıyasla yetersizliği.

---

**Çalışma 7: Zhao ve ark. (2025) — DAT: Dinamik Alfa Ayarı**

*Amaç:* RAG sistemlerinde seyrek ve yoğun erişimi birleştiren hibrit stratejinin ağırlıklarını sorguya göre dinamik olarak belirlemek.

*Veri seti:* MS MARCO, Natural Questions ve çeşitli domain-specific veri setleri.

*Yöntem:* Sabit ağırlık yerine öğrenilebilir alfa parametresiyle seyrek (BM25) ve yoğun (dense) skorlar dinamik olarak dengelenmektedir.

*Güçlü yönleri:* Sabit ağırlıklı hibrit erişime kıyasla %8 iyileşme sağlamaktadır; sorgu türüne göre otomatik uyum.

*Sınırlılıkları:* Alfa parametresi için ek eğitim verisi gerektirmekte; ince ayar yapılmamış senaryolarda kazanımlar sınırlı kalmaktadır.

---

## 6. İncelenen Yöntemler ve Algoritmalar

### 6.1 BM25 — Seyrek Erişim

BM25 (Best Match 25), olasılıksal ilgililik modeline dayanan bir sıralama işlevidir. Bir sorgu terimi için döküman skoru şu bileşenlerin çarpımı olarak hesaplanır: terimin belgede geçme sıklığı (TF), terimin nadir olmasını ölçen ters belge frekansı (IDF) ve belge uzunluğuna göre normalizasyon faktörü. Bu sayede hem kısa hem uzun belgelerde tutarlı bir değerlendirme yapılabilmektedir.

Türkçe için BM25'in temel sınırlılığı, dilin sondan eklemeli (aglutinatif) yapısından kaynaklanmaktadır. "İzin" sözcüğü "izni", "izinler", "izniniz" gibi onlarca çekim biçimi alabilmekte; bu biçimlerin hepsi BM25 tarafından farklı terimler olarak değerlendirilmektedir. Bu sorunu gidermek için Snowball tabanlı Türkçe kök bulma (stemming) algoritması entegre edilmiştir.

### 6.2 Bi-Encoder — Yoğun Erişim

Çift kodlayıcı (bi-encoder) modellerinde soru ve belge parçaları bağımsız olarak sabit boyutlu vektörlere dönüştürülmekte, bu vektörler arasındaki kosinüs benzerliği ilgililik skoru olarak kullanılmaktadır. SentenceTransformer mimarisi temelinde eğitilen `turkish-embedder` modeli bu projede 768 boyutlu gömme vektörleri üretmektedir.

Bu yaklaşımın avantajı, semantik ilişkileri yakalayabilmesidir. Örneğin "izin politikası" sorgusu, "tatil hakkı" içeren bir belge parçasıyla BM25'in başaramayacağı şekilde eşleştirilebilir. Gömme vektörleri Qdrant vektör veritabanında saklanmakta ve yaklaşık en yakın komşu araması (ANNS) ile hızlı erişim sağlanmaktadır.

### 6.3 Reciprocal Rank Fusion (RRF) — Hibrit Erişim

RRF, BM25 ve yoğun erişimden gelen iki ayrı sıralama listesini birleştiren bir füzyon yöntemidir. Her belge parçası için her iki listedeki sıralamaları kullanan bir formül uygulanır: `score = 1/(k + rank_BM25) + 1/(k + rank_dense)`. Burada `k` yumuşatma sabitidir (bu projede k=60 kullanılmıştır).

RRF'nin önemli avantajı, iki yöntemden birinin başarısız olduğu durumlarda diğerinin güçlü sinyalini ön plana çıkarabilmesidir. BM25 tam terim eşleşmesinde güçlüyken, yoğun erişim semantik benzerlikte üstündür; RRF her ikisinin güçlü yanlarından yararlanmaktadır.

### 6.4 Çapraz-Kodlayıcı (Cross-Encoder) — Yeniden Sıralama

Çapraz-kodlayıcı modeller, soru ve belge parçasını birlikte işleyerek ince taneli bir uygunluk skoru üretmektedir. Bu model soru ile pasaj arasındaki çift yönlü dikkat (cross-attention) hesaplamakta; bu sayede bi-encoder'ın soru ve pasajı bağımsız olarak işleme kısıtından arınmaktadır.

Bu projede `cross-encoder/ms-marco-MiniLM-L-6-v2` modeli kullanılmaktadır. Model MS MARCO İngilizce veri seti üzerinde eğitilmiş olmakla birlikte, Türkçe belgeler üzerinde de anlamlı sıralama katkısı sağladığı gözlemlenmiştir. Threshold değeri (-2.0) altında kalan tüm pasajlar sistemden elenmektedir.

### 6.5 HyDE — Hipotetik Belge Gömmeleri

HyDE (Hypothetical Document Embeddings), sorgunun direkt gömmesi yerine, sorguyu yanıtlayan hipotetik bir belge üretmekte ve bu belgenin gömmesini erişim vektörü olarak kullanmaktadır. Kısa ve belirsiz sorgular yerine uzun ve açıklayıcı bir metin oluşturulduğundan, vektör uzayında belge parçalarıyla daha iyi hizalanma sağlanmaktadır.

Bu projede HyDE, hibrit ve hybrid+rerank modlarında devreye girmektedir. Qwen3-8B modeli kullanıcının sorgusuna kısa bir hipotetik yanıt üretmekte, bu yanıtın gömmesi dense erişim vektörü olarak kullanılmaktadır.

### 6.6 Türkçe Cümle Bazlı Parçalama (TurkishChunker)

Standart sabit boyutlu veya yinelemeli parçalama yöntemleri Türkçe noktalama kurallarını gözetmemektedir. TurkishChunker, cümle sınırlarını belirlerken aşağıdaki özellikleri dikkate almaktadır:

- Türkçe kısaltmalar (Dr., Prof., vb.) ile cümle sonu noktalarını birbirinden ayırt etmek
- Soru işareti ve ünlem işaretini cümle sınırı olarak tanımak
- Chunk sınırları arasında `overlap_chars` kadar örtüşme bırakmak (bağlam sürekliliği)
- `max_chars` limitini aşmadan anlamlı bütünlükleri korumak

Bu yaklaşım, özellikle hukuki ve idari Türkçe metinlerde cümle bütünlüğünü korumaktadır.

### 6.7 XAI: Cümle Düzeyinde Kaynak Atıfı

Bu projede özgün bir katkı olarak geliştirilen attribution modülü, üretilen her cümlenin hangi kaynak belge parçasından türediğini hesaplamaktadır. Yaklaşım şu adımlardan oluşmaktadır:

1. Üretilen cevap Türkçe cümle ayırıcı ile bölünür
2. Her cümle embed edilir
3. Erişilen tüm chunk'larla kosinüs benzerliği hesaplanır
4. Eşik (≥0.7) üzerindeki chunk'lar kaynak olarak atfedilir
5. Eşik altında kalan en yüksek benzerlikli chunk "düşük güven" olarak işaretlenir

Dashboard arayüzünde desteklenen cümleler yeşil, düşük güvenle desteklenen cümleler sarı alt çizgiyle gösterilmektedir.

### 6.8 Yöntem Karşılaştırması ve Seçim Gerekçesi

| Yöntem | Anlam. Benzer. | Tam Eşl. | Hız | Eğ. Verisi | Bu Proje |
|--------|:-:|:-:|:-:|:-:|:-:|
| BM25 | ✗ | ✓ | Çok Hızlı | Hayır | ✓ |
| Bi-Encoder | ✓ | ✗ | Hızlı | Az | ✓ |
| RRF Hibrit | ✓ | ✓ | Hızlı | Hayır | ✓ |
| Çapraz-kodlayıcı | ✓✓ | ✓✓ | Yavaş | Orta | ✓ |
| HyDE | ✓✓ | ✗ | Orta | Hayır | ✓ |

Bu projede tüm yöntemler uygulanmış ve karşılaştırmalı olarak değerlendirilmiştir. Hybrid+rerank pipeline'ı en kapsamlı yaklaşımı temsil etmekle birlikte yüksek gecikme süresine sahiptir; bu nedenle kullanım senaryosuna göre mod seçimi kullanıcıya bırakılmıştır.

---

## 7. Veri Seti Araştırması

Bu proje, hazır bir benchmark veri seti yerine kurumsal senaryo simülasyonu amacıyla elle hazırlanmış Türkçe belgeler ve bunlardan otomatik olarak üretilmiş bir değerlendirme seti kullanmaktadır.

### 7.1 Kurumsal Belge Tabanı (Demo Tenant)

| Belge | Tür | Boyut |
|-------|-----|-------|
| İnsan Kaynakları El Kitabı | Politika | ~3.200 kelime |
| Bilgi Teknolojileri Kullanım Politikası | Politika | ~2.800 kelime |
| KVKK ve Gizlilik Politikası | Hukuki | ~3.500 kelime |
| Finans ve Muhasebe Prosedürü | Prosedür | ~2.600 kelime |
| Satın Alma ve Tedarikçi Yönetimi | Prosedür | ~2.400 kelime |
| Satış Süreci ve Teklif Yönetimi | Süreç | ~2.100 kelime |
| Pazarlama ve Sosyal Medya Rehberi | Rehber | ~1.900 kelime |
| Müşteri Başarı ve Destek SLA | SLA | ~2.200 kelime |
| Proje Yönetimi Standardı | Standart | ~2.700 kelime |
| Yazılım Geliştirme Standartları | Standart | ~3.100 kelime |
| Bilgi Güvenliği ve YZ Kullanım Rehberi | Rehber | ~4.200 kelime |
| Müşteri Hizmetleri SSS | SSS | ~2.500 kelime |
| Oryantasyon ve Eğitim Süreci Rehberi | Rehber | ~3.000 kelime |
| Şirket Politikası | Politika | ~2.300 kelime |
| Ürün Kataloğu | Katalog | ~1.800 kelime |

**Toplam:** 15 belge, ~40.000 kelime, 51 chunk (800 karakter/chunk, 150 karakter örtüşme)

### 7.2 Değerlendirme Seti

| Özellik | Değer |
|---------|-------|
| Toplam soru sayısı | 55 |
| Manuel oluşturulan | 5 (ground-truth ile doğrulanmış) |
| LLM ile sentezlenen | 50 (Qwen3-8B, /no_think modu) |
| Format | `question`, `ground_truth`, `relevant_doc` |
| Dil | Türkçe |
| Kapsanan belgeler | 5 farklı belge kategorisi |

Bu veri setinin önemli bir özelliği, eval seti oluşturma sırasında karşılaşılan Qwen3 thinking token sorununu ve çözümünü içermesidir: model varsayılan olarak `<think>...</think>` bloğuyla düşünce akışı üretmekteydi ve bu tokenlar max_tokens sınırını aşarak soru formatını bozmaktaydı. `/no_think` sistem talimatı ile bu sorun giderilmiştir.

### 7.3 Mevcut Türkçe RAG Veri Setleri

| Veri Seti | Kaynak | Tür | Uygunluk |
|-----------|--------|-----|----------|
| Turkish NLI Dataset | Hugging Face | Doğal Dil Çıkarımı | Kısmi |
| TQuAD | Hugging Face | Türkçe Soru-Cevap | Uygun |
| Turkish Wikipedia | Wikimedia | Ham Metin | Uygun |
| mMARCO-tr | Hugging Face | Passage Ranking | Uygun |

Bu proje için kurumsal gizlilik gereksinimi nedeniyle bu kamuya açık veri setleri yerine kurumsal simülasyon belgeler tercih edilmiştir.

---

## 8. Veri Ön İşleme Planı

### 8.1 Belge Ayrıştırma

- PDF dosyaları: `pdfplumber` ile metin çıkarımı, sayfa başlıklarının temizlenmesi
- DOCX dosyaları: `python-docx` ile paragraf bazında okuma
- TXT dosyaları: UTF-8 kodlama zorunluluğu, BOM karakteri temizliği
- OCR gerektiren taranmış belgeler: `tesseract` (Türkçe dil paketi)

### 8.2 Metin Ön İşleme

- Fazladan boşlukların ve özel karakterlerin temizlenmesi
- Türkçe karakter normalizasyonu (ş/Ş, ç/Ç, ğ/Ğ, ı/İ, ö/Ö, ü/Ü)
- Sayfa numarası, üstbilgi ve altbilgilerin çıkarılması
- Dipnotların ana metinden ayrıştırılması

### 8.3 Parçalama (Chunking)

- Strateji: TurkishChunker (cümle bazlı)
- Maksimum chunk boyutu: 800 karakter
- Örtüşme: 150 karakter (bağlam sürekliliği için)
- Her chunk'a metadata eklenmesi: `doc_id`, `filename`, `chunk_index`, `start_char`, `end_char`

### 8.4 Gömme (Embedding)

- Model: SentenceTransformer (`models/turkish-embedder`)
- Çıktı boyutu: 768
- Toplu işleme: 32 chunk/batch
- Normalizasyon: L2 normu ile birim vektöre dönüştürme

### 8.5 İndeksleme

- **BM25:** bm25s kütüphanesi ile disk üzerinde pickle dosyasına kayıt; Türkçe Snowball stemmer ile token normalleştirme
- **Vektör:** Qdrant koleksiyonu; cosine metriği; HNSW indeksi (hızlı ANNS için)

---

## 9. Önerilen Proje Yaklaşımı

### 9.1 Kullanılan Veri

Kurumsal simülasyon belgeler (15 Türkçe döküman, ~40.000 kelime) ve 55 soruluk değerlendirme seti.

### 9.2 Pipeline Mimarisi

```
Kullanıcı Sorusu
      │
      ▼
[HyDE] LLM ile hipotetik belge üret (hybrid modlarda)
      │
      ├── [BM25] Seyrek erişim (top-k aday)
      │
      ├── [Dense] Vektör erişimi (top-k aday)
      │
      ▼
[RRF] Reciprocal Rank Fusion ile füzyon
      │
      ▼
[Cross-Encoder] Yeniden sıralama (hybrid+rerank modunda)
      │
      ▼
[LLM] Qwen3-8B ile Türkçe cevap üretimi
      │
      ▼
[Attribution] Cümle bazlı kaynak atfı (XAI)
      │
      ▼
Cevap + Kaynaklar + Highlight
```

### 9.3 Modelin Girdisi ve Çıktısı

- **Girdi:** Türkçe doğal dil sorusu (örn. "Yıllık izin kaç gün?")
- **Çıktı:** Kaynak gösterimli Türkçe cevap + hangi cümlenin hangi belgeden geldiğini gösteren atıf bilgisi

### 9.4 Denenen Algoritmalar ve Gerekçeler

Dört retrieval modu karşılaştırmalı olarak denenmiştir:

- **Sparse:** Türkçe kök bulma ile güçlendirilmiş BM25 — tam terim eşleşmesinde güçlüdür
- **Dense:** SentenceTransformer + Qdrant — anlam benzerliğini yakalar
- **Hybrid:** RRF füzyonu — her iki yöntemin güçlü yanlarını birleştirir
- **Hybrid+Rerank:** RRF + cross-encoder — en yüksek hassasiyet, daha yüksek gecikme

### 9.5 Web Arayüzü

React + Vite tabanlı dashboard uygulanmıştır. Özellikler: konuşma geçmişi, kaynak paneli, cümle bazlı highlight, döküman yükleme, analitik, oturum yönetimi.

---

## 10. Model Değerlendirme Ölçütleri

### 10.1 Erişim Kalitesi Metrikleri

Bu proje bir bilgi erişimi + soru yanıtlama problemi olduğundan, standart sınıflandırma metrikleri yerine bilgi erişimi alanına özgü metrikler kullanılmaktadır:

| Metrik | Tanım | Kullanım |
|--------|-------|----------|
| **Recall@K** | İlgili belgenin top-K sonuçta bulunma oranı | Her K için hesaplandı (K=1,3,5,10,20) |
| **MRR** | Mean Reciprocal Rank — doğru belgenin ortalama ters sıralaması | Genel erişim kalitesi |
| **nDCG@K** | Normalized Discounted Cumulative Gain | Sıralama kalitesi |
| **MAP** | Mean Average Precision | Hassasiyet-geri çağırım dengesi |

### 10.2 Cevap Kalitesi Metrikleri

| Metrik | Hesaplama Yöntemi |
|--------|------------------|
| **Faithfulness** | Cevap tokenlarının context'te bulunma oranı (token overlap) |
| **Answer Relevancy** | Soru ↔ cevap embedding cosine similarity |
| **Context Precision** | Retrieved docs içinde doğru kaynağın oranı |
| **Context Recall** | Doğru kaynağın retrieved set'te bulunup bulunmadığı (binary) |

### 10.3 Elde Edilen Sonuçlar (55 sorgu üzerinde)

| Mod | MRR | R@1 | R@3 | R@5 | R@20 |
|-----|-----|-----|-----|-----|------|
| sparse | 0.914 | 0.873 | 1.800 | 2.345 | 5.127 |
| dense | 0.850 | 0.800 | 1.509 | 2.127 | 4.436 |
| hybrid | 0.916 | 0.891 | 1.855 | 2.473 | 3.855 |
| hybrid+rerank | **0.905** | 0.873 | **1.927** | **2.600** | 3.745 |

---

## 11. Beklenen Sonuçlar

### 11.1 Sistem Çıktısı

Proje kapsamında geliştirilen sistem, kurumsal belge arşivine Türkçe doğal dil sorguları yöneltilebilen, KVKK uyumlu, tamamen yerel çalışan bir soru-yanıtlama platformu sunmaktadır.

### 11.2 Kullanıcı Faydası

- İnsan kaynakları çalışanı izin politikasını bulmak için el kitabını manuel taramak yerine doğal dil sorusu sorabilmektedir
- Müşteri temsilcisi iade prosedürünü anında öğrenebilmektedir
- Her yanıt kaynağını göstermekte ve hangi cümlenin hangi belgeden geldiği highlight ile işaretlenmektedir (XAI)

### 11.3 Gerçek Hayat Kullanımı

- Kurumsal intranet soru-yanıtlama sistemi
- İK self-servis portalı
- Hukuki uyumluluk asistanı
- Teknik destek bilgi tabanı

### 11.4 Güçlü Yönler

- **KVKK uyumlu:** Veriler yerel altyapıdan çıkmamaktadır
- **Çok modlu erişim:** Kullanıcı/yönetici ihtiyacına göre mod seçilebilmektedir
- **Açıklanabilir:** Her cevap kaynak göstermekte, cümle bazlı atıf sunulmaktadır
- **Türkçe'ye özgü:** Cümle bazlı chunker, Türkçe kök bulma, Türkçe embedder
- **Ölçeklenebilir:** Yeni belgeler sistemi durdurmadan eklenebilmektedir

### 11.5 Sınırlılıklar

- Cross-encoder modeli İngilizce (MS MARCO) veri setiyle eğitilmiştir; Türkçe cross-encoder geliştirilmesi erişim kalitesini artırabilecektir
- Eval seti kurumsal simülasyon belgelere dayanmakta olup gerçek kurumsal ortamda ek doğrulama gerekmektedir
- Büyük belge hacimlerinde (>10.000 chunk) BM25 indeksi yeniden oluşturma süresi artmaktadır
- LLM (Qwen3-8B) cevap üretimi GPU olmadan 30-60 saniye sürebilmektedir

---

## 12. Kaynakça

Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., Küttler, H., Lewis, M., Yih, W., Rocktäschel, T., Riedel, S., & Kiela, D. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. *Advances in Neural Information Processing Systems 33 (NeurIPS 2020)*. https://proceedings.neurips.cc/paper/2020/hash/6b493230205f780e1bc26945df7481e5-Abstract.html

Karpukhin, V., Oguz, B., Min, S., Lewis, P., Wu, L., Edunov, S., Chen, D., & Yih, W. (2020). Dense Passage Retrieval for Open-Domain Question Answering. *Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing (EMNLP)*, 6769–6781. https://aclanthology.org/2020.emnlp-main.550/

Robertson, S., & Zaragoza, H. (2009). The Probabilistic Relevance Framework: BM25 and Beyond. *Foundations and Trends in Information Retrieval*, 3(4), 333–389. https://dl.acm.org/doi/abs/10.1561/1500000019

Nogueira, R., & Cho, K. (2019). Passage Re-Ranking with BERT. *arXiv preprint arXiv:1901.04085*. https://arxiv.org/abs/1901.04085

Gao, L., Ma, X., Lin, J. J., & Callan, J. (2022). Precise Zero-Shot Dense Retrieval without Relevance Labels. *Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (ACL 2023)*. https://arxiv.org/abs/2212.10496

Yıldız, E., & Tantuğ, A. C. (2021). Advancing Natural Language Processing Applications of Morphologically Rich Languages with BERT: An Empirical Case Study for Turkish. *ResearchGate / Natural Language Engineering*. https://www.researchgate.net/publication/351386823

Zhao, T., ve ark. (2025). DAT: Dynamic Alpha Tuning for Hybrid Retrieval in Retrieval-Augmented Generation. *arXiv preprint arXiv:2503.23013*. https://arxiv.org/pdf/2503.23013

Hugging Face. (2024). Sentence Transformers Documentation. https://sbert.net

Qdrant. (2024). Qdrant Vector Database Documentation. https://qdrant.tech/documentation/

T.C. Kişisel Verileri Koruma Kurumu. (2016). 6698 Sayılı Kişisel Verilerin Korunması Kanunu. https://www.kvkk.gov.tr

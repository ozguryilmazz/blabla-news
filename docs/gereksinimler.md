# Haber Analiz Web Botu: Gereksinim Özeti (Taslak v1)

Tarih: 25 Eylül 2026 · Durum: Onay bekliyor

## 1. Amaç
Yunanistan ve İsrail'de yayın yapan kaynaklardan Türkiye ile ilgili haberleri sürekli bulan, Türkçeye aktaran, arşivleyen ve kategorileyen, geliştirmeye açık bir web sitesi.

## 2. Kaynaklar
- **1. aşama:** Haber siteleri (RSS ve web sayfaları).
  - Yunanistan: Kathimerini (Yunanca ve İngilizce), To Vima, Ta Nea, Proto Thema, Naftemporiki, ERT, Greek City Times
  - İsrail: Haaretz (İbranice ve İngilizce), Ynet ve Ynetnews, Maariv, Israel Hayom, Times of Israel, Jerusalem Post, i24News
- **2. aşama:** Sosyal medya. Yalnızca resmi kurumlar ve takipçi sayısı ile etkileşimi yüksek hesaplar.
- Yönetim panelinden yeni kaynak eklenip çıkarılabilir.

## 3. Diller
Yunanca, İbranice ve İngilizce. Arapça ileride eklenebilir.

## 4. Türkiye ile ilgili haberlerin tespiti
1. Her dilde anahtar kelimeyle ön eleme (Türkiye, Erdoğan, Ankara, Ege, Kıbrıs vb.).
2. Ucuz bir yapay zekâ modeliyle (Claude Haiku) "gerçekten Türkiye ile ilgili mi" kontrolü.

## 5. Türkçeleştirme ve içerik (telif uyumlu)
- Bire bir çeviri yapılmaz. Güçlü bir model (Claude Sonnet) haberi **Türkçe olarak yeniden yazar**: geniş bir özet ve önemli noktalar çıkarır.
- Her haberde **orijinal kaynağa link** bulunur.
- Orijinal taraf: yalnızca orijinal başlık ve kısa bir alıntı gösterilir, haberin tam metni yayınlanmaz.
  - Varsayılan olarak bunu seçtim. "Yan yana" görünüm şöyle olur: solda orijinal başlık, kısa alıntı ve link; sağda Türkçe başlık ve geniş özet.
- Tam orijinal metin yalnızca sistemin içinde, analiz için saklanır; sitede gösterilmez.

## 6. Kategoriler
- Siyaset ve Diplomasi, Savunma ve Güvenlik, Ekonomi ve Enerji, Kıbrıs, Ege ve Doğu Akdeniz, Göç, Kültür ve Toplum, Diğer.
- Tüm kategoriler mevcut olur, ancak **tarama öncesinde hangilerinin toplanacağı seçilebilir.** Seçilmeyen kategorideki haberler kaydedilmez.
- Kategori listesi panelden düzenlenebilir.

## 7. Güncelleme
- Otomatik tarama **saatte bir**.
- Panelde **"Şimdi tara"** (manuel güncelleme) düğmesi.
- Panelde **"Taramayı durdur / devam ettir"** düğmesi.

## 8. Arşiv ve arama
- Tüm haberler kalıcı olarak arşivlenir.
- Tarih, ülke, kaynak ve kategoriye göre filtreleme.
- Türkçe metinde ve orijinal dilde tam metin arama.

## 9. Bütçe
- Aylık toplam bütçe sınırı **50 €**.
- Sunucu için yaklaşık 5 ila 10 € ayrılır. Kalanı yapay zekâ kullanımına gider.
- Sistem aylık yapay zekâ harcamasını takip eder:
  - Sınıra yaklaşınca panelde uyarı gösterir.
  - Sınıra ulaşınca yeni çeviriyi durdurur, haberleri toplamaya devam eder. Bekleyen haberler bir sonraki ay çevrilir.

## 10. Yayın ve erişim
- **1. aşama:** Yerel bilgisayarda çalışır (Docker ile tek komutla).
- **2. aşama:** Sunucuya taşınır ve herkese açık olur. Yönetim paneli şifreyle korunur.
- **İleride:** Haberlerin alındığı ülkelerden (Yunanistan ve İsrail) erişim engellenir. Bu, Cloudflare gibi bir hizmetin ülke bazlı kurallarıyla yapılır. VPN kullanan ziyaretçiler bu engeli aşabilir.

## 11. Teknoloji
| Bileşen | Seçim |
|---|---|
| Toplayıcı bot ve arka uç | Python (FastAPI) |
| Veritabanı ve arama | PostgreSQL (tam metin arama) |
| Web sitesi | Next.js |
| Yapay zekâ | Claude Haiku (ayıklama), Claude Sonnet (Türkçeleştirme) |
| Çalıştırma | Docker Compose (yerelde ve sunucuda aynı) |
| Sunucu | Tek sanal sunucu (ör. Hetzner) ve Cloudflare |

## 12. Kapsam dışı (1. aşama)
Sosyal medya, Arapça, kullanıcı hesapları ve bildirimler (e-posta veya Telegram). Bunların hepsi sonraki aşamalarda eklenebilir.

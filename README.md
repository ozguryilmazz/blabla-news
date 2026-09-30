# Haber Analiz

Yunanistan ve İsrail'de yayın yapan kaynaklardan Türkiye ile ilgili haberleri düzenli olarak bulan, Türkçe olarak yeniden yazan, kategorileyen ve arşivleyen web sitesi.

Gereksinimler: [docs/gereksinimler.md](docs/gereksinimler.md)

## Nasıl çalışır

1. **Toplama:** Saatte bir (veya panelden "Şimdi tara" ile) tüm aktif kaynakların RSS beslemeleri okunur, yeni haberlerin metni sayfadan ayıklanır. Daha önce görülen haberler atlanır.
2. **Ön eleme:** Başlık ve metinde Yunanca, İbranice ve İngilizce anahtar kelimeler aranır (Türkiye, Erdoğan, Ankara, Ege…). Eşleşmeyen haberler yapay zekâya hiç gönderilmez.
3. **İlgi kontrolü:** Ucuz model (Claude Haiku 4.5) haberin gerçekten Türkiye ile ilgili olup olmadığına karar verir ve kategori atar.
4. **Kategori seçimi:** Panelde kapatılan kategorilerdeki haberler Türkçeleştirilmez.
5. **Türkçeleştirme:** Güçlü model (Claude Sonnet 5) haberi birebir çevirmeden, kendi cümleleriyle geniş bir Türkçe özet, önemli noktalar ve etiketler olarak yeniden yazar.
6. **Yayın:** Sitede solda orijinal başlık, kısa alıntı ve kaynak linki; sağda Türkçe özet gösterilir. Tam orijinal metin yalnızca veritabanında tutulur, sitede gösterilmez.

**Ücretsiz mod:** `ANTHROPIC_API_KEY` boşsa sistem otomatik olarak ücretsiz yönteme geçer. İlgi ve kategori anahtar kelimelerle belirlenir, başlık ve haberin giriş paragrafları ücretsiz servislerle Türkçeye çevrilir. Sıra: kendi LibreTranslate sunucunuz (ayarlıysa), Google Translate, MyMemory. Bir servis sınırına takılırsa o tarama boyunca atlanır ve sıradakine geçilir; hepsi doluysa haberler bekletilip sonraki taramada çevrilir. Özet ve önemli noktalar üretilmez; sitede "makine çevirisi" notu görünür. Anahtar eklenip sistem yeniden başlatıldığında Claude'a geri dönülür. `TRANSLATOR=free` ile anahtar olsa bile ücretsiz mod zorlanabilir.

- `MYMEMORY_EMAIL`: Bir e-posta adresi yazılırsa MyMemory'nin günlük sınırı 5.000'den 50.000 karaktere çıkar (yaklaşık 30 haber).
- Sınırsız yerel çeviri: `docker compose --profile ceviri up --build` ile LibreTranslate sunucusu da açılır (ilk açılışta dil modellerini indirir). `.env` içine `LIBRETRANSLATE_URL=http://libretranslate:5000` yazın.

**Bütçe:** Her yapay zekâ çağrısının maliyeti kaydedilir. Aylık sınıra (varsayılan 50 €, bunun 10 €'su sunucuya ayrılır) ulaşıldığında haberler toplanmaya devam eder, Türkçeleştirme bir sonraki ay kaldığı yerden sürer.

## Yerelde çalıştırma

Gerekenler: [Docker Desktop](https://www.docker.com/products/docker-desktop/). [Anthropic API anahtarı](https://console.anthropic.com) isteğe bağlıdır; yoksa ücretsiz çeviri kullanılır.

```bash
cp .env.example .env      # ANTHROPIC_API_KEY ve ADMIN_PASSWORD değerlerini doldurun
docker compose up --build
```

- Site: http://localhost:3000
- Yönetim paneli: http://localhost:3000/yonetim (şifre: `.env` içindeki `ADMIN_PASSWORD`)
- API belgeleri: http://localhost:8000/docs

İlk açılışta örnek kaynaklar ve kategoriler otomatik eklenir. İlk sonuçları görmek için panelden **Şimdi tara** düğmesine basın.

> Örnek kaynakların RSS adresleri geliştirme ortamından doğrulanamadı. Bir adres çalışmazsa panelde "Son hata" sütununda görünür; o kaynağı kapatıp doğru adresle yeniden ekleyebilirsiniz.

## Hızlı geliştirme modu

Her güncellemede yeniden derlemek yerine kod klasörleri kapsayıcılara bağlanabilir. `.env` dosyasına şu satırı ekleyin:

```
COMPOSE_FILE=docker-compose.yml;docker-compose.dev.yml
```

Bir kez `docker compose up -d` çalıştırın (ilk açılışta web paketleri kurulur). Bundan sonra güncellemek için `git pull` yeterli: arka uç ve site değişiklikleri birkaç saniye içinde kendiliğinden yüklenir, sayfayı yenilemeniz yeter. Yalnızca `requirements.txt` veya `package.json` değiştiğinde `docker compose up -d --build` gerekir. Sunucuya taşırken bu satır kaldırılır.

## Yönetim paneli

- **Şimdi tara / Durdur / Devam ettir:** Manuel tarama ve otomatik taramayı durdurma.
- **Bütçe:** Bu ayki yapay zekâ harcaması ve sınır.
- **Taranacak kategoriler:** Hangi kategorilerin yayınlanacağını seçme.
- **Kaynaklar:** Kaynak ekleme, kapatma, son hata durumunu görme.
- **Son taramalar:** Her taramada kaç yeni aday bulunduğu, kaç haberin yayınlandığı.

## Geliştirme

```bash
# Arka uç
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
pytest

# Web sitesi
cd frontend
npm install
API_URL=http://localhost:8000 npm run dev
```

| Dosya | İçerik |
|---|---|
| `backend/app/collector.py` | RSS okuma ve metin ayıklama |
| `backend/app/keywords.py` | Çok dilli anahtar kelime ön elemesi |
| `backend/app/ai.py` | Claude ile ilgi kontrolü ve Türkçe yeniden yazım |
| `backend/app/pipeline.py` | Tarama akışı |
| `backend/app/budget.py` | Maliyet hesabı ve aylık sınır |
| `backend/app/main.py` | API uçları |
| `frontend/app` | Haber listesi, haber sayfası, yönetim paneli |

## Sonraki aşamalar

- Sunucuya taşıma (Docker Compose ile aynı kurulum) ve alan adı
- Yunanistan ve İsrail'den erişimi engelleme (Cloudflare ülke kuralları)
- Sosyal medya kaynakları (resmi kurumlar, yüksek etkileşimli hesaplar)

"""İlk kurulumda örnek kaynakları ve kategorileri ekler (varsa dokunmaz).

RSS adresleri geliştirme ortamından doğrulanamadı; hatalı olanlar yönetim
panelinde "son hata" sütununda görünür ve oradan düzeltilebilir.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Category, Source

CATEGORIES = [
    ("siyaset-diplomasi", "Siyaset ve Diplomasi"),
    ("savunma-guvenlik", "Savunma ve Güvenlik"),
    ("ekonomi-enerji", "Ekonomi ve Enerji"),
    ("kibris", "Kıbrıs"),
    ("ege-dogu-akdeniz", "Ege ve Doğu Akdeniz"),
    ("goc", "Göç"),
    ("kultur-toplum", "Kültür ve Toplum"),
    ("diger", "Diğer"),
]

# (ad, ülke, dil, RSS adresi)
SOURCES = [
    ("Kathimerini", "GR", "el", "https://www.kathimerini.gr/rss"),
    ("eKathimerini", "GR", "en", "https://www.ekathimerini.com/rss"),
    ("To Vima", "GR", "el", "https://www.tovima.gr/feed/"),
    ("Ta Nea", "GR", "el", "https://www.tanea.gr/feed/"),
    ("Proto Thema", "GR", "el", "https://www.protothema.gr/rss/"),
    ("Naftemporiki", "GR", "el", "https://www.naftemporiki.gr/feed/"),
    ("ERT News", "GR", "el", "https://www.ertnews.gr/feed/"),
    ("Greek City Times", "GR", "en", "https://greekcitytimes.com/feed/"),
    ("Haaretz (İbranice)", "IL", "he", "https://www.haaretz.co.il/srv/htz---all-articles"),
    ("Haaretz (İngilizce)", "IL", "en", "https://www.haaretz.com/srv/haaretz-latest-headlines"),
    ("Ynet", "IL", "he", "https://www.ynet.co.il/Integration/StoryRss2.xml"),
    ("Ynetnews", "IL", "en", "https://www.ynetnews.com/Integration/StoryRss3089.xml"),
    ("Maariv", "IL", "he", "https://www.maariv.co.il/Rss/RssChadashot"),
    ("Israel Hayom (İbranice)", "IL", "he", "https://www.israelhayom.co.il/rss.xml"),
    ("Israel Hayom (İngilizce)", "IL", "en", "https://www.israelhayom.com/feed/"),
    ("Times of Israel", "IL", "en", "https://www.timesofisrael.com/feed/"),
    ("Jerusalem Post", "IL", "en", "https://www.jpost.com/rss/rssfeedsfrontpage.aspx"),
    ("i24News", "IL", "en", "https://www.i24news.tv/en/rss"),
]


def seed(session: Session) -> None:
    existing_slugs = set(session.scalars(select(Category.slug)))
    for order, (slug, name) in enumerate(CATEGORIES):
        if slug not in existing_slugs:
            session.add(Category(slug=slug, name=name, sort_order=order))

    existing_urls = set(session.scalars(select(Source.url)))
    for name, country, language, url in SOURCES:
        if url not in existing_urls:
            session.add(Source(name=name, country=country, language=language, url=url))

    session.commit()

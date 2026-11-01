"""キングス公式サイトのニュースと、公式 YouTube の新しい動画を読み、news.json を書き換える

GitHub Actions から update_schedule.py と一緒に1時間おきに起動される。内容が変わったときだけ書き換える。
- ニュース: https://goldenkings.jp/news/ の一覧(サムネイル・日付・見出し・タグ)
- 動画: YouTube のチャンネルのフィード(誰でも読める RSS)
片方が読めなくても、もう片方は更新する(読めなかった方は前の内容を残す)。

手元で試す:
  pip install requests beautifulsoup4
  python update_news.py
"""
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime

from bs4 import BeautifulSoup

from update_schedule import JST, fetch

NEWS_URLS = ["https://goldenkings.jp/news/", "https://goldenkings.jp/renewal_news/?pageID=2"]
YT_CHANNEL = "UCBUFfz9DwYS5nECTHql8mAQ"
YT_FEED = f"https://www.youtube.com/feeds/videos.xml?channel_id={YT_CHANNEL}"
NEWS_MAX, VIDEOS_MAX = 20, 12
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "news.json")


def parse_news(html):
    """一覧の1件(li.p-news__item)ごとに {title, url, date, tags, image} を返す。"""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for li in soup.select("li.p-news__item"):
        a = li.select_one("a[href]")
        h3 = li.select_one("h3")
        if not a or not h3:
            continue
        t = li.select_one("time")
        img = li.select_one("img[src]")
        out.append({
            "title": " ".join(h3.get_text(" ").split()),
            "url": a["href"],
            "date": (t.get_text(strip=True) if t else "").replace("/", "-"),
            "tags": [s.get_text(strip=True) for s in li.select(".p-news__tags .c-tag") if s.get_text(strip=True)],
            "image": img["src"] if img else "",
        })
    return out


def read_news():
    items, seen = [], set()
    for url in NEWS_URLS:
        try:
            page = parse_news(fetch(url))
        except Exception as e:
            print(f"[news] {url} を読めませんでした: {e}")
            continue
        for n in page:
            if n["url"] not in seen:
                seen.add(n["url"])
                items.append(n)
    # 新しい順(日付の無いものは後ろ)
    items.sort(key=lambda n: n["date"] or "", reverse=True)
    return items[:NEWS_MAX]


def read_videos():
    ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
          "media": "http://search.yahoo.com/mrss/"}
    root = ET.fromstring(fetch(YT_FEED).encode("utf-8"))
    out = []
    for e in root.findall("a:entry", ns):
        vid = (e.findtext("yt:videoId", default="", namespaces=ns) or "").strip()
        if not vid:
            continue
        thumb = e.find("media:group/media:thumbnail", ns)
        out.append({
            "id": vid,
            "title": (e.findtext("a:title", default="", namespaces=ns) or "").strip(),
            "published": (e.findtext("a:published", default="", namespaces=ns) or "").strip(),
            "thumb": thumb.get("url") if thumb is not None else f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
            "url": f"https://www.youtube.com/watch?v={vid}",
        })
    return out[:VIDEOS_MAX]


def main():
    try:
        with open(OUT, encoding="utf-8") as f:
            old = json.load(f)
    except Exception:
        old = {}
    news = read_news()
    try:
        videos = read_videos()
    except Exception as e:
        print(f"[youtube] 読めませんでした: {e}")
        videos = []
    print(f"ニュース {len(news)}件・動画 {len(videos)}本")
    news = news or old.get("news", [])
    videos = videos or old.get("videos", [])
    if not news and not videos:
        raise SystemExit("ニュースも動画も読めませんでした")
    if news == old.get("news") and videos == old.get("videos"):
        print("news.json に変更はありません")
        return
    data = {
        "updated": datetime.now(JST).strftime("%Y/%m/%d %H:%M"),
        "news": news,
        "videos": videos,
        "x": "https://x.com/RyukyuKings",
        "youtube": f"https://www.youtube.com/channel/{YT_CHANNEL}",
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("news.json を更新しました")


if __name__ == "__main__":
    main()

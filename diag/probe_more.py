"""調査用: 試合カードのチケット・配信リンクと、順位表ページの作り(一時的なもの)"""
import re
import requests
from bs4 import BeautifulSoup

H = {"User-Agent": "kings-next-game (personal use)"}
get = lambda u: requests.get(u, headers=H, timeout=30)

r = get("https://www.bleague.jp/schedule/?tab=1&year=2026&mon=11&day=07&event=&club=701&ha=&fb=")
soup = BeautifulSoup(r.text, "html.parser")
li = soup.select_one("li.list-item")
print("== card html:", re.sub(r"\s+", " ", str(li))[:4000] if li else None)
for m in list(re.finditer(r"micromodal|broadcast|放送|配信|LIVE", r.text))[:6]:
    print("-- ctx:", re.sub(r"\s+", " ", r.text[max(0, m.start() - 300):m.end() + 500]))

for url in ("https://www.bleague.jp/standings/?tab=1", "https://www.bleague.jp/standings/"):
    r = get(url)
    print(f"== {url} {r.status_code} len={len(r.text)}")
    soup = BeautifulSoup(r.text, "html.parser")
    for i, t in enumerate(soup.find_all("table")[:6]):
        rows = [[c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])] for tr in t.find_all("tr")[:5]]
        cap = t.find_previous(["h2", "h3", "h4", "p"])
        print(f"TABLE {i} before={cap.get_text(' ', strip=True)[:60] if cap else ''} rows={len(t.find_all('tr'))}")
        for row in rows:
            print("   ", " | ".join(row)[:300])
    i = r.text.find("琉球")
    print("-- around 琉球:", re.sub(r"\s+", " ", r.text[max(0, i - 1500):i + 800]))
    break

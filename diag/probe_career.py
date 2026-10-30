"""調査用: 選手ページの生年月日と通算成績(一時的なもの)"""
import re
import requests
from bs4 import BeautifulSoup

H = {"User-Agent": "kings-next-game (personal use)"}
for pid in ("26914", "8658"):
    r = requests.get(f"https://www.bleague.jp/roster_detail/?PlayerID={pid}", headers=H, timeout=30)
    soup = BeautifulSoup(r.text, "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    lines = [l.strip() for l in soup.get_text("\n").split("\n") if l.strip()]
    print(f"== {pid} len={len(r.text)}")
    for kw in ("生年月日", "誕生日", "出身", "身長"):
        for i, l in enumerate(lines):
            if kw in l:
                print(f"   {kw}:", " | ".join(lines[max(0, i - 2):i + 4]))
                break
    for i, t in enumerate(soup.find_all("table")[:12]):
        rows = [[c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])] for tr in t.find_all("tr")]
        prev = t.find_previous(["h2", "h3", "h4", "p", "button", "li"])
        print(f"   TABLE {i} rows={len(rows)} before={prev.get_text(' ', strip=True)[:40] if prev else ''}")
        for row in rows[:3] + rows[-2:]:
            print("      ", " | ".join(row)[:260])
    for kw in ("通算", "キャリア", "CAREER", "TOTAL"):
        i = r.text.find(kw)
        if i >= 0:
            print(f"   -- {kw}:", re.sub(r"\s+", " ", r.text[max(0, i - 200):i + 400]))

"""調査用: B.LEAGUE のキングス選手一覧ページの作りを調べる(一時的なもの)"""
import re
import requests
from bs4 import BeautifulSoup

H = {"User-Agent": "kings-next-game (personal use)"}
URLS = [
    "https://www.bleague.jp/roster/?tab=1&club=701",
    "https://www.bleague.jp/club_detail/?TeamID=701",
    "https://www.bleague.jp/club_detail/?TeamID=701&tab=2",
]
for url in URLS:
    try:
        r = requests.get(url, headers=H, timeout=30)
    except Exception as e:
        print("==", url, "ERR", e)
        continue
    html = r.text
    print(f"== {url} {r.status_code} len={len(html)} final={r.url}")
    pids = list(dict.fromkeys(re.findall(r"roster_detail/\?PlayerID=(\d+)", html)))
    print("   player ids:", len(pids), pids[:20])
    print("   links:", sorted(set(re.findall(r'href="([^"]*(?:roster|player|club_detail)[^"]*)"', html)))[:30])
    if pids:
        i = html.find("roster_detail/?PlayerID=" + pids[0])
        print("   html around first player:", re.sub(r"\s+", " ", html[max(0, i - 1500):i + 2500]))
        soup = BeautifulSoup(html, "html.parser")
        for t in soup(["script", "style"]):
            t.decompose()
        lines = [l.strip() for l in soup.get_text("\n").split("\n") if l.strip()]
        k = next((j for j, l in enumerate(lines) if "#" in l or "背番号" in l or "PG" in l or "ポジション" in l), 0)
        print("   text sample:", " | ".join(lines[max(0, k - 20):k + 120]))
    imgs = re.findall(r'<img[^>]+src="([^"]+)"[^>]*alt="([^"]*)"', html)
    print("   imgs sample:", [x for x in imgs if "player" in x[0].lower() or "roster" in x[0].lower()][:8])

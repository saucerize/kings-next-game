"""調査用: 選手のSNSが公式サイトに載っているか(一時的なもの)"""
import re
import requests

H = {"User-Agent": "kings-next-game (personal use)"}
SNS = re.compile(r'href="(https?://(?:www\.)?(?:twitter\.com|x\.com|instagram\.com|tiktok\.com|youtube\.com|facebook\.com|threads\.net|threads\.com)/[^"]*)"', re.I)


def probe(label, url, show=0):
    try:
        r = requests.get(url, headers=H, timeout=30)
    except Exception as e:
        print(f"== {label} ERR {e}")
        return ""
    links = sorted(set(SNS.findall(r.text)))
    print(f"== {label} {r.status_code} len={len(r.text)} final={r.url}")
    print("   sns links:", links[:30])
    if show:
        for m in list(re.finditer(r"(?i)sns|instagram|twitter|x\.com", r.text))[:show]:
            print("   -- ctx:", re.sub(r"\s+", " ", r.text[max(0, m.start() - 300):m.end() + 300]))
    return r.text


probe("bleague roster_detail 26914", "https://www.bleague.jp/roster_detail/?PlayerID=26914", show=4)
probe("bleague roster_detail 51000416", "https://www.bleague.jp/roster_detail/?PlayerID=51000416")
home = probe("club top", "https://goldenkings.jp/")
cands = sorted(set(re.findall(r'href="([^"]*(?:player|team|roster|member)[^"]*)"', home)))
print("club candidate links:", cands[:40])
for u in [c for c in cands if "player" in c or "roster" in c][:3]:
    if u.startswith("/"):
        u = "https://goldenkings.jp" + u
    html = probe(f"club {u}", u)
    sub = sorted(set(re.findall(r'href="([^"]*(?:player|roster)[^"]*/[^"]+)"', html)))
    print("   player links:", sub[:30])
    for s in sub[:2]:
        if s.startswith("/"):
            s = "https://goldenkings.jp" + s
        probe(f"club player {s}", s, show=3)
    break

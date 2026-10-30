"""調査用: クラブ公式サイトのダンサーズのページの作り(一時的なもの)"""
import re
import requests
from bs4 import BeautifulSoup

H = {"User-Agent": "kings-next-game (personal use)"}
SNS = re.compile(r'href="(https?://(?:www\.)?(?:twitter\.com|x\.com|instagram\.com|tiktok\.com|youtube\.com)/[^"]*)"', re.I)

r = requests.get("https://goldenkings.jp/team/dancers/", headers=H, timeout=30)
html = r.text
print(f"== dancers {r.status_code} len={len(html)} final={r.url}")
links = sorted(set(re.findall(r'href="([^"]*dancers[^"]*)"', html)))
print("dancer links:", links[:40])
print("sns:", sorted(set(SNS.findall(html)))[:20])
soup = BeautifulSoup(html, "html.parser")
for t in soup(["script", "style", "noscript"]):
    t.decompose()
text = [l.strip() for l in soup.get_text("\n").split("\n") if l.strip()]
i = next((k for k, l in enumerate(text) if "DANCERS" in l.upper() or "ダンサー" in l), 0)
print("text:", " | ".join(text[i:i + 150]))
imgs = re.findall(r'<img[^>]+(?:data-src|src)="([^"]+)"[^>]*alt="([^"]*)"', html)
print("imgs:", [x for x in imgs if "dancer" in x[0].lower() or "dancer" in x[1].lower()][:20])
m = re.search(r"dancers/detail", html)
if m:
    print("-- around first detail:", re.sub(r"\s+", " ", html[max(0, m.start() - 1500):m.start() + 1500]))
detail = [l for l in links if "detail" in l]
for u in detail[:2]:
    if u.startswith("/"):
        u = "https://goldenkings.jp" + u
    d = requests.get(u, headers=H, timeout=30).text
    s = BeautifulSoup(d, "html.parser")
    for t in s(["script", "style", "noscript"]):
        t.decompose()
    tx = [l.strip() for l in s.get_text("\n").split("\n") if l.strip()]
    print(f"== detail {u}")
    print("   sns:", sorted(set(SNS.findall(d)))[:10])
    j = next((k for k, l in enumerate(tx) if "プロフィール" in l or "PROFILE" in l.upper() or "誕生日" in l or "出身" in l), 0)
    print("   text:", " | ".join(tx[max(0, j - 15):j + 40]))

"""調査用: 終わった試合のボックススコアの置き場所を調べる(一時的なもの)"""
import json
import re
import requests

H = {"User-Agent": "kings-next-game (personal use)"}
KEY = "506413"   # 2026/10/3 の試合(終了済み)


def show(label, url):
    try:
        r = requests.get(url, headers=H, timeout=30)
        print(f"== {label} {r.status_code} {r.headers.get('content-type')} len={len(r.text)} {url}")
        return r
    except Exception as e:
        print(f"== {label} ERR {e} {url}")


def walk(o, path="", depth=0, out=None):
    if out is None:
        out = []
    if depth > 6 or len(out) > 120:
        return out
    if isinstance(o, dict):
        out.append(f"{path} {{{', '.join(list(o.keys())[:25])}}}")
        for k, v in list(o.items())[:30]:
            walk(v, f"{path}.{k}", depth + 1, out)
    elif isinstance(o, list):
        out.append(f"{path} [list x{len(o)}]")
        if o:
            walk(o[0], f"{path}[0]", depth + 1, out)
    return out


for base in ("https://b-league.s3.amazonaws.com", "http://b-league.s3.amazonaws.com"):
    r = show("genius", f"{base}/web_json/v2_genius_contexts/{KEY}")
    if r is not None and r.ok:
        try:
            j = r.json()
            print("\n".join(walk(j)))
            s = json.dumps(j, ensure_ascii=False)
            for kw in ("PTS", "Point", "PlayerName", "Boxscore", "BoxScore", "Stats"):
                i = s.find(kw)
                if i >= 0:
                    print(f"-- {kw}:", s[max(0, i - 300):i + 500])
        except Exception as e:
            print("not json:", r.text[:500])
        break

for tab in ("1", "4"):
    r = show(f"detail tab={tab}", f"https://www.bleague.jp/game_detail/?ScheduleKey={KEY}&tab={tab}")
    if r is not None:
        html = r.text
        print("   json-ish urls:", sorted(set(re.findall(r'["\'](https?://[^"\']*(?:json|api|genius|s3)[^"\']*)["\']', html)))[:20])
        heads = re.findall(r"<th[^>]*>\s*([^<]{1,10})\s*</th>", html)
        print("   th sample:", heads[:40])
        for kw in ("PTS", "ボックススコア", "BOX SCORE", "v2_genius", "playerstats", "BoxScore"):
            i = html.find(kw)
            if i >= 0:
                print(f"-- {kw}:", re.sub(r"\s+", " ", html[max(0, i - 400):i + 600]))

print("== rendered (playwright)")
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(locale="ja-JP")
    seen = []
    pg.on("response", lambda r: seen.append((r.status, r.url, r.headers.get("content-type"))) if (r.request.resource_type in ("xhr", "fetch") or "json" in (r.headers.get("content-type") or "")) else None)
    pg.goto(f"https://www.bleague.jp/game_detail/?ScheduleKey={KEY}&tab=4", wait_until="networkidle", timeout=90000)
    pg.wait_for_timeout(5000)
    for s in seen:
        if "wovn" not in s[1] and "google" not in s[1]:
            print("XHR", s)
    tables = pg.evaluate("""() => [...document.querySelectorAll('table')].map(t => [...t.querySelectorAll('tr')].slice(0, 4).map(tr => [...tr.querySelectorAll('th,td')].map(c => c.innerText.trim()).join(' | ')))""")
    for t in tables[:8]:
        print("TABLE", t)
    b.close()

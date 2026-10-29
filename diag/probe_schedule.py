"""調査用: B.LEAGUE のキングス日程ページの作りを調べてログに出す(一時的なもの)"""
import re
import requests

URL = "https://www.bleague.jp/schedule/?tab=1&club=701"
H = {"User-Agent": "kings-next-game (personal use)"}

html = requests.get(URL, headers=H, timeout=30).text
print("== static html", len(html))
print("keys:", list(dict.fromkeys(re.findall(r"ScheduleKey=(\d+)", html))))
print("schedule links:", sorted(set(re.findall(r'href="([^"]*schedule[^"]*)"', html)))[:40])
print("scripts:", re.findall(r'<script[^>]+src="([^"]+)"', html)[:30])
print("api-ish:", sorted(set(re.findall(r'["\'](https?://[^"\']*(?:api|json|ajax)[^"\']*|/[^"\'\s]*(?:api|json|ajax)[^"\'\s]*)["\']', html)))[:40])
for kw in ("ScheduleKey", "club=701", "month", "season", "Ajax", "fetch("):
    for m in list(re.finditer(re.escape(kw), html))[:3]:
        print(f"-- ctx {kw}:", html[max(0, m.start() - 200):m.end() + 200].replace("\n", " "))

print("== rendered")
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(locale="ja-JP")
    seen = []

    def on_resp(r):
        rt = r.request.resource_type
        if rt in ("xhr", "fetch") or "json" in (r.headers.get("content-type") or ""):
            try:
                body = r.text()
            except Exception:
                body = ""
            seen.append((r.status, r.request.method, r.url, r.headers.get("content-type"), len(body), body[:600].replace("\n", " ")))
    pg.on("response", on_resp)
    pg.goto(URL, wait_until="networkidle", timeout=90000)
    pg.wait_for_timeout(5000)
    for s in seen:
        print("XHR", s[:5])
        print("    ", s[5])
    keys = pg.evaluate("""() => [...document.querySelectorAll('a[href*="ScheduleKey"]')].map(a => [a.href.match(/ScheduleKey=(\\d+)/)[1], a.innerText.replace(/\\s+/g,' ').slice(0,120)])""")
    print("rendered keys:", len(keys))
    for k in keys[:25]:
        print("  ", k)
    links = pg.evaluate("""() => [...new Set([...document.querySelectorAll('a[href*="schedule"]')].map(a => a.href))].slice(0,40)""")
    print("rendered schedule links:", links)
    text = pg.evaluate("() => document.body.innerText")
    i = text.find("TIP OFF")
    print("text around first TIP OFF:", text[max(0, i - 800):i + 1500] if i >= 0 else text[:2000])
    b.close()

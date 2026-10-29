"""調査用(2回目): 日付を選んだときの動きと、月ごとのページを調べる(一時的なもの)"""
import re
import requests

H = {"User-Agent": "kings-next-game (personal use)"}
BASE = "https://www.bleague.jp/schedule/"


def get(url):
    r = requests.get(url, headers=H, timeout=30)
    return r.status_code, r.text


def summary(label, url):
    code, html = get(url)
    days = re.findall(r'data-day="(\d+)"', html)
    keys = list(dict.fromkeys(re.findall(r"ScheduleKey=(\d+)", html)))
    print(f"== {label} {code} len={len(html)} url={url}")
    print("   days:", days)
    print("   keys:", keys)
    for m in list(re.finditer(r'class="[^"]*(?:active|current|is-select|selected)[^"]*"[^>]*data-day="(\d+)"', html))[:3]:
        print("   active day:", m.group(1))
    return html


html = summary("default", BASE + "?tab=1&club=701")
summary("nov", BASE + "?tab=1&year=2026&mon=11&event=&club=701&ha=&fb=")
summary("oct", BASE + "?tab=1&year=2026&mon=10&event=&club=701&ha=&fb=")
for q in ("day=03", "dy=03", "date=20261003", "date=2026-10-03", "d=03"):
    summary(q, BASE + f"?tab=1&year=2026&mon=10&{q}&event=&club=701&ha=&fb=")

for js in re.findall(r'<script[^>]+src="([^"]+(?:function_new2208|genius_schedule|common_slider)[^"]*)"', html):
    code, src = get(js)
    print(f"== js {js} {code} len={len(src)}")
    for kw in ("js_click_data", "data-day", "ajax", "$.get", "fetch(", "location", "schedule"):
        for m in list(re.finditer(re.escape(kw), src))[:4]:
            print(f"-- {kw}:", src[max(0, m.start() - 300):m.end() + 400].replace("\n", " "))

# 日付一覧のまわりと、試合カードのまわりのHTML
i = html.find("js_click_data")
print("== strip html:", html[i - 300:i + 600].replace("\n", " "))
i = html.find("ScheduleKey")
print("== card html:", re.sub(r"\s+", " ", html[i - 1500:i + 2500]))
for kw in ("js_click_data", "data-day", "schedule_list", "game_list"):
    for m in list(re.finditer(r"<script(?![^>]*src)[^>]*>(.*?)</script>", html, re.S)):
        if kw in m.group(1):
            print(f"== inline script with {kw}:", re.sub(r"\s+", " ", m.group(1))[:3000])
            break

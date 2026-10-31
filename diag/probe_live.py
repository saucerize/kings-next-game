"""調査用: 試合中の速報が送られているか、公式サイトで試合が始まっているか(一時的なもの)"""
import json
import requests

H = {"User-Agent": "kings-next-game (personal use)"}
r = requests.get("https://ntfy.sh/kings-live-a38853caea/json?poll=1&since=2h", headers=H, timeout=30)
print("== ntfy live", r.status_code, "messages:", len([l for l in r.text.splitlines() if l.strip()]))
for line in r.text.splitlines()[-3:]:
    m = json.loads(line)
    print("   ", m.get("time"), (m.get("message") or "")[:300])
key = "506531"
base = f"https://b-league.s3.amazonaws.com/web_json/v2_genius_contexts/{key}/"
lid = requests.get(base + "latestid", headers=H, timeout=30)
print("== genius latestid", lid.status_code, lid.text[:40])
if lid.ok and lid.text.strip().isdigit():
    j = requests.get(base + lid.text.strip() + ".json", headers=H, timeout=30).json()
    g = j.get("Game", {})
    print("   period", g.get("GameCurrentPeriod"), "ended", g.get("GameEndedFlg"), "plays", len(j.get("PlayByPlays") or []))
    for p in (j.get("PlayByPlays") or [])[-3:]:
        print("   play", p.get("Period"), p.get("RestTime"), p.get("Score"), p.get("PlayText"))
html = requests.get(f"https://www.bleague.jp/game_detail/?ScheduleKey={key}&tab=1", headers=H, timeout=30).text
import re
i = html.find("TIP OFF")
print("== detail around TIP OFF:", re.sub(r"<[^>]+>", " ", html[max(0, i - 600):i + 300]).split()[:60])

"""schedule.json(これからの試合)と games.json(終わった試合)から、カレンダー用の calendar.ics を作る

iPhone などのカレンダーで webcal:// のアドレスを「照会(購読)」すると、試合予定が自動で入る。
GitHub Actions で他の更新スクリプトのあとに起動される。内容が同じなら書き換えない
(DTSTAMP も試合開始時刻にそろえて、毎回ファイルが変わらないようにしている)。
"""
import json
import os
from datetime import datetime, timedelta, timezone

DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(DIR, "calendar.ics")
GAME_LENGTH = timedelta(hours=2)


def load(name):
    try:
        with open(os.path.join(DIR, name), encoding="utf-8") as f:
            return json.load(f).get("games", [])
    except Exception:
        return []


def esc(s):
    return str(s).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def utc(dt):
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def fold(line):
    """iCalendar は1行75バイトまで。超える分は折り返す。"""
    out, cur = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        if len(cur) + len(b) > 74:
            out.append(cur.decode("utf-8"))
            cur = b" "
        cur += b
    out.append(cur.decode("utf-8"))
    return "\r\n".join(out)


def key_of(g):
    url = g.get("url", "")
    return url.split("ScheduleKey=")[1].split("&")[0] if "ScheduleKey=" in url else g["datetime"]


def main():
    events = {}
    for g in load("schedule.json"):
        events[g["datetime"]] = {
            "uid": key_of(g),
            "start": datetime.fromisoformat(g["datetime"]),
            "summary": f"🏀 キングス vs {g['opponent']}（{'HOME' if g.get('home') else 'AWAY'}）",
            "location": g.get("venue", ""),
            "url": g.get("url", ""),
            "desc": "\n".join(x for x in (f"チケット: {g['ticket']}" if g.get("ticket") else "",
                                          f"ライブ配信: {g['live']}" if g.get("live") else "") if x),
        }
    for g in load("games.json"):   # 終わった試合は結果入りで上書き
        win = g["kings"] > g["opp"]
        events[g["datetime"]] = {
            "uid": g.get("key") or g["datetime"],
            "start": datetime.fromisoformat(g["datetime"]),
            "summary": f"🏀 キングス {g['kings']}-{g['opp']} {g['opponent']}（{'勝' if win else '負'}）",
            "location": "",
            "url": g.get("url", ""),
            "desc": "",
        }

    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//kings-next-game//JA", "CALSCALE:GREGORIAN",
             "METHOD:PUBLISH", "X-WR-CALNAME:琉球ゴールデンキングス 試合", "X-WR-TIMEZONE:Asia/Tokyo"]
    for e in sorted(events.values(), key=lambda e: e["start"]):
        lines += ["BEGIN:VEVENT",
                  f"UID:{e['uid']}@kings-next-game",
                  f"DTSTAMP:{utc(e['start'])}",
                  f"DTSTART:{utc(e['start'])}",
                  f"DTEND:{utc(e['start'] + GAME_LENGTH)}",
                  f"SUMMARY:{esc(e['summary'])}"]
        if e["location"]:
            lines.append(f"LOCATION:{esc(e['location'])}")
        if e["url"]:
            lines.append(f"URL:{e['url']}")
        if e["desc"]:
            lines.append(f"DESCRIPTION:{esc(e['desc'])}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    text = "\r\n".join(fold(l) for l in lines) + "\r\n"

    try:
        with open(OUT, encoding="utf-8", newline="") as f:
            if f.read() == text:
                print("calendar.ics に変更はありません")
                return
    except FileNotFoundError:
        pass
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(f"calendar.ics を更新しました({len(events)}試合)")


if __name__ == "__main__":
    main()

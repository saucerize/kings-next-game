"""B.LEAGUE 公式サイトから琉球ゴールデンキングスの選手一覧を読み、players.json を書き換える

GitHub Actions から update_schedule.py と一緒に起動される。選手が変わったときだけファイルを書き換える。

手元で試す:
  pip install requests beautifulsoup4
  python update_players.py
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

JST = timezone(timedelta(hours=9))
ROSTER_URL = "https://www.bleague.jp/roster/?tab=1&club=701"
HEADERS = {"User-Agent": "kings-next-game (personal use)"}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "players.json")
MIN_PLAYERS = 5   # これより少なければ読み取り失敗とみなす


def parse_roster(html):
    """選手一覧ページから [{id, name, number, position, photo, url}] を背番号順で返す。"""
    soup = BeautifulSoup(html, "html.parser")
    players, seen = [], set()
    for a in soup.select("a.playerInfo-player"):
        m = re.search(r"PlayerID=(\d+)", a.get("href", ""))
        name_el = a.select_one(".playerInfo-player-name")
        if not m or not name_el or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        pos_el = a.select_one(".playerInfo-player-position span")
        pos_text = pos_el.get_text(" ", strip=True) if pos_el else ""
        num = re.search(r"#\s*(\d+)", pos_text)
        position = re.sub(r"#\s*\d+", "", pos_text).strip()
        # 背景のクラブロゴではなく、選手の写真(遅延読み込みで data-src に入っている)
        img = a.select_one("img[data-src]")
        players.append({
            "id": m.group(1),
            "name": re.sub(r"\s+", " ", name_el.get_text(" ", strip=True)),
            "number": int(num.group(1)) if num else None,
            "position": position,
            "photo": img["data-src"] if img else "",
            "url": a["href"],
        })
    players.sort(key=lambda p: (p["number"] is None, p["number"] if p["number"] is not None else 0))
    return players


def load_old():
    try:
        with open(OUT, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def main():
    r = requests.get(ROSTER_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    players = parse_roster(r.text)
    for p in players:
        print(f"[player] #{p['number']} {p['name']} {p['position']}")
    if len(players) < MIN_PLAYERS:
        sys.exit(f"選手を {len(players)} 人しか読み取れませんでした(ページの形が変わった可能性があります)")

    if players == load_old().get("players"):
        print("選手一覧に変更はありません")
        return
    data = {
        "team": "琉球ゴールデンキングス",
        "updated": datetime.now(JST).strftime("%Y/%m/%d %H:%M"),
        "source": ROSTER_URL,
        "players": players,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"players.json を更新しました({len(players)}人)")


if __name__ == "__main__":
    main()

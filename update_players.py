"""B.LEAGUE 公式サイトから琉球ゴールデンキングスの選手一覧を読み、players.json を書き換える

GitHub Actions から update_schedule.py と一緒に起動される。選手が変わったときだけファイルを書き換える。
選手の SNS は、B.LEAGUE 公式の選手ページに載っているものだけを使う(1日1回読み直す)。

手元で試す:
  pip install requests beautifulsoup4
  python update_players.py
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

JST = timezone(timedelta(hours=9))
ROSTER_URL = "https://www.bleague.jp/roster/?tab=1&club=701"
HEADERS = {"User-Agent": "kings-next-game (personal use)"}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "players.json")
MIN_PLAYERS = 5   # これより少なければ読み取り失敗とみなす

SNS_RE = re.compile(r'href="(https?://(?:www\.)?(x\.com|twitter\.com|instagram\.com|tiktok\.com|youtube\.com|'
                    r'facebook\.com|threads\.net|threads\.com)/[^"]+)"', re.I)
SNS_NAMES = {"x.com": "X", "twitter.com": "X", "instagram.com": "Instagram", "tiktok.com": "TikTok",
             "youtube.com": "YouTube", "facebook.com": "Facebook", "threads.net": "Threads", "threads.com": "Threads"}


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


def page_sns(html):
    """選手ページにある SNS のリンクを [(種類, URL)] で返す(ページ共通のものも含む)。"""
    out = []
    for url, host in SNS_RE.findall(html):
        url = url.split("?")[0].rstrip("/")
        if (SNS_NAMES[host.lower()], url) not in out:
            out.append((SNS_NAMES[host.lower()], url))
    return out


def fetch_sns(players):
    """各選手の B.LEAGUE 公式ページから SNS を読み、選手ID → [{type, url}] を返す。
    どの選手のページにも出てくるリンクは B.LEAGUE やクラブの公式アカウントなので除く。"""
    found = {}
    for p in players:
        time.sleep(0.5)
        try:
            r = requests.get(p["url"], headers=HEADERS, timeout=30)
            r.raise_for_status()
            found[p["id"]] = page_sns(r.text)
        except Exception as e:
            print(f"[sns] {p['name']}: 読めませんでした({e})")
    if len(found) < MIN_PLAYERS:
        return None
    count = {}
    for links in found.values():
        for link in links:
            count[link] = count.get(link, 0) + 1
    common = {link for link, n in count.items() if n > len(found) / 2}
    return {pid: [{"type": t, "url": u} for t, u in links if (t, u) not in common]
            for pid, links in found.items()}


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

    old = load_old()
    today = datetime.now(JST).strftime("%Y-%m-%d")
    old_sns = {p["id"]: p["sns"] for p in old.get("players", []) if "sns" in p}
    sns_date = old.get("sns_date")
    # SNS は1日1回、または新しい選手が加わったときだけ読み直す
    if sns_date != today or any(p["id"] not in old_sns for p in players):
        sns = fetch_sns(players)
        if sns is not None:
            old_sns, sns_date = sns, today
    for p in players:
        p["sns"] = old_sns.get(p["id"], [])
        if p["sns"]:
            print(f"[sns] {p['name']}: " + " / ".join(f"{x['type']} {x['url']}" for x in p["sns"]))

    if players == old.get("players") and sns_date == old.get("sns_date"):
        print("選手一覧に変更はありません")
        return
    data = {
        "team": "琉球ゴールデンキングス",
        "updated": datetime.now(JST).strftime("%Y/%m/%d %H:%M"),
        "source": ROSTER_URL,
        "sns_date": sns_date,
        "players": players,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"players.json を更新しました({len(players)}人)")


if __name__ == "__main__":
    main()

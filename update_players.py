"""B.LEAGUE 公式サイトから琉球ゴールデンキングスの選手一覧を読み、players.json を書き換える

GitHub Actions から update_schedule.py と一緒に起動される。選手が変わったときだけファイルを書き換える。
選手の SNS・生年月日・B.LEAGUE 通算成績は、B.LEAGUE 公式の選手ページから読む(1日1回読み直す)。
SNS はそのページに載っているものだけを使う。

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


def page_birthday(soup):
    """「生年月日」の次の行(例「1990年3月23日｜36歳」)から "1990-03-23" を返す。"""
    lines = [l.strip() for l in soup.get_text("\n").split("\n") if l.strip()]
    for i, l in enumerate(lines):
        if l == "生年月日" and i + 1 < len(lines):
            m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", lines[i + 1])
            if m:
                return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return ""


def page_career(soup):
    """シーズンごとの合計成績の表から、(B.LEAGUE 通算, 今シーズン) を
    {games, pts, reb, ast} で返す。読めなければ (None, None)。"""
    num = lambda v: int(v) if v.isdigit() else 0
    for t in soup.find_all("table"):
        rows = [[c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])] for tr in t.find_all("tr")]
        head = next((r for r in rows if "SEASON" in r and "PTS" in r and "G" in r), None)
        if head is None:
            continue
        idx = {k: head.index(k) for k in ("SEASON", "TYPE", "G", "PTS", "TR", "AS") if k in head}
        if len(idx) < 6:
            continue
        seasons = [r for r in rows if len(r) == len(head) and re.match(r"^\d{4}-\d{2}$", r[idx["SEASON"]])
                   and r[idx["TYPE"]].startswith("B")]   # B1・B2・B.PREMIER(BP)などのリーグ戦だけ
        if not seasons:
            continue
        stat = lambda rs: {"games": sum(num(r[idx["G"]]) for r in rs), "pts": sum(num(r[idx["PTS"]]) for r in rs),
                           "reb": sum(num(r[idx["TR"]]) for r in rs), "ast": sum(num(r[idx["AS"]]) for r in rs)}
        latest = max(r[idx["SEASON"]] for r in seasons)
        return stat(seasons), stat([r for r in seasons if r[idx["SEASON"]] == latest])
    return None, None


def fetch_details(players):
    """各選手の B.LEAGUE 公式ページから、選手ID → {sns, birthday, career, season} を返す。
    SNS は、どの選手のページにも出てくるリンク(B.LEAGUE やクラブの公式アカウント)を除く。"""
    found = {}
    for p in players:
        time.sleep(0.5)
        try:
            r = requests.get(p["url"], headers=HEADERS, timeout=30)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            for x in soup(["script", "style", "noscript"]):
                x.decompose()
            career, season = page_career(soup)
            found[p["id"]] = {"sns": page_sns(r.text), "birthday": page_birthday(soup),
                              "career": career, "season": season}
        except Exception as e:
            print(f"[detail] {p['name']}: 読めませんでした({e})")
    if len(found) < MIN_PLAYERS:
        return None
    count = {}
    for d in found.values():
        for link in d["sns"]:
            count[link] = count.get(link, 0) + 1
    common = {link for link, n in count.items() if n > len(found) / 2}
    for d in found.values():
        d["sns"] = [{"type": t, "url": u} for t, u in d["sns"] if (t, u) not in common]
    return found


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
    keys = ("sns", "birthday", "career", "season")
    old_details = {p["id"]: {k: p.get(k) for k in keys} for p in old.get("players", []) if "career" in p}
    details_date = old.get("details_date")
    # 選手ページは1日1回(日付が変わって最初の更新)、または新しい選手が加わったときだけ読み直す
    if details_date != today or any(p["id"] not in old_details for p in players):
        details = fetch_details(players)
        if details is not None:
            old_details, details_date = details, today
    for p in players:
        d = old_details.get(p["id"], {})
        p["sns"] = d.get("sns") or []
        p["birthday"] = d.get("birthday") or ""
        p["career"] = d.get("career")
        p["season"] = d.get("season")
        print(f"[detail] {p['name']}: 誕生日 {p['birthday'] or '?'} 通算 {p['career']} "
              + " / ".join(f"{x['type']} {x['url']}" for x in p["sns"]))

    if players == old.get("players") and details_date == old.get("details_date"):
        print("選手一覧に変更はありません")
        return
    data = {
        "team": "琉球ゴールデンキングス",
        "updated": datetime.now(JST).strftime("%Y/%m/%d %H:%M"),
        "source": ROSTER_URL,
        "details_date": details_date,
        "players": players,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"players.json を更新しました({len(players)}人)")


if __name__ == "__main__":
    main()

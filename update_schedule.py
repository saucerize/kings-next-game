"""B.LEAGUE 公式サイトから琉球ゴールデンキングスの試合予定を読み、schedule.json を書き換える

GitHub Actions から定期的に起動される。予定が変わったときだけファイルを書き換える。
読み取り方は kings-notify の notifier.py と同じ。

手元で試す:
  pip install requests beautifulsoup4
  python update_schedule.py
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
KINGS_ID = 701
KINGS_NAME = "琉球"
BASE = "https://www.bleague.jp"
SCHEDULE_URL = BASE + "/schedule/?tab=1&club={club}"
# 日程ページは月ごとで、1回に表示されるのは選んだ日の試合だけ。日付一覧にはキングスの試合日が並ぶ
DAY_URL = BASE + "/schedule/?tab=1&year={y}&mon={m:02d}&day={d:02d}&event=&club={club}&ha=&fb="
MONTH_URL = BASE + "/schedule/?tab=1&year={y}&mon={m:02d}&event=&club={club}&ha=&fb="
DETAIL_URL = BASE + "/game_detail/?ScheduleKey={key}&tab=1"
HEADERS = {"User-Agent": "kings-next-game (personal use)"}

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schedule.json")
MAX_KEYS = 12                 # 最大何試合ぶん詳細ページを読むか
MAX_GAMES = 5                 # schedule.json に書く試合数
GAME_LENGTH = timedelta(hours=2, minutes=30)  # index.html の GAME_LENGTH_MS と同じ


# ---------------------------------------------------------------- 取得・解析
def fetch(url, tries=4):
    """公式サイトの読み込み。一時的な失敗(混雑・通信切れ)なら少し待ってやり直す。"""
    for i in range(tries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
            return r.text
        except Exception as e:
            if i == tries - 1:
                raise
            print(f"[fetch] 失敗、やり直します({i + 1}/{tries - 1}): {e}")
            time.sleep(5 * (i + 1))


def text_lines(html):
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    return [ln.strip() for ln in soup.get_text("\n").split("\n") if ln.strip()]


def schedule_keys(html):
    seen, out = set(), []
    for k in re.findall(r"game_detail/\?ScheduleKey=(\d+)", html):
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def game_days(html):
    """月のページの日付一覧から、試合のある日(数字)を返す。"""
    days = re.findall(r'js-schedule-date-slider-item[^>]*>\s*<a[^>]*data-day="(\d+)"', html)
    return sorted({int(d) for d in days})


def upcoming_keys(now):
    """今日以降のキングスの試合の ScheduleKey を、日付の近い順に返す。"""
    keys = schedule_keys(fetch(SCHEDULE_URL.format(club=KINGS_ID)))  # 何も選ばないと次の試合の日が出る
    y, m = now.year, now.month
    for _ in range(2):  # 今月と来月
        for d in game_days(fetch(MONTH_URL.format(y=y, m=m, club=KINGS_ID))):
            if (y, m, d) < (now.year, now.month, now.day):
                continue
            time.sleep(1)
            keys += schedule_keys(fetch(DAY_URL.format(y=y, m=m, d=d, club=KINGS_ID)))
            if len(dict.fromkeys(keys)) >= MAX_KEYS:
                return list(dict.fromkeys(keys))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return list(dict.fromkeys(keys))


SCORE_RE = re.compile(r"^(\d{1,3}|--|-)$")
DATE_RE = re.compile(r"^(\d{4})\.(\d{1,2})\.(\d{1,2})")
LEAGUE_RE = re.compile(r"^(B\.?[A-Z0-9]*|B[123]|B\.(PREMIER|ONE|NEXT)|ホーム|アウェイ)$", re.I)
VENUE_RE = re.compile(r"アリーナ|体育館|ドーム|ホール|センター|会館|ジム|コロシアム|ARENA|Arena|GYM|Gym|DOME|Dome")


def _team_before(L, idx, stop):
    """HOME/AWAY の行から上にさかのぼり、(正式名, 略称) を返す。"""
    names = []
    for j in range(idx - 1, stop, -1):
        x = L[j]
        if SCORE_RE.match(x) or "位" in x or "｜" in x or "|" in x or LEAGUE_RE.match(x):
            continue
        names.append(x)
        if len(names) == 2:
            break
    if len(names) < 2:
        raise ValueError("チーム名が見つからない")
    short, full = names
    return full, short


def find_venue(L, lo, hi, teams):
    """試合見出しのまわりから会場名を探す。見つからなければ空文字。"""
    for i in range(lo, min(hi, len(L))):
        x = L[i]
        m = re.match(r"^会場\s*[:：]?\s*(.*)$", x)
        if m:
            return m.group(1) or (L[i + 1] if i + 1 < len(L) else "")
    for i in range(lo, min(hi, len(L))):
        x = L[i]
        if DATE_RE.match(x):  # 「2026.11.01 SUN 沖縄サントリーアリーナ」のように日付と同じ行にある場合
            x = re.sub(r"^\d{4}\.\d{1,2}\.\d{1,2}\S*\s*(\([^)]*\)|[A-Z]{3})?\s*", "", x)
        if x and x not in teams and len(x) <= 40 and VENUE_RE.search(x):
            return x
    return ""


def parse_game(key, html):
    L = text_lines(html)
    di = next((i for i, l in enumerate(L) if DATE_RE.match(l)), None)
    if di is None:
        raise ValueError("試合日の行が見つからない")
    y, mo, d = map(int, DATE_RE.match(L[di]).groups())

    hi = next(i for i in range(di, len(L)) if L[i] == "HOME")
    wi = next(i for i in range(hi + 1, len(L)) if L[i] == "AWAY")
    home_full, home_short = _team_before(L, hi, di)

    tip = None
    for i in range(hi, wi):
        if re.search(r"TIP\s*OFF", L[i], re.I):
            m = re.search(r"(\d{1,2}):(\d{2})", L[i]) or re.search(r"(\d{1,2}):(\d{2})", L[i - 1])
            if m:
                tip = datetime(y, mo, d, int(m.group(1)), int(m.group(2)), tzinfo=JST)
            break
    stop = next((i for i in range(wi - 1, hi, -1) if re.search(r"TIP\s*OFF|^VS$", L[i], re.I)), hi)
    away_full, away_short = _team_before(L, wi, stop)

    home = KINGS_NAME in home_full
    teams = {home_full, home_short, away_full, away_short}
    return {
        "key": key,
        "tipoff": tip,
        "opponent": away_full if home else home_full,
        "home": home,
        "venue": find_venue(L, max(0, di - 5), wi + 15, teams),
    }


# ---------------------------------------------------------------- schedule.json
def load_old():
    try:
        with open(OUT, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def main():
    now = datetime.now(JST)
    keys = upcoming_keys(now)[:MAX_KEYS]
    print(f"[keys] {keys}")
    if not keys:
        sys.exit("予定一覧に試合が見つかりませんでした(ページの形が変わった可能性があります)")

    games, parsed = [], 0
    for key in keys:
        time.sleep(1)
        try:
            g = parse_game(key, fetch(DETAIL_URL.format(key=key)))
        except Exception as e:
            print(f"[skip] {key}: {e}")
            continue
        parsed += 1
        print(f"[read] {key}: {g['tipoff']} {'HOME' if g['home'] else 'AWAY'} "
              f"vs {g['opponent']} @ {g['venue'] or '(会場不明)'}")
        if g["tipoff"] is None:
            print(f"[skip] {key}: 開始時刻が未定")
            continue
        if g["tipoff"] + GAME_LENGTH > now:
            games.append(g)
            if len(games) >= MAX_GAMES:
                break
    if parsed == 0:
        sys.exit("どの試合ページも読み取れませんでした(ページの形が変わった可能性があります)")

    old = load_old()
    old_venues = {(g.get("datetime"), g.get("opponent"), g.get("home")): g.get("venue")
                  for g in old.get("games", [])}

    games.sort(key=lambda g: g["tipoff"])
    out_games = []
    for g in games[:MAX_GAMES]:
        dt = g["tipoff"].isoformat()
        out_games.append({
            "datetime": dt,
            "opponent": g["opponent"],
            # 会場が読めなかったときは、前回の内容があればそれを使う
            "venue": g["venue"] or old_venues.get((dt, g["opponent"], g["home"])) or "",
            "home": g["home"],
            "url": DETAIL_URL.format(key=g["key"]),
        })

    if out_games == old.get("games"):
        print("予定に変更はありません")
        return

    data = {
        "team": "琉球ゴールデンキングス",
        "note": f"B.LEAGUE 公式サイトから自動で更新しています（最終更新 {now:%Y/%m/%d %H:%M}）",
        "games": out_games,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"schedule.json を更新しました({len(out_games)}試合)")


if __name__ == "__main__":
    main()

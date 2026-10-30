"""B.LEAGUE 公式サイトから、今シーズンの終わった試合のキングスの選手別成績を読み、games.json に書く

GitHub Actions から update_schedule.py と一緒に起動される。新しく終わった試合だけ読み足す。
シーズンの合計・平均はページ側で games.json から計算する。
ボックススコアの数字はページ上の JavaScript で描かれるため、新しい試合があるときだけ
ヘッドレスブラウザ(Playwright)を用意して読む。

手元で試す:
  pip install requests beautifulsoup4
  python update_stats.py
"""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from update_schedule import (DAY_URL, DETAIL_URL, JST, KINGS_ID, MONTH_URL, fetch,
                             game_days, parse_game, schedule_keys)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "games.json")
FINISHED_AFTER = timedelta(hours=3)   # 試合開始からこの時間たったら終わったとみなす
STATS = {"MIN": "min", "PTS": "pts", "TR": "reb", "AS": "ast"}


def season_months(now):
    """今シーズン(9月始まり)の、9月から今月までの (年, 月) を返す。"""
    y, m = (now.year, 9) if now.month >= 9 else (now.year - 1, 9)
    out = []
    while (y, m) <= (now.year, now.month):
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def team_tables(html):
    """ボックススコアのうち、試合全体の2つの表(ホーム, アウェイ)を返す。
    各表は [{"number", "starter", "name", "position", "min", "pts", "reb", "ast"}]。"""
    soup = BeautifulSoup(html, "html.parser")
    tables = []
    for t in soup.find_all("table"):
        rows = t.find_all("tr")
        head = next((r for r in rows if r.find(string=re.compile(r"^\s*PTS\s*$"))), None)
        if head is None:
            continue
        cols = [c.get_text(strip=True) for c in head.find_all(["th", "td"])]
        players = []
        for r in rows:
            cells = [c.get_text(" ", strip=True) for c in r.find_all(["th", "td"])]
            if r is head or len(cells) < len(cols) or not cells[0].isdigit():
                continue
            off = len(cells) - len(cols)   # 「#」「S」の列は2段目の見出しに無いぶん、ずれる
            row = {"number": int(cells[0]), "starter": bool(cells[1].strip()) if off >= 2 else False,
                   "name": re.sub(r"\s+", " ", cells[off]).strip()}
            pi = cols.index("PO") if "PO" in cols else None
            row["position"] = cells[pi + off] if pi is not None else ""
            for col, key in STATS.items():
                if col not in cols:
                    continue
                v = cells[cols.index(col) + off]
                row[key] = v if key == "min" else (int(v) if v.isdigit() else 0)
            players.append(row)
        if players:
            tables.append(players)
        if len(tables) == 2:   # 3つ目以降はクォーター別の表
            break
    return tables


class Browser:
    """ボックススコアを描画させるためのブラウザ。初めて使うときに用意する。"""

    def __init__(self):
        self.pw = self.browser = self.page = None

    def html(self, url):
        if self.page is None:
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "playwright"], check=True)
            subprocess.run([sys.executable, "-m", "playwright", "install", "--with-deps", "chromium"], check=True)
            from playwright.sync_api import sync_playwright
            self.pw = sync_playwright().start()
            self.browser = self.pw.chromium.launch()
            self.page = self.browser.new_page(locale="ja-JP")
        self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        html = ""
        for _ in range(15):   # 表に数字が入るまで最大30秒ほど待つ
            self.page.wait_for_timeout(2000)
            html = self.page.content()
            if len(team_tables(html)) == 2:
                break
        return html

    def close(self):
        for x in (self.browser, self.pw):
            try:
                if x is self.pw and x:
                    x.stop()
                elif x:
                    x.close()
            except Exception:
                pass


def read_game(key, now, browser):
    """終わった試合なら成績を返す。まだ終わっていない・読めないときは None。"""
    html = fetch(DETAIL_URL.format(key=key))
    g = parse_game(key, html)
    if g["tipoff"] is None or g["tipoff"] + FINISHED_AFTER > now:
        return None
    tables = team_tables(html) or team_tables(browser.html(DETAIL_URL.format(key=key).replace("tab=1", "tab=4")))
    if len(tables) != 2:
        print(f"[skip] {key}: ボックススコアの表が見つからない({len(tables)})")
        return None
    kings, opp = (tables[0], tables[1]) if g["home"] else (tables[1], tables[0])
    kp, op = sum(p.get("pts", 0) for p in kings), sum(p.get("pts", 0) for p in opp)
    if kp == 0 and op == 0:
        print(f"[skip] {key}: 得点が入っていない(中止・未入力?)")
        return None
    return {
        "key": key,
        "datetime": g["tipoff"].isoformat(),
        "opponent": g["opponent"],
        "home": g["home"],
        "kings": kp,
        "opp": op,
        "url": DETAIL_URL.format(key=key).replace("tab=1", "tab=4"),
        "players": kings,
    }


def load_old():
    try:
        with open(OUT, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def main():
    now = datetime.now(JST)
    old = load_old()
    games = {g["key"]: g for g in old.get("games", [])}
    known_days = {g["datetime"][:10] for g in games.values()}

    keys = []
    for y, m in season_months(now):
        for d in game_days(fetch(MONTH_URL.format(y=y, m=m, club=KINGS_ID))):
            day = f"{y:04d}-{m:02d}-{d:02d}"
            if day in known_days or (y, m, d) > (now.year, now.month, now.day):
                continue
            time.sleep(1)
            keys += schedule_keys(fetch(DAY_URL.format(y=y, m=m, d=d, club=KINGS_ID)))
    keys = [k for k in dict.fromkeys(keys) if k not in games]
    print(f"[keys] 新しく読む試合: {keys}")

    errors = 0
    browser = Browser()
    try:
        for key in keys:
            time.sleep(1)
            try:
                g = read_game(key, now, browser)
            except Exception as e:
                errors += 1
                print(f"[skip] {key}: {e}")
                continue
            if g is None:
                continue
            games[key] = g
            top = sorted(g["players"], key=lambda p: -p.get("pts", 0))[:3]
            print(f"[read] {g['datetime'][:10]} vs {g['opponent']} {g['kings']}-{g['opp']} "
                  + " / ".join(f"{p['name']} {p.get('pts', 0)}" for p in top))
    finally:
        browser.close()
    if keys and errors == len(keys):
        sys.exit("どの試合ページも読み取れませんでした(ページの形が変わった可能性があります)")

    out_games = sorted(games.values(), key=lambda g: g["datetime"])
    if out_games == old.get("games"):
        print("成績に変更はありません")
        return
    data = {
        "team": "琉球ゴールデンキングス",
        "updated": now.strftime("%Y/%m/%d %H:%M"),
        "games": out_games,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"games.json を更新しました({len(out_games)}試合)")


if __name__ == "__main__":
    main()

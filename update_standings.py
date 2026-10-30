"""B.LEAGUE 公式サイトの順位表から、琉球ゴールデンキングスがいる地区の順位を読み、standings.json に書く

GitHub Actions から update_schedule.py と一緒に起動される。順位が変わったときだけファイルを書き換える。

手元で試す:
  pip install requests beautifulsoup4
  python update_standings.py
"""
import json
import os
import re
import sys
from datetime import datetime

from bs4 import BeautifulSoup

from update_schedule import JST, KINGS_ID, fetch

STANDINGS_URL = "https://www.bleague.jp/standings/?tab=1"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "standings.json")


def parse_standings(html):
    """キングスの載っている表から (地区名, [{rank, team, short, w, l, pct, gb, last5, streak, kings}]) を返す。"""
    soup = BeautifulSoup(html, "html.parser")
    for t in soup.find_all("table"):
        if not t.find("a", href=re.compile(rf"TeamID={KINGS_ID}\b")):
            continue
        head = t.find("tr")
        cols = [c.get_text(" ", strip=True) for c in head.find_all(["th", "td"])]
        idx = {name: cols.index(name) for name in ("順位", "クラブ", "勝", "負", "勝率", "差", "過去5試合", "連勝/連敗") if name in cols}
        if not {"順位", "クラブ", "勝", "負"} <= idx.keys():
            continue
        rows = []
        for tr in t.find_all("tr")[1:]:
            cells = tr.find_all(["th", "td"])
            if len(cells) < len(cols):
                continue
            club = cells[idx["クラブ"]]
            full = club.select_one(".team-name-line")
            short = club.select_one(".pc-tab-dn")
            link = club.find("a", href=True)
            text = lambda name: cells[idx[name]].get_text(strip=True) if name in idx else ""
            rows.append({
                "rank": int(text("順位")) if text("順位").isdigit() else None,
                "team": (full or club).get_text(strip=True),
                "short": short.get_text(strip=True) if short else "",
                "w": int(text("勝")) if text("勝").isdigit() else 0,
                "l": int(text("負")) if text("負").isdigit() else 0,
                "pct": text("勝率"),
                "gb": text("差"),
                "last5": text("過去5試合"),
                "streak": text("連勝/連敗"),
                "kings": bool(link and re.search(rf"TeamID={KINGS_ID}\b", link["href"])),
            })
        # 表の見出し(「西地区」など)。見出しのタグは決まっていないので、表の直前の短い文字を使う
        title = next((x.get_text(" ", strip=True) for x in t.find_all_previous(["h2", "h3", "h4", "p"])
                      if 0 < len(x.get_text(strip=True)) <= 20), "")
        return title, rows
    return "", []


def main():
    division, rows = parse_standings(fetch(STANDINGS_URL))
    for r in rows:
        print(f"[standings] {r['rank']} {r['team']} {r['w']}-{r['l']} {r['pct']} {'★' if r['kings'] else ''}")
    if len(rows) < 3 or not any(r["kings"] for r in rows):
        sys.exit("順位表を読み取れませんでした(ページの形が変わった可能性があります)")

    try:
        with open(OUT, encoding="utf-8") as f:
            old = json.load(f)
    except Exception:
        old = {}
    if rows == old.get("rows") and division == old.get("division"):
        print("順位に変更はありません")
        return
    data = {
        "division": division,
        "updated": datetime.now(JST).strftime("%Y/%m/%d %H:%M"),
        "source": STANDINGS_URL,
        "rows": rows,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"standings.json を更新しました({division} {len(rows)}クラブ)")


if __name__ == "__main__":
    main()

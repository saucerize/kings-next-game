"""キングス公式サイトのダンサーズのページから、キングスダンサーズのメンバーを読み、dancers.json を書き換える

GitHub Actions から update_schedule.py と一緒に起動される。メンバーが変わったときだけファイルを書き換える。
公式ページは写真とプロフィール画像だけで、プロフィールの文字は画像の中に書かれている。

手元で試す:
  pip install requests beautifulsoup4
  python update_dancers.py
"""
import json
import os
import sys
from datetime import datetime

from bs4 import BeautifulSoup

from update_schedule import JST, fetch

DANCERS_URL = "https://goldenkings.jp/team/dancers/"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dancers.json")
MIN_DANCERS = 5   # これより少なければ読み取り失敗とみなす


def parse_dancers(html):
    """メンバー一覧(ul.kd-list)の順に [{name, photo, profile}] を返す。
    一覧に無い人(前のシーズンのプロフィール画像が残っているだけの人)は含めない。"""
    soup = BeautifulSoup(html, "html.parser")
    profiles = {}
    for modal in soup.select("div.kdmodal[id]"):
        # スマホ向けの縦長画像(a.sp)を優先。無ければ最初の画像
        img = modal.select_one("a.sp img[src]") or modal.select_one("img[src]")
        if img:
            profiles[modal["id"]] = img["src"]
    dancers = []
    for img in soup.select("ul.kd-list li img[alt]"):
        key = img["alt"].strip()
        if not key or any(d["key"] == key for d in dancers):
            continue
        dancers.append({
            "key": key,
            "name": key.replace(".", " "),   # 「RIN.Suzuki」→「RIN Suzuki」
            "photo": img.get("src", ""),
            "profile": profiles.get(key, ""),
        })
    return dancers


def main():
    dancers = parse_dancers(fetch(DANCERS_URL))
    for d in dancers:
        print(f"[dancer] {d['name']} {'(プロフィール画像あり)' if d['profile'] else ''}")
    if len(dancers) < MIN_DANCERS:
        sys.exit(f"ダンサーを {len(dancers)} 人しか読み取れませんでした(ページの形が変わった可能性があります)")

    try:
        with open(OUT, encoding="utf-8") as f:
            old = json.load(f)
    except Exception:
        old = {}
    if dancers == old.get("dancers"):
        print("ダンサーズに変更はありません")
        return
    data = {
        "updated": datetime.now(JST).strftime("%Y/%m/%d %H:%M"),
        "source": DANCERS_URL,
        "dancers": dancers,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"dancers.json を更新しました({len(dancers)}人)")


if __name__ == "__main__":
    main()

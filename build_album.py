"""公開された(main にマージされた)写真から、アルバムの一覧 album.json を作る

album/<日付>/<ID>.json(写真の情報)を集めて、新しい順に並べる。内容が同じなら書き換えない。
album/sample/ に置いた写真は日付のアルバムには入れず、見本(samples)として別に出す。
"""
import glob
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(DIR, "album.json")


def main():
    photos, samples = [], []
    for path in glob.glob(os.path.join(DIR, "album", "*", "*.json")):
        try:
            with open(path, encoding="utf-8") as f:
                info = json.load(f)
        except Exception:
            continue
        base = os.path.relpath(path, DIR)[:-len(".json")].replace(os.sep, "/")
        if not (os.path.exists(os.path.join(DIR, base + ".jpg")) and os.path.exists(os.path.join(DIR, base + "_t.jpg"))):
            continue
        item = {**info, "src": base + ".jpg", "thumb": base + "_t.jpg"}
        (samples if base.split("/")[1] == "sample" else photos).append(item)
    for lst in (photos, samples):
        lst.sort(key=lambda p: (p.get("time") or "", p.get("id") or ""), reverse=True)
    text = json.dumps({"photos": photos, "samples": samples}, ensure_ascii=False, indent=1) + "\n"
    try:
        with open(OUT, encoding="utf-8") as f:
            if f.read() == text:
                print("album.json に変更はありません")
                return
    except FileNotFoundError:
        pass
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"album.json を更新しました({len(photos)}枚・見本{len(samples)}枚)")


if __name__ == "__main__":
    main()

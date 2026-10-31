"""アルバムに投稿された写真を ntfy から受け取り、写真1枚ごとに承認用のプルリクエストを作る

album.html から投稿された写真は ntfy の公開トピックに添付ファイルとして届く(3時間で消える)。
GitHub Actions で1時間おきに起動され、まだ受け取っていない写真を
  - 縮小・回転補正し、位置情報などのメタデータを消した JPEG にする(本体と一覧用の小さい画像)
  - photo/<ID> ブランチに album/<日付>/<ID>.jpg・<ID>_t.jpg・<ID>.json として置く
  - main へのプルリクエストを作る(マージ=公開、閉じる=却下)
受け取った写真の ID は album/seen.json に控え、二重に受け取らないようにする。

手元で試す(プルリクエストは作らず、out/ に書き出すだけ):
  pip install requests pillow
  python collect_photos.py --dry-run
"""
import io
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import requests
from PIL import Image, ImageOps

JST = timezone(timedelta(hours=9))
NTFY = "https://ntfy.sh"
PHOTO_TOPIC = "kings-photo-a38853caea"
DIR = os.path.dirname(os.path.abspath(__file__))
SEEN = os.path.join(DIR, "album", "seen.json")
MAX_BYTES = 15 * 1024 * 1024    # ntfy の添付ファイルの上限
MAX_SIDE, THUMB_SIDE = 1600, 480
MAX_PER_RUN = 20                # 1回の起動で受け取る最大枚数(いたずら対策)
MAX_PER_SENDER = 5              # 同じ人(同じブラウザ)から1回の起動で受け取る最大枚数
NICK_MAX, COMMENT_MAX = 20, 100
HEADERS = {"User-Agent": "kings-next-game (personal use)"}


def load_seen():
    try:
        with open(SEEN, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def clean_text(s, limit):
    s = re.sub(r"[\x00-\x1f\x7f]", " ", str(s or "")).strip()
    return s[:limit]


def fetch_messages():
    """添付ファイル付きのメッセージを古い順に返す(添付は3時間で消えるので、それより前は見ない)。"""
    r = requests.get(f"{NTFY}/{PHOTO_TOPIC}/json?poll=1&since=3h", headers=HEADERS, timeout=30)
    r.raise_for_status()
    out = []
    for line in r.text.splitlines():
        try:
            m = json.loads(line)
        except Exception:
            continue
        if m.get("event") == "message" and m.get("attachment") and m.get("id"):
            out.append(m)
    return sorted(out, key=lambda m: m.get("time", 0))


def to_jpeg(data, side):
    """画像を開き直して、向きを直し、長い辺を side 以下にした JPEG(メタデータなし)を返す。"""
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((side, side))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=82, optimize=True)
    return buf.getvalue(), img.size


def prepare(m):
    """メッセージ1件から {id, date, files: {相対パス: bytes}, meta} を作る。画像でなければ None。"""
    att = m["attachment"]
    if int(att.get("size") or 0) > MAX_BYTES:
        print(f"[skip] {m['id']}: 大きすぎる")
        return None
    try:
        meta = json.loads(m.get("message") or "{}")
    except Exception:
        meta = {}
    if meta.get("type") != "kings-photo":
        print(f"[skip] {m['id']}: アルバムの投稿ではない")
        return None
    r = requests.get(att["url"], headers=HEADERS, timeout=60)
    r.raise_for_status()
    if len(r.content) > MAX_BYTES:
        return None
    try:
        full, size = to_jpeg(r.content, MAX_SIDE)
        thumb, _ = to_jpeg(r.content, THUMB_SIDE)
    except Exception as e:
        print(f"[skip] {m['id']}: 画像として開けない({e})")
        return None
    when = datetime.fromtimestamp(m.get("time", 0), JST)
    pid = re.sub(r"[^A-Za-z0-9]", "", m["id"])[:20]
    date = when.strftime("%Y-%m-%d")
    base = f"album/{date}/{pid}"
    info = {
        "id": pid,
        "date": date,
        "time": when.isoformat(timespec="minutes"),
        "nick": clean_text(meta.get("nick"), NICK_MAX),
        "comment": clean_text(meta.get("comment"), COMMENT_MAX),
        "width": size[0], "height": size[1],
    }
    return {
        "id": pid, "date": date, "cid": clean_text(meta.get("cid"), 20), "info": info,
        "files": {f"{base}.jpg": full, f"{base}_t.jpg": thumb,
                  f"{base}.json": (json.dumps(info, ensure_ascii=False, indent=1) + "\n").encode("utf-8")},
    }


def git(*args):
    return subprocess.run(["git", *args], cwd=DIR, check=True, capture_output=True, text=True).stdout


def open_pr(photo, repo):
    """photo/<ID> ブランチを main から作って写真を置き、プルリクエストを作る。"""
    branch = f"photo/{photo['id']}"
    git("checkout", "-q", "-B", branch, "origin/main")
    for path, data in photo["files"].items():
        full = os.path.join(DIR, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as f:
            f.write(data)
        git("add", path)
    info = photo["info"]
    who = info["nick"] or "名無しさん"
    git("commit", "-q", "-m", f"写真の投稿 {info['date']} {who}")
    git("push", "-q", "-f", "origin", branch)
    img = f"https://github.com/{repo}/blob/{branch}/album/{info['date']}/{info['id']}.jpg?raw=true"
    body = "\n".join([
        f"アルバムに写真が投稿されました。**公開してよければマージ、だめなら閉じてください。**",
        "",
        f"- 投稿日時：{info['time'].replace('T', ' ')}",
        f"- ニックネーム：{who}",
        f"- コメント：{info['comment'] or '（なし）'}",
        "",
        f"<img src=\"{img}\" width=\"480\">",
        "",
        "確認のポイント：不適切な内容でないか／知らない人の顔がはっきり写っていないか／ネットから拾った写真ではないか",
    ])
    subprocess.run(["gh", "pr", "create", "--base", "main", "--head", branch,
                    "--title", f"📷 写真の投稿：{info['date']} {who}", "--body", body],
                   cwd=DIR, check=True)
    git("checkout", "-q", "main")


def main():
    dry = "--dry-run" in sys.argv
    seen = load_seen()
    photos, per_sender = [], {}
    for m in fetch_messages():
        pid = re.sub(r"[^A-Za-z0-9]", "", m["id"])[:20]
        if pid in seen:
            continue
        seen.append(pid)   # 受け取れなかったものも、もう一度は試さない
        if len(photos) >= MAX_PER_RUN:
            break
        try:
            p = prepare(m)
        except Exception as e:
            print(f"[skip] {pid}: {e}")
            continue
        if not p:
            continue
        per_sender[p["cid"]] = per_sender.get(p["cid"], 0) + 1
        if p["cid"] and per_sender[p["cid"]] > MAX_PER_SENDER:
            print(f"[skip] {pid}: 同じ人からの投稿が多すぎる")
            continue
        photos.append(p)
        print(f"[photo] {p['id']} {p['date']} {p['info']['nick']!r} {p['info']['width']}x{p['info']['height']}")

    if dry:
        for p in photos:
            for path, data in p["files"].items():
                full = os.path.join(DIR, "out", path)
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, "wb") as f:
                    f.write(data)
        print(f"{len(photos)}枚を out/ に書き出しました(dry-run)")
        return

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    done = 0
    for p in photos:
        try:
            open_pr(p, repo)
            done += 1
        except Exception as e:
            print(f"[pr] {p['id']}: プルリクエストを作れませんでした({e})")
            subprocess.run(["git", "checkout", "-q", "main"], cwd=DIR)
    # 受け取った ID を main に控える
    os.makedirs(os.path.dirname(SEEN), exist_ok=True)
    with open(SEEN, "w", encoding="utf-8") as f:
        json.dump(seen[-2000:], f)
        f.write("\n")
    print(f"{done}枚の承認用プルリクエストを作りました")


if __name__ == "__main__":
    main()

"""試合結果を、通知を登録した人に Webプッシュで送る(GitHub Actions の push.yml から起動)

1. 通知の登録(ntfy の公開トピックに、サイトの公開鍵で暗号化して置かれる)を集め、push/subs.enc に保管する
   (保管するファイルも暗号化する。鍵はどちらも GitHub の Secret の VAPID_PRIVATE_KEY から作る)
2. 速報(kings-live)を見て、まだ知らせていない試合終了があれば、全員に結果を送る
3. 試合中なら、試合が終わるまで速報をリアルタイムで待ち、終わったらすぐ送る
送った試合は push/sent.json に控え、二度は送らない。

手元で試す(通知は送らず、何をするかだけ表示する):
  VAPID_PRIVATE_KEY=... python push_result.py --dry-run
"""
import base64
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

JST = timezone(timedelta(hours=9))
NTFY = "https://ntfy.sh"
SUB_TOPIC = "kings-pushsub-a38853caea"
LIVE_TOPIC = "kings-live-a38853caea"
SITE = "https://saucerize.github.io/kings-next-game/"
DIR = os.path.dirname(os.path.abspath(__file__))
SUBS_FILE = os.path.join(DIR, "push", "subs.enc")
SENT_FILE = os.path.join(DIR, "push", "sent.json")
FINAL_LATE = timedelta(hours=3)      # 試合終了からこれ以上たっていたら、もう送らない
LIVE_FRESH = timedelta(minutes=20)   # この時間内に速報があれば「試合中」とみなして終わるまで待つ
WATCH_MAX = timedelta(hours=3)       # 試合終了を待つ最長時間
HEADERS = {"User-Agent": "kings-next-game (personal use)"}


def b64u_dec(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def load_key():
    raw_b64 = os.environ.get("VAPID_PRIVATE_KEY", "").strip()
    if not raw_b64:
        sys.exit("VAPID_PRIVATE_KEY(GitHub の Secret)が設定されていません")
    raw = b64u_dec(raw_b64)
    priv = ec.derive_private_key(int.from_bytes(raw, "big"), ec.SECP256R1())
    store_key = hashlib.sha256(b"kings-push-subs:" + raw).digest()
    return raw_b64, priv, store_key


# ------------------------------------------------------------------ 登録の保管
def load_subs(store_key):
    try:
        blob = open(SUBS_FILE, "rb").read()
    except FileNotFoundError:
        return []
    data = AESGCM(store_key).decrypt(blob[:12], blob[12:], None)
    return json.loads(data)


def save_subs(store_key, subs):
    os.makedirs(os.path.dirname(SUBS_FILE), exist_ok=True)
    nonce = os.urandom(12)
    blob = nonce + AESGCM(store_key).encrypt(nonce, json.dumps(subs, separators=(",", ":")).encode(), None)
    with open(SUBS_FILE, "wb") as f:
        f.write(blob)


def decrypt_message(priv, msg):
    """ブラウザ(push.js)が暗号化した {action, sub} を読む。読めなければ None。"""
    try:
        d = json.loads(msg)
        if d.get("type") != "kings-push":
            return None
        peer = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), b64u_dec(d["epk"]))
        shared = priv.exchange(ec.ECDH(), peer)
        key = hashlib.sha256(shared).digest()
        return json.loads(AESGCM(key).decrypt(b64u_dec(d["iv"]), b64u_dec(d["ct"]), None))
    except Exception:
        return None


def collect(priv, subs):
    """ntfy に届いている登録・解除を反映する。変わったら True。"""
    r = requests.get(f"{NTFY}/{SUB_TOPIC}/json?poll=1&since=12h", headers=HEADERS, timeout=30)
    r.raise_for_status()
    by_ep = {s["endpoint"]: s for s in subs}
    changed = False
    events = []
    for line in r.text.splitlines():
        try:
            m = json.loads(line)
        except Exception:
            continue
        if m.get("event") != "message":
            continue
        d = decrypt_message(priv, m.get("message") or "")
        if d:
            events.append((m.get("time", 0), d))
    for t, d in sorted(events, key=lambda x: x[0]):
        sub = d.get("sub") or {}
        ep = sub.get("endpoint")
        if not isinstance(ep, str) or not ep.startswith("https://"):
            continue
        if d.get("action") == "sub":
            keys = sub.get("keys") or {}
            if keys.get("p256dh") and keys.get("auth"):
                new = {"endpoint": ep, "keys": {"p256dh": keys["p256dh"], "auth": keys["auth"]}, "t": t}
                old = by_ep.get(ep)
                if not old or old.get("keys") != new["keys"]:
                    by_ep[ep] = new
                    changed = True
        elif d.get("action") == "unsub" and ep in by_ep and by_ep[ep].get("t", 0) <= t:
            del by_ep[ep]
            changed = True
    return list(by_ep.values()), changed


# ------------------------------------------------------------------ 速報
def parse_live(line):
    try:
        m = json.loads(line)
        if m.get("event") != "message":
            return None
        d = json.loads(m.get("message") or "")
        if d.get("type") == "kings-live" and d.get("key") and d.get("updated"):
            return d
    except Exception:
        pass
    return None


def latest_live():
    r = requests.get(f"{NTFY}/{LIVE_TOPIC}/json?poll=1&since=6h", headers=HEADERS, timeout=30)
    r.raise_for_status()
    items = [d for d in map(parse_live, r.text.splitlines()) if d]
    return max(items, key=lambda d: d["updated"]) if items else None


def wait_final(key):
    """速報をリアルタイムで受け、その試合の試合終了が届いたら返す(時間切れなら None)。"""
    deadline = datetime.now(JST) + WATCH_MAX
    while datetime.now(JST) < deadline:
        try:
            with requests.get(f"{NTFY}/{LIVE_TOPIC}/json", headers=HEADERS, stream=True, timeout=(15, 90)) as r:
                for line in r.iter_lines(decode_unicode=True):
                    if datetime.now(JST) >= deadline:
                        return None
                    d = parse_live(line) if line else None
                    if d and str(d["key"]) == str(key) and d.get("period") == "FINAL":
                        return d
        except Exception as e:
            print(f"[watch] つなぎ直します: {e}")
            time.sleep(5)
        # つなぎ直す間に終わっていないか、履歴も確かめる
        d = latest_live()
        if d and str(d["key"]) == str(key) and d.get("period") == "FINAL":
            return d
    return None


# ------------------------------------------------------------------ 送信
def message_for(d):
    opp = d.get("opponent") or "相手"
    k, o = d.get("kings"), d.get("opp")
    win = isinstance(k, int) and isinstance(o, int) and k > o
    return {
        "title": "🏆 キングス勝利！" if win else "試合終了",
        "body": f"琉球 {k} - {o} {opp}",
        "url": SITE,
        "tag": f"result-{d['key']}",
    }


def send_all(vapid_key, subs, payload, dry):
    from pywebpush import WebPushException, webpush
    keep, ok = [], 0
    for s in subs:
        if dry:
            keep.append(s)
            continue
        try:
            webpush(subscription_info={"endpoint": s["endpoint"], "keys": s["keys"]},
                    data=json.dumps(payload, ensure_ascii=False),
                    vapid_private_key=vapid_key, vapid_claims={"sub": SITE.rstrip("/")}, ttl=6 * 3600)
            ok += 1
            keep.append(s)
        except WebPushException as e:
            code = getattr(e.response, "status_code", None)
            if code in (404, 410):
                print(f"[push] 登録が無効になっていたので消します({code})")
                continue
            print(f"[push] 送れませんでした({code}): {e}")
            keep.append(s)
        except Exception as e:
            print(f"[push] 送れませんでした: {e}")
            keep.append(s)
    print(f"[push] {ok}/{len(subs)} 人に送りました: {payload['title']} {payload['body']}")
    return keep


def main():
    dry = "--dry-run" in sys.argv
    vapid_key, priv, store_key = load_key()
    subs = load_subs(store_key)
    subs, changed = collect(priv, subs)
    print(f"登録 {len(subs)}人{'(更新あり)' if changed else ''}")
    try:
        sent = json.load(open(SENT_FILE, encoding="utf-8"))
    except Exception:
        sent = []

    d = latest_live()
    now = datetime.now(JST)
    final = None
    if d and str(d["key"]) not in sent:
        updated = datetime.fromisoformat(d["updated"])
        if d.get("period") == "FINAL":
            if now - updated <= FINAL_LATE:
                final = d
        elif now - updated <= LIVE_FRESH:
            print(f"試合中({d.get('period')} {d.get('kings')}-{d.get('opp')})。試合終了まで待ちます")
            final = wait_final(d["key"])
            subs, ch2 = collect(priv, subs)   # 待っている間の登録も入れる
            changed = changed or ch2
    if final:
        before = len(subs)
        subs = send_all(vapid_key, subs, message_for(final), dry)
        changed = changed or len(subs) != before
        sent = (sent + [str(final["key"])])[-200:]
        if not dry:
            os.makedirs(os.path.dirname(SENT_FILE), exist_ok=True)
            with open(SENT_FILE, "w", encoding="utf-8") as f:
                json.dump(sent, f)
                f.write("\n")
    else:
        print("送る試合結果はありません")
    if changed and not dry:
        save_subs(store_key, subs)


if __name__ == "__main__":
    main()

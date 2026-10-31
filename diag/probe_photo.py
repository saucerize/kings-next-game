"""調査用: 写真の投稿が ntfy に届いているか、写真を送ると ntfy が何と返すか(一時的なもの)"""
import io
import json
import requests
from PIL import Image

H = {"User-Agent": "kings-next-game (personal use)"}
T = "kings-photo-a38853caea"
r = requests.get(f"https://ntfy.sh/{T}/json?poll=1&since=12h", headers=H, timeout=30)
lines = [l for l in r.text.splitlines() if l.strip()]
print("== topic messages (12h):", r.status_code, len(lines))
for l in lines[-5:]:
    m = json.loads(l)
    print("   ", {k: m.get(k) for k in ("id", "time", "event", "message", "attachment")})
# ブラウザと同じ形で、テスト用の小さな JPEG を送ってみる(別のテスト用トピックへ)
buf = io.BytesIO(); Image.new("RGB", (800, 600), (200, 160, 40)).save(buf, "JPEG"); data = buf.getvalue()
meta = json.dumps({"type": "kings-photo", "v": 1, "cid": "diag", "nick": "テスト", "comment": ""}, ensure_ascii=False)
for label, kw in [("PUT query", dict(params={"filename": "kings.jpg", "message": meta})),
                  ("PUT header", dict(headers={"Filename": "kings.jpg"}))]:
    r = requests.put(f"https://ntfy.sh/{T}-diag", data=data, timeout=30, **kw)
    print(f"== {label}: {r.status_code} {r.text[:400]}")
o = requests.options(f"https://ntfy.sh/{T}", headers={"Origin": "https://saucerize.github.io", "Access-Control-Request-Method": "PUT"}, timeout=30)
print("== CORS preflight:", o.status_code, {k: v for k, v in o.headers.items() if k.lower().startswith("access-control")})

"""調査用: B.LEAGUE 速報の試合データ(S3 の v2_genius_contexts)の中身(一時的なもの)"""
import json
import requests

H = {"User-Agent": "kings-next-game (personal use)", "Referer": "https://www.bleague.jp/"}
BASE = "https://b-league.s3.amazonaws.com/web_json/v2_genius_contexts/{key}/{name}"


def walk(o, path="", depth=0, out=None):
    out = [] if out is None else out
    if depth > 5 or len(out) > 150:
        return out
    if isinstance(o, dict):
        out.append(f"{path} {{{', '.join(list(o.keys())[:30])}}}")
        for k, v in list(o.items())[:40]:
            walk(v, f"{path}.{k}", depth + 1, out)
    elif isinstance(o, list):
        out.append(f"{path} [list x{len(o)}]")
        if o:
            walk(o[0], f"{path}[0]", depth + 1, out)
    return out


for key in ("506518", "506413"):
    r = requests.get(BASE.format(key=key, name="latestid"), headers=H, timeout=30)
    print(f"== {key} latestid {r.status_code} {r.text[:80]!r}")
    if not r.ok:
        continue
    lid = r.text.strip()
    r = requests.get(BASE.format(key=key, name=f"{lid}.json"), headers=H, timeout=30)
    print(f"== {key} {lid}.json {r.status_code} len={len(r.text)}")
    if not r.ok:
        continue
    j = r.json()
    print("\n".join(walk(j)))
    s = json.dumps(j, ensure_ascii=False)
    for kw in ("Clock", "clock", "PlayByPlay", "Pbp", "pbp", "Actions", "Action", "Period", "Score", "Foul", "ファウル"):
        i = s.find(kw)
        if i >= 0:
            print(f"-- {kw}:", s[max(0, i - 300):i + 700])
    break

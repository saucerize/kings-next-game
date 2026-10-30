"""調査用(2回目): ダンサーズの写真のまわりの HTML(一時的なもの)"""
import re
import requests

H = {"User-Agent": "kings-next-game (personal use)"}
html = requests.get("https://goldenkings.jp/team/dancers/", headers=H, timeout=30).text
for key in ("01.HINA.png", "02.RINKA.png", "15.THIRA_full.png", "16.2025-26_HIROKA"):
    i = html.find(key)
    print(f"== around {key}:", re.sub(r"\s+", " ", html[max(0, i - 1200):i + 900]) if i >= 0 else None)
i = html.find("cheer")
print("== around cheer:", re.sub(r"\s+", " ", html[max(0, i - 600):i + 2500]))
print("== instagram-ish:", sorted(set(re.findall(r"instagram\.com/[A-Za-z0-9_.]+", html))))
print("== scripts:", re.findall(r'<script[^>]+src="([^"]+)"', html)[-8:])

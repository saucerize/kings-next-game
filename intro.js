// サイトを開いたときのオープニング演出(index.html で使う)
// 黒い画面に金の王冠が光りながら現れ、「RYUKYU GOLDEN KINGS」と、その日のひとこと
// (試合中・今日の試合・前の試合の勝利・次の試合まであと何日)を出して、金の粒を散らして消える。
// - 1日1回だけ(同じ日に何度開いても2回目からは出さない)。?intro=1 で何度でも見られる
// - タップするとすぐ終わる。動きを減らす設定の端末では出さない
(function () {
  const KEY = "kings-intro";
  const TZ = "Asia/Tokyo";
  const params = new URLSearchParams(location.search);
  const force = params.has("intro");
  if (!force && window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const today = new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(new Date());
  try { if (!force && localStorage.getItem(KEY) === today) return; localStorage.setItem(KEY, today); } catch {}

  const css = `
  .kintro { position: fixed; inset: 0; z-index: 1000; display: grid; place-items: center; overflow: hidden;
    background: radial-gradient(60% 45% at 50% 45%, #3a2d0c 0%, #0b0b0b 70%); transition: opacity .55s ease, transform .55s ease; }
  .kintro.out { opacity: 0; transform: scale(1.06); pointer-events: none; }
  .kintro .in { display: flex; flex-direction: column; align-items: center; gap: 10px; text-align: center; padding: 0 24px; }
  .kintro svg { width: 128px; height: 100px; filter: drop-shadow(0 0 18px rgba(241,215,122,.55)); }
  .kintro .crown { fill: url(#kgold); transform-origin: 50% 60%; animation: kcrown 1s cubic-bezier(.2,1.4,.4,1) both; }
  .kintro .shine { fill: url(#kshine); mix-blend-mode: screen; animation: kshine 1.4s .55s ease-in-out both; }
  .kintro .rays { position: absolute; width: 140vmax; height: 140vmax; left: 50%; top: 45%; transform: translate(-50%, -50%);
    background: repeating-conic-gradient(from 0deg, rgba(241,215,122,.10) 0 6deg, transparent 6deg 18deg);
    -webkit-mask: radial-gradient(circle, #000 0, transparent 55%); mask: radial-gradient(circle, #000 0, transparent 55%);
    animation: krays 6s linear infinite, kfade .8s ease both; }
  .kintro .team { margin: 6px 0 0; font: 900 20px/1.2 "Hiragino Sans","Noto Sans JP",system-ui,sans-serif; letter-spacing: .18em;
    background: linear-gradient(90deg, #a8842a, #fff4c2 45%, #d4af37 55%, #a8842a); background-size: 250% 100%;
    -webkit-background-clip: text; background-clip: text; color: transparent; animation: kup .6s .45s ease both, kglint 1.6s .8s ease both; }
  .kintro .msg { margin: 0; font: 800 15px/1.5 "Hiragino Sans","Noto Sans JP",system-ui,sans-serif; color: #f5f1e6; min-height: 1.5em; animation: kup .6s .8s ease both; }
  .kintro .msg b { color: #f1d77a; } .kintro .msg .live { color: #ff5b5b; }
  .kintro .skip { position: absolute; bottom: max(22px, env(safe-area-inset-bottom)); font: 600 11px system-ui, sans-serif; color: rgba(245,241,230,.45); animation: kfade .5s 1s both; }
  .kintro i { position: absolute; left: 50%; top: 45%; width: 6px; height: 6px; border-radius: 50%; background: #f1d77a; box-shadow: 0 0 8px #f1d77a;
    animation: kspark 1.1s ease-out forwards; }
  @keyframes kcrown { 0% { transform: scale(.3) translateY(30px); opacity: 0; } 100% { transform: none; opacity: 1; } }
  @keyframes kshine { 0% { transform: translateX(-120%); } 100% { transform: translateX(120%); } }
  @keyframes krays { to { transform: translate(-50%, -50%) rotate(360deg); } }
  @keyframes kfade { from { opacity: 0; } }
  @keyframes kup { from { opacity: 0; transform: translateY(12px); } }
  @keyframes kglint { from { background-position: 100% 0; } to { background-position: 0 0; } }
  @keyframes kspark { 0% { transform: translate(-50%, -50%); opacity: 1; } 100% { transform: translate(calc(-50% + var(--x)), calc(-50% + var(--y))) scale(.3); opacity: 0; } }`;

  const style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);
  const el = document.createElement("div");
  el.className = "kintro";
  el.setAttribute("aria-hidden", "true");
  el.innerHTML = `<div class="rays"></div><div class="in">
    <svg viewBox="-24 -22 48 34"><defs>
      <linearGradient id="kgold" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff4c2"/><stop offset=".5" stop-color="#f1d77a"/><stop offset="1" stop-color="#b8902e"/></linearGradient>
      <linearGradient id="kshine" x1="0" y1="0" x2="1" y2="0"><stop offset=".35" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".9"/><stop offset=".65" stop-color="#fff" stop-opacity="0"/></linearGradient>
      <clipPath id="kclip"><path d="M-14 6L-17 -10L-7 -2L0 -14L7 -2L17 -10L14 6Z"/></clipPath></defs>
      <path class="crown" d="M-14 6L-17 -10L-7 -2L0 -14L7 -2L17 -10L14 6Z"/>
      <g clip-path="url(#kclip)"><rect class="shine" x="-24" y="-22" width="48" height="34"/></g>
      <circle cx="0" cy="-15" r="1.6" fill="#fff4c2"/><circle cx="-17" cy="-11" r="1.3" fill="#fff4c2"/><circle cx="17" cy="-11" r="1.3" fill="#fff4c2"/>
    </svg>
    <p class="team">RYUKYU GOLDEN KINGS</p>
    <p class="msg" id="kintroMsg"></p>
  </div><div class="skip">タップでスキップ</div>`;
  document.documentElement.appendChild(el);

  let done = false;
  function close() {
    if (done) return;
    done = true;
    el.classList.add("out");
    setTimeout(() => el.remove(), 600);
  }
  el.addEventListener("click", close);

  // 金の粒をはじけさせてから消す
  setTimeout(() => {
    if (done) return;
    for (let i = 0; i < 26; i++) {
      const s = document.createElement("i");
      const a = Math.random() * Math.PI * 2, r = 90 + Math.random() * 140;
      s.style.setProperty("--x", `${Math.cos(a) * r}px`);
      s.style.setProperty("--y", `${Math.sin(a) * r}px`);
      s.style.animationDelay = `${Math.random() * .15}s`;
      el.appendChild(s);
    }
  }, 700);
  setTimeout(close, 2600);

  // その日のひとこと(読めなければ空のまま)
  const WD = ["日", "月", "火", "水", "木", "金", "土"];
  const fmt = dt => {
    const d = new Date(new Date(dt).getTime() + 9 * 3600e3);
    return { ymd: d.toISOString().slice(0, 10), md: `${d.getUTCMonth() + 1}/${d.getUTCDate()}(${WD[d.getUTCDay()]})`,
      hm: `${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}` };
  };
  const short = n => (String(n || "").match(/\p{Script=Han}{2,}/u) || [])[0] || String(n || "").slice(0, 6);
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  Promise.all([
    fetch("schedule.json", { cache: "no-store" }).then(r => r.json()).catch(() => ({})),
    fetch("games.json", { cache: "no-store" }).then(r => r.json()).catch(() => ({})),
  ]).then(([s, g]) => {
    const now = Date.now();
    const next = (s.games || []).filter(x => new Date(x.datetime).getTime() + 2.5 * 3600e3 > now)
      .sort((a, b) => new Date(a.datetime) - new Date(b.datetime))[0];
    const last = (g.games || []).filter(x => Number.isFinite(x.kings)).slice(-1)[0];
    let html = "";
    if (next && new Date(next.datetime).getTime() <= now) {
      html = `<span class="live">● LIVE</span>　vs ${esc(short(next.opponent))} 試合中！`;
    } else if (next && fmt(next.datetime).ymd === today) {
      html = `🏀 <b>今日は試合の日！</b><br>${esc(fmt(next.datetime).hm)} TIP OFF　vs ${esc(short(next.opponent))}`;
    } else if (last && last.kings > last.opp && now - new Date(last.datetime).getTime() < 36 * 3600e3) {
      html = `🏆 <b>WIN!</b>　${last.kings}-${last.opp}　vs ${esc(short(last.opponent))}`;
    } else if (next) {
      const days = Math.round((new Date(fmt(next.datetime).ymd) - new Date(today)) / 864e5);
      html = `次の試合まで <b>あと${days}日</b><br>${esc(fmt(next.datetime).md)} vs ${esc(short(next.opponent))}`;
    }
    const m = document.getElementById("kintroMsg");
    if (m && !done) m.innerHTML = html;
  });
})();

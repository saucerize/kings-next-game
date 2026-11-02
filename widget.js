// 琉球ゴールデンキングス「次の試合」ウィジェット(iPhone の無料アプリ Scriptable 用)
//
// 使い方: Scriptable に新しいスクリプトを作ってこの中身を貼り付け、
//         ホーム画面に Scriptable のウィジェット(小 or 中)を置いて、スクリプトにこれを選ぶ。
// 表示: 試合中はライブのスコア / 終わった直後は結果 / それ以外は次の試合とカウントダウン(中サイズは前の試合と今季の成績も)
// データはファンサイト(saucerize.github.io/kings-next-game)と同じものを読む。

const SITE = "https://saucerize.github.io/kings-next-game/";
const LIVE = "https://ntfy.sh/kings-live-a38853caea/json?poll=1&since=4h";
const GOLD = new Color("#d4af37"), GOLD_SOFT = new Color("#f1d77a"), TEXT = new Color("#f5f1e6"), MUTED = new Color("#a39c8a");
const RED = new Color("#e5484d");
const GAME_LENGTH_MS = 2.5 * 60 * 60 * 1000;
const WD = ["日", "月", "火", "水", "木", "金", "土"];

async function getJSON(url) {
  try { const r = new Request(url); r.timeoutInterval = 15; return await r.loadJSON(); } catch (e) { return null; }
}
async function getLive() {
  try {
    const r = new Request(LIVE); r.timeoutInterval = 15;
    const text = await r.loadString();
    let last = null;
    for (const line of text.split("\n")) {
      try {
        const d = JSON.parse(JSON.parse(line).message);
        if (d.type === "kings-live" && Number.isFinite(d.kings) && (!last || d.updated > last.updated)) last = d;
      } catch (e) {}
    }
    if (!last) return null;
    // ページと同じく、直近のプレーのスコア・クォーターを優先する
    const p = Array.isArray(last.plays) && last.plays[0];
    if (p && Number.isFinite(p.kings) && Number.isFinite(p.opp)) { last.kings = p.kings; last.opp = p.opp; }
    if (p && p.period && last.period !== "FINAL" && !(last.period === "HALF" && p.period === "Q2")) last.period = p.period;
    return last;
  } catch (e) { return null; }
}

// 日本時間で「11/7(土) 16:00」
function jst(dt) {
  const d = new Date(new Date(dt).getTime() + 9 * 3600 * 1000);
  return { md: `${d.getUTCMonth() + 1}/${d.getUTCDate()}(${WD[d.getUTCDay()]})`, hm: `${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}`, ymd: d.toISOString().slice(0, 10) };
}
function countdown(dt) {
  const ms = new Date(dt).getTime() - Date.now();
  if (ms <= 0) return "まもなく";
  const today = jst(Date.now()).ymd, day = jst(dt).ymd;
  const days = Math.round((new Date(day) - new Date(today)) / 86400000);
  if (days === 0) { const h = Math.floor(ms / 3600000), m = Math.floor(ms / 60000) % 60; return h ? `あと${h}時間${m}分` : `あと${m}分`; }
  return days === 1 ? "明日" : `あと${days}日`;
}
const PERIOD = { Q1: "1Q", Q2: "2Q", Q3: "3Q", Q4: "4Q", HALF: "ハーフ", FINAL: "試合終了" };
const periodLabel = p => PERIOD[p] || String(p || "").replace(/^OT/, "延長") || "試合中";

function text(stack, s, size, color, weight = "bold") {
  const t = stack.addText(String(s));
  t.font = weight === "heavy" ? Font.heavySystemFont(size) : weight === "bold" ? Font.boldSystemFont(size) : Font.systemFont(size);
  t.textColor = color;
  t.lineLimit = 1;
  t.minimumScaleFactor = 0.6;
  return t;
}

async function build(size) {
  const [sched, games, standings, live] = await Promise.all([
    getJSON(SITE + "schedule.json"), getJSON(SITE + "games.json"), getJSON(SITE + "standings.json"), getLive(),
  ]);
  const short = {};
  for (const r of (standings && standings.rows) || []) if (r.team && r.short) short[r.team] = r.short;
  // 略称(順位表に無いチームは、名前の中の地名=漢字の部分。「宇都宮ブレックス」→「宇都宮」)
  const sn = name => short[name] || (String(name || "").match(/\p{Script=Han}{2,}/u) || [])[0] || String(name || "相手").slice(0, 4);
  const now = Date.now();

  const w = new ListWidget();
  const g = new LinearGradient();
  g.colors = [new Color("#2a2210"), new Color("#0b0b0b")];
  g.locations = [0, 1];
  w.backgroundGradient = g;
  w.setPadding(12, 14, 12, 14);
  w.url = SITE;

  const head = w.addStack();
  head.centerAlignContent();
  text(head, "👑 KINGS", 12, GOLD, "heavy");
  head.addSpacer();

  const age = live ? now - new Date(live.updated).getTime() : Infinity;
  const isLive = live && live.period !== "FINAL" && age < 15 * 60 * 1000;
  const isFinal = live && live.period === "FINAL" && age < 3 * 3600 * 1000;

  if (isLive || isFinal) {
    const win = live.kings > live.opp;
    text(head, isLive ? "● LIVE" : (win ? "WIN" : "LOSE"), 11, isLive ? RED : (win ? GOLD_SOFT : MUTED), "heavy");
    w.addSpacer();
    text(w, isLive ? periodLabel(live.period) + (live.clock ? "  " + live.clock : "") : "試合終了", 12, GOLD_SOFT);
    const row = w.addStack();
    row.centerAlignContent();
    text(row, "琉球", 13, TEXT);
    row.addSpacer(6);
    text(row, live.kings, size === "small" ? 30 : 34, GOLD_SOFT, "heavy");
    row.addSpacer(6);
    text(row, "-", 20, MUTED);
    row.addSpacer(6);
    text(row, live.opp, size === "small" ? 30 : 34, TEXT, "heavy");
    if (size !== "small") { row.addSpacer(6); text(row, sn(live.opponent), 13, TEXT); }
    if (size === "small") text(w, "vs " + sn(live.opponent), 12, MUTED, "regular");
    w.refreshAfterDate = new Date(now + (isLive ? 5 : 30) * 60 * 1000);
  } else {
    const next = ((sched && sched.games) || [])
      .filter(x => new Date(x.datetime).getTime() + GAME_LENGTH_MS > now)
      .sort((a, b) => new Date(a.datetime) - new Date(b.datetime))[0];
    if (!next) {
      w.addSpacer();
      text(w, "次の試合は未定", 14, TEXT);
    } else {
      const t = jst(next.datetime);
      text(head, next.home ? "HOME" : "AWAY", 10, next.home ? GOLD_SOFT : MUTED, "heavy");
      w.addSpacer();
      text(w, "NEXT GAME", 10, MUTED);
      text(w, "vs " + (size === "small" ? sn(next.opponent) : next.opponent), size === "small" ? 17 : 18, TEXT, "heavy");
      text(w, `${t.md} ${t.hm}`, 13, GOLD_SOFT);
      text(w, countdown(next.datetime), size === "small" ? 20 : 18, GOLD, "heavy");
    }
    // 中サイズは、前の試合の結果と今季の成績も
    const done = ((games && games.games) || []).filter(x => Number.isFinite(x.kings) && Number.isFinite(x.opp));
    if (size !== "small" && done.length) {
      w.addSpacer(4);
      const last = done[done.length - 1];
      const wins = done.filter(x => x.kings > x.opp).length;
      const lt = jst(last.datetime);
      text(w, `前回 ${lt.md} ${last.kings > last.opp ? "○" : "●"} ${last.kings}-${last.opp} ${sn(last.opponent)}　今季 ${wins}勝${done.length - wins}敗`, 11, MUTED, "regular");
    }
    // 試合の日はこまめに、それ以外は1時間ごとに更新(実際の間隔は iPhone が決める)
    const soon = next && new Date(next.datetime).getTime() - now < 6 * 3600 * 1000;
    w.refreshAfterDate = new Date(now + (soon ? 10 : 60) * 60 * 1000);
  }
  return w;
}

const size = config.widgetFamily || "medium";
const widget = await build(size);
if (config.runsInWidget) Script.setWidget(widget);
else if (size === "small") await widget.presentSmall();
else await widget.presentMedium();
Script.complete();

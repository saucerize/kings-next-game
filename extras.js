// 記録達成ウォッチと誕生日(index.html・players.html・stats.html で共通)
// players.json の career(B.LEAGUE 通算)・season(今シーズン)・birthday を使う
(function () {
  const TZ = "Asia/Tokyo";
  const WATCH_GAMES = 5;   // 今のペースで何試合以内に届く記録を出すか

  // 種類ごとに「次の節目」の刻み。通算が少ないうちは細かめに刻む
  const KINDS = [
    { key: "pts", label: "得点", unit: "点", step: v => (v < 2000 ? 500 : 1000) },
    { key: "reb", label: "リバウンド", unit: "本", step: v => (v < 1000 ? 250 : 500) },
    { key: "ast", label: "アシスト", unit: "本", step: v => (v < 1000 ? 250 : 500) },
    { key: "games", label: "試合出場", unit: "試合", step: () => 100 },
  ];

  const shortName = n => (n.includes(" ") ? n.split(" ")[0] : n.split("・").pop());

  function milestones(players) {
    const out = [];
    for (const p of players || []) {
      const c = p.career, s = p.season;
      if (!c || !c.games) continue;
      for (const k of KINDS) {
        const total = c[k.key] || 0;
        const step = k.step(total);
        const goal = Math.floor(total / step) * step + step;
        const left = goal - total;
        // 1試合あたりのペースは今シーズンの数字、まだ出ていなければ通算から
        const rate = k.key === "games" ? 1
          : (s && s.games ? (s[k.key] || 0) / s.games : total / c.games);
        if (!(rate > 0)) continue;
        const games = Math.ceil(left / rate);
        if (games > WATCH_GAMES) continue;
        out.push({ player: p, name: shortName(p.name), kind: k, goal, left, games });
      }
    }
    return out.sort((a, b) => a.games - b.games || a.left - b.left);
  }

  // 日本時間の「今日」の月日・年
  function todayJst(now = new Date()) {
    const [y, m, d] = new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit" })
      .format(now).split("-").map(Number);
    return { y, m, d };
  }

  function birthdaysToday(players, now) {
    const t = todayJst(now);
    return (players || []).filter(p => {
      const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(p.birthday || "");
      return m && Number(m[2]) === t.m && Number(m[3]) === t.d;
    }).map(p => ({ player: p, name: p.name, age: t.y - Number(p.birthday.slice(0, 4)) }));
  }

  function birthdayLabel(p) {
    const m = /^\d{4}-(\d{2})-(\d{2})$/.exec(p.birthday || "");
    return m ? `${Number(m[1])}月${Number(m[2])}日` : "";
  }

  window.KingsExtras = { milestones, birthdaysToday, birthdayLabel, shortName };
})();

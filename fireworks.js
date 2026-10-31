// 試合開始の花火(index.html で使う)
// 画面いっぱいの canvas に、金色を中心とした花火を数秒間打ち上げ、真ん中にメッセージを出す。
// 動きを減らす設定(prefers-reduced-motion)の端末では、花火は出さずにメッセージだけ出す。
(function () {
  const COLORS = ["#f1d77a", "#d4af37", "#fff4c2", "#ffffff", "#ff8a65", "#7fd3ff"];
  const DURATION_MS = 6500;      // 打ち上げ続ける時間
  const LAUNCH_EVERY_MS = 280;   // 打ち上げの間隔
  const GRAVITY = 0.045;

  function showMessage(icon, title, sub, ms) {
    const el = document.createElement("div");
    el.className = "fw-message";
    // 絵文字は金色のグラデーション文字の外に置く(中に入れると絵文字まで金色に塗られてしまう)
    el.innerHTML = `${icon ? `<i>${icon}</i>` : ""}<b>${title}</b>${sub ? `<span>${sub}</span>` : ""}`;
    document.body.appendChild(el);
    setTimeout(() => el.classList.add("out"), ms - 700);
    setTimeout(() => el.remove(), ms);
  }

  function launch({ icon = "🏀", title = "TIP OFF!", sub = "みんなで応援しよう！" } = {}) {
    if (document.querySelector(".fw-canvas") || document.querySelector(".fw-message")) return;   // 打ち上げ中なら重ねない
    showMessage(icon, title, sub, DURATION_MS + 1200);
    if (window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const canvas = document.createElement("canvas");
    canvas.className = "fw-canvas";
    document.body.appendChild(canvas);
    const ctx = canvas.getContext("2d");
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    let w = 0, h = 0;
    const resize = () => {
      w = window.innerWidth; h = window.innerHeight;
      canvas.width = w * dpr; canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);

    const rockets = [], sparks = [];
    const start = performance.now();
    let lastLaunch = 0;

    function addRocket() {
      rockets.push({
        x: w * (0.15 + Math.random() * 0.7), y: h + 10,
        vx: (Math.random() - 0.5) * 1.2, vy: -(h / 95 + Math.random() * 3),
        color: COLORS[Math.floor(Math.random() * COLORS.length)],
        burstAt: h * (0.18 + Math.random() * 0.3),
      });
    }

    function burst(r) {
      const n = 70 + Math.floor(Math.random() * 40);
      const speed = 2.2 + Math.random() * 2.2;
      for (let i = 0; i < n; i++) {
        const a = (Math.PI * 2 * i) / n + Math.random() * 0.1;
        const s = speed * (0.6 + Math.random() * 0.5);
        sparks.push({
          x: r.x, y: r.y, vx: Math.cos(a) * s, vy: Math.sin(a) * s,
          life: 1, decay: 0.012 + Math.random() * 0.012,
          color: Math.random() < 0.25 ? "#ffffff" : r.color,
        });
      }
    }

    function frame(now) {
      const elapsed = now - start;
      if (elapsed < DURATION_MS && now - lastLaunch > LAUNCH_EVERY_MS) {
        lastLaunch = now;
        addRocket();
        if (Math.random() < 0.35) addRocket();
      }
      // 軌跡が少し残るように、全部は消さずに薄く塗り重ねる
      ctx.globalCompositeOperation = "destination-out";
      ctx.fillStyle = "rgba(0,0,0,0.22)";
      ctx.fillRect(0, 0, w, h);
      ctx.globalCompositeOperation = "lighter";

      for (let i = rockets.length - 1; i >= 0; i--) {
        const r = rockets[i];
        r.x += r.vx; r.y += r.vy; r.vy += GRAVITY;
        ctx.fillStyle = r.color;
        ctx.beginPath(); ctx.arc(r.x, r.y, 2.2, 0, Math.PI * 2); ctx.fill();
        if (r.y <= r.burstAt || r.vy >= 0) { burst(r); rockets.splice(i, 1); }
      }
      for (let i = sparks.length - 1; i >= 0; i--) {
        const s = sparks[i];
        s.x += s.vx; s.y += s.vy; s.vx *= 0.985; s.vy = s.vy * 0.985 + GRAVITY;
        s.life -= s.decay;
        if (s.life <= 0) { sparks.splice(i, 1); continue; }
        ctx.globalAlpha = Math.max(0, s.life);
        ctx.fillStyle = s.color;
        ctx.beginPath(); ctx.arc(s.x, s.y, 2, 0, Math.PI * 2); ctx.fill();
      }
      ctx.globalAlpha = 1;

      if (elapsed < DURATION_MS || rockets.length || sparks.length) {
        requestAnimationFrame(frame);
      } else {
        window.removeEventListener("resize", resize);
        canvas.remove();
      }
    }
    requestAnimationFrame(frame);
  }

  window.KingsFireworks = { launch };
})();

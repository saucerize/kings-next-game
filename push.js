// 試合結果の通知(Webプッシュ)の登録 —— index.html の「試合結果を通知で受け取る」で使う
//
// しくみ:
//  1. ブラウザに通知の許可をもらい、プッシュの宛先(subscription)を作る
//  2. 宛先をサイトの公開鍵で暗号化して、ntfy の公開トピックに置く(中身は管理側の秘密鍵でしか読めない)
//  3. GitHub Actions(push_result.py)が宛先を集めて保管し、試合が終わったら結果を送る
// iPhone は「ホーム画面に追加」したサイトでしか通知を受け取れない(Apple の制限)
(function () {
  const VAPID_PUBLIC = "BJs4SBHJ5CVfb1ZU_e2dw4s_gOtrguXq2fToYTnDp79IrXb98xhS1XUD_ZKPiV-5igKc6V4VtNJ_sU8SEnjsGvQ";
  const SUB_TOPIC = "https://ntfy.sh/kings-pushsub-a38853caea";
  const STORE = "kings-push";

  const b64u = buf => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  const unb64u = s => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4)), c => c.charCodeAt(0));
  const store = {
    get() { try { return localStorage.getItem(STORE); } catch { return null; } },
    set(v) { try { v ? localStorage.setItem(STORE, v) : localStorage.removeItem(STORE); } catch {} },
  };

  const isIOS = /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const standalone = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  const supported = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;

  // 宛先を、使い捨ての鍵とサイトの公開鍵(ECDH P-256)から作った AES-GCM の鍵で暗号化して送る
  async function sendEncrypted(obj) {
    const server = await crypto.subtle.importKey("raw", unb64u(VAPID_PUBLIC), { name: "ECDH", namedCurve: "P-256" }, false, []);
    const eph = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"]);
    const shared = await crypto.subtle.deriveBits({ name: "ECDH", public: server }, eph.privateKey, 256);
    const keyBytes = await crypto.subtle.digest("SHA-256", shared);
    const key = await crypto.subtle.importKey("raw", keyBytes, "AES-GCM", false, ["encrypt"]);
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, new TextEncoder().encode(JSON.stringify(obj)));
    const epk = await crypto.subtle.exportKey("raw", eph.publicKey);
    const r = await fetch(SUB_TOPIC, { method: "POST", body: JSON.stringify({ type: "kings-push", v: 1, epk: b64u(epk), iv: b64u(iv), ct: b64u(ct) }) });
    if (!r.ok) throw new Error("送信に失敗しました(" + r.status + ")");
  }

  async function registration() {
    const reg = await navigator.serviceWorker.register("sw.js");
    await navigator.serviceWorker.ready;
    return reg;
  }

  async function subscribe() {
    const perm = await Notification.requestPermission();
    if (perm !== "granted") throw new Error("通知が許可されませんでした。設定から通知を許可してください");
    const reg = await registration();
    const sub = await reg.pushManager.getSubscription() ||
      await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: unb64u(VAPID_PUBLIC) });
    await sendEncrypted({ action: "sub", sub: sub.toJSON() });
    store.set("on");
  }

  async function unsubscribe() {
    const reg = await registration();
    const sub = await reg.pushManager.getSubscription();
    if (sub) {
      try { await sendEncrypted({ action: "unsub", sub: { endpoint: sub.endpoint } }); } catch {}
      await sub.unsubscribe();
    }
    store.set(null);
  }

  // 画面: #pushBox の中にボタンと説明を描く
  function mount(box) {
    if (!box) return;
    const draw = (msg = "") => {
      const on = store.get() === "on" && supported && Notification.permission === "granted";
      let body;
      if (isIOS && !standalone) {
        body = `<p class="push-help">iPhone は、このサイトを<b>ホーム画面に追加</b>してから開くと通知を受け取れます。<br>
          Safari の下の <b>共有ボタン（□↑）</b> →「<b>ホーム画面に追加</b>」→ ホーム画面のキングスのアイコンから開いて、ここをもう一度押してください。</p>`;
      } else if (!supported) {
        body = '<p class="push-help">このブラウザは通知に対応していません。</p>';
      } else if (Notification.permission === "denied") {
        body = '<p class="push-help">通知がブロックされています。ブラウザやスマホの設定で、このサイトの通知を許可してください。</p>';
      } else {
        body = `<button type="button" class="push-btn${on ? " on" : ""}" id="pushBtn">${on ? "🔔 通知オン（タップでオフ）" : "🔔 試合結果を通知で受け取る"}</button>`;
      }
      box.innerHTML = `<p>🔔 試合結果をお知らせ</p><small>試合が終わったら、勝敗とスコアをスマホに通知します</small>${body}<p class="push-msg">${msg}</p>`;
      const btn = box.querySelector("#pushBtn");
      if (btn) btn.addEventListener("click", async () => {
        btn.disabled = true;
        try {
          if (on) { await unsubscribe(); draw("通知をオフにしました"); }
          else { await subscribe(); draw("登録しました！次の試合から結果が届きます"); }
        } catch (e) {
          draw(String(e && e.message || e));
        }
      });
    };
    draw();
  }

  window.KingsPush = { mount };
})();

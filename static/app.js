"use strict";

const PERSONAS = [
  { username: "emma", name: "Emma", channel: "app" },
  { username: "sofia", name: "Sofia", channel: "human" },
  { username: "jan", name: "Jan & Monique", channel: "voice" },
  { username: "marcel", name: "Marcel", channel: "voice" },
  { username: "lucas", name: "Lucas", channel: "push" },
  { username: "yasmine", name: "Yasmine", channel: "app" },
  { username: "thomas", name: "Thomas", channel: "app" },
  { username: "nina", name: "Nina", channel: "app" },
];

const state = {
  me: null, feed: null,
  view: "app",            // app | lock | call
  tab: "home",            // home | appts | data
  openedFrom: null,       // null | push | voice
  call: "ringing",        // ringing | active
  missedCall: false,
  booking: false,         // booking panel open
  bookingMode: "phone",
  bookingSlot: null,
  slots: [],
  appointments: [],
  holdTimer: null,
};

function onUnauthorized() { showLogin(); }

// =========================================================================== sign in
function showLogin() {
  document.getElementById("app-view").hidden = true;
  document.getElementById("login-view").hidden = false;
  renderPersonas();
}

function renderPersonas() {
  const grid = clear(document.getElementById("persona-grid"));
  for (const p of PERSONAS) {
    grid.append(el("button", {
      class: "persona", type: "button", dataset: { u: p.username },
      onclick: () => {
        document.getElementById("login-username").value = p.username;
        document.getElementById("login-password").focus();
        grid.querySelectorAll(".persona").forEach((b) => b.classList.toggle("selected", b.dataset.u === p.username));
      },
    }, el("strong", { text: p.name }),
       el("span", { class: "muted small", text: t(`persona.${p.username}`) }),
       el("span", { class: "tags" },
         el("span", { class: "tag", text: t(`persona.${p.username}.expect`) }),
         el("span", { class: `tag ch-${p.channel}`, text: t(`channel.${p.channel}`) }))));
  }
}

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const err = document.getElementById("login-error");
  err.textContent = "";
  try {
    const r = await Api.post("/api/auth/login", {
      username: document.getElementById("login-username").value.trim(),
      password: document.getElementById("login-password").value,
    });
    if (r.role !== "customer") { window.location.href = "/advisor"; return; }
    Api.token = r.token;
    document.getElementById("login-password").value = "";
    await showApp();
  } catch (ex) { err.textContent = ex.message; }
});

document.getElementById("logout").addEventListener("click", () => { Api.token = null; showLogin(); });
document.getElementById("replay").addEventListener("click", () => { startDelivery(); renderPhone(); });

// =========================================================================== app
async function showApp() {
  document.getElementById("login-view").hidden = true;
  document.getElementById("app-view").hidden = false;
  state.me = await Api.get("/api/me");
  // The presenter's language wins: keep the customer's preferred language in sync with the page
  if (state.me.language !== getLang()) {
    await Api.put("/api/me/language", { language: getLang() });
    state.me.language = getLang();
  }
  state.tab = "home";
  await loadFeed({ restart: true });
}

async function onLanguageChange(lang) {
  renderPersonas();
  if (!Api.token || document.getElementById("app-view").hidden) return;
  await Api.put("/api/me/language", { language: lang });
  state.me.language = lang;
  await loadFeed({ restart: false });
}

async function loadFeed({ restart } = { restart: false }) {
  const [feed, appts] = await Promise.all([Api.get("/api/me/feed"), Api.get("/api/me/appointments")]);
  state.feed = feed;
  state.appointments = appts;
  if (restart) startDelivery();
  renderHeader();
  renderPhone();
  renderJournal(feed.journal);
}

/** Put the phone in the state that matches how the message is delivered. */
function startDelivery() {
  const ch = state.feed.screen.channel;
  state.openedFrom = null;
  state.missedCall = false;
  state.booking = false;
  state.tab = "home";
  if (ch === "push") state.view = "lock";
  else if (ch === "voice") { state.view = "call"; state.call = "ringing"; }
  else state.view = "app";
}

function renderHeader() {
  document.getElementById("who").textContent = `${state.me.display_name} · ${t(`persona.${usernameOf()}`)}`;
  document.getElementById("demo-clock").textContent = `${t("top.clock")} ${fmtDateTime(state.me.demo_now)}`;
  const ch = state.feed.screen.channel;
  const chip = document.getElementById("channel-chip");
  chip.textContent = `${t("phone.deliveredBy")} ${t(`channel.${ch}`)}`;
  chip.className = `channel-chip ch-${ch}`;
}

function usernameOf() { return state.me.username; }

// =========================================================================== phone views
function renderPhone() {
  clearInterval(state.holdTimer);
  const root = document.getElementById("phone-screen");
  // Keep the scroll position when re-rendering the same view (e.g. picking a time slot)
  const keepScroll = root.dataset.view === `${state.view}:${state.tab}` ? root.scrollTop : 0;
  clear(root);
  root.dataset.view = `${state.view}:${state.tab}`;
  root.className = `phone-screen view-${state.view}`;
  requestAnimationFrame(() => { root.scrollTop = keepScroll; });
  root.append(statusBar(state.view !== "app"));
  if (state.view === "lock") root.append(lockScreen());
  else if (state.view === "call") root.append(callScreen());
  else root.append(appScreen());
}

function statusBar(dark) {
  return el("div", { class: `status-bar${dark ? " dark" : ""}` },
    el("span", { text: fmtTime(state.me.demo_now) }), el("span", { text: "5G ▮▮▮ 82%" }));
}

// ---------------------------------------------------------------- lock screen (push notification)
function lockScreen() {
  const s = state.feed.screen;
  const now = state.me.demo_now;
  const wrap = el("div", { class: "lock" },
    el("div", { class: "lock-time", text: fmtTime(now) }),
    el("div", { class: "lock-date", text: fmtDay(now) }));
  let title, text;
  if (state.missedCall) {
    title = t("lock.missedCall");
    text = s.delivery.title;
  } else {
    title = s.delivery.title;
    text = s.delivery.text;
  }
  wrap.append(el("button", {
    class: "notif", type: "button",
    onclick: () => { state.view = "app"; state.openedFrom = state.missedCall ? "voice" : "push"; renderPhone(); },
  },
    el("div", { class: "notif-head" }, el("span", { class: "app-icon", text: "M" }), el("span", { text: "Moments" }),
      el("span", { class: "muted", text: t("lock.now") })),
    el("strong", { text: title }),
    el("p", { text: text })));
  wrap.append(el("p", { class: "lock-hint", text: t("lock.hint") }));
  return wrap;
}

// ---------------------------------------------------------------- call screen (voice)
function callScreen() {
  const s = state.feed.screen;
  const wrap = el("div", { class: "call" },
    el("div", { class: "call-avatar", text: "M" }),
    el("div", { class: "call-name", text: t("call.caller") }),
    el("div", { class: "call-sub", text: state.call === "ringing" ? t("call.incoming") : t("call.inProgress") }));

  if (state.call === "ringing") {
    wrap.append(el("p", { class: "call-topic", text: s.delivery.title }));
    wrap.append(el("div", { class: "call-actions" },
      el("button", { class: "call-btn decline", type: "button", "aria-label": t("call.decline"),
        onclick: () => { state.view = "lock"; state.missedCall = true; renderPhone(); } }, el("span", { text: "✕" }), el("small", { text: t("call.decline") })),
      el("button", { class: "call-btn accept", type: "button", "aria-label": t("call.accept"),
        onclick: () => { state.call = "active"; renderPhone(); playVoice(); } }, el("span", { text: "✆" }), el("small", { text: t("call.accept") }))));
    return wrap;
  }

  // Call in progress: transcript + big, simple buttons (low-digital customers)
  const hold = s.blocks.find((b) => b.type === "transfer_hold");
  if (hold) wrap.append(transferHold(hold, true));
  wrap.append(el("div", { class: "wave" }, ...Array.from({ length: 18 }, () => el("i"))));
  wrap.append(el("details", { class: "transcript", open: true },
    el("summary", { text: t("call.transcript") }), el("p", { text: s.delivery.text })));
  const hl = s.blocks.find((b) => b.type === "highlight");
  if (hl) {
    const ctas = el("div", { class: "call-ctas" });
    hl.ctas.forEach((c) => ctas.append(el("button", { class: "btn big", type: "button", text: c.label, onclick: () => clickCta(c) })));
    wrap.append(ctas);
  }
  wrap.append(el("div", { class: "call-foot" },
    el("button", { class: "btn ghost-light small", type: "button", text: t("call.replay"), onclick: playVoice }),
    el("button", { class: "call-btn decline small", type: "button", "aria-label": t("call.end"),
      onclick: () => { stopVoice(); state.view = "app"; state.openedFrom = "voice"; renderPhone(); } },
      el("span", { text: "✕" }), el("small", { text: t("call.end") }))));
  return wrap;
}

let currentAudio = null;
async function playVoice() {
  stopVoice();
  const s = state.feed.screen;
  try {
    const res = await Api.request("GET", `/api/me/decisions/${state.feed.decision_id}/voice`, null, { raw: true });
    if (res.status === 200) {
      const url = URL.createObjectURL(await res.blob());
      currentAudio = new Audio(url);
      currentAudio.addEventListener("ended", () => URL.revokeObjectURL(url));
      await currentAudio.play();
      return;
    }
  } catch { /* fall back to the browser voice */ }
  if ("speechSynthesis" in window) {
    const u = new SpeechSynthesisUtterance(s.delivery.text);
    u.lang = { en: "en-GB", fr: "fr-BE", nl: "nl-BE" }[s.language] || "en-GB";
    u.rate = 0.95;
    speechSynthesis.speak(u);
    toast(t("toast.browserVoice"));
  }
}
function stopVoice() {
  if (currentAudio) { currentAudio.pause(); currentAudio = null; }
  if ("speechSynthesis" in window) speechSynthesis.cancel();
}

// ---------------------------------------------------------------- app screen
function appScreen() {
  const wrap = el("div", { class: "app" });
  wrap.append(el("div", { class: "app-head" },
    el("p", { class: "greeting", text: `${t("app.hello")} ${state.me.first_name}` }),
    el("div", { class: "balance card" }, el("span", { class: "muted small", text: t("app.account") }), el("strong", { text: fmtEUR(state.me.balance) }))));
  const tabs = el("nav", { class: "tabs", role: "tablist" });
  for (const [id, key] of [["home", "app.tab.home"], ["appts", "app.tab.appts"], ["data", "app.tab.data"]]) {
    const count = id === "appts" ? state.appointments.filter((a) => a.status === "booked").length : 0;
    tabs.append(el("button", { class: `tab${state.tab === id ? " active" : ""}`, role: "tab", type: "button",
      onclick: async () => { state.tab = id; if (id === "data") await loadConsents(); renderPhone(); } },
      t(key), count ? el("span", { class: "badge", text: String(count) }) : null));
  }
  wrap.append(tabs);
  if (state.tab === "home") wrap.append(homeTab());
  else if (state.tab === "appts") wrap.append(appointmentsTab());
  else wrap.append(dataTab());
  return wrap;
}

function homeTab() {
  const s = state.feed.screen;
  const box = el("div", { class: "home" });
  if (state.openedFrom) {
    box.append(el("div", { class: `opened-from ch-${state.openedFrom}`, text: t(`app.openedFrom.${state.openedFrom}`) }));
  }
  box.append(el("div", { class: `family-line f-${s.family}`, text: t(`family.${s.family}`) }));
  const renderers = { highlight, checklist, why_panel: whyPanel, transfer_hold: (b) => transferHold(b, false), human: humanBlock, abstain: abstainBlock };
  for (const b of s.blocks) {
    const fn = renderers[b.type];
    if (fn) box.append(fn(b));                           // unknown block types are ignored
    if (b.type === "highlight" && state.booking && s.channel !== "human") box.append(bookingPanel());
  }
  if (s.action_id !== "abstain") {
    box.append(el("div", { class: "feedback-bar" },
      el("span", { class: "muted small", text: t("fb.question") }),
      ...[["clicked", "fb.useful"], ["not_now", "fb.notNow"], ["never", "fb.never"]].map(([r, k]) =>
        el("button", { class: "btn chip", type: "button", text: t(k), onclick: () => sendFeedback(r) }))));
  }
  return box;
}

function highlight(b) {
  const s = state.feed.screen;
  const ctas = el("div", { class: "ctas" });
  b.ctas.forEach((c, i) => ctas.append(el("button", {
    class: `btn ${i === 0 ? "primary" : "secondary"}`, type: "button", text: c.label, onclick: () => clickCta(c),
  })));
  return el("article", { class: `block highlight f-${s.family}` }, el("h3", { text: b.title }), el("p", { text: b.body }), ctas);
}

function checklist(b) {
  return el("article", { class: "block checklist" }, b.title ? el("h4", { text: b.title }) : null,
    el("ul", {}, b.items.map((i) => el("li", { text: i }))));
}

function whyPanel(b) {
  const d = el("details", { class: "block why" }, el("summary", { text: b.title }));
  if (b.signals_used.length) d.append(el("ul", {}, b.signals_used.map((x) => el("li", { text: x }))));
  b.notes.forEach((n) => d.append(el("p", { class: "small muted", text: n })));
  if (b.families.length) {
    d.append(el("button", { class: "btn link small", type: "button", text: t("why.manage"),
      onclick: async () => { state.tab = "data"; await loadConsents(); renderPhone(); } }));
  }
  d.addEventListener("toggle", () => {
    if (d.open && state.feed.screen.action_id !== "abstain") Api.post(`/api/me/decisions/${state.feed.decision_id}/why`).catch(() => {});
  });
  return d;
}

function transferHold(b, dark) {
  const counter = el("strong", { class: "countdown" });
  const box = el("article", { class: `block hold${dark ? " dark" : ""}` },
    el("p", { class: "small", text: t("hold.title") }),
    el("p", {}, el("strong", { text: fmtEUR(b.amount) }), " → ", el("span", { text: b.beneficiary })),
    el("p", { class: "small" }, `${t("hold.until")} `, counter));
  const until = b.hold_until ? new Date(b.hold_until + "Z").getTime() : 0;
  const tick = () => {
    const sec = Math.max(0, Math.round((until - Date.now()) / 1000));
    counter.textContent = sec ? `${Math.floor(sec / 60)} min ${String(sec % 60).padStart(2, "0")} s` : t("hold.now");
    if (!sec) clearInterval(state.holdTimer);
  };
  if (b.status === "held") { tick(); state.holdTimer = setInterval(tick, 1000); } else counter.textContent = b.status;
  return box;
}

function humanBlock(b) {
  const box = el("article", { class: "block human" },
    el("div", { class: "advisor-row" }, el("span", { class: "advisor-avatar", text: "A" }),
      el("div", {}, el("strong", { text: b.title }), el("p", { class: "small", text: b.body }))));
  box.append(state.feed.active_appointment ? appointmentCard(state.feed.active_appointment) : bookingPanel(true));
  return box;
}

function abstainBlock(b) {
  return el("article", { class: "block abstain" }, el("div", { class: "abstain-icon", text: "✓" }),
    el("h3", { text: b.title }), el("p", { text: b.body }));
}

// ---------------------------------------------------------------- booking
function bookingPanel(embedded = false) {
  const panel = el("div", { class: `booking${embedded ? " embedded" : ""}` });
  if (state.feed.active_appointment) { panel.append(appointmentCard(state.feed.active_appointment)); return panel; }
  panel.append(el("h4", { text: t("book.title") }));
  const modes = el("div", { class: "seg" });
  for (const m of ["phone", "video", "branch"]) {
    modes.append(el("button", { type: "button", class: `seg-btn${state.bookingMode === m ? " active" : ""}`, text: t(`mode.${m}`),
      onclick: () => { state.bookingMode = m; renderPhone(); } }));
  }
  panel.append(modes);
  const list = el("div", { class: "slots" });
  if (!state.slots.length) { loadSlots(); list.append(el("p", { class: "muted small", text: "…" })); }
  let lastDay = "";
  for (const sl of state.slots) {
    const day = sl.starts_at.slice(0, 10);
    if (day !== lastDay) { list.append(el("div", { class: "slot-day", text: fmtDay(sl.starts_at) })); lastDay = day; }
    list.append(el("button", { type: "button", class: `slot${state.bookingSlot === sl.id ? " active" : ""}`, text: fmtTime(sl.starts_at),
      onclick: () => { state.bookingSlot = sl.id; renderPhone(); } }));
  }
  panel.append(list);
  panel.append(el("button", { class: "btn primary full", type: "button", text: t("book.confirm"), disabled: !state.bookingSlot, onclick: confirmBooking }));
  return panel;
}

async function loadSlots() {
  try { state.slots = await Api.get("/api/me/slots"); renderPhone(); } catch (ex) { toast(ex.message, "error"); }
}

async function confirmBooking() {
  try {
    const r = await Api.post("/api/me/appointments", { decision_id: state.feed.decision_id, slot_id: state.bookingSlot, mode: state.bookingMode });
    toast(r.message, "ok");
    state.booking = false; state.bookingSlot = null; state.slots = [];
    await loadFeed();
  } catch (ex) { toast(ex.message, "error"); state.slots = []; renderPhone(); }
}

function appointmentCard(a) {
  return el("div", { class: "appt-card" },
    el("div", { class: "appt-when" }, el("strong", { text: fmtDateTime(a.starts_at) }), el("span", { class: "tag", text: t(`mode.${a.mode}`) })),
    el("p", { class: "small muted", text: `${t("appt.with")} ${a.advisor || "advisor"} · ${t(`appt.status.${a.status}`)}` }),
    a.status === "booked" ? el("button", { class: "btn secondary small", type: "button", text: t("appt.cancel"), onclick: () => cancelAppointment(a.id) }) : null);
}

async function cancelAppointment(id) {
  try { const r = await Api.post(`/api/me/appointments/${id}/cancel`); toast(r.message, "ok"); await loadFeed(); }
  catch (ex) { toast(ex.message, "error"); }
}

function appointmentsTab() {
  const box = el("div", { class: "home" }, el("h3", { text: t("appt.title") }));
  if (!state.appointments.length) box.append(el("p", { class: "muted small", text: t("appt.none") }));
  state.appointments.forEach((a) => box.append(el("article", { class: "block" }, appointmentCard(a))));
  return box;
}

// ---------------------------------------------------------------- actions
async function clickCta(c) {
  if (c.effect === "book") {
    state.booking = true; state.view = "app"; state.tab = "home"; stopVoice();
    try { await Api.post(`/api/me/decisions/${state.feed.decision_id}/cta`, { cta_id: c.id }); } catch { /* not blocking */ }
    await loadSlots();
    return;
  }
  try {
    const r = await Api.post(`/api/me/decisions/${state.feed.decision_id}/cta`, { cta_id: c.id });
    toast(r.message, "ok");
    await loadFeed();
  } catch (ex) { toast(ex.message, "error"); }
}

async function sendFeedback(reaction) {
  try {
    await Api.post(`/api/me/decisions/${state.feed.decision_id}/feedback`, { reaction });
    toast(reaction === "clicked" ? t("toast.thanks") : t("toast.respected"), "ok");
    await loadFeed({ restart: true });
  } catch (ex) { toast(ex.message, "error"); }
}

// ---------------------------------------------------------------- consent
let consentCache = [];
async function loadConsents() { consentCache = await Api.get("/api/me/consents"); }

function dataTab() {
  const box = el("div", { class: "home" }, el("h3", { text: t("data.title") }), el("p", { class: "muted small", text: t("data.intro") }));
  for (const c of consentCache) {
    const input = el("input", { type: "checkbox", role: "switch", "aria-label": t(`consent.${c.family}`) });
    input.checked = c.enabled;
    input.addEventListener("change", async () => {
      try {
        await Api.put(`/api/me/consents/${c.family}`, { enabled: input.checked });
        toast(input.checked ? t("toast.consentOn") : t("toast.consentOff"), "ok");
        await loadConsents();
        await loadFeed();
      } catch (ex) { input.checked = !input.checked; toast(ex.message, "error"); }
    });
    box.append(el("label", { class: "consent" }, el("span", { text: t(`consent.${c.family}`) }), input));
  }
  box.append(el("div", { class: "consent locked" }, el("span", { text: t("consent.fraud") }), el("span", { class: "small muted", text: t("consent.always") })));
  return box;
}

// =========================================================================== backstage
function renderJournal(j) {
  const root = clear(document.getElementById("journal"));
  if (!j) { root.append(el("p", { class: "muted", text: t("back.hidden") })); return; }
  const step = (n, key) => el("h3", {}, el("span", { class: "step", text: String(n) }), t(key));

  const sig = el("section", { class: "jcard" }, step(1, "back.signals"));
  if (!j.derived.signals.length) sig.append(el("p", { class: "muted small", text: t("back.noSignal") }));
  for (const s of j.derived.signals) {
    const bar = el("div", { class: "bar" }, el("span", { class: s.confidence >= 0.6 ? "fill ok" : "fill low" }));
    bar.firstChild.style.width = `${Math.round(s.confidence * 100)}%`;
    sig.append(el("div", { class: "signal" },
      el("div", { class: "signal-head" }, el("code", { text: `${s.name} = ${s.value}` }), el("span", { class: "small", text: `conf. ${s.confidence.toFixed(2)}` })),
      bar, el("p", { class: "small muted", text: `${t("back.data")} ${s.families.map((f) => t(`fam.${f}`)).join(", ")}` })));
  }
  sig.append(el("p", { class: "small" }, `${t("back.stress")} `, el("strong", { text: `${j.derived.financial_stress}/3` }),
    ` · ${t("back.income")} ${t(`income.${j.derived.income_stability}`)} · ${t("back.pref")} ${t(`channel.${j.derived.channel_pref}`)}`));
  sig.append(el("p", { class: "small excluded", text: t("back.excluded", { n: j.excluded_sensitive_transactions }) }));
  const off = Object.entries(j.consents).filter(([, v]) => !v).map(([k]) => t(`fam.${k}`));
  if (off.length) sig.append(el("p", { class: "small warn", text: `${t("back.consentOff")} ${off.join(", ")}` }));
  root.append(sig);

  const cand = el("section", { class: "jcard" }, step(2, "back.candidates"));
  cand.append(el("p", { class: "small muted formula", text: t("back.formula") }));
  if (!j.candidates.length) cand.append(el("p", { class: "muted small", text: t("back.noCandidate") }));
  else {
    const tb = el("tbody");
    for (const c of j.candidates) {
      tb.append(el("tr", { class: `st-${c.status}` },
        el("td", {}, el("code", { text: c.action_id }), el("div", { class: "small muted", text: `${c.trigger}${c.is_commercial ? ` · ${t("back.commercial")}` : ""}` })),
        el("td", { text: c.score.toFixed(3) }),
        el("td", {}, el("span", { class: `status ${c.status}`, text: t(`status.${c.status}`) }),
          c.reasons.length ? el("div", { class: "small muted", text: c.reasons.map((r) => t(`reason.${r}`)).join(", ") }) : null)));
    }
    cand.append(el("table", { class: "jtable" }, el("thead", {}, el("tr", {}, [t("back.col.action"), t("back.col.score"), t("back.col.status")].map((h) => el("th", { text: h })))), tb));
  }
  root.append(cand);

  const g = el("section", { class: "jcard" }, step(3, "back.guardrails"));
  if (!j.guardrails.length) g.append(el("p", { class: "muted small", text: t("back.noGuardrail") }));
  g.append(el("ul", { class: "guards" }, j.guardrails.map((x) => el("li", { text: t(`guard.${x}`) }))));
  root.append(g);

  const d = j.decision;
  const dec = el("section", { class: "jcard decision" }, step(4, "back.decision"),
    el("p", {}, el("strong", { text: d.action_id === "abstain" ? t("family.abstain") : d.action_id }), d.score ? ` · score ${d.score.toFixed(3)}` : ""),
    el("p", { class: "small" }, `${t("back.channel")} `, el("span", { class: `tag ch-${d.channel}`, text: t(`channel.${d.channel}`) }), ` ${t(`chreason.${d.channel_reason}`)}`),
    d.requires_human ? el("p", { class: "small warn", text: t("back.credit") }) : null,
    el("p", { class: "small muted", text: t("back.render", { source: j.render.source, tone: j.render.variant, lang: j.render.language.toUpperCase() }) }));
  const bandit = j.render.bandit || {};
  if (Object.keys(bandit).length) {
    dec.append(el("p", { class: "small muted", text: `${t("back.bandit")} ` + Object.entries(bandit).map(([v, s]) => `${v} ${s.successes}✓/${s.failures}✗ → ${s.draw}`).join(" · ") }));
  }
  root.append(dec);
}

function mountSwitches() {
  document.querySelectorAll("[data-lang-switch]").forEach((c) => mountLanguageSwitch(c, async (lang) => {
    mountSwitches();
    await onLanguageChange(lang);
  }));
}

// =========================================================================== start
(async () => {
  applyStaticI18n();
  mountSwitches();
  if (Api.token) { try { await showApp(); return; } catch { Api.token = null; } }
  showLogin();
})();

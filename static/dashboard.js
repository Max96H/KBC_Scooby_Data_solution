"use strict";

const dash = { tasks: [], metrics: null, appointments: [], slots: [], filter: "open", selected: null, journal: null };

function onUnauthorized() { showLogin(); }

function showLogin() {
  document.getElementById("app-view").hidden = true;
  document.getElementById("login-view").hidden = false;
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
    if (r.role !== "advisor") { err.textContent = t("dash.notAdvisor"); return; }
    Api.token = r.token;
    document.getElementById("login-password").value = "";
    await showApp();
  } catch (ex) { err.textContent = ex.message; }
});
document.getElementById("logout").addEventListener("click", () => { Api.token = null; showLogin(); });
document.getElementById("refresh").addEventListener("click", () => loadAll());

async function showApp() {
  document.getElementById("login-view").hidden = true;
  document.getElementById("app-view").hidden = false;
  buildCostForm();
  await loadAll();
}

async function loadAll() {
  const [tasks, metrics, appts, slots] = await Promise.all([
    Api.get("/api/advisor/tasks"), Api.get("/api/advisor/metrics"), Api.get("/api/advisor/appointments"), Api.get("/api/advisor/slots"),
  ]);
  Object.assign(dash, { tasks, metrics, appointments: appts, slots });
  if (dash.selected && !tasks.some((x) => x.id === dash.selected)) dash.selected = null;
  renderAll();
}

function renderAll() {
  if (!dash.metrics) return;
  renderKpis();
  renderFilter();
  renderTasks();
  renderDetail();
  renderAgenda();
  renderActions(dash.metrics.actions);
  renderTimeline(dash.metrics.timeline);
  renderChannels(dash.metrics.channels);
  renderFairness(dash.metrics.fairness);
  renderBandit(dash.metrics.bandit);
  computeCost();
}

function kpi(label, value, hint) {
  return el("div", { class: "kpi card" }, el("span", { class: "small muted", text: label }), el("strong", { text: value }), hint ? el("span", { class: "small muted", text: hint }) : null);
}

function renderKpis() {
  const m = dash.metrics;
  clear(document.getElementById("kpis")).append(
    kpi(t("kpi.sent"), fmtNum(m.totals.sent)),
    kpi(t("kpi.abstentions"), fmtNum(m.totals.abstentions), t("kpi.abstentionsHint")),
    kpi(t("kpi.completed"), fmtPct(m.totals.completion_rate, 1)),
    kpi(t("kpi.refusals"), fmtPct(m.totals.refusal_rate, 1)),
    kpi(t("kpi.openTasks"), fmtNum(m.totals.open_tasks)),
    kpi(t("kpi.appointments"), fmtNum(m.totals.appointments)),
    kpi(t("kpi.cache"), fmtPct(m.render_cache.hit_rate, 1), t("kpi.cacheHint", { entries: m.render_cache.entries, hits: m.render_cache.hits })),
  );
}

// =========================================================================== task queue
function renderFilter() {
  const box = clear(document.getElementById("task-filter"));
  for (const f of ["open", "done"]) {
    const n = dash.tasks.filter((x) => x.status === f).length;
    box.append(el("button", { type: "button", class: `seg-btn${dash.filter === f ? " active" : ""}`, text: `${t(`dash.filter.${f}`)} (${n})`,
      onclick: () => { dash.filter = f; dash.selected = null; renderTasks(); renderDetail(); renderFilter(); } }));
  }
}

function renderTasks() {
  const root = clear(document.getElementById("tasks"));
  const list = dash.tasks.filter((x) => x.status === dash.filter);
  if (!list.length) { root.append(el("p", { class: "muted small", text: t("dash.noTasks") })); return; }
  if (!dash.selected) dash.selected = list[0].id;
  for (const task of list) {
    root.append(el("button", { type: "button", class: `task-card${task.id === dash.selected ? " active" : ""}${task.priority === "high" ? " high" : ""}`,
      onclick: () => { dash.selected = task.id; dash.journal = null; renderTasks(); renderDetail(); } },
      el("div", { class: "task-top" },
        el("span", { class: `tag tt-${task.task_type}`, text: t(`tasktype.${task.task_type}`) }),
        task.priority === "high" ? el("span", { class: "tag danger", text: t("dash.urgent") }) : null,
        el("span", { class: "small muted", text: fmtDateTime(task.created_at) })),
      el("strong", { text: task.display_name }),
      el("span", { class: "small", text: t(`taskreason.${task.reason_code}`) }),
      el("code", { class: "small", text: task.action_id })));
  }
}

function renderDetail() {
  const root = clear(document.getElementById("task-detail"));
  const task = dash.tasks.find((x) => x.id === dash.selected);
  if (!task) { root.append(el("p", { class: "muted", text: t("dash.selectTask") })); return; }

  root.append(el("div", { class: "detail-head" },
    el("div", {}, el("h3", { text: task.display_name }), el("p", { class: "small muted", text: `${task.username ? t(`persona.${task.username}`) : task.persona} · ${task.language.toUpperCase()}` })),
    el("span", { class: `tag tt-${task.task_type}`, text: t(`tasktype.${task.task_type}`) })));
  root.append(el("p", { class: "small help", text: t(`tasktype.${task.task_type}.help`) }));

  const facts = el("dl", { class: "facts" });
  const fact = (k, v) => facts.append(el("dt", { text: k }), el("dd", {}, v));
  fact(t("dash.reason"), t(`taskreason.${task.reason_code}`));
  fact(t("dash.action"), el("code", { text: task.action_id }));
  if (task.appointment) fact(t("dash.appointment"), `${fmtDateTime(task.appointment.starts_at)} · ${t(`mode.${task.appointment.mode}`)} · ${t(`appt.status.${task.appointment.status}`)}`);
  if (task.transfer) fact(t("dash.transfer"), `${fmtEUR(task.transfer.amount)} → ${task.transfer.beneficiary} · ${t(`transfer.${task.transfer.status}`)}`);
  if (task.status === "done") fact(t("dash.outcome"), `${t(`outcome.${task.outcome}`)}${task.outcome_note ? ` · “${task.outcome_note}”` : ""}`);
  root.append(facts);

  if (task.decision_id) {
    root.append(el("button", { class: "btn link small", type: "button", text: dash.journal ? t("dash.hideJournal") : t("dash.showJournal"),
      onclick: () => toggleJournal(task.decision_id) }));
    if (dash.journal) root.append(journalBox(dash.journal));
  }

  if (task.allowed_actions.length) root.append(actionForms(task));

  root.append(el("h4", { class: "mt", text: t("dash.history") }));
  root.append(el("ol", { class: "timeline-list" }, task.events.map((e) =>
    el("li", {}, el("span", { class: "small muted", text: `${fmtDateTime(e.at)} · ${e.actor}` }), el("span", { text: eventText(e) })))));
}

function eventText(e) {
  const [kind, value] = e.event.split(":");
  let txt;
  if (kind === "closed") txt = `${t("event.closed")} · ${t(`outcome.${value}`)}`;
  else if (kind === "call") txt = `${t("event.call")} · ${t(`outcome.${value}`)}`;
  else if (kind === "created") txt = `${t("event.created")} · ${t(`taskreason.${e.detail}`)}`;
  else txt = t(`event.${kind}`) !== `event.${kind}` ? t(`event.${kind}`) : t(`taskreason.${kind}`);
  if (kind === "appointment_booked") {
    const [when, mode] = e.detail.split(" ");
    txt += ` · ${fmtDateTime(when)} · ${t(`mode.${(mode || "").replace(/[()]/g, "")}`)}`;
  } else if (e.detail && kind !== "created") txt += ` · ${e.detail}`;
  return txt;
}

async function toggleJournal(decisionId) {
  if (dash.journal) { dash.journal = null; renderDetail(); return; }
  try { dash.journal = (await Api.get(`/api/advisor/decisions/${decisionId}`)).journal; renderDetail(); }
  catch (ex) { toast(ex.message, "error"); }
}

function journalBox(j) {
  return el("div", { class: "task-journal" },
    el("p", { class: "small", text: `${t("back.channel")} ${t(`channel.${j.decision.channel}`)} · ${t(`chreason.${j.decision.channel_reason}`)}` }),
    el("ul", {}, j.derived.signals.map((s) => el("li", { class: "small", text: `${s.name} = ${s.value} (conf. ${s.confidence}) · ${s.families.map((f) => t(`fam.${f}`)).join(", ")}` }))),
    el("p", { class: "small muted", text: `${t("back.guardrails")}: ${j.guardrails.map((g) => t(`guard.${g}`)).join(" · ") || "–"}` }),
    el("p", { class: "small muted", text: `${t("back.stress")} ${j.derived.financial_stress}/3 · ${t("back.excluded", { n: j.excluded_sensitive_transactions })}` }));
}

// ---------------------------------------------------------------- action forms, coherent with the task type
function actionForms(task) {
  const box = el("div", { class: "actions-box" }, el("h4", { text: t("dash.takeAction") }));
  const note = el("textarea", { rows: 2, maxlength: 500, placeholder: t("dash.notePlaceholder") });
  box.append(el("label", {}, el("span", { class: "small", text: t("dash.note") }), note));
  const has = (a) => task.allowed_actions.includes(a);
  const run = (action, extra = {}) => doAction(task.id, { action, note: note.value, ...extra });

  if (has("log_call")) {
    const outcome = el("select", {}, el("option", { value: "reached", text: t("outcome.reached") }), el("option", { value: "no_answer", text: t("outcome.no_answer") }));
    box.append(el("div", { class: "action-row" }, el("span", { class: "small strong", text: t("act.log_call") }), outcome,
      el("button", { class: "btn secondary small", type: "button", text: t("act.log_call.btn"), onclick: () => run("log_call", { outcome: outcome.value }) })));
  }
  if (has("book_appointment")) {
    const slot = el("select", {}, dash.slots.map((s) => el("option", { value: String(s.id), text: fmtDateTime(s.starts_at) })));
    const mode = el("select", {}, ["phone", "video", "branch"].map((m) => el("option", { value: m, text: t(`mode.${m}`) })));
    box.append(el("div", { class: "action-row" }, el("span", { class: "small strong", text: t("act.book_appointment") }), slot, mode,
      el("button", { class: "btn primary small", type: "button", text: t("act.book_appointment.btn"), disabled: !dash.slots.length,
        onclick: () => run("book_appointment", { slot_id: Number(slot.value), mode: mode.value }) })));
  }
  if (has("complete")) {
    box.append(el("div", { class: "action-row" },
      el("button", { class: "btn primary small", type: "button", text: t("act.complete"), onclick: () => run("complete") }),
      el("button", { class: "btn secondary small", type: "button", text: t("act.no_show"), onclick: () => run("no_show") }),
      el("button", { class: "btn ghost small", type: "button", text: t("act.cancel_appointment"), onclick: () => run("cancel_appointment") })));
    if (task.task_type === "credit_review") box.append(el("p", { class: "small warn", text: t("act.creditNote") }));
  }
  if (has("release_transfer")) {
    box.append(el("p", { class: "small warn", text: t("act.fraudNote") }));
    box.append(el("div", { class: "action-row" },
      el("button", { class: "btn danger small", type: "button", text: t("act.block_transfer"), onclick: () => run("block_transfer") }),
      el("button", { class: "btn secondary small", type: "button", text: t("act.release_transfer"), onclick: () => run("release_transfer") })));
  }
  if (has("dismiss")) {
    box.append(el("div", { class: "action-row" },
      el("button", { class: "btn ghost small", type: "button", text: t("act.dismiss"), onclick: () => run("dismiss") })));
  }
  return box;
}

async function doAction(taskId, body) {
  try {
    await Api.post(`/api/advisor/tasks/${taskId}/actions`, body);
    toast(t("toast.actionDone"), "ok");
    await loadAll();
  } catch (ex) { toast(ex.message, "error"); }
}

// =========================================================================== agenda
function renderAgenda() {
  const root = clear(document.getElementById("agenda"));
  if (!dash.appointments.length) { root.append(el("p", { class: "muted small", text: t("dash.noAppointments") })); return; }
  let day = "";
  const list = el("div", { class: "agenda" });
  for (const a of dash.appointments) {
    const d = a.starts_at.slice(0, 10);
    if (d !== day) { list.append(el("div", { class: "slot-day", text: fmtDay(a.starts_at) })); day = d; }
    list.append(el("button", { class: "agenda-item", type: "button",
      onclick: () => { dash.filter = "open"; dash.selected = a.task_id; renderFilter(); renderTasks(); renderDetail(); document.getElementById("task-detail").scrollIntoView({ behavior: "smooth", block: "nearest" }); } },
      el("strong", { text: fmtTime(a.starts_at) }), el("span", { text: a.display_name }),
      el("span", { class: "tag", text: t(`mode.${a.mode}`) }), el("code", { class: "small", text: a.action_id })));
  }
  root.append(list);
}

// =========================================================================== learning & fairness
function table(headers, rows) {
  return el("div", { class: "table-wrap" }, el("table", { class: "jtable" },
    el("thead", {}, el("tr", {}, headers.map((h) => el("th", { text: h })))), el("tbody", {}, rows)));
}

function renderActions(actions) {
  const root = clear(document.getElementById("actions-table"));
  if (!actions.length) { root.append(el("p", { class: "muted", text: t("dash.noData") })); return; }
  root.append(table([t("col.action"), t("col.segment"), t("col.sent"), t("col.efficiency"), t("col.completed"), t("col.refusals"), t("col.why")],
    actions.map((a) => el("tr", {},
      el("td", {}, el("code", { text: a.action_id }), el("div", { class: "small muted", text: t(`family.${a.family}`) })),
      el("td", { class: "small", text: a.segment }), el("td", { text: fmtNum(a.sent) }),
      el("td", {}, meter(a.efficiency), el("span", { class: "small", text: ` ${a.efficiency.toFixed(2)}` })),
      el("td", { text: fmtPct(a.completion_rate) }), el("td", { text: fmtPct(a.refusal_rate) }), el("td", { text: fmtPct(a.why_opened_rate) })))));
}

function meter(v) {
  const m = el("span", { class: "meter" }, el("span", { class: "meter-fill" }));
  m.firstChild.style.width = `${Math.round(v * 100)}%`;
  return m;
}

function renderChannels(ch) {
  const root = clear(document.getElementById("channels"));
  const total = Object.values(ch).reduce((a, b) => a + b, 0) || 1;
  for (const c of ["app", "push", "voice", "human"]) {
    const v = ch[c] || 0;
    root.append(el("div", { class: "hbar" }, el("span", { class: `tag ch-${c}`, text: t(`channel.${c}`) }), meter(v / total), el("span", { class: "small", text: `${fmtNum(v)} · ${fmtPct(v / total)}` })));
  }
}

function renderFairness(rows) {
  const root = clear(document.getElementById("fairness"));
  if (!rows.length) { root.append(el("p", { class: "muted small", text: t("dash.noData") })); return; }
  root.append(table([t("col.band"), t("col.sent"), t("col.commercial"), t("col.refusals"), ""], rows.map((r) => el("tr", {},
    el("td", { text: r.age_band }), el("td", { text: fmtNum(r.sent) }), el("td", { text: fmtPct(r.commercial_share) }), el("td", { text: fmtPct(r.refusal_rate) }),
    el("td", {}, r.alert ? el("span", { class: "status blocked", text: t("dash.review") }) : el("span", { class: "status chosen", text: "OK" }))))));
}

function renderBandit(bandit) {
  const root = clear(document.getElementById("bandit"));
  const rows = [];
  for (const [action, variants] of Object.entries(bandit)) {
    for (const [v, s] of Object.entries(variants)) {
      const n = s.successes + s.failures;
      rows.push(el("tr", {}, el("td", {}, el("code", { text: action })), el("td", { text: t(`tone.${v}`) }), el("td", { text: fmtNum(n) }), el("td", { text: n ? fmtPct(s.successes / n) : "–" })));
    }
  }
  if (!rows.length) { root.append(el("p", { class: "muted small", text: t("dash.noData") })); return; }
  root.append(table([t("col.action"), t("col.tone"), t("col.sent"), t("col.success")], rows));
}

// ---------------------------------------------------------------- SVG line chart (one series, hover)
const SVGNS = "http://www.w3.org/2000/svg";
function svg(tag, attrs) { const n = document.createElementNS(SVGNS, tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); return n; }

function renderTimeline(points) {
  const root = clear(document.getElementById("timeline"));
  if (points.length < 2) { root.append(el("p", { class: "muted small", text: t("dash.noData") })); return; }
  const W = 560, H = 220, P = { l: 40, r: 12, t: 12, b: 28 };
  const ys = points.map((p) => p.mean_value);
  const yMin = Math.min(0, ...ys), yMax = Math.max(0.5, ...ys);
  const x = (i) => P.l + (i * (W - P.l - P.r)) / (points.length - 1);
  const y = (v) => P.t + ((yMax - v) * (H - P.t - P.b)) / (yMax - yMin || 1);
  const s = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": t("dash.timeline"), class: "line-chart" });
  for (const v of [yMin, 0, yMax].filter((v, i, a) => a.indexOf(v) === i)) {
    s.append(svg("line", { x1: P.l, x2: W - P.r, y1: y(v), y2: y(v), class: v === 0 ? "axis" : "grid" }));
    const tx = svg("text", { x: P.l - 6, y: y(v) + 4, "text-anchor": "end", class: "tick" }); tx.textContent = v.toFixed(2); s.append(tx);
  }
  [0, points.length - 1].forEach((i) => {
    const tx = svg("text", { x: x(i), y: H - 8, "text-anchor": i ? "end" : "start", class: "tick" }); tx.textContent = points[i].day.slice(5); s.append(tx);
  });
  s.append(svg("path", { d: points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.mean_value).toFixed(1)}`).join(" "), class: "series" }));
  const cross = svg("line", { y1: P.t, y2: H - P.b, class: "crosshair", visibility: "hidden" });
  const dot = svg("circle", { r: 4.5, class: "dot", visibility: "hidden" });
  s.append(cross, dot);
  const tip = el("div", { class: "tooltip", hidden: true });
  s.addEventListener("mousemove", (ev) => {
    const r = s.getBoundingClientRect();
    const px = ((ev.clientX - r.left) / r.width) * W;
    const i = Math.max(0, Math.min(points.length - 1, Math.round(((px - P.l) / (W - P.l - P.r)) * (points.length - 1))));
    const p = points[i];
    cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i)); cross.setAttribute("visibility", "visible");
    dot.setAttribute("cx", x(i)); dot.setAttribute("cy", y(p.mean_value)); dot.setAttribute("visibility", "visible");
    tip.hidden = false;
    tip.textContent = t("dash.tooltip", { day: p.day, value: p.mean_value.toFixed(2), sent: p.sent });
    tip.style.left = `${(x(i) / W) * 100}%`;
  });
  s.addEventListener("mouseleave", () => { cross.setAttribute("visibility", "hidden"); dot.setAttribute("visibility", "hidden"); tip.hidden = true; });
  root.append(s, tip);
}

// ---------------------------------------------------------------- cost calculator
const COST_FIELDS = [
  ["customers", 2300000, 1], ["trigger", 3, 0.1], ["cache", 95, 1], ["tin", 700, 50], ["tout", 250, 10],
  ["pin", 0.30, 0.01], ["pout", 2.50, 0.01], ["voice", 5, 1], ["vchars", 400, 10], ["vcache", 90, 1], ["vprice", 0.10, 0.01], ["naive_tin", 4000, 100],
];
const costValues = {};

function buildCostForm() {
  const form = clear(document.getElementById("cost-form"));
  for (const [id, value, step] of COST_FIELDS) {
    const input = el("input", { type: "number", id: `c_${id}`, step, min: 0, value: costValues[id] ?? value });
    input.addEventListener("input", () => { costValues[id] = input.value; computeCost(); });
    form.append(el("label", {}, el("span", { class: "small", text: t(`cost.${id}`) }), input));
  }
}

function computeCost() {
  const v = Object.fromEntries(COST_FIELDS.map(([id]) => [id, parseFloat(document.getElementById(`c_${id}`)?.value) || 0]));
  const actions = v.customers * (v.trigger / 100);
  const llmCalls = actions * (1 - v.cache / 100);
  const llmDay = llmCalls * (v.tin * v.pin + v.tout * v.pout) / 1e6;
  const voiceDay = actions * (v.voice / 100) * (1 - v.vcache / 100) * (v.vchars / 1000) * v.vprice;
  const day = llmDay + voiceDay;
  const naiveDay = v.customers * (v.naive_tin * v.pin + v.tout * v.pout) / 1e6;
  const usd = (n) => new Intl.NumberFormat(locale(), { style: "currency", currency: "USD", maximumFractionDigits: n < 0.1 ? 4 : n < 10 ? 2 : 0 }).format(n);
  const out = clear(document.getElementById("cost-out"));
  const row = (key, value, strong) => el("div", { class: `cost-row${strong ? " strong" : ""}` }, el("span", { text: t(key) }), el("span", { text: value }));
  out.append(
    row("cost.out.decisions", fmtNum(v.customers)), row("cost.out.actions", fmtNum(actions)), row("cost.out.calls", fmtNum(llmCalls)),
    row("cost.out.llm", usd(llmDay)), row("cost.out.voice", usd(voiceDay)), row("cost.out.month", usd(day * 30), true),
    row("cost.out.perCustomer", usd((day * 365) / (v.customers || 1)), true), el("hr"),
    row("cost.out.naive", `${usd(naiveDay * 30)} / ${t("cost.month")}`), row("cost.out.factor", naiveDay && day ? `× ${fmtNum(naiveDay / day)}` : "–", true));
  if (dash.metrics) out.append(el("p", { class: "small muted", text: t("cost.cacheNote", { entries: dash.metrics.render_cache.entries, rate: fmtPct(dash.metrics.render_cache.hit_rate, 1) }) }));
}

// =========================================================================== start
function mountSwitches() {
  document.querySelectorAll("[data-lang-switch]").forEach((c) => mountLanguageSwitch(c, async () => {
    mountSwitches();
    if (!document.getElementById("app-view").hidden) { buildCostForm(); renderAll(); }
  }));
}

(async () => {
  applyStaticI18n();
  mountSwitches();
  if (Api.token) { try { await showApp(); return; } catch { Api.token = null; } }
  showLogin();
})();

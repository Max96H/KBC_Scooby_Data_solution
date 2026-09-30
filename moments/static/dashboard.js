"use strict";

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
    if (r.role !== "advisor") { err.textContent = "Ce compte n'est pas un compte conseiller."; return; }
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

let lastMetrics = null;

async function loadAll() {
  const [tasks, metrics] = await Promise.all([Api.get("/api/advisor/tasks"), Api.get("/api/advisor/metrics")]);
  lastMetrics = metrics;
  renderKpis(metrics, tasks);
  renderTasks(tasks);
  renderActions(metrics.actions);
  renderTimeline(metrics.timeline);
  renderFairness(metrics.fairness);
  renderBandit(metrics.bandit);
  computeCost();
}

function kpi(label, value, hint) {
  return el("div", { class: "kpi card" }, el("span", { class: "small muted", text: label }), el("strong", { text: value }), hint ? el("span", { class: "small muted", text: hint }) : null);
}

function renderKpis(m, tasks) {
  const root = clear(document.getElementById("kpis"));
  root.append(
    kpi("Messages envoyés (30 j)", fmtNum(m.totals.sent)),
    kpi("Abstentions", fmtNum(m.totals.abstentions), "le moteur a choisi de ne rien faire"),
    kpi("Actions utiles complétées", fmtPct(m.totals.completion_rate, 1)),
    kpi("Taux de refus", fmtPct(m.totals.refusal_rate, 1)),
    kpi("Tâches ouvertes", fmtNum(tasks.filter((t) => t.status === "open").length)),
    kpi("Cache de rendu", fmtPct(m.render_cache.hit_rate, 1), `${m.render_cache.entries} textes, ${m.render_cache.hits} réutilisations`),
  );
}

function table(headers, rows) {
  return el("div", { class: "table-wrap" }, el("table", { class: "jtable" },
    el("thead", {}, el("tr", {}, headers.map((h) => el("th", { text: h })))),
    el("tbody", {}, rows)));
}

function renderTasks(tasks) {
  const root = clear(document.getElementById("tasks"));
  if (!tasks.length) { root.append(el("p", { class: "muted", text: "Aucune tâche pour l'instant. Ouvrez la démo client (Sofia, Marcel, ou un clic sur « Prendre rendez-vous »)." })); return; }
  root.append(table(["Client", "Action", "Motif", "Statut", ""], tasks.map((t) => el("tr", {},
    el("td", { text: t.display_name }),
    el("td", {}, el("span", { class: "tag", text: t.family }), " ", el("code", { text: t.action_id })),
    el("td", { class: "small", text: t.reason }),
    el("td", {}, el("span", { class: `status ${t.status === "open" ? "eligible" : "chosen"}`, text: t.status === "open" ? "ouverte" : "traitée" })),
    el("td", { class: "actions" },
      t.decision_id ? el("button", { class: "btn small secondary", text: "Journal", onclick: () => showJournal(t.decision_id) }) : null,
      t.status === "open" ? el("button", { class: "btn small primary", text: "Clôturer", onclick: () => closeTask(t.id) }) : null)))));
}

async function closeTask(id) {
  try { await Api.post(`/api/advisor/tasks/${id}/done`); toast("Tâche clôturée.", "ok"); await loadAll(); } catch (ex) { toast(ex.message, "error"); }
}

async function showJournal(decisionId) {
  const box = document.getElementById("task-journal");
  try {
    const r = await Api.get(`/api/advisor/decisions/${decisionId}`);
    const j = r.journal;
    clear(box).hidden = false;
    box.append(
      el("h3", { text: `Pourquoi le moteur a proposé « ${r.action_id} »` }),
      el("p", { class: "small", text: `Canal : ${r.channel} · ${j.decision.channel_reason}` }),
      el("ul", {}, j.derived.signals.map((s) => el("li", { class: "small", text: `${s.name} = ${s.value} (conf. ${s.confidence}) · ${s.families.join(", ")}` }))),
      el("p", { class: "small muted", text: "Garde-fous : " + (j.guardrails.map((g) => g.text).join(" · ") || "aucun") }),
      el("p", { class: "small muted", text: `Stress financier ${j.derived.financial_stress}/3 · ${j.excluded_sensitive_transactions} transaction(s) sensible(s) exclue(s)` }),
    );
  } catch (ex) { toast(ex.message, "error"); }
}

function renderActions(actions) {
  const root = clear(document.getElementById("actions-table"));
  if (!actions.length) { root.append(el("p", { class: "muted", text: "Pas encore de données. Lancez « python -m scripts.simulate_feedback » pour simuler 30 jours." })); return; }
  root.append(table(["Action", "Segment", "Envois", "Efficacité", "Complétées", "Refus", "« Pourquoi » ouvert"], actions.map((a) => el("tr", {},
    el("td", {}, el("code", { text: a.action_id }), el("div", { class: "small muted", text: a.family })),
    el("td", { class: "small", text: a.segment }),
    el("td", { text: fmtNum(a.sent) }),
    el("td", {}, meter(a.efficiency), el("span", { class: "small", text: ` ${a.efficiency.toFixed(2)}` })),
    el("td", { text: fmtPct(a.completion_rate) }),
    el("td", { text: fmtPct(a.refusal_rate) }),
    el("td", { text: fmtPct(a.why_opened_rate) }),
  ))));
}

function meter(v) {
  const m = el("span", { class: "meter" }, el("span", { class: "meter-fill" }));
  m.firstChild.style.width = `${Math.round(v * 100)}%`;
  return m;
}

function renderFairness(rows) {
  const root = clear(document.getElementById("fairness"));
  if (!rows.length) { root.append(el("p", { class: "muted small", text: "Pas encore de données." })); return; }
  root.append(table(["Tranche", "Envois", "Part commerciale", "Refus", ""], rows.map((r) => el("tr", {},
    el("td", { text: r.age_band }), el("td", { text: fmtNum(r.sent) }), el("td", { text: fmtPct(r.commercial_share) }),
    el("td", { text: fmtPct(r.refusal_rate) }),
    el("td", {}, r.alert ? el("span", { class: "status blocked", text: "⚠ à revoir" }) : el("span", { class: "status chosen", text: "OK" })),
  ))));
}

function renderBandit(bandit) {
  const root = clear(document.getElementById("bandit"));
  const rows = [];
  for (const [action, variants] of Object.entries(bandit)) {
    for (const [v, s] of Object.entries(variants)) {
      const n = s.successes + s.failures;
      rows.push(el("tr", {}, el("td", {}, el("code", { text: action })), el("td", { text: v }), el("td", { text: fmtNum(n) }), el("td", { text: n ? fmtPct(s.successes / n) : "–" })));
    }
  }
  if (!rows.length) { root.append(el("p", { class: "muted small", text: "Pas encore de données." })); return; }
  root.append(table(["Action", "Ton", "Envois", "Succès"], rows));
}

// ---------------------------------------------------------------- Courbe SVG (une série, survol)
const SVGNS = "http://www.w3.org/2000/svg";
function svg(tag, attrs) { const n = document.createElementNS(SVGNS, tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); return n; }

function renderTimeline(points) {
  const root = clear(document.getElementById("timeline"));
  if (points.length < 2) { root.append(el("p", { class: "muted small", text: "Pas encore assez de jours." })); return; }
  const W = 560, H = 220, P = { l: 40, r: 12, t: 12, b: 28 };
  const ys = points.map((p) => p.mean_value);
  const yMin = Math.min(0, ...ys), yMax = Math.max(0.5, ...ys);
  const x = (i) => P.l + (i * (W - P.l - P.r)) / (points.length - 1);
  const y = (v) => P.t + ((yMax - v) * (H - P.t - P.b)) / (yMax - yMin || 1);
  const s = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Valeur moyenne des réactions par jour", class: "line-chart" });
  for (const v of [yMin, 0, yMax].filter((v, i, a) => a.indexOf(v) === i)) {
    s.append(svg("line", { x1: P.l, x2: W - P.r, y1: y(v), y2: y(v), class: v === 0 ? "axis" : "grid" }));
    const t = svg("text", { x: P.l - 6, y: y(v) + 4, "text-anchor": "end", class: "tick" }); t.textContent = v.toFixed(2); s.append(t);
  }
  [0, points.length - 1].forEach((i) => {
    const t = svg("text", { x: x(i), y: H - 8, "text-anchor": i ? "end" : "start", class: "tick" }); t.textContent = points[i].day.slice(5); s.append(t);
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
    tip.textContent = `${p.day} · valeur moyenne ${p.mean_value.toFixed(2)} · ${p.sent} envois`;
    tip.style.left = `${(x(i) / W) * 100}%`;
  });
  s.addEventListener("mouseleave", () => { cross.setAttribute("visibility", "hidden"); dot.setAttribute("visibility", "hidden"); tip.hidden = true; });
  root.append(s, tip);
}

// ---------------------------------------------------------------- Calculateur de coût
const COST_FIELDS = [
  ["customers", "Clients", 2300000, 1],
  ["trigger", "Clients avec une action / jour (%)", 3, 0.1],
  ["cache", "Taux de réutilisation du cache (%)", 95, 1],
  ["tin", "Tokens en entrée par rendu", 700, 50],
  ["tout", "Tokens en sortie par rendu", 250, 10],
  ["pin", "Prix entrée ($ / 1M tokens)", 0.30, 0.01],
  ["pout", "Prix sortie ($ / 1M tokens)", 2.50, 0.01],
  ["voice", "Part des actions en voix (%)", 5, 1],
  ["vchars", "Caractères par message vocal", 400, 10],
  ["vcache", "Réutilisation audio (%)", 90, 1],
  ["vprice", "Prix voix ($ / 1 000 caractères)", 0.10, 0.01],
  ["naive_tin", "Approche naïve : tokens entrée / client / jour", 4000, 100],
];

function buildCostForm() {
  const form = clear(document.getElementById("cost-form"));
  for (const [id, label, value, step] of COST_FIELDS) {
    const input = el("input", { type: "number", id: `c_${id}`, step, min: 0, value });
    input.addEventListener("input", computeCost);
    form.append(el("label", {}, el("span", { class: "small", text: label }), input));
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
  const usd = (n) => new Intl.NumberFormat("fr-BE", { style: "currency", currency: "USD", maximumFractionDigits: n < 0.1 ? 4 : n < 10 ? 2 : 0 }).format(n);
  const out = clear(document.getElementById("cost-out"));
  const row = (label, value, strong) => el("div", { class: `cost-row${strong ? " strong" : ""}` }, el("span", { text: label }), el("span", { text: value }));
  out.append(
    row("Décisions calculées / jour (déterministes)", fmtNum(v.customers)),
    row("Actions déclenchées / jour", fmtNum(actions)),
    row("Appels LLM réels / jour (après cache)", fmtNum(llmCalls)),
    row("Coût LLM / jour", usd(llmDay)),
    row("Coût voix / jour", usd(voiceDay)),
    row("Total / mois (30 j)", usd(day * 30), true),
    row("Par client et par an", usd((day * 365) / (v.customers || 1)), true),
    el("hr"),
    row("Approche naïve : un LLM analyse chaque client chaque jour", usd(naiveDay * 30) + " / mois"),
    row("Facteur d'économie", naiveDay && day ? `× ${fmtNum(naiveDay / day)}` : "–", true),
  );
  if (lastMetrics) out.append(el("p", { class: "small muted", text: `Dans cette démo, le cache contient ${lastMetrics.render_cache.entries} textes (7 personas, presque tous uniques : réutilisation mesurée ${fmtPct(lastMetrics.render_cache.hit_rate, 1)}). À l'échelle, un même texte sert tout un segment : la clé de cache compte environ 15 actions × 12 segments × 2 langues × 2 tons × 2 formats ≈ 1 440 textes pour 2,3 M de clients.` }));
}

(async () => {
  if (Api.token) { try { await showApp(); return; } catch { Api.token = null; } }
  showLogin();
})();

"use strict";

const PERSONAS = [
  { username: "emma", name: "Emma", desc: "Jeune couple, bébé en route", expect: "Proposer" },
  { username: "sofia", name: "Sofia", desc: "Même bébé, budget sous tension", expect: "Accompagner" },
  { username: "jan", name: "Jan & Monique", desc: "Grands-parents, peu digitaux (NL)", expect: "Informer · voix" },
  { username: "marcel", name: "Marcel", desc: "Virement suspect en cours", expect: "Protéger" },
  { username: "yasmine", name: "Yasmine", desc: "Premier salaire", expect: "Informer" },
  { username: "thomas", name: "Thomas", desc: "Rien de particulier", expect: "S'abstenir" },
  { username: "nina", name: "Nina", desc: "Simulation de prêt abandonnée", expect: "Simplifier" },
];

const CHANNEL_LABEL = {
  app: "Bloc sur l'écran d'accueil",
  push: "Notification push",
  voice: "Message vocal",
  human: "Proposition de rendez-vous humain",
};
const FAMILY_CLASS = { inform: "f-inform", protect: "f-protect", simplify: "f-simplify", propose: "f-propose", accompany: "f-accompany", abstain: "f-abstain" };

let state = { decisionId: null, screen: null, me: null, holdTimer: null };

function onUnauthorized() { showLogin(); }

// ---------------------------------------------------------------- Connexion
function showLogin() {
  document.getElementById("app-view").hidden = true;
  document.getElementById("login-view").hidden = false;
  const grid = clear(document.getElementById("persona-grid"));
  for (const p of PERSONAS) {
    grid.append(el("button", {
      class: "persona", type: "button",
      onclick: () => {
        document.getElementById("login-username").value = p.username;
        document.getElementById("login-password").focus();
        document.querySelectorAll(".persona").forEach((b) => b.classList.remove("selected"));
        grid.querySelector(`[data-u="${p.username}"]`).classList.add("selected");
      },
      dataset: { u: p.username },
    }, el("strong", { text: p.name }), el("span", { class: "muted small", text: p.desc }), el("span", { class: "tag", text: p.expect })));
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
    if (r.role !== "customer") { window.location.href = "/conseiller"; return; }
    Api.token = r.token;
    document.getElementById("login-password").value = "";
    await showApp();
  } catch (ex) { err.textContent = ex.message; }
});

document.getElementById("logout").addEventListener("click", () => { Api.token = null; showLogin(); });

// ---------------------------------------------------------------- Application
async function showApp() {
  document.getElementById("login-view").hidden = true;
  document.getElementById("app-view").hidden = false;
  state.me = await Api.get("/api/me");
  document.getElementById("who").textContent = `${state.me.display_name} · ${state.me.persona}`;
  document.getElementById("greeting").textContent = (state.me.language === "nl" ? "Goeiedag " : "Bonjour ") + state.me.first_name;
  document.getElementById("balance").textContent = fmtEUR(state.me.balance);
  document.getElementById("demo-clock").textContent = "Date de démo : " + new Date(state.me.demo_now).toLocaleString("fr-BE", { dateStyle: "medium", timeStyle: "short" });
  selectTab("home");
  await loadFeed();
}

function selectTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  document.getElementById("tab-home").hidden = name !== "home";
  document.getElementById("tab-data").hidden = name !== "data";
  if (name === "data") loadConsents();
}
document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => selectTab(t.dataset.tab)));

async function loadFeed() {
  const r = await Api.get("/api/me/feed");
  state.decisionId = r.decision_id;
  state.screen = r.screen;
  renderScreen(r.screen);
  renderJournal(r.journal);
}

// ---------------------------------------------------------------- Rendu des blocs (types connus uniquement)
function renderScreen(screen) {
  const root = clear(document.getElementById("blocks"));
  clearInterval(state.holdTimer);
  const banner = document.getElementById("channel-banner");
  banner.textContent = `${screen.family_label} · ${CHANNEL_LABEL[screen.channel] || screen.channel}`;
  banner.className = `channel-banner ${FAMILY_CLASS[screen.family] || ""}`;
  const renderers = { highlight, checklist, why_panel: whyPanel, transfer_hold: transferHold, voice: voiceBlock, human: humanBlock, abstain: abstainBlock };
  for (const block of screen.blocks) {
    const fn = renderers[block.type];
    if (fn) root.append(fn(block, screen)); // tout type inconnu est ignoré
  }
  document.getElementById("feedback-bar").hidden = screen.action_id === "abstain";
}

function highlight(b, screen) {
  const ctas = el("div", { class: "ctas" });
  b.ctas.forEach((c, i) => ctas.append(el("button", {
    class: `btn ${i === 0 ? "primary" : "secondary"}`, text: c.label, onclick: () => clickCta(c.id),
  })));
  return el("article", { class: `block highlight ${FAMILY_CLASS[screen.family] || ""}` },
    el("h3", { text: b.title }), el("p", { text: b.body }), ctas);
}

function checklist(b) {
  return el("article", { class: "block checklist" },
    b.title ? el("h4", { text: b.title }) : null,
    el("ul", {}, b.items.map((i) => el("li", { text: i }))));
}

function whyPanel(b) {
  const details = el("details", { class: "block why" });
  details.append(el("summary", { text: b.title }));
  if (b.signals_used.length) details.append(el("ul", {}, b.signals_used.map((s) => el("li", { text: s }))));
  b.notes.forEach((n) => details.append(el("p", { class: "small muted", text: n })));
  if (b.families.length) {
    details.append(el("button", { class: "btn link small", text: "Gérer ces données →", onclick: () => selectTab("data") }));
  }
  details.addEventListener("toggle", () => {
    if (details.open && state.decisionId && state.screen.action_id !== "abstain") {
      Api.post(`/api/me/decisions/${state.decisionId}/why`).catch(() => {});
    }
  }, { once: false });
  return details;
}

function transferHold(b) {
  const counter = el("strong", { class: "countdown" });
  const box = el("article", { class: "block hold" },
    el("p", { class: "small muted", text: "Virement en attente de sécurité" }),
    el("p", {}, el("strong", { text: fmtEUR(b.amount) }), " → ", el("span", { text: b.beneficiary })),
    el("p", { class: "small" }, "Exécution possible dans : ", counter));
  const until = b.hold_until ? new Date(b.hold_until + "Z").getTime() : 0;
  const tick = () => {
    const s = Math.max(0, Math.round((until - Date.now()) / 1000));
    counter.textContent = s ? `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, "0")} s` : "maintenant (si vous connaissez ce bénéficiaire)";
    if (!s) clearInterval(state.holdTimer);
  };
  if (b.status === "held") { tick(); state.holdTimer = setInterval(tick, 1000); } else counter.textContent = b.status;
  return box;
}

function voiceBlock(b, screen) {
  const btn = el("button", { class: "btn primary", text: "▶ Écouter le message" });
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    try {
      const res = await Api.request("GET", `/api/me/decisions/${state.decisionId}/voice`, null, { raw: true });
      if (res.status === 200) {
        const url = URL.createObjectURL(await res.blob());
        const audio = new Audio(url);
        audio.addEventListener("ended", () => URL.revokeObjectURL(url));
        await audio.play();
      } else if ("speechSynthesis" in window) {
        // Repli : synthèse vocale du navigateur (ElevenLabs non configuré)
        const u = new SpeechSynthesisUtterance(b.script);
        u.lang = screen.language === "nl" ? "nl-BE" : "fr-BE";
        u.rate = 0.95;
        speechSynthesis.cancel();
        speechSynthesis.speak(u);
        toast("Voix du navigateur (ElevenLabs non configuré)");
      }
    } catch (ex) { toast(ex.message, "error"); } finally { btn.disabled = false; }
  });
  return el("article", { class: "block voice" }, el("p", { class: "small muted", text: b.title }), btn);
}

function humanBlock(b) {
  return el("article", { class: "block human" }, el("h4", { text: b.title }), el("p", { class: "small", text: b.body }));
}

function abstainBlock(b) {
  return el("article", { class: "block abstain" }, el("div", { class: "abstain-icon", text: "✓" }),
    el("h3", { text: b.title }), el("p", { text: b.body }));
}

async function clickCta(ctaId) {
  try {
    const r = await Api.post(`/api/me/decisions/${state.decisionId}/cta`, { cta_id: ctaId });
    toast(r.message, "ok");
    await loadFeed();
  } catch (ex) { toast(ex.message, "error"); }
}

document.querySelectorAll("#feedback-bar [data-reaction]").forEach((b) => b.addEventListener("click", async () => {
  try {
    await Api.post(`/api/me/decisions/${state.decisionId}/feedback`, { reaction: b.dataset.reaction });
    toast(b.dataset.reaction === "clicked" ? "Merci pour votre retour." : "Compris. Nous ne vous le reproposerons pas de sitôt.", "ok");
    await loadFeed();
  } catch (ex) { toast(ex.message, "error"); }
}));

// ---------------------------------------------------------------- Consentement
async function loadConsents() {
  const list = await Api.get("/api/me/consents");
  const root = clear(document.getElementById("consents"));
  for (const c of list) {
    const input = el("input", { type: "checkbox", role: "switch" });
    input.checked = c.enabled;
    input.addEventListener("change", async () => {
      try {
        await Api.put(`/api/me/consents/${c.family}`, { enabled: input.checked });
        toast(input.checked ? "Réactivé." : "Coupé : cette famille de données n'est plus calculée.", "ok");
        await loadFeed();
      } catch (ex) { input.checked = !input.checked; toast(ex.message, "error"); }
    });
    root.append(el("label", { class: "consent" }, el("span", { text: c.label }), input));
  }
  root.append(el("div", { class: "consent locked" }, el("span", { text: "Prévention de la fraude (obligation légale)" }), el("span", { class: "small muted", text: "toujours actif" })));
}

// ---------------------------------------------------------------- Coulisses
const REASON_TEXT = {
  consent_withdrawn: "consentement retiré", low_confidence: "confiance < 0,6", financial_stress_no_sales: "stress ≥ 2 : pas de vente",
  suppressed_after_refusal: "refusée récemment", credit_human_in_the_loop: "crédit : humain obligatoire", one_action_at_a_time: "une seule action à la fois",
};

function renderJournal(j) {
  const root = clear(document.getElementById("journal"));
  if (!j) { root.append(el("p", { class: "muted", text: "Journal masqué (mode production)." })); return; }

  // 1. Signaux dérivés
  const sig = el("section", { class: "jcard" }, el("h3", {}, el("span", { class: "step", text: "1" }), "Signaux dérivés"));
  if (!j.derived.signals.length) sig.append(el("p", { class: "muted small", text: "Aucun signal au-dessus du bruit." }));
  for (const s of j.derived.signals) {
    const bar = el("div", { class: "bar" }, el("span", { class: s.confidence >= 0.6 ? "fill ok" : "fill low" }));
    bar.firstChild.style.width = `${Math.round(s.confidence * 100)}%`;
    sig.append(el("div", { class: "signal" },
      el("div", { class: "signal-head" }, el("code", { text: `${s.name} = ${s.value}` }), el("span", { class: "small", text: `conf. ${s.confidence.toFixed(2)}` })),
      bar,
      el("p", { class: "small muted", text: `Données : ${s.families.join(", ")}` })));
  }
  sig.append(el("p", { class: "small" },
    `Stress financier : `, el("strong", { text: `${j.derived.financial_stress}/3` }),
    ` · Revenus : ${j.derived.income_stability} · Canal préféré : ${j.derived.channel_pref}`));
  sig.append(el("p", { class: "small excluded", text: `${j.excluded_sensitive_transactions} transaction(s) sensible(s) exclue(s) avant tout calcul (RGPD art. 9)` }));
  const off = Object.entries(j.consents).filter(([, v]) => !v).map(([k]) => k);
  if (off.length) sig.append(el("p", { class: "small warn", text: `Consentement coupé : ${off.join(", ")} (non calculé)` }));
  root.append(sig);

  // 2. Candidates et score
  const cand = el("section", { class: "jcard" }, el("h3", {}, el("span", { class: "step", text: "2" }), "Actions candidates"));
  cand.append(el("p", { class: "small muted formula", text: "score = (0,35·valeur client + 0,25·urgence + 0,20·confiance + 0,10·valeur banque − 0,10·sensibilité) × (0,7 + 0,3·efficacité)" }));
  if (!j.candidates.length) cand.append(el("p", { class: "muted small", text: "Aucune candidate." }));
  const table = el("table", { class: "jtable" }, el("thead", {}, el("tr", {}, ["Action", "Score", "Statut"].map((h) => el("th", { text: h })))));
  const tb = el("tbody");
  for (const c of j.candidates) {
    tb.append(el("tr", { class: `st-${c.status}` },
      el("td", {}, el("code", { text: c.action_id }), el("div", { class: "small muted", text: `${c.trigger}${c.is_commercial ? " · commercial" : ""}` })),
      el("td", { text: c.score.toFixed(3) }),
      el("td", {}, el("span", { class: `status ${c.status}`, text: c.status === "chosen" ? "choisie" : c.status === "blocked" ? "bloquée" : "écartée" }),
        c.reasons.length ? el("div", { class: "small muted", text: c.reasons.map((r) => REASON_TEXT[r] || r).join(", ") }) : null)));
  }
  table.append(tb);
  if (j.candidates.length) cand.append(table);
  root.append(cand);

  // 3. Garde-fous
  const g = el("section", { class: "jcard" }, el("h3", {}, el("span", { class: "step", text: "3" }), "Garde-fous déclenchés"));
  if (!j.guardrails.length) g.append(el("p", { class: "muted small", text: "Aucun : la voie est libre." }));
  g.append(el("ul", { class: "guards" }, j.guardrails.map((x) => el("li", { text: x.text }))));
  root.append(g);

  // 4. Décision, canal, rendu
  const d = j.decision;
  const dec = el("section", { class: "jcard decision" }, el("h3", {}, el("span", { class: "step", text: "4" }), "Décision"),
    el("p", {}, el("strong", { text: d.action_id === "abstain" ? "S'abstenir" : d.action_id }), d.score ? ` · score ${d.score.toFixed(3)}` : ""),
    el("p", { class: "small", text: `Canal : ${CHANNEL_LABEL[d.channel] || d.channel} (${d.channel_reason})` }),
    d.requires_human ? el("p", { class: "small warn", text: "Crédit : aucune décision automatique, un humain valide (RGPD art. 22)" }) : null,
    el("p", { class: "small muted", text: `Rendu : ${j.render.source} · ton « ${j.render.variant} » · entrée LLM : ${j.render.llm_input}` }));
  const bandit = j.render.bandit || {};
  if (Object.keys(bandit).length) {
    dec.append(el("p", { class: "small muted", text: "Bandit (Thompson) : " + Object.entries(bandit).map(([v, s]) => `${v} ${s.successes}✓/${s.failures}✗ → ${s.draw}`).join(" · ") }));
  }
  root.append(dec);
}

// ---------------------------------------------------------------- Démarrage
(async () => {
  if (Api.token) { try { await showApp(); return; } catch { Api.token = null; } }
  showLogin();
})();

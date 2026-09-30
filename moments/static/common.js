// Utilitaires partagés. Règle : on ne construit JAMAIS de HTML à partir de données (pas d'innerHTML),
// uniquement des nœuds DOM avec textContent. Même un texte généré par LLM ne peut donc rien injecter.
"use strict";

const Api = {
  tokenKey: "moments_token",
  get token() { try { return sessionStorage.getItem(this.tokenKey); } catch { return this._t; } },
  set token(v) {
    this._t = v;
    try { v ? sessionStorage.setItem(this.tokenKey, v) : sessionStorage.removeItem(this.tokenKey); } catch { /* stockage indisponible */ }
  },
  async request(method, path, body, { raw = false } = {}) {
    const headers = { "Content-Type": "application/json" };
    if (this.token) headers.Authorization = `Bearer ${this.token}`;
    const res = await fetch(path, { method, headers, body: body ? JSON.stringify(body) : undefined });
    if (res.status === 401) { this.token = null; if (typeof onUnauthorized === "function") onUnauthorized(); }
    if (raw) return res;
    const data = res.status === 204 ? null : await res.json().catch(() => null);
    if (!res.ok) throw new Error((data && typeof data.detail === "string") ? data.detail : `Erreur ${res.status}`);
    return data;
  },
  get(p) { return this.request("GET", p); },
  post(p, b) { return this.request("POST", p, b || {}); },
  put(p, b) { return this.request("PUT", p, b); },
};

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else if (k === "dataset") Object.assign(node.dataset, v);
    else node.setAttribute(k, v === true ? "" : String(v));
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); return node; }

function toast(message, kind = "info") {
  const t = document.getElementById("toast");
  t.textContent = message;
  t.className = `toast show ${kind}`;
  clearTimeout(toast._h);
  toast._h = setTimeout(() => { t.className = "toast"; }, 3800);
}

const fmtEUR = (n) => new Intl.NumberFormat("fr-BE", { style: "currency", currency: "EUR" }).format(n);
const fmtPct = (n, d = 0) => `${(n * 100).toFixed(d)} %`;
const fmtNum = (n, d = 0) => new Intl.NumberFormat("fr-BE", { maximumFractionDigits: d }).format(n);

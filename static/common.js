// Shared helpers. Rule: HTML is NEVER built from data (no innerHTML), only DOM nodes with textContent.
// Even LLM-generated text therefore cannot inject anything.
"use strict";

const Api = {
  tokenKey: "moments_token",
  get token() { try { return sessionStorage.getItem(this.tokenKey); } catch { return this._t; } },
  set token(v) {
    this._t = v;
    try { v ? sessionStorage.setItem(this.tokenKey, v) : sessionStorage.removeItem(this.tokenKey); } catch { /* storage unavailable */ }
  },
  async request(method, path, body, { raw = false } = {}) {
    const headers = { "Content-Type": "application/json" };
    if (this.token) headers.Authorization = `Bearer ${this.token}`;
    const res = await fetch(path, { method, headers, body: body ? JSON.stringify(body) : undefined });
    if (res.status === 401) { this.token = null; if (typeof onUnauthorized === "function") onUnauthorized(); }
    if (raw) return res;
    const data = res.status === 204 ? null : await res.json().catch(() => null);
    if (!res.ok) throw new Error((data && typeof data.detail === "string") ? data.detail : `Error ${res.status}`);
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

const fmtEUR = (n) => new Intl.NumberFormat(locale(), { style: "currency", currency: "EUR" }).format(n);
const fmtPct = (n, d = 0) => new Intl.NumberFormat(locale(), { style: "percent", maximumFractionDigits: d, minimumFractionDigits: d }).format(n);
const fmtNum = (n, d = 0) => new Intl.NumberFormat(locale(), { maximumFractionDigits: d }).format(n);
const fmtDateTime = (iso) => new Date(iso).toLocaleString(locale(), { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
const fmtDay = (iso) => new Date(iso).toLocaleDateString(locale(), { weekday: "long", day: "numeric", month: "long" });
const fmtTime = (iso) => new Date(iso).toLocaleTimeString(locale(), { hour: "2-digit", minute: "2-digit" });

// Language switcher shared by every page
function mountLanguageSwitch(container, onChange) {
  clear(container);
  for (const code of LANGS) {
    container.append(el("button", {
      class: `lang-btn${code === getLang() ? " active" : ""}`, type: "button", text: code.toUpperCase(),
      "aria-pressed": code === getLang() ? "true" : "false",
      onclick: async () => {
        if (code === getLang()) return;
        setLang(code);
        mountLanguageSwitch(container, onChange);
        applyStaticI18n();
        if (onChange) await onChange(code);
      },
    }));
  }
}

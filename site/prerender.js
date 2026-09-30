// Build-time pre-render: runs the assembled app.js in Node against a minimal fake DOM and returns, as JSON, the
// HTML it writes into the text blocks (tier cards, crown, Pareto blocks, tables, source counts). build.py injects it
// into index.html, so crawlers that do not run JavaScript (AI robots) read the same conclusions as the browser.
// The browser still runs app.js on load and redraws everything; the charts (SVG) are not pre-rendered.
// Input on stdin: {"app": <app.js with data substituted>, "css": <style.css>}. No npm dependency.
"use strict";
const vm = require("vm");

// Blocks worth serving without JS: element id → innerHTML; "#id tbody" → rows; ".nsrc" → text.
const WANTED = ["tier-crown-top", "tier-cards-top", "pareto-blocks", "pareto-r2", "tier-cards", "tier-crown",
                "answer", "#score-tbl tbody", "#matrix-tbl tbody", "#edge-tbl tbody", ".nsrc"];

const esc = s => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const escAttr = s => esc(s).replace(/"/g, "&quot;");

class El {
  constructor(tag) { this.tagName = tag; this.attrs = {}; this.kids = []; this.style = {}; this.dataset = {};
                     this.parentNode = null; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return this.attrs[k] ?? null; }
  appendChild(c) { c.parentNode = this; this.kids.push(c); return c; }
  insertBefore(c) { return this.appendChild(c); }
  removeChild(c) { this.kids = this.kids.filter(k => k !== c); return c; }
  remove() {}
  addEventListener() {}
  removeEventListener() {}
  focus() {}
  closest() { return new El("div"); }
  querySelector(sel) { return doc.querySelector(sel); }
  querySelectorAll() { return []; }
  getBBox() { return { x: 0, y: 0, width: 0, height: 0 }; }
  set innerHTML(h) { this.kids = h === "" ? [] : [{ raw: String(h) }]; }
  get innerHTML() { return this.kids.map(k => k.raw ?? k.outerHTML).join(""); }
  set textContent(t) { this.kids = [{ raw: esc(t) }]; }
  get textContent() { return this.innerHTML.replace(/<[^>]*>/g, ""); }
  get outerHTML() {
    const a = Object.entries(this.attrs).map(([k, v]) => ` ${k}="${escAttr(v)}"`).join("");
    return `<${this.tagName}${a}>${this.innerHTML}</${this.tagName}>`;
  }
}

const byKey = new Map();                       // one stub per id / selector, created on first access
const stub = key => { if (!byKey.has(key)) byKey.set(key, new El("div")); return byKey.get(key); };
const doc = {
  documentElement: new El("html"),
  activeElement: null,
  getElementById: id => stub(id),
  querySelector: sel => stub(sel),
  querySelectorAll: sel => [stub(sel)],
  createElement: tag => new El(tag),
  createElementNS: (_, tag) => new El(tag),
  addEventListener() {},
};

// CSS custom properties of the light theme (first :root block), for cvar().
function rootVars(css) {
  const block = (css.match(/:root\s*\{([^}]*)\}/) || [, ""])[1], vars = {};
  for (const m of block.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) vars[m[1]] = m[2].trim();
  return vars;
}

function main(input) {
  const { app, css } = JSON.parse(input), vars = rootVars(css), store = new Map();
  const ctx = vm.createContext({
    document: doc, console,
    getComputedStyle: () => ({ getPropertyValue: v => vars[v] ?? "" }),
    localStorage: { getItem: k => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)) },
    matchMedia: () => ({ matches: false, addEventListener() {} }),
    requestAnimationFrame: () => 0,
    MutationObserver: class { observe() {} },
  });
  ctx.window = ctx;
  vm.runInContext(app, ctx, { filename: "app.js" });
  const out = {};
  for (const key of WANTED) {                  // a block app.js no longer fills would silently vanish for crawlers
    const html = byKey.has(key) ? byKey.get(key).innerHTML : "";
    if (!html) throw new Error(`app.js wrote nothing into ${key}`);
    out[key] = html;
  }
  if (typeof ctx.answerFull === "function") out["answer-full"] = ctx.answerFull();   // plain text, for llms.txt only
  process.stdout.write(JSON.stringify(out));
}

let input = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", d => (input += d));
process.stdin.on("end", () => main(input));

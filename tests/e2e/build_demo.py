"""Construit la page de DÉMONSTRATION (un seul fichier HTML, aucun serveur) : l'interface réelle de GMeeting (style.css, recorder.js, app.js)
branchée sur de fausses réponses d'API et un faux enregistreur natif. Données d'exemple : rien n'est enregistré ni envoyé.
Usage : python tests/e2e/build_demo.py   → docs/demo/gmeeting-demo.html  (données : docs/demo/demo-data.json, extraites du serveur de test)"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
S = ROOT / "app" / "static"; D = ROOT / "docs" / "demo"
data = json.loads((D / "demo-data.json").read_text(encoding="utf-8"))
data["config"].update(has_anthropic=True, has_openai=True)
css, rec, app, i18n = (S / "style.css").read_text(encoding="utf-8"), (S / "recorder.js").read_text(encoding="utf-8"), (S / "app.js").read_text(encoding="utf-8"), (S / "i18n.js").read_text(encoding="utf-8")
for s in (rec, app, i18n):
    assert "</script" not in s.lower()

PRE = r"""
(() => {
  const DATA = %DATA%;
  const realFetch = window.fetch.bind(window);
  const json = (o, status = 200) => new Response(JSON.stringify(o), { status, headers: { "Content-Type": "application/json" } });
  const born = {};                                            // réunions « créées » pendant la démo : traitement simulé de 4 s
  const rid = () => Array.from({ length: 12 }, () => "0123456789abcdef"[Math.floor(Math.random() * 16)]).join("");
  const meeting = (id) => {
    const m = JSON.parse(JSON.stringify(DATA.meeting)); m.id = id;
    const t = born[id];
    if (t) { const age = Date.now() - t.at; m.title = t.title || m.title;
      if (age < 2000) { m.status = "processing"; m.progress = "Transcription…"; m.analysis = null; }
      else if (age < 4500) { m.status = "analyzing"; m.progress = "Rédaction du compte rendu…"; m.analysis = null; } }
    return m;
  };
  window.fetch = async (url, opts = {}) => {
    const u = typeof url === "string" ? url : url.url;
    if (!u.startsWith("/api")) return realFetch(url, opts);
    const method = (opts.method || "GET").toUpperCase(), path = u.slice(4).split("?")[0];
    let m;
    if (method === "GET" && path === "/config") return json(DATA.config);
    if (method === "GET" && path === "/meetings") return json([...Object.keys(born).map((id) => ({ ...DATA.list[0], id, title: born[id].title || DATA.list[0].title })), ...DATA.list]);
    if (method === "GET" && (m = path.match(/^\/meetings\/(\w+)$/))) return json(meeting(m[1]));
    if (method === "GET" && /^\/meetings\/\w+\/attachments$/.test(path)) return json(DATA.attachments);
    if (method === "GET" && (m = path.match(/^\/meetings\/\w+\/preview\/(\w+)$/))) return DATA.previews[m[1]] ? json(DATA.previews[m[1]]) : json({ detail: "Aperçu indisponible dans la démo" }, 404);
    if (method === "GET" && path === "/branding") return json(DATA.branding);
    if (method === "PUT" && path === "/branding") { Object.assign(DATA.branding, JSON.parse(opts.body)); return json(DATA.branding); }
    if (method === "POST" && /^\/meetings\/(text|url|audio)$/.test(path)) { const id = rid(); born[id] = { at: Date.now() }; return json({ id }); }
    if (method === "POST" && path === "/attachments") {
      const files = opts.body.getAll("files");
      return json({ attachments: files.map((f) => ({ id: rid(), name: f.name, kind: /\.(msg|eml)$/i.test(f.name) ? "mail" : /xls|csv/i.test(f.name) ? "sheet" : "doc", label: "Pièce jointe (exemple)", size: f.size, snippet: "" })), errors: [] });
    }
    if (method === "POST" || method === "PUT" || method === "PATCH" || method === "DELETE") return json({ ok: true });
    return json({});
  };

  // Faux enregistreur natif : même contrat que l'application Android (voir NativeBridge.kt), sans micro.
  let st = { state: "idle", t: 0, acc: 0, id: null };
  window.GMeetingNative = {
    isAvailable: () => true, version: () => "démo", hasMicPermission: () => true, requestPermissions: () => {},
    start: (meta) => { const id = rid(); st = { state: "recording", t: Date.now(), acc: 0, id }; born[id] = { at: 0, title: (JSON.parse(meta || "{}").title) || "Réunion enregistrée (démo)" }; return id; },
    pause: () => { st.acc += (Date.now() - st.t) / 1000; st.state = "paused"; },
    resume: () => { st.t = Date.now(); st.state = "recording"; },
    mark: () => {}, cancel: () => { st = { state: "idle" }; },
    finish: () => { if (born[st.id]) born[st.id].at = Date.now(); st = { state: "idle" }; },
    state: () => { const el = st.state === "recording" ? st.acc + (Date.now() - st.t) / 1000 : st.acc || 0;
      return JSON.stringify({ state: st.state, elapsed: Math.round(el), level: st.state === "recording" ? 0.15 + Math.random() * 0.5 : 0, id: st.id || null, error: null }); },
  };

  // Les téléchargements (PDF, Word…) n'existent pas dans la démo.
  document.addEventListener("click", (e) => {
    const a = e.target.closest && e.target.closest("a[download], a[href^='/api/']");
    if (!a) return;
    e.preventDefault(); const t = document.getElementById("toast"); t.textContent = "Démo : les exports PDF, Word, Excel et PowerPoint sont disponibles avec votre serveur.";; t.hidden = false; setTimeout(() => (t.hidden = true), 4000);
  }, true);
})();
""".replace("%DATA%", json.dumps(data, ensure_ascii=False))

html = f"""<title>GMeeting – Démonstration</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>
{css}
html{{color-scheme:light}}
.demo-note{{background:#fff7e6;color:#5c3d00;border-bottom:1px solid #f0d9a8;padding:8px max(16px,env(safe-area-inset-left,0px));font-size:13px;line-height:1.4}}
.top,.wrap{{padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}}
</style>
<div class="demo-note" id="demo-note" data-notr></div>
<header class="top">
  <a class="brand" href="#/" aria-label="Accueil GMeeting">GMeeting</a>
  <a id="recbar" class="recbar" href="#/" hidden aria-live="polite"></a>
  <nav class="nav"><a href="#/brand">Gabarit</a></nav>
  <span id="cfg" class="cfg" role="status"></span>
</header>
<main id="app" class="wrap"></main>
<div id="toast" class="toast" role="alert" hidden></div>
<script>{i18n}</script>
<script>{PRE}</script>
<script>document.getElementById("demo-note").innerHTML = window.GM_LANG === "en"
  ? "<strong>Demo.</strong> The app's real interface with sample data: nothing is recorded or sent. The REC button simulates a recording (no microphone). Exports cannot be downloaded here. Sample reports are in French."
  : "<strong>Démonstration.</strong> Interface réelle de l'application, avec des données d'exemple : rien n'est enregistré ni envoyé. Le bouton REC simule un enregistrement (sans micro). Les exports ne sont pas téléchargeables ici.";</script>
<script>{rec}</script>
<script>{app}</script>
"""
out = D / "gmeeting-demo.html"; out.write_text(html, encoding="utf-8")
print(out, f"{len(html)/1024:.0f} Ko")

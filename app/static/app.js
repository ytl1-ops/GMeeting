"use strict";
/* GMeeting – interface (JS natif, sans build). Tout contenu dynamique passe par textContent. */

const $app = document.getElementById("app");
const DOC_LABELS = { pv: "Procès-verbal", cr: "Compte rendu", note: "Note de synthèse" };
const STATUS = { pending: "En attente", queued: "En file", processing: "Traitement", analyzing: "Rédaction", done: "Prêt", error: "Erreur" };

function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else if (v === true) n.setAttribute(k, "");
    else if (v !== false && v != null) n.setAttribute(k, v);
  }
  for (const c of kids.flat()) if (c != null) n.append(c.nodeType ? c : document.createTextNode(c));
  return n;
}
function toast(msg) {
  const t = document.getElementById("toast"); t.textContent = msg; t.hidden = false;
  clearTimeout(toast.h); toast.h = setTimeout(() => (t.hidden = true), 5000);
}
async function api(path, opts) {
  const r = await fetch("/api" + path, opts);
  if (!r.ok) {
    let d = r.statusText; try { d = (await r.json()).detail || d; } catch {}
    throw new Error(typeof d === "string" ? d : JSON.stringify(d));
  }
  return r.json();
}
const fmtDur = (s) => { s = Math.round(s || 0); const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60); return (h ? h + " h " : "") + m + " min"; };
const fmtDate = (iso) => new Date(iso).toLocaleString("fr-FR", { dateStyle: "medium", timeStyle: "short" });

let stopPoll = () => {}, stopRecorderCleanup = () => {};
window.addEventListener("hashchange", route);
window.addEventListener("beforeunload", (e) => { if (Recorder.active) { e.preventDefault(); e.returnValue = ""; } });

async function route() {
  stopPoll(); stopRecorderCleanup();
  const m = location.hash.match(/^#\/m\/(\w+)/);
  if (location.hash === "#/brand") await viewBrand();
  else m ? await viewMeeting(m[1]) : await viewHome();
}

/* ============================================================ ENREGISTREUR */
const Recorder = {
  active: false, rec: null, chunks: [], stream: null, ctx: null, raf: 0, t0: 0, acc: 0, paused: false, tick: 0, wake: null,
  mime() { return ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"].find((t) => MediaRecorder.isTypeSupported(t)) || ""; },
  async start(withTab, onLevel, onEnded) {
    if (!navigator.mediaDevices || !window.MediaRecorder) throw new Error("Enregistrement non supporté par ce navigateur.");
    const mic = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    this.ctx = new AudioContext();
    const dest = this.ctx.createMediaStreamDestination();
    const analyser = this.ctx.createAnalyser(); analyser.fftSize = 512;
    const micSrc = this.ctx.createMediaStreamSource(mic);
    micSrc.connect(dest); micSrc.connect(analyser);
    this.extra = [mic];
    if (withTab) {
      const disp = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true });
      if (!disp.getAudioTracks().length) {
        disp.getTracks().forEach((t) => t.stop()); mic.getTracks().forEach((t) => t.stop());
        throw new Error("Aucun son partagé. Dans la fenêtre de partage, choisissez un onglet (Chrome/Edge) et cochez « Partager l'audio de l'onglet ».");
      }
      const dSrc = this.ctx.createMediaStreamSource(new MediaStream(disp.getAudioTracks()));
      dSrc.connect(dest); dSrc.connect(analyser);
      disp.getVideoTracks()[0].addEventListener("ended", () => onEnded && onEnded());
      this.extra.push(disp);
    }
    this.stream = dest.stream;
    this.chunks = [];
    const mime = this.mime();
    this.rec = new MediaRecorder(this.stream, mime ? { mimeType: mime } : undefined);
    this.rec.ondataavailable = (e) => e.data.size && this.chunks.push(e.data);
    this.rec.start(5000);
    this.active = true; this.paused = false; this.t0 = Date.now(); this.acc = 0;
    try { this.wake = await navigator.wakeLock?.request("screen"); } catch {}
    const buf = new Uint8Array(analyser.frequencyBinCount);
    const loop = () => { analyser.getByteTimeDomainData(buf); let p = 0; for (const v of buf) p = Math.max(p, Math.abs(v - 128)); onLevel(p / 128); this.raf = requestAnimationFrame(loop); };
    loop();
  },
  elapsed() { return this.acc + (this.paused ? 0 : Date.now() - this.t0); },
  pause() { this.rec.pause(); this.acc += Date.now() - this.t0; this.paused = true; },
  resume() { this.rec.resume(); this.t0 = Date.now(); this.paused = false; },
  stop() {
    return new Promise((resolve) => {
      const type = this.rec.mimeType || "audio/webm";
      this.rec.onstop = () => { this.release(); resolve(new Blob(this.chunks, { type })); };
      if (this.rec.state !== "inactive") this.rec.stop(); else this.rec.onstop();
    });
  },
  release() {
    cancelAnimationFrame(this.raf); this.active = false;
    (this.extra || []).forEach((s) => s.getTracks().forEach((t) => t.stop()));
    this.ctx?.close(); this.wake?.release?.();
  },
};

/* ============================================================ ACCUEIL */
function metaFields() {
  const f = (id, label, type = "text", ph = "") => el("div", {}, el("label", { for: id }, label), el("input", { id, type, placeholder: ph }));
  return el("details", { class: "card-sub" },
    el("summary", { class: "hint", style: "cursor:pointer;margin:10px 0" }, "Informations sur la réunion (facultatif, améliore la qualité du rendu)"),
    el("div", { class: "grid" },
      f("m-title", "Titre", "text", "Ex. COPIL sûreté site Nord"),
      f("m-date", "Date", "date"),
      f("m-loc", "Lieu / outil", "text", "Teams, salle B12…"),
      el("div", {}, el("label", { for: "m-lang" }, "Langue parlée"),
        el("select", { id: "m-lang" }, el("option", { value: "" }, "Détection auto"), el("option", { value: "fr" }, "Français"), el("option", { value: "en" }, "Anglais"), el("option", { value: "es" }, "Espagnol"), el("option", { value: "de" }, "Allemand"), el("option", { value: "pt" }, "Portugais"), el("option", { value: "ar" }, "Arabe")))),
    el("label", { for: "m-part" }, "Participants (nom, fonction – un par ligne)"),
    el("textarea", { id: "m-part", placeholder: "Awa Koné – Directrice sûreté\nMarc Dubois – DSI" }),
    el("label", { for: "m-ctx" }, "Contexte / consignes de rédaction"),
    el("textarea", { id: "m-ctx", placeholder: "Acronymes, enjeux, ton souhaité, destinataires du document…" }));
}
const meta = () => ({
  title: val("m-title"), meeting_date: val("m-date"), location: val("m-loc"),
  participants: val("m-part"), context: val("m-ctx"), language: val("m-lang"),
});
const val = (id) => (document.getElementById(id)?.value || "").trim();

async function submitForm(path, build, btn) {
  btn && (btn.disabled = true);
  try {
    const { id } = await api(path, build());
    location.hash = "#/m/" + id;
  } catch (e) { toast(e.message); btn && (btn.disabled = false); }
}

async function viewHome() {
  const tabsDef = [["rec", "🎙 Enregistrer"], ["url", "🔗 Lien vidéo"], ["file", "📁 Fichier"], ["txt", "📝 Texte"]];
  const panel = el("div");
  const tabs = el("div", { class: "tabs", role: "tablist" });
  const show = (k) => {
    tabs.querySelectorAll(".tab").forEach((b) => b.setAttribute("aria-selected", b.dataset.k === k));
    stopRecorderCleanup(); panel.replaceChildren(panels[k]());
  };
  const panels = { rec: recPanel, url: urlPanel, file: filePanel, txt: textPanel };
  tabsDef.forEach(([k, l]) => tabs.append(el("button", { class: "tab", role: "tab", "data-k": k, onclick: () => show(k) }, l)));

  const list = el("ul", { class: "list" });
  $app.replaceChildren(
    el("h1", {}, "Nouvelle réunion"),
    el("div", { class: "card" }, tabs, panel, metaFields()),
    el("div", { class: "card" }, el("h2", {}, "Mes réunions"), list));
  show("rec");
  try {
    const all = await api("/meetings");
    list.replaceChildren(...(all.length ? all.map((m) => el("li", {}, el("a", { href: "#/m/" + m.id },
      el("span", {}, el("strong", {}, m.title || "Sans titre"), el("br"), el("span", { class: "hint" }, fmtDate(m.created_at) + (m.duration ? " · " + fmtDur(m.duration) : "") + " · " + ({ url: "lien", upload: "fichier", record: "enregistrement", text: "texte" }[m.source_type] || m.source_type))),
      el("span", { class: "badge " + m.status }, STATUS[m.status] || m.status)))) : [el("li", { class: "empty" }, "Aucune réunion pour l'instant.")]));
  } catch (e) { toast(e.message); }
  loadConfig();
}

function recPanel() {
  const timer = el("div", { class: "timer" }, "00:00:00");
  const meter = el("div", { class: "meter" }, el("i"));
  const btn = el("button", { class: "rec-btn", "aria-label": "Démarrer l'enregistrement" }, "REC");
  const pauseBtn = el("button", { class: "btn sec", hidden: true }, "⏸ Pause");
  const stopBtn = el("button", { class: "btn", hidden: true }, "⏹ Terminer et générer");
  const info = el("p", { class: "hint" });
  const mode = el("select", { id: "rec-mode", "aria-label": "Source audio" },
    el("option", { value: "mic" }, "Micro seul (réunion en présentiel)"),
    el("option", { value: "tab" }, "Micro + audio de l'onglet (Teams/Meet/Zoom web)"));
  const result = el("div");
  let iv = 0;

  const finish = async () => {
    clearInterval(iv);
    const blob = await Recorder.stop();
    btn.hidden = false; btn.classList.remove("live"); pauseBtn.hidden = stopBtn.hidden = true; mode.disabled = false; meter.firstChild.style.width = "0";
    const ext = blob.type.includes("mp4") ? "m4a" : blob.type.includes("ogg") ? "ogg" : "webm";
    const url = URL.createObjectURL(blob);
    const send = el("button", { class: "btn" }, "Générer les documents");
    send.onclick = () => submitForm("/meetings/audio", () => {
      const fd = new FormData(); const m = meta();
      fd.append("file", blob, `reunion.${ext}`); fd.append("source_type", "record");
      for (const [k, v] of Object.entries(m)) fd.append(k, v);
      return { method: "POST", body: fd };
    }, send);
    result.replaceChildren(el("div", { class: "card", style: "background:var(--bg)" },
      el("strong", {}, `Enregistrement terminé (${fmtDur(timer.dataset.s)})`),
      el("audio", { controls: true, src: url, style: "width:100%;margin:10px 0" }),
      el("div", { class: "row" }, send, el("a", { class: "btn sec", href: url, download: `reunion.${ext}` }, "Sauvegarder l'audio"))));
  };

  btn.onclick = async () => {
    try {
      result.replaceChildren();
      await Recorder.start(mode.value === "tab", (l) => (meter.firstChild.style.width = Math.min(100, l * 140) + "%"), () => Recorder.active && finish());
    } catch (e) { toast(e.message); return; }
    btn.hidden = true; pauseBtn.hidden = stopBtn.hidden = false; mode.disabled = true; btn.classList.add("live");
    info.textContent = "Enregistrement en cours — gardez cet onglet ouvert.";
    iv = setInterval(() => { const s = Recorder.elapsed() / 1000; timer.dataset.s = s; timer.textContent = new Date(s * 1000).toISOString().substr(11, 8); }, 250);
  };
  pauseBtn.onclick = () => { Recorder.paused ? Recorder.resume() : Recorder.pause(); pauseBtn.textContent = Recorder.paused ? "▶ Reprendre" : "⏸ Pause"; };
  stopBtn.onclick = finish;
  stopRecorderCleanup = () => { clearInterval(iv); if (Recorder.active) Recorder.stop(); };
  return el("div", { class: "rec-box" }, el("div", { class: "row", style: "justify-content:center" }, mode), timer, meter,
    el("div", { class: "row", style: "justify-content:center;margin:12px 0" }, btn, pauseBtn, stopBtn), info,
    el("p", { class: "hint" }, "L'accès au micro exige HTTPS ou localhost. Pour capturer une visio, choisissez « Micro + audio de l'onglet » puis partagez l'onglet de la réunion en cochant l'audio."), result);
}

function urlPanel() {
  const input = el("input", { id: "u-url", type: "url", placeholder: "https://… (YouTube, Vimeo, LinkedIn, Loom, lien direct .mp4/.mp3, etc.)", autocomplete: "off" });
  const subs = el("input", { type: "checkbox", id: "u-subs", checked: true, style: "width:auto" });
  const go = el("button", { class: "btn" }, "Analyser le lien");
  go.onclick = () => {
    const url = input.value.trim(); if (!url) return toast("Collez un lien.");
    submitForm("/meetings/url", () => ({ method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, prefer_subtitles: subs.checked, ...meta() }) }), go);
  };
  return el("div", {}, el("label", { for: "u-url" }, "Lien de la vidéo ou de l'audio"), input,
    el("label", { style: "display:flex;gap:8px;align-items:center;font-weight:400" }, subs, "Utiliser les sous-titres existants quand ils sont disponibles (plus rapide)"),
    el("p", { class: "hint" }, "Les liens privés (Teams, Zoom, Drive protégés) ne sont pas accessibles : téléchargez le fichier puis utilisez l'onglet « Fichier »."),
    el("div", { class: "row" }, go));
}

function filePanel() {
  const input = el("input", { id: "f-file", type: "file", accept: "audio/*,video/*,.m4a,.mp3,.wav,.mp4,.webm,.mkv,.mov,.ogg" });
  const go = el("button", { class: "btn" }, "Transcrire et générer");
  go.onclick = () => {
    const f = input.files[0]; if (!f) return toast("Choisissez un fichier.");
    submitForm("/meetings/audio", () => { const fd = new FormData(); fd.append("file", f); fd.append("source_type", "upload"); for (const [k, v] of Object.entries(meta())) fd.append(k, v); return { method: "POST", body: fd }; }, go);
  };
  return el("div", {}, el("label", { for: "f-file" }, "Fichier audio ou vidéo (mp3, m4a, wav, mp4, webm…)"), input,
    el("p", { class: "hint" }, "Fonctionne avec les enregistrements Plaud, dictaphone, Teams, Zoom, etc."), el("div", { class: "row" }, go));
}

function textPanel() {
  const ta = el("textarea", { id: "t-text", style: "min-height:200px", placeholder: "Collez ici une transcription existante (Teams, Zoom, Otter, sous-titres…)" });
  const go = el("button", { class: "btn" }, "Générer les documents");
  go.onclick = () => { const text = ta.value.trim(); if (!text) return toast("Collez un texte."); submitForm("/meetings/text", () => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, ...meta() }) }), go); };
  return el("div", {}, el("label", { for: "t-text" }, "Transcription"), ta, el("div", { class: "row", style: "margin-top:10px" }, go));
}

async function loadConfig() {
  try {
    const c = await api("/config");
    const warn = [];
    if (!c.has_anthropic) warn.push("clé ANTHROPIC_API_KEY manquante");
    if (c.transcribe_provider === "openai" && !c.has_openai) warn.push("aucun moteur de transcription configuré");
    document.getElementById("cfg").textContent = warn.length ? "⚠ " + warn.join(" · ") : `Transcription : ${c.transcribe_provider} · Rédaction : ${c.model}`;
  } catch {}
}

/* ============================================================ DÉTAIL */
async function viewMeeting(id) {
  let tab = sessionStorage.getItem("tab") || "pv";
  const head = el("div"), body = el("div");
  $app.replaceChildren(el("p", { class: "no-print" }, el("a", { href: "#/" }, "← Toutes les réunions")), head, body);
  let m, polling = true, lastKey = "";
  stopPoll = () => (polling = false);

  const render = async () => {
    const key = [m.status, m.progress, tab, m.analysis ? 1 : 0].join("|");
    if (key === lastKey) return; lastKey = key;
    head.replaceChildren(el("h1", {}, m.title || "Réunion sans titre"),
      el("p", { class: "hint" }, fmtDate(m.created_at) + (m.duration ? " · " + fmtDur(m.duration) : "") + (m.source_url ? " · " + m.source_url : "")));
    if (m.status === "error") {
      body.replaceChildren(el("div", { class: "card" }, el("div", { class: "err" }, m.error || "Erreur inconnue"),
        el("div", { class: "row", style: "margin-top:12px" },
          m.transcript ? el("button", { class: "btn", onclick: () => regenerate(id) }, "Relancer la rédaction") : null,
          el("button", { class: "btn danger", onclick: () => del(id) }, "Supprimer"))));
      return;
    }
    if (m.status !== "done") {
      body.replaceChildren(el("div", { class: "card progress", role: "status" }, el("div", { class: "spin" }), el("div", {}, el("strong", {}, STATUS[m.status] || m.status), el("br"), m.progress || "")));
      return;
    }
    const tabs = el("div", { class: "tabs", role: "tablist" });
    [...Object.entries(DOC_LABELS), ["transcript", "Transcription"], ["infos", "Informations"]].forEach(([k, l]) =>
      tabs.append(el("button", { class: "tab", role: "tab", "aria-selected": k === tab, onclick: () => { tab = k; sessionStorage.setItem("tab", k); lastKey = ""; render(); } }, l)));
    const content = el("div", { class: "card" });
    body.replaceChildren(tabs, content);
    if (DOC_LABELS[tab]) await docView(content, id, tab);
    else if (tab === "transcript") transcriptView(content);
    else infosView(content);
  };

  const tick = async () => {
    while (polling) {
      try { m = window.__m = await api("/meetings/" + id); await render(); } catch (e) { toast(e.message); }
      if (m && ["done", "error"].includes(m.status) && polling) {
        // reste actif uniquement pour détecter une régénération
        await new Promise((r) => setTimeout(r, 4000));
      } else await new Promise((r) => setTimeout(r, 1800));
    }
  };
  tick();
}

async function docView(host, id, type) {
  const exp = el("div", { class: "exports no-print" }, el("strong", {}, "Exporter :"),
    ...[["pdf", "PDF"], ["docx", "Word"], ["xlsx", "Excel"]].map(([f, l]) =>
      el("a", { class: "btn sec", href: `/api/meetings/${id}/export/${type}.${f}`, download: true }, "⬇ " + l)));
  host.replaceChildren(exp, el("p", { class: "hint" }, "Chargement…"));
  try {
    const [blocks, br] = await Promise.all([api(`/meetings/${id}/preview/${type}`), api("/branding")]);
    host.replaceChildren(exp, brandBand(br), renderBlocks(blocks), brandFoot(br));
  } catch (e) { host.append(el("div", { class: "err" }, e.message)); }
}

/* ============================================================ GABARIT */
function brandBand(b) {
  if (!b.has_logo && !b.org_name && !b.header_right) return el("span");
  return el("div", { class: "band", style: `border-color:${b.color}` },
    el("div", { class: "l", style: `color:${b.color}` }, b.has_logo ? el("img", { src: "/api/branding/logo?v=" + (b.v || Date.now()), alt: "Logo" }) : null, b.org_name),
    el("div", { class: "r" }, b.header_right));
}
function brandFoot(b) {
  if (!b.footer && !b.confidential) return el("span");
  return el("div", { class: "bandfoot" }, el("span", {}, b.footer), el("b", {}, b.confidential));
}

async function viewBrand() {
  let b = await api("/branding");
  const prev = el("div", { class: "card", style: "background:var(--card)" });
  const field = (k, label, ph) => el("div", {}, el("label", { for: "b-" + k }, label), el("input", { id: "b-" + k, value: b[k] || "", placeholder: ph, oninput: refresh }));
  const color = el("input", { type: "color", id: "b-color", value: b.color, oninput: (e) => { hex.value = e.target.value.toUpperCase(); refresh(); } });
  const hex = el("input", { type: "text", id: "b-hex", value: b.color, maxlength: 7, "aria-label": "Code couleur", oninput: (e) => { if (/^#[0-9a-fA-F]{6}$/.test(e.target.value)) { color.value = e.target.value; refresh(); } } });
  const logoBox = el("div", { class: "logo-prev" });
  const file = el("input", { type: "file", accept: "image/png,image/jpeg,image/gif,image/webp", "aria-label": "Fichier logo" });
  const cur = () => ({ ...b, org_name: val("b-org_name"), header_right: val("b-header_right"), footer: val("b-footer"), confidential: val("b-confidential"), color: color.value.toUpperCase() });
  function refresh() {
    const c = cur(); c.v = b.v;
    prev.replaceChildren(el("div", { class: "hint", style: "margin-bottom:6px" }, "Aperçu de l'en-tête et du pied de page"),
      brandBand(c).tagName === "SPAN" ? el("div", { class: "empty" }, "Ajoutez un logo ou un texte d'en-tête") : brandBand(c),
      el("div", { class: "doc" }, el("div", { class: "dt", style: `color:${c.color}` }, "PROCÈS-VERBAL DE RÉUNION"), el("h3", { style: `color:${c.color};border-color:${c.color}` }, "Exemple de titre de section")),
      brandFoot(c));
    logoBox.replaceChildren(b.has_logo ? el("img", { src: "/api/branding/logo?v=" + (b.v || 0), alt: "Logo actuel" }) : el("span", { class: "hint" }, "Aucun logo"));
  }
  file.onchange = async () => {
    const f = file.files[0]; if (!f) return;
    const fd = new FormData(); fd.append("file", f);
    try { await api("/branding/logo", { method: "POST", body: fd }); b.has_logo = true; b.v = Date.now(); refresh(); toast("Logo enregistré."); }
    catch (e) { toast(e.message); } file.value = "";
  };
  const rm = el("button", { class: "btn danger", onclick: async () => { await api("/branding/logo", { method: "DELETE" }); b.has_logo = false; refresh(); } }, "Retirer le logo");
  const save = el("button", { class: "btn" }, "Enregistrer le gabarit");
  save.onclick = async () => {
    const { org_name, header_right, footer, confidential, color: col } = cur();
    try { b = { ...(await api("/branding", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ org_name, header_right, footer, confidential, color: col }) })), v: b.v }; toast("Gabarit enregistré : il s'applique aux nouveaux exports PDF, Word et Excel."); }
    catch (e) { toast(e.message); }
  };
  $app.replaceChildren(el("p", {}, el("a", { href: "#/" }, "← Retour")), el("h1", {}, "Gabarit des documents"),
    el("div", { class: "card" },
      el("p", { class: "hint" }, "Ces éléments sont appliqués à tous les exports (PV, CR, note de synthèse) en PDF, Word et Excel."),
      el("label", {}, "Logo (PNG, JPEG, GIF ou WebP – fond transparent recommandé)"), logoBox,
      el("div", { class: "row", style: "margin-top:8px" }, file, b.has_logo ? rm : null),
      el("div", { class: "grid" }, field("org_name", "Nom de l'organisation", "Ex. Direction de la Sûreté – ACME"),
        field("header_right", "Texte d'en-tête (à droite)", "Ex. Diffusion restreinte"),
        field("footer", "Pied de page (remplace le pied par défaut)", "Ex. ACME – Document interne"),
        field("confidential", "Mention de confidentialité", "Ex. CONFIDENTIEL")),
      el("label", { for: "b-hex" }, "Couleur des titres et des tableaux"), el("div", { class: "colorrow" }, color, hex),
      el("div", { class: "row", style: "margin-top:14px" }, save)),
    prev);
  refresh();
}

function renderBlocks(blocks) {
  const d = el("article", { class: "doc" });
  for (const b of blocks) {
    if (b.t === "title") d.append(el("div", { class: "dt" }, b.text));
    else if (b.t === "subtitle") d.append(el("div", { class: "ds" }, b.text));
    else if (b.t === "h") d.append(el("h3", {}, b.text));
    else if (b.t === "h2") d.append(el("h4", {}, b.text));
    else if (b.t === "p") d.append(el("p", b.bold ? { style: "font-weight:700" } : {}, b.text));
    else if (b.t === "bullets") d.append(el("ul", {}, b.items.map((i) => el("li", {}, i))));
    else if (b.t === "numbered") d.append(el("ol", {}, b.items.map((i) => el("li", {}, i))));
    else if (b.t === "meta") d.append(el("table", { class: "meta" }, b.rows.map(([k, v]) => el("tr", {}, el("td", {}, k), el("td", {}, v)))));
    else if (b.t === "table") d.append(el("table", {}, el("thead", {}, el("tr", {}, b.headers.map((h) => el("th", {}, h)))), el("tbody", {}, b.rows.map((r) => el("tr", {}, r.map((c) => el("td", {}, c)))))));
    else if (b.t === "signatures") d.append(el("div", { class: "sign" }, b.labels.map((l) => el("div", {}, l))));
  }
  return d;
}

function transcriptView(host) {
  const ta = el("textarea", { class: "transcript", "aria-label": "Transcription" }); ta.value = m_transcript();
  const save = el("button", { class: "btn" }, "Enregistrer et régénérer les documents");
  save.onclick = async () => {
    save.disabled = true;
    try {
      await api("/meetings/" + currentId(), { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ transcript: ta.value }) });
      await regenerate(currentId());
    } catch (e) { toast(e.message); save.disabled = false; }
  };
  host.replaceChildren(el("p", { class: "hint" }, "Corrigez les noms propres ou acronymes mal transcrits, puis régénérez : les trois documents sont réécrits à partir du texte corrigé."),
    ta, el("div", { class: "row", style: "margin-top:10px" }, save,
      el("a", { class: "btn sec", href: "data:text/plain;charset=utf-8," + encodeURIComponent(ta.value), download: "transcription.txt" }, "⬇ .txt")));
}
const currentId = () => location.hash.match(/#\/m\/(\w+)/)[1];
const m_transcript = () => window.__m?.transcript || "";

function infosView(host) {
  const m = window.__m;
  const inp = (k, label, type = "text") => el("div", {}, el("label", {}, label), el("input", { type, "data-k": k, value: m[k] || "" }));
  const part = el("textarea", { "data-k": "participants" }); part.value = m.participants || "";
  const ctx = el("textarea", { "data-k": "context" }); ctx.value = m.context || "";
  const save = el("button", { class: "btn" }, "Enregistrer");
  save.onclick = async () => {
    const body = {}; host.querySelectorAll("[data-k]").forEach((n) => (body[n.dataset.k] = n.value));
    try { await api("/meetings/" + m.id, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }); toast("Enregistré. Utilisez « Régénérer » pour appliquer au contenu."); } catch (e) { toast(e.message); }
  };
  host.replaceChildren(el("div", { class: "grid" }, inp("title", "Titre"), inp("meeting_date", "Date", "date"), inp("location", "Lieu / outil")),
    el("label", {}, "Participants"), part, el("label", {}, "Contexte / consignes"), ctx,
    el("div", { class: "row", style: "margin-top:12px" }, save,
      el("button", { class: "btn sec", onclick: () => regenerate(m.id) }, "↻ Régénérer les documents"),
      el("button", { class: "btn danger", onclick: () => del(m.id) }, "Supprimer")));
}

async function regenerate(id) { try { await api(`/meetings/${id}/regenerate`, { method: "POST" }); location.hash = "#/m/" + id; route(); } catch (e) { toast(e.message); } }
async function del(id) { if (!confirm("Supprimer définitivement cette réunion et ses documents ?")) return; try { await api("/meetings/" + id, { method: "DELETE" }); location.hash = "#/"; } catch (e) { toast(e.message); } }

route();

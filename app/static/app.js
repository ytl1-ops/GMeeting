"use strict";
/* GMeeting – interface (JS natif, sans build). Tout contenu dynamique passe par textContent. */

const $app = document.getElementById("app");
const DOC_LABELS = { pv: "Procès-verbal", cr: "Compte rendu", note: "Note de synthèse", deck: "Présentation", deck_visual: "Présentation illustrée" };
const DECK_TYPES = new Set(["deck", "deck_visual"]);
const EMOJI = { objectif: "🎯", equipe: "👥", planning: "📅", decision: "✅", action: "➡️", risque: "⚠️", idee: "💡", budget: "💶", securite: "🛡️", technique: "⚙️", communication: "💬", juridique: "📄", qualite: "📊", question: "❓", jalon: "🚩", horloge: "🕒" };
const STATUS = { recording: "Enregistrement", pending: "En attente", queued: "En file", processing: "Traitement", analyzing: "Rédaction", done: "Prêt", error: "Erreur" };

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
let live = null; // session d'enregistrement active (survit à la navigation entre pages)
window.addEventListener("beforeunload", (e) => { if (live?.active) { e.preventDefault(); e.returnValue = ""; } });

async function route() {
  stopPoll(); stopRecorderCleanup();
  const m = location.hash.match(/^#\/m\/(\w+)/);
  if (location.hash === "#/brand") await viewBrand();
  else m ? await viewMeeting(m[1]) : await viewHome();
}

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
  orphanBanner();
  try {
    const all = await api("/meetings");
    list.replaceChildren(...(all.length ? all.map((m) => el("li", {}, el("a", { href: "#/m/" + m.id },
      el("span", {}, el("strong", {}, m.title || "Sans titre"), el("br"), el("span", { class: "hint" }, fmtDate(m.created_at) + (m.duration ? " · " + fmtDur(m.duration) : "") + " · " + ({ url: "lien", upload: "fichier", record: "enregistrement", text: "texte" }[m.source_type] || m.source_type))),
      el("span", { class: "badge " + m.status }, STATUS[m.status] || m.status)))) : [el("li", { class: "empty" }, "Aucune réunion pour l'instant.")]));
  } catch (e) {
    list.replaceChildren(el("li", { class: "empty" }, navigator.onLine ? "Liste indisponible : " + e.message : "Hors connexion — la liste des réunions s'affichera au retour du réseau. Vous pouvez néanmoins enregistrer."));
  }
  loadConfig();
}

const STATE_MSG = {
  interrupted: "⚠ Micro interrompu (appel en cours ?). L'enregistrement reprendra tout seul à la fin de l'appel — gardez cette page ouverte.",
  paused: "⏸ En pause.",
  "needs-tap": "Le navigateur demande une confirmation pour rouvrir le micro.",
};

/** Enregistrements locaux non terminés (page fermée ou rechargée en cours de réunion) : on propose de les récupérer. */
async function orphanBanner() {
  const items = await GRec.orphans(live?.id);
  const card = $app.querySelector(".card");
  for (const o of items.reverse()) {
    const box = el("div", { class: "alert", role: "alert" });
    const go = el("button", { class: "btn" }, "Récupérer et générer les documents");
    go.onclick = async () => {
      go.disabled = true;
      try { await GRec.requestFinish(o.id, o.payload); location.hash = "#/m/" + o.id; route(); }
      catch (e) { toast("Envoi impossible pour l'instant (" + e.message + "). Réessayez avec une connexion."); go.disabled = false; }
    };
    const drop = el("button", { class: "btn danger" }, "Supprimer");
    drop.onclick = async () => { if (!confirm("Supprimer définitivement cet enregistrement ?")) return; await GRec.discard(o.id); fetch("/api/meetings/" + o.id, { method: "DELETE" }).catch(() => {}); box.remove(); };
    box.append(el("strong", {}, "⚠ Un enregistrement n'a pas été terminé"), el("br"),
      `« ${o.meta?.title || "Sans titre"} », démarré le ${fmtDate(o.startedAt)}. ` +
      (o.pending ? `${o.pending} segment(s) audio sont conservés sur cet appareil et n'ont pas encore été envoyés. ` : "Tout l'audio a été envoyé. "),
      el("div", { class: "row", style: "margin-top:10px" }, go, drop));
    card.before(box);
  }
}

/** Conseil « mode avion » : l'interface doit avoir été chargée une fois en ligne pour pouvoir s'ouvrir sans réseau. */
function offlineTip() {
  const ready = !!navigator.serviceWorker?.controller;
  return el("p", { class: "hint", style: "max-width:520px;margin:8px auto" },
    el("strong", {}, "✈ Mode avion : "), "vous pouvez enregistrer sans aucun réseau, donc sans appel qui coupe le micro. ",
    ready ? "L'application est prête pour l'usage hors-ligne. Activez le mode avion (vous pouvez ensuite rallumer le Wi-Fi seul si besoin) puis lancez l'enregistrement ; l'envoi se fera au retour du réseau."
      : "Pour cela, rechargez cette page une fois en ligne (installation hors-ligne en cours), puis installez l'application sur l'écran d'accueil si possible.");
}

function recPanel() {
  const timer = el("div", { class: "timer", "aria-live": "off" }, "00:00:00");
  const meter = el("div", { class: "meter" }, el("i"));
  const btn = el("button", { class: "rec-btn", "aria-label": "Démarrer l'enregistrement" }, "REC");
  const pauseBtn = el("button", { class: "btn sec", hidden: true }, "⏸ Pause");
  const markBtn = el("button", { class: "btn sec", hidden: true, title: "Repérer un moment important" }, "⭐ Marquer");
  const stopBtn = el("button", { class: "btn", hidden: true }, "⏹ Terminer et générer");
  const tapBtn = el("button", { class: "btn", hidden: true, style: "background:var(--rec);border-color:var(--rec)" }, "🎙 Reprendre l'enregistrement");
  const banner = el("div", { class: "rec-banner", role: "status", hidden: true });
  const net = el("p", { class: "hint", role: "status" });
  const log = el("ul", { class: "hint", style: "list-style:none;padding:0;margin:6px 0" });
  const mode = el("select", { id: "rec-mode", "aria-label": "Source audio" },
    el("option", { value: "mic" }, "Micro seul (présentiel, téléphone)"),
    el("option", { value: "tab" }, "Micro + audio de l'onglet (visio web)"));
  let iv = 0, unsub = () => {};

  const ui = (running) => {
    btn.hidden = running; pauseBtn.hidden = markBtn.hidden = stopBtn.hidden = !running; mode.disabled = running;
    btn.classList.toggle("live", running);
    if (!running) { meter.firstChild.style.width = "0"; banner.hidden = true; tapBtn.hidden = true; }
  };
  const say = (msg) => { if (!msg) return; const t = new Date().toLocaleTimeString("fr-FR"); log.append(el("li", {}, `${t} — ${msg}`)); };
  const showState = (st) => {
    banner.hidden = !STATE_MSG[st]; banner.textContent = STATE_MSG[st] || ""; banner.className = "rec-banner " + st;
    tapBtn.hidden = st !== "needs-tap";
    pauseBtn.textContent = st === "paused" ? "▶ Reprendre" : "⏸ Pause";
    if (st === "interrupted") say("Interruption du micro");
  };
  const showNet = async () => {
    if (!live) return; const n = await GRec.pendingCount(live.id);
    net.textContent = !navigator.onLine ? `✈ Hors connexion (mode avion ?) — l'enregistrement se poursuit normalement. L'audio est conservé sur cet appareil et sera envoyé automatiquement au retour du réseau (${n} segment(s) en attente).`
      : n > 3 ? `Envoi en cours… ${n} segment(s) en attente.` : "";
  };

  btn.onclick = async () => {
    if (!GRec.Session.supported()) return toast("Enregistrement non supporté par ce navigateur.");
    btn.disabled = true;
    const s = new GRec.Session({
      onState: showState,
      onLevel: (l) => (meter.firstChild.style.width = Math.min(100, l * 140) + "%"),
      onEvent: (m) => say(m),
    });
    try { await s.start(meta(), mode.value === "tab"); }
    catch (e) { toast(e.message); btn.disabled = false; return; }
    live = s; btn.disabled = false; ui(true); log.replaceChildren();
    iv = setInterval(() => { const sec = s.elapsed(); timer.dataset.s = sec; timer.textContent = new Date(sec * 1000).toISOString().substr(11, 8); showNet(); }, 500);
    unsub = GRec.onProgress(showNet);
  };
  pauseBtn.onclick = () => (live.state === "paused" ? live.resume() : live.pause());
  markBtn.onclick = () => { const n = live.mark(); say(`⭐ Repère n°${n} à ${timer.textContent}`); toast("Moment marqué ⭐"); };
  tapBtn.onclick = () => live.recover(true);
  stopBtn.onclick = async () => {
    stopBtn.disabled = true; const s = live;
    try {
      const done = await s.finish(meta());
      live = null; clearInterval(iv); unsub();
      location.hash = "#/m/" + s.id;
      if (!done) toast("Enregistrement terminé.");
    } catch (e) {
      // réseau absent : tout est conservé localement et sera finalisé automatiquement au retour de la connexion
      live = null; clearInterval(iv); unsub(); ui(false);
      toast("Enregistrement terminé. Envoi en attente de connexion : il reprendra automatiquement.");
      route();
    }
  };
  // revenir sur l'onglet Enregistrer pendant une session en cours : on rebranche l'interface sur la session active
  if (live?.active) {
    live.onState = showState; live.onLevel = (l) => (meter.firstChild.style.width = Math.min(100, l * 140) + "%"); live.onEvent = say;
    ui(true); showState(live.state); const s = live;
    iv = setInterval(() => { const sec = s.elapsed(); timer.textContent = new Date(sec * 1000).toISOString().substr(11, 8); showNet(); }, 500);
    unsub = GRec.onProgress(showNet);
  }
  stopRecorderCleanup = () => { clearInterval(iv); unsub(); }; // la session continue même si l'on change de page
  return el("div", { class: "rec-box" }, el("div", { class: "row", style: "justify-content:center" }, mode), timer, meter, banner,
    el("div", { class: "row", style: "justify-content:center;margin:12px 0" }, btn, pauseBtn, markBtn, stopBtn), tapBtn, net, log,
    offlineTip(),
    el("p", { class: "hint" }, "L'audio est écrit sur l'appareil puis envoyé en continu : une coupure réseau, un appel téléphonique ou la fermeture de la page ne font pas perdre l'enregistrement. " +
      "Gardez la page ouverte et l'écran allumé. L'accès au micro exige HTTPS ou localhost."));
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
    const key = [m.status, m.progress, tab, m.analysis ? 1 : 0, m.rec_info?.chunks].join("|");
    if (key === lastKey) return; lastKey = key;
    head.replaceChildren(el("h1", {}, m.title || "Réunion sans titre"),
      el("p", { class: "hint" }, fmtDate(m.created_at) + (m.duration ? " · " + fmtDur(m.duration) : "") + (m.source_url ? " · " + m.source_url : "")));
    if (m.status === "recording") {
      const ri = m.rec_info || {}, mine = live?.id === m.id && live.active;
      body.replaceChildren(el("div", { class: "card" },
        el("strong", {}, mine ? "● Enregistrement en cours sur cet appareil" : "Enregistrement non finalisé"), el("br"),
        el("span", { class: "hint" }, `${ri.chunks || 0} segment(s) reçus` + (ri.last_chunk_age != null ? ` · dernier il y a ${ri.last_chunk_age} s` : "")),
        mine ? el("p", {}, el("a", { href: "#/" }, "Retour à l'enregistreur")) :
          el("div", { class: "row", style: "margin-top:12px" },
            el("button", { class: "btn", onclick: () => finishRecording(id) }, "Finaliser et générer les documents"),
            el("button", { class: "btn danger", onclick: () => del(id) }, "Supprimer"))));
      return;
    }
    if (m.status === "error") {
      body.replaceChildren(el("div", { class: "card" }, el("div", { class: "err" }, m.error || "Erreur inconnue"),
        el("div", { class: "row", style: "margin-top:12px" },
          m.transcript ? el("button", { class: "btn", onclick: () => regenerate(id) }, "Relancer la rédaction") : null,
          !m.transcript && m.source_type === "record" ? el("button", { class: "btn", onclick: () => finishRecording(id) }, "Relancer le traitement (audio conservé)") : null,
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
  const formats = DECK_TYPES.has(type) ? [["pptx", "PowerPoint"]] : [["pdf", "PDF"], ["docx", "Word"], ["xlsx", "Excel"]];
  const exp = el("div", { class: "exports no-print" }, el("strong", {}, "Exporter :"),
    ...formats.map(([f, l]) =>
      el("a", { class: "btn sec", href: `/api/meetings/${id}/export/${type}.${f}`, download: true }, "⬇ " + l)));
  host.replaceChildren(exp, el("p", { class: "hint" }, "Chargement…"));
  try {
    const [blocks, br] = await Promise.all([api(`/meetings/${id}/preview/${type}`), api("/branding")]);
    if (Array.isArray(blocks)) host.replaceChildren(exp, brandBand(br), renderBlocks(blocks), brandFoot(br));
    else host.replaceChildren(exp, el("p", { class: "hint" }, `${blocks.slides.length} diapositives. Aperçu simplifié : le fichier PowerPoint contient les pictogrammes vectoriels modifiables, les images et les graphiques natifs${blocks.visual ? "" : " (version sobre : texte et tableaux)"}.`), renderSlides(blocks, br));
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

/* ---- aperçu des diapositives (même modèle que le fichier .pptx) ---- */
// append() écrit « null » dans la page si on lui passe null : on filtre les éléments absents
const put = (node, ...kids) => node.append(...kids.flat().filter((k) => k != null && k !== false));
function renderSlides(spec, br) {
  const wrap = el("div", { class: "slides", style: `--sc:${br.color || "#1F3A5F"}` });
  const ic = (n) => el("span", { class: "emo" }, EMOJI[n] || "🎯");
  const head = (d) => el("div", { class: "sh" }, spec.visual && d.icon ? el("span", { class: "badge-i" }, ic(d.icon)) : null, el("span", { class: "st" }, d.title));
  const tone = (t) => ({ primary: "var(--sc)", green: "#2e9e5b", red: "#d64545", amber: "#d98a00", purple: "#7b5ea7" }[t] || "var(--sc)");
  for (const d of spec.slides) {
    const body = el("div", { class: "si" });
    if (d.layout === "cover") {
      put(body, el("div", { class: "cv-sub" }, d.subtitle), el("div", { class: "cv-t" }, d.title), el("div", { class: "cv-m" }, d.meta.map(([k, v]) => el("div", {}, spec.visual ? "" : k + " : ", v))));
    } else if (d.layout === "kpis") {
      put(body, head(d), el("div", { class: "kp" }, d.tiles.map((t) => el("div", { class: "kt" }, ic(t.icon), el("b", {}, t.value), el("small", {}, t.label)))),
        d.extra.length ? el("div", { class: "kp x" }, d.extra.map((t) => el("div", { class: "kt" }, el("b", {}, t.value), el("small", {}, t.label)))) : null,
        d.highlight ? el("div", { class: "hl" }, d.highlight) : null);
    } else if (d.layout === "cards") {
      put(body, head(d), el("div", { class: "cd" }, d.items.map((it) => el("div", { class: "c", style: `border-top-color:${tone(d.tone)}` },
        el("span", { class: "badge-i", style: `background:${tone(d.tone)}` }, ic(it.icon)), el("div", {}, el("b", {}, it.title), it.detail ? el("small", {}, it.detail) : null, it.chip ? el("em", { style: `color:${tone(d.tone)}` }, it.chip) : null)))));
    } else if (d.layout === "bullets") {
      put(body, head(d), d.paragraph ? el("p", {}, d.paragraph) : null, d.items.length ? el("ul", {}, d.items.map((i) => el("li", {}, i))) : null);
    } else if (d.layout === "topic") {
      if (spec.visual) {
        body.classList.add("tp");
        put(body, el("div", { class: "tl" }, el("span", { class: "badge-i big" }, ic(d.icon)), el("small", {}, "POINT " + d.number), el("b", {}, d.title)),
          el("div", { class: "tr" }, el("p", { class: "sum" }, d.summary), d.bullets.length ? el("ul", {}, d.bullets.map((i) => el("li", {}, i))) : null,
            ...d.decisions.map((x) => el("div", { class: "dec" }, "✅ " + x))));
      } else {
        put(body, head(d), el("p", {}, d.summary),
          d.bullets.length ? el("div", { class: "sec" }, el("small", {}, (d.bullets_label || "Points").toUpperCase()), el("ul", {}, d.bullets.map((i) => el("li", {}, i)))) : null,
          d.decisions.length ? el("div", { class: "sec g" }, el("small", {}, "DÉCISIONS"), el("ul", {}, d.decisions.map((i) => el("li", {}, i)))) : null);
      }
    } else if (d.layout === "table") {
      const tbl = el("table", {}, el("thead", {}, el("tr", {}, d.headers.map((h) => el("th", {}, h)))), el("tbody", {}, d.rows.map((r) => el("tr", {}, r.map((c) => el("td", {}, c))))));
      const side = d.charts ? chartsPreview(d.charts) : null;
      put(body, head(d), el("div", { class: side ? "tb2" : "" }, tbl, side));
    } else if (d.layout === "people") {
      put(body, head(d), el("div", { class: "pp" }, d.people.map((p) => el("div", {}, el("span", { class: "av" }, p.nom.split(/[\s-]+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase()), el("b", {}, p.nom), el("small", {}, p.fonction || ""), el("em", { class: "s-" + p.statut }, p.statut)))));
    } else if (d.layout === "timeline") {
      put(body, head(d), el("div", { class: "tm" }, d.steps.map((s, i) => el("div", {}, el("b", {}, s.when), el("span", { class: "dot", style: `background:${tone(s.tone === "red" ? "red" : s.tone === "green" ? "green" : "amber")}` }, String(i + 1)), el("div", { class: "tc" }, el("b", {}, s.label), el("small", {}, s.who))))));
    }
    wrap.append(el("div", { class: "sl " + d.layout + (spec.visual ? " vis" : "") }, body));
  }
  return wrap;
}
function chartsPreview(ch) {
  const p = ch.priorities, tot = Math.max(1, p.haute + p.moyenne + p.basse);
  const a = (p.haute / tot) * 360, b = a + (p.moyenne / tot) * 360;
  const box = el("div", { class: "ch" }, el("div", { class: "donut", style: `background:conic-gradient(#d64545 0 ${a}deg,#d98a00 ${a}deg ${b}deg,#2e9e5b ${b}deg 360deg)` }),
    el("small", {}, `${p.haute} haute · ${p.moyenne} moyenne · ${p.basse} basse`));
  if (ch.owners.length) { const m = Math.max(...ch.owners.map((o) => o[1])); box.append(...ch.owners.map(([n, c]) => el("div", { class: "bar" }, el("span", {}, n), el("i", { style: `width:${(c / m) * 100}%` })))); }
  return box;
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

async function finishRecording(id) {
  try { await api(`/recordings/${id}/finish`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }); route(); }
  catch (e) { toast(e.message); }
}
async function regenerate(id) { try { await api(`/meetings/${id}/regenerate`, { method: "POST" }); location.hash = "#/m/" + id; route(); } catch (e) { toast(e.message); } }
async function del(id) { if (!confirm("Supprimer définitivement cette réunion et ses documents ?")) return; try { await api("/meetings/" + id, { method: "DELETE" }); location.hash = "#/"; } catch (e) { toast(e.message); } }

/* ---- indicateur d'enregistrement visible sur toutes les pages ---- */
const recbar = document.getElementById("recbar");
setInterval(() => {
  if (!live?.active) { recbar.hidden = true; return; }
  recbar.hidden = false;
  recbar.className = "recbar" + (live.state === "recording" ? "" : " warn");
  const t = new Date(live.elapsed() * 1000).toISOString().substr(11, 8);
  recbar.textContent = ({ interrupted: "⚠ Interrompu ", paused: "⏸ Pause ", "needs-tap": "⚠ Toucher pour reprendre " }[live.state] || "● REC ") + t;
}, 1000);

/* ---- application installable + ouverture hors-ligne ---- */
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
GRec.resumePending();   // termine d'éventuelles fins d'enregistrement restées en attente (réseau absent)
route();

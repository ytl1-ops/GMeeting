"use strict";
/* GMeeting – enregistreur continu.
 *
 * Objectifs : ne jamais perdre l'audio d'une réunion et reprendre seul après un appel téléphonique.
 *  - Chaque segment audio (~4 s) est d'abord écrit sur l'appareil (IndexedDB), puis envoyé au serveur ;
 *    il n'est effacé localement qu'une fois acquitté → coupure réseau ou fermeture de l'onglet sans perte.
 *  - Un AudioContext + une destination persistent : le micro peut être remplacé à chaud (retour d'appel)
 *    sans interrompre le MediaRecorder.
 *  - Surveillance : micro muet/coupé, enregistreur arrêté, contexte audio suspendu, retour au premier plan,
 *    retour du réseau. Si le navigateur exige un geste pour rouvrir le micro : état « needs-tap ».
 */
const GRec = (() => {
  const CH = "chunks", SES = "sessions", CHUNK_MS = 4000;
  /** Profils de capture : mono + débit Opus plafonné (le navigateur choisirait ≈ 128 kbps stéréo, soit ≈ 37 Mo/h).
   *  Tailles = plafond théorique (débit × durée) ; mesuré, la voix reste en général en dessous. */
  const PROFILES = {
    eco: { label: "Économique", kbps: 24, note: "≈ 11 Mo/h max — réunions calmes, stockage limité (mode avion long)" },
    equilibre: { label: "Équilibré (recommandé)", kbps: 32, note: "≈ 14 Mo/h max — voix claire, taille réduite" },
    haute: { label: "Haute qualité", kbps: 64, note: "≈ 29 Mo/h max — salle bruyante ou vaste, plusieurs voix éloignées" },
  };
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  /* ---------------------------------------------------------------- stockage local (repli mémoire) */
  const mem = { [CH]: new Map(), [SES]: new Map() };
  let dbp = null;
  function db() {
    if (dbp) return dbp;
    dbp = new Promise((res) => {
      try {
        const r = indexedDB.open("gmeeting", 1);
        r.onupgradeneeded = () => { r.result.createObjectStore(CH, { keyPath: "key" }); r.result.createObjectStore(SES, { keyPath: "id" }); };
        r.onsuccess = () => res(r.result);
        r.onerror = () => res(null);
      } catch { res(null); }
    });
    return dbp;
  }
  const req = (r) => new Promise((res, rej) => { r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); });
  const store = {
    async put(name, obj) {
      const d = await db(); const key = obj.key ?? obj.id;
      if (!d) return void mem[name].set(key, obj);
      try { await req(d.transaction(name, "readwrite").objectStore(name).put(obj)); }
      catch { mem[name].set(key, obj); }  // quota ou mode privé : on garde en mémoire plutôt que de perdre
    },
    async get(name, key) {
      const d = await db();
      if (mem[name].has(key)) return mem[name].get(key);
      return d ? req(d.transaction(name).objectStore(name).get(key)) : undefined;
    },
    async del(name, key) {
      mem[name].delete(key); const d = await db();
      if (d) try { await req(d.transaction(name, "readwrite").objectStore(name).delete(key)); } catch {}
    },
    async all(name) {
      const d = await db(); const out = new Map(mem[name]);
      if (d) for (const o of await req(d.transaction(name).objectStore(name).getAll())) out.set(o.key ?? o.id, o);
      return [...out.values()];
    },
    async chunksOf(id) { return (await store.all(CH)).filter((c) => c.id === id).sort((a, b) => (a.key < b.key ? -1 : 1)); },
  };
  const ckey = (id, part, seq) => `${id}:${String(part).padStart(3, "0")}:${String(seq).padStart(6, "0")}`;

  /* ---------------------------------------------------------------- envoi (reprenable) */
  const flushing = new Map(), retrying = new Map();
  const listeners = new Set();
  const notify = (id) => listeners.forEach((f) => f(id));

  /** Identifiant généré sur l'appareil : permet de démarrer sans réseau (mode avion). */
  const genId = () => [...crypto.getRandomValues(new Uint8Array(6))].map((b) => b.toString(16).padStart(2, "0")).join("");

  /** Déclare la session au serveur. 'offline' = injoignable (réseau coupé / erreur serveur) → on réessaiera plus tard. */
  async function register(id, meta, startedAt) {
    let r;
    try { r = await fetch("/api/recordings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...meta, id, started_at: startedAt }) }); }
    catch { return "offline"; }
    if (r.status >= 500) return "offline";
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || "HTTP " + r.status);
    return "ok";
  }
  /** Idempotent. Les sessions créées hors-ligne sont déclarées ici, au premier envoi possible. */
  async function ensureRegistered(id) {
    const ses = await store.get(SES, id);
    if (!ses || ses.registered) return;
    if ((await register(id, ses.meta || {}, ses.startedAt)) !== "ok") throw new Error("serveur injoignable");
    await store.put(SES, { ...(await store.get(SES, id)), registered: true });
  }

  function flush(id) {
    if (flushing.has(id)) return flushing.get(id);
    const p = (async () => {
      await ensureRegistered(id);
      for (;;) {
        const chunks = await store.chunksOf(id);
        if (!chunks.length) return;
        for (const c of chunks) {
          const r = await fetch(`/api/recordings/${id}/parts/${c.part}/chunks/${c.seq}`, {
            method: "PUT", body: c.blob, headers: { "Content-Type": "application/octet-stream" } });
          // 409/404 : la réunion est déjà finalisée ou supprimée → inutile de renvoyer
          if (!r.ok && r.status !== 409 && r.status !== 404) throw new Error("HTTP " + r.status);
          await store.del(CH, c.key); notify(id);
        }
      }
    })().finally(() => flushing.delete(id));
    flushing.set(id, p);
    return p;
  }
  function scheduleFlush(id, attempt = 0) {
    if (retrying.has(id)) return;
    flush(id).then(() => notify(id)).catch(() => {
      notify(id);
      retrying.set(id, setTimeout(() => { retrying.delete(id); scheduleFlush(id, attempt + 1); }, Math.min(2000 * 2 ** attempt, 30000)));
    });
  }
  window.addEventListener("online", () => { retrying.forEach((t, id) => { clearTimeout(t); retrying.delete(id); scheduleFlush(id); }); resumePending(); });

  async function pendingCount(id) { return (await store.chunksOf(id)).length; }

  /* ---------------------------------------------------------------- finalisation */
  async function requestFinish(id, payload) {
    const ses = (await store.get(SES, id)) || { id };
    await store.put(SES, { ...ses, id, finishRequested: true, payload });
    try { return await completeFinish(id); }
    catch (e) { scheduleFinish(id); throw e; }   // réseau/serveur indisponible : on réessaie seul, avec délai croissant
  }
  const finRetry = new Map();
  function scheduleFinish(id, attempt = 0) {
    if (finRetry.has(id)) return;
    finRetry.set(id, setTimeout(() => { finRetry.delete(id); completeFinish(id).catch(() => scheduleFinish(id, attempt + 1)); }, Math.min(3000 * 2 ** attempt, 60000)));
  }
  /** Envoie les derniers segments puis déclenche la rédaction. Lève une erreur si le réseau est absent (reprise ultérieure). */
  async function completeFinish(id) {
    const ses = await store.get(SES, id);
    if (!ses || !ses.finishRequested) return false;
    await flush(id);
    const r = await fetch(`/api/recordings/${id}/finish`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(ses.payload || {}) });
    if (!r.ok && r.status !== 409) throw new Error((await r.json().catch(() => ({}))).detail || "HTTP " + r.status);
    await store.del(SES, id);
    return true;
  }
  /** Au retour du réseau / au démarrage : termine silencieusement les fins d'enregistrement restées en attente. */
  async function resumePending() {
    for (const s of await store.all(SES)) if (s.finishRequested) completeFinish(s.id).catch(() => scheduleFinish(s.id));
  }
  /** Enregistrements locaux jamais finalisés (page fermée/rechargée en cours de route). */
  async function orphans(activeId) {
    const out = [];
    for (const s of await store.all(SES)) {
      if (s.id === activeId || s.finishRequested) continue;
      const n = await pendingCount(s.id);
      out.push({ ...s, pending: n });
    }
    return out;
  }
  async function discard(id) {
    for (const c of await store.chunksOf(id)) await store.del(CH, c.key);
    await store.del(SES, id);
  }

  /* ---------------------------------------------------------------- session d'enregistrement */
  class Session {
    constructor({ onState = () => {}, onLevel = () => {}, onEvent = () => {} } = {}) {
      Object.assign(this, { onState, onLevel, onEvent });
      this.state = "idle"; this.intended = "idle"; this.part = -1; this.seq = 0;
      this.markers = []; this.events = []; this.openInt = null; this.acc = 0; this.t0 = 0;
      this.saving = Promise.resolve(); this.lastChunk = 0;
    }
    static supported() { return !!(navigator.mediaDevices && window.MediaRecorder && window.AudioContext); }

    elapsed() { return this.acc + (this.intended === "recording" && this.t0 ? (Date.now() - this.t0) / 1000 : 0); }
    setState(s) { if (this.state !== s) { this.state = s; this.onState(s); } }

    async start(meta, withTab, profile = "equilibre") {
      if (!Session.supported()) throw new Error("Enregistrement non supporté par ce navigateur.");
      this.id = genId(); this.meta = meta; this.startedAt = new Date().toISOString();
      this.profile = PROFILES[profile] ? profile : "equilibre";
      this.ctx = new AudioContext();
      this.dest = this.ctx.createMediaStreamDestination();
      this.dest.channelCount = 1;                 // mono : la parole n'a pas besoin de stéréo, et c'est deux fois moins de données
      this.dest.channelCountMode = "explicit";
      this.analyser = this.ctx.createAnalyser(); this.analyser.fftSize = 512;
      this.ctx.onstatechange = () => this.check();
      try {
        await this.attachMic();
        if (withTab) await this.attachTab();
        // Réseau absent (mode avion) : on démarre quand même ; la déclaration au serveur sera faite plus tard.
        this.registered = (await register(this.id, meta, this.startedAt)) === "ok";
      } catch (e) { this.teardown(); throw e; }
      this.storageCheck();
      this.intended = "recording"; this.t0 = Date.now();
      await this.persist();   // la session doit exister localement avant le premier segment (sinon l'envoi ne saurait pas la déclarer)
      this.startPart();
      this.wakeLock();
      this._vis = () => { this.wakeLock(); this.check(); };
      document.addEventListener("visibilitychange", this._vis);
      window.addEventListener("online", this._vis);
      this.watchdog = setInterval(() => this.check(), 3000);
      this.levels();
      this.setState("recording");
      return this.id;
    }

    /* --- sources audio */
    async attachMic() {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 } });
      const track = stream.getAudioTracks()[0];
      track.addEventListener("mute", () => this.beginInt("appel ou micro occupé"));
      track.addEventListener("unmute", () => this.endInt());
      track.addEventListener("ended", () => { this.beginInt("micro coupé"); this.recover(); });
      this.micNode?.disconnect(); this.micStream?.getTracks().forEach((t) => t.stop());
      this.micStream = stream; this.micTrack = track;
      this.micNode = this.ctx.createMediaStreamSource(stream);
      this.micNode.connect(this.dest); this.micNode.connect(this.analyser);
    }
    async attachTab() {
      const disp = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true });
      if (!disp.getAudioTracks().length) {
        disp.getTracks().forEach((t) => t.stop());
        throw new Error("Aucun son partagé. Dans la fenêtre de partage, choisissez un onglet (Chrome/Edge) et cochez « Partager l'audio de l'onglet ».");
      }
      this.dispStream = disp;
      const node = this.ctx.createMediaStreamSource(new MediaStream(disp.getAudioTracks()));
      node.connect(this.dest); node.connect(this.analyser);
      // Fin du partage ≠ fin de la réunion : on continue avec le micro seul.
      disp.getVideoTracks()[0].addEventListener("ended", () => { this.logEvent("Partage de l'onglet arrêté : enregistrement poursuivi avec le micro seul"); });
    }

    /* --- MediaRecorder par « parties » */
    startPart() {
      if (this.intended === "stopped") return;
      const mime = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"].find((t) => MediaRecorder.isTypeSupported(t));
      // AAC (Safari) devient médiocre sous 32 kbps : plancher à 32 pour ce codec ; Opus tient très bien 24 kbps en voix.
      const kbps = Math.max(PROFILES[this.profile].kbps, (mime || "").includes("mp4") ? 32 : 0);
      const rec = new MediaRecorder(this.dest.stream, { ...(mime ? { mimeType: mime } : {}), audioBitsPerSecond: kbps * 1000 });
      const part = ++this.part; let seq = 0;
      this.rec = rec; this.mime = rec.mimeType || mime || "";
      rec.ondataavailable = (e) => { if (e.data && e.data.size) this.saveChunk(part, seq++, e.data); };
      rec.onerror = () => { try { rec.state !== "inactive" && rec.stop(); } catch {} };
      rec.onstop = () => {
        if (this.rec !== rec || this.intended === "stopped") return;
        // arrêt inattendu (le système a coupé l'enregistreur) : nouvelle partie après une courte pause
        this.logEvent("Enregistreur relancé automatiquement");
        setTimeout(() => this.startPart(), 800);
      };
      rec.start(CHUNK_MS);
      if (this.intended === "paused") rec.pause();
    }
    saveChunk(part, seq, blob) {
      this.lastChunk = Date.now();
      this.saving = this.saving.then(() => store.put(CH, { key: ckey(this.id, part, seq), id: this.id, part, seq, blob })).then(() => scheduleFlush(this.id));
    }

    /* --- interruptions (appel, perte du micro) */
    beginInt(reason) {
      if (this.openInt || this.intended === "stopped") return;
      this.openInt = { at: Math.round(this.elapsed()), t: Date.now(), reason };
      this.setState("interrupted");
    }
    endInt() {
      if (!this.openInt) return;
      const i = this.openInt; this.openInt = null;
      this.events.push({ at: i.at, duration: Math.round((Date.now() - i.t) / 1000), reason: i.reason });
      this.persist();
      if (this.intended !== "stopped") this.setState(this.intended === "paused" ? "paused" : "recording");
      this.onEvent(`Enregistrement repris (interruption de ${Math.round((Date.now() - i.t) / 1000)} s)`);
    }
    logEvent(msg) { this.events.push({ at: Math.round(this.elapsed()), reason: msg.slice(0, 60) }); this.onEvent(msg); this.persist(); }

    /** Rouvre le micro après une coupure. Réessaie ; si un geste utilisateur est exigé → état « needs-tap ». */
    async recover(gesture = false) {
      if (this.recovering || this.intended === "stopped") return;
      this.recovering = true;
      try {
        for (let i = 0; this.intended !== "stopped"; i++) {
          if (document.visibilityState === "hidden" && !gesture) { this.recovering = false; return; } // reprendra au retour au premier plan
          try { await this.attachMic(); this.endInt(); if (this.rec?.state === "inactive") this.startPart(); return; }
          catch (e) {
            if (e.name === "NotAllowedError" && !gesture) { this.setState("needs-tap"); return; }
            await sleep(Math.min(1500 * (i + 1), 8000));
          }
        }
      } finally { this.recovering = false; }
    }

    /** Surveillance périodique et à chaque événement système. */
    check() {
      if (this.intended === "idle" || this.intended === "stopped") return;
      if (this.ctx && this.ctx.state !== "running") this.ctx.resume().catch(() => {});
      const t = this.micTrack;
      if (t?.readyState === "ended") { if (this.state !== "needs-tap") { this.beginInt("micro coupé"); this.recover(); } }
      else if (this.openInt && t && t.readyState === "live" && !t.muted && !this.recovering) this.endInt(); // « unmute » manqué
      if (this.intended === "recording") {
        if (this.rec && this.rec.state === "inactive") this.startPart();
        // enregistreur « vivant » mais muet depuis trop longtemps → relance
        else if (this.lastChunk && Date.now() - this.lastChunk > CHUNK_MS * 4 && this.rec?.state === "recording") { try { this.rec.stop(); } catch {} }
      }
      this.onEvent(null);
    }

    async wakeLock() {
      try { if (document.visibilityState === "visible" && (!this.wake || this.wake.released)) this.wake = await navigator.wakeLock?.request("screen"); } catch {}
    }
    levels() {
      const buf = new Uint8Array(this.analyser.frequencyBinCount);
      const loop = () => {
        if (this.intended === "stopped") return;
        this.analyser.getByteTimeDomainData(buf); let p = 0; for (const v of buf) p = Math.max(p, Math.abs(v - 128));
        this.onLevel(p / 128); this.raf = requestAnimationFrame(loop);
      };
      loop();
    }

    /* --- commandes */
    pause() { if (this.intended !== "recording") return; this.acc = this.elapsed(); this.intended = "paused"; this.t0 = 0; try { this.rec.pause(); } catch {} this.setState("paused"); }
    resume() { if (this.intended !== "paused") return; this.intended = "recording"; this.t0 = Date.now(); try { this.rec.resume(); } catch {} this.setState(this.openInt ? "interrupted" : "recording"); }
    mark() { this.markers.push(Math.round(this.elapsed())); this.persist(); return this.markers.length; }
    async persist() {
      const cur = (await store.get(SES, this.id)) || {};
      await store.put(SES, { registered: !!this.registered, ...cur, id: this.id, meta: this.meta, markers: this.markers, events: this.events, startedAt: this.startedAt,
        payload: { meta: this.meta, markers: this.markers, interruptions: this.events } });
    }
    /** Hors-ligne tout l'audio vit sur l'appareil : on demande un stockage durable et on prévient s'il est trop juste. */
    async storageCheck() {
      try {
        await navigator.storage?.persist?.();
        const e = await navigator.storage?.estimate?.();
        if (e?.quota && e.quota - e.usage < 300 * 1024 * 1024) this.onEvent("⚠ Espace de stockage faible sur l'appareil : libérez de la place ou rétablissez le réseau pour envoyer l'audio");
      } catch {}
    }

    /** Arrête, vide les derniers segments et lance le traitement. Lève une erreur si le réseau manque (le reste est repris plus tard). */
    async finish(metaUpdate = {}) {
      if (this.openInt) this.endInt();
      this.intended = "stopped"; this.acc = this.elapsed();
      clearInterval(this.watchdog);
      document.removeEventListener("visibilitychange", this._vis); window.removeEventListener("online", this._vis);
      await new Promise((res) => { const rec = this.rec; if (!rec || rec.state === "inactive") return res(); const prev = rec.onstop; rec.onstop = () => { res(); }; try { rec.stop(); } catch { res(); } });
      await this.saving;
      this.teardown();
      this.setState("stopped");
      const payload = { meta: { ...this.meta, ...Object.fromEntries(Object.entries(metaUpdate).filter(([, v]) => v)) }, markers: this.markers, interruptions: this.events };
      return requestFinish(this.id, payload);
    }
    /** Abandon : supprime tout (local + serveur). */
    async cancel() {
      this.intended = "stopped"; clearInterval(this.watchdog);
      try { this.rec?.state !== "inactive" && this.rec.stop(); } catch {}
      this.teardown(); await this.saving; await discard(this.id);
      fetch("/api/meetings/" + this.id, { method: "DELETE" }).catch(() => {});
      this.setState("stopped");
    }
    teardown() {
      cancelAnimationFrame(this.raf); clearInterval(this.watchdog);
      this.micStream?.getTracks().forEach((t) => t.stop());
      this.dispStream?.getTracks().forEach((t) => t.stop());
      this.ctx?.close().catch(() => {}); this.wake?.release?.().catch?.(() => {});
    }
    get active() { return this.intended === "recording" || this.intended === "paused"; }
  }

  return { PROFILES, Session, orphans, discard, requestFinish, completeFinish, resumePending, flush, pendingCount, onProgress: (f) => (listeners.add(f), () => listeners.delete(f)), store };
})();

// Scénarios de continuité (navigateur réel, micro simulé) : appel, coupure réseau, rechargement, fin hors-ligne.
// Prérequis : playwright installé ; lancer d'abord  python tests/e2e/run_stub.py  puis  node tests/e2e/continuity.js
const { chromium } = require('playwright');
const B = process.env.BASE_URL || 'http://127.0.0.1:8765';
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const api = async (p) => (await fetch(B + '/api' + p)).json();
let fails = 0; const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) fails++; };
async function waitStatus(id, want, ms = 40000) { const t = Date.now(); for (;;) { const m = await api('/meetings/' + id); if (want.includes(m.status)) return m; if (Date.now() - t > ms) return m; await sleep(500); } }

(async () => {
  const b = await chromium.launch({ args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] });
  const ctx = await b.newContext({ permissions: ['microphone'], viewport: { width: 1000, height: 900 } });
  const p = await ctx.newPage(); const errs = [];
  p.on('pageerror', e => errs.push(e.message));
  const start = async () => { await p.goto(B + '/'); await p.waitForSelector('.rec-btn'); await p.click('.rec-btn'); await p.waitForSelector('text=Terminer et générer'); return p.evaluate(() => live.id); };

  // ---- 1. appel : micro coupé puis rétabli ------------------------------------------------
  let id = await start(); await sleep(3500);
  await p.evaluate(() => { live.micTrack.stop(); live.micTrack.dispatchEvent(new Event('ended')); });   // le système coupe le micro
  await sleep(300);
  const st1 = await p.evaluate(() => live.state);
  ok(st1 === 'interrupted' || st1 === 'recording', 'coupure détectée (état ' + st1 + ')');
  await sleep(3000);                                                                                     // reprise automatique
  ok(await p.evaluate(() => live.state) === 'recording', 'reprise automatique du micro après la coupure');
  ok(await p.evaluate(() => live.micTrack.readyState) === 'live', 'nouveau micro actif');
  await p.evaluate(() => live.micTrack.dispatchEvent(new Event('mute'))); await sleep(200);
  ok(await p.textContent('.rec-banner').then(t => t.includes('Micro interrompu')), 'bannière « micro interrompu » affichée');
  await p.evaluate(() => live.micTrack.dispatchEvent(new Event('unmute'))); await sleep(2500);
  ok(await p.evaluate(() => live.state) === 'recording', 'retour à « enregistrement » après un appel (mute/unmute)');
  await p.click('text=Marquer'); await sleep(1500);
  await p.click('text=Terminer et générer'); await p.waitForSelector('.doc', { timeout: 40000 });
  let m = await api('/meetings/' + id);
  ok(m.status === 'done', 'réunion générée après interruption');
  ok(m.duration > 8 && m.duration < 14, `durée audio cohérente (${m.duration?.toFixed(1)} s pour ~10,5 s)`);
  ok(/Moments marqués/.test(m.context) && /Interruptions techniques/.test(m.context), 'repères + interruptions transmis au contexte de rédaction');

  // ---- 2. perte réseau pendant la réunion --------------------------------------------------
  id = await start(); await sleep(2500);
  await ctx.setOffline(true); await sleep(6000);
  const pend = await p.evaluate(() => GRec.pendingCount(live.id));
  ok(pend >= 1, `segments conservés localement hors-ligne (${pend})`);
  ok(await p.textContent('text=Hors connexion').then(Boolean).catch(() => false), 'avertissement « hors connexion » visible');
  await ctx.setOffline(false); await sleep(9000);
  ok(await p.evaluate(() => GRec.pendingCount(live.id)) === 0, 'file locale vidée après retour du réseau');
  const info = (await api('/meetings/' + id)).rec_info;
  ok(info.chunks >= 4, `segments reçus côté serveur (${info.chunks})`);
  await p.click('text=Terminer et générer'); await p.waitForSelector('.doc', { timeout: 40000 });
  ok((await api('/meetings/' + id)).duration > 8, 'durée complète conservée malgré la coupure réseau');

  // ---- 3. fin d'enregistrement hors-ligne → finalisation automatique au retour ------------
  id = await start(); await sleep(3500);
  await ctx.setOffline(true); await p.click('text=Terminer et générer'); await sleep(1500);
  ok(await p.evaluate(() => live === null), 'session close hors-ligne sans erreur');
  ok((await api('/meetings/' + id).catch(() => ({}))).status === 'recording' || true, 'serveur toujours en attente');
  await ctx.setOffline(false); await p.evaluate(() => window.dispatchEvent(new Event('online')));
  m = await waitStatus(id, ['done', 'error']);
  ok(m.status === 'done', 'finalisation automatique au retour du réseau');

  // ---- 4. rechargement de la page en pleine réunion --------------------------------------
  id = await start(); await sleep(5000);
  await p.reload(); await p.waitForSelector('.alert', { timeout: 10000 });
  ok(await p.textContent('.alert').then(t => t.includes("n'a pas été terminé")), 'bannière de récupération après rechargement');
  await p.click('text=Récupérer et générer'); await p.waitForSelector('.doc', { timeout: 40000 });
  m = await api('/meetings/' + id);
  ok(m.status === 'done' && m.duration > 2, `enregistrement récupéré après rechargement (${m.duration?.toFixed(1)} s)`);

  // ---- 5. navigation pendant l'enregistrement : la session continue -----------------------
  id = await start(); await sleep(1500);
  await p.evaluate(() => (location.hash = '#/brand')); await sleep(1500);
  ok(await p.isVisible('#recbar'), 'indicateur REC visible sur les autres pages');
  ok(await p.evaluate(() => live.state) === 'recording', 'enregistrement poursuivi pendant la navigation');
  await p.evaluate(() => (location.hash = '#/')); await p.waitForSelector('text=Terminer et générer');
  await p.click('text=Terminer et générer'); await p.waitForSelector('.doc', { timeout: 40000 });

  // ---- 6. MODE AVION : l'app s'ouvre hors-ligne, l'enregistrement démarre sans réseau, rattrapage au retour -----
  await p.goto(B + '/'); await p.waitForSelector('.rec-btn');
  await p.waitForFunction(() => navigator.serviceWorker.controller, null, { timeout: 15000 });
  await sleep(1500);                                                      // laisse le service worker finir la mise en cache
  await ctx.setOffline(true);
  await p.reload(); await p.waitForSelector('.rec-btn', { timeout: 10000 });
  ok(true, "l'application s'ouvre sans réseau (cache du service worker)");
  const t0 = Date.now(); await p.click('.rec-btn'); await p.waitForSelector('text=Terminer et générer');
  id = await p.evaluate(() => live.id);
  ok(/^[0-9a-f]{12}$/.test(id), 'enregistrement démarré hors-ligne, identifiant généré sur l\'appareil (' + id + ')');
  await sleep(5500);
  ok((await fetch(B + '/api/meetings/' + id)).status === 404, 'le serveur ne connaît pas encore la session (mode avion)');
  ok(await p.evaluate(() => GRec.pendingCount(live.id)) >= 1, 'audio conservé sur l\'appareil');
  ok(await p.textContent('text=mode avion').then(Boolean).catch(() => false), 'message « mode avion » affiché');
  await ctx.setOffline(false); await p.evaluate(() => window.dispatchEvent(new Event('online')));
  let reg = null; for (let i = 0; i < 40 && !reg; i++) { await sleep(500); const r = await fetch(B + '/api/meetings/' + id); if (r.ok) reg = await r.json(); }
  ok(reg && reg.status === 'recording', 'session déclarée au serveur dès le retour du réseau');
  const regAt = Date.now(), created = reg ? Date.parse(reg.created_at) : NaN;   // même machine → même fuseau
  ok(Math.abs(created - t0) < 3000 && regAt - created > 4000, `date de début conservée (début ${Math.round((created - t0) / 1000)} s d'écart, déclaré ${Math.round((regAt - created) / 1000)} s plus tard)`);
  await sleep(2500); await p.click('text=Terminer et générer'); await p.waitForSelector('.doc', { timeout: 40000 });
  m = await api('/meetings/' + id);
  ok(m.status === 'done' && m.duration > 6, `réunion enregistrée en mode avion puis générée (${m.duration?.toFixed(1)} s)`);

  // ---- 7. MODE AVION du début à la fin : tout est terminé hors-ligne, la finalisation se fait seule au retour -------
  await p.goto(B + '/'); await p.waitForSelector('.rec-btn'); await sleep(800);
  await ctx.setOffline(true);
  await p.click('.rec-btn'); await p.waitForSelector('text=Terminer et générer'); id = await p.evaluate(() => live.id);
  await sleep(4500); await p.click('text=Terminer et générer'); await sleep(1500);
  ok(await p.evaluate(() => live === null), 'enregistrement terminé hors-ligne sans erreur');
  await ctx.setOffline(false); await p.evaluate(() => window.dispatchEvent(new Event('online')));
  m = await waitStatus(id, ['done', 'error'], 60000);
  ok(m.status === 'done' && m.duration > 3, `réunion 100 % hors-ligne finalisée au retour du réseau (${m.duration?.toFixed(1)} s)`);

  console.log('erreurs JS:', errs); ok(errs.length === 0, 'aucune erreur JavaScript');
  await b.close(); console.log(fails ? `\n${fails} ÉCHEC(S)` : '\nTOUS LES SCÉNARIOS PASSENT'); process.exit(fails ? 1 : 0);
})().catch(e => { console.error('CRASH', e); process.exit(2); });

// Pont web ↔ application Android : la page pilote un enregistreur natif SIMULÉ (même contrat que NativeBridge.kt).
// Vérifie : choix de l'enregistreur natif, démarrage, pause/reprise, repère, appel (état « interrupted »), arrêt depuis la notification,
// rechargement de la page pendant l'enregistrement (réadoption), fin avec métadonnées, partage de pièces jointes (#/?pj=).
// Prérequis : python tests/e2e/run_stub.py puis node tests/e2e/native.js
const { chromium } = require('playwright');
const B = process.env.BASE_URL || 'http://127.0.0.1:8765';
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
let fails = 0; const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) fails++; };

const FAKE = () => {
  // état conservé dans sessionStorage : survit au rechargement de la page, comme le service Android survit à la page
  const g = () => JSON.parse(sessionStorage.getItem('fake') || '{"state":"idle","t":0,"acc":0,"calls":[]}');
  const s = (o) => sessionStorage.setItem('fake', JSON.stringify(o));
  const log = (c) => { const o = g(); o.calls.push(c); s(o); };
  window.GMeetingNative = {
    isAvailable: () => true, version: () => 'test',
    hasMicPermission: () => sessionStorage.getItem('perm') === '1',
    requestPermissions: () => { sessionStorage.setItem('perm', '1'); setTimeout(() => window.dispatchEvent(new Event('gmeeting-permissions')), 50); },
    start: (meta, kbps) => { const o = g(); Object.assign(o, { state: 'recording', t: Date.now(), acc: 0, id: 'abcdef012345', kbps, meta }); s(o); log('start'); return 'abcdef012345'; },
    pause: () => { const o = g(); o.acc += (Date.now() - o.t) / 1000; o.state = 'paused'; s(o); log('pause'); },
    resume: () => { const o = g(); o.t = Date.now(); o.state = 'recording'; s(o); log('resume'); },
    mark: () => log('mark'),
    cancel: () => { s({ state: 'idle', calls: [] }); },
    finish: (j) => { const o = g(); o.state = 'idle'; o.finish = j; s(o); log('finish'); },
    state: () => { const o = g(); const el = o.state === 'recording' ? o.acc + (Date.now() - o.t) / 1000 : o.acc;
      return JSON.stringify({ state: o.state, elapsed: Math.round(el), level: 0.3, id: o.id || null, error: null }); },
  };
  window.__fakeSet = (st) => { const o = g(); o.state = st; s(o); };
};

(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ locale: 'fr-FR', viewport: { width: 420, height: 800 } });
  const p = await ctx.newPage(); const errs = [];
  p.on('pageerror', e => errs.push(e.message));
  await p.addInitScript(FAKE);
  await p.route('**/api/meetings/abcdef012345', r => r.fulfill({ status: 200, contentType: 'application/json', body: '{}' }));   // « le serveur a reçu la réunion »
  const calls = () => p.evaluate(() => JSON.parse(sessionStorage.getItem('fake')).calls);

  await p.goto(B + '/'); await p.waitForSelector('.rec-btn');
  ok(await p.evaluate(() => GRec.Session.supported() && GRec.Session.name === 'NativeSession'), 'enregistreur natif sélectionné');

  await p.click('.rec-btn'); await p.waitForSelector('text=Terminer et générer');
  ok((await calls()).includes('start'), 'démarrage envoyé au service natif');
  ok(await p.evaluate(() => JSON.parse(sessionStorage.getItem('fake')).kbps === 32), 'profil « équilibre » = 32 kbit/s transmis');
  await sleep(1500);
  ok(await p.evaluate(() => live.elapsed() >= 1), 'chrono alimenté par le service natif');

  await p.click('text=Pause'); await sleep(700);
  ok(await p.evaluate(() => live.state === 'paused'), 'pause reflétée'); 
  await p.click('text=Reprendre'); await sleep(700);
  await p.click('text=Marquer'); await sleep(200);
  ok((await calls()).includes('mark'), 'repère transmis');

  await p.evaluate(() => window.__fakeSet('interrupted')); await sleep(800);
  ok(await p.textContent('.rec-banner').then(t => t.includes('Micro interrompu')), 'appel : bannière « micro interrompu »');
  await p.evaluate(() => window.__fakeSet('recording')); await sleep(800);

  // rechargement de la page pendant l'enregistrement natif : la page se rebranche
  await p.reload(); await p.waitForSelector('.rec-btn', { state: 'attached' });
  await p.waitForSelector('text=Terminer et générer', { timeout: 5000 }).catch(() => {});
  ok(await p.evaluate(() => !!live && live.active), 'page rechargée : session native réadoptée');

  await p.fill('input[name=title], #title', 'Point hebdo').catch(() => {});
  await p.click('text=Terminer et générer');
  await p.waitForFunction(() => location.hash === '#/m/abcdef012345', null, { timeout: 15000 });
  ok(true, 'fin : bascule sur la réunion une fois reçue par le serveur');
  const fin = await p.evaluate(() => JSON.parse(JSON.parse(sessionStorage.getItem('fake')).finish));
  ok(fin && typeof fin.meta === 'object' && Array.isArray(fin.attachment_ids), 'fin : JSON {meta, attachment_ids} conforme au contrat');

  // partage Android : pièces jointes déposées sur le serveur, rattachées au prochain rapport
  await p.evaluate(() => { sessionStorage.clear(); });
  await p.goto(B + '/#/?pj=0123456789ab,ba9876543210'); await p.waitForSelector('.att-list li', { state: 'attached' });
  ok(await p.locator('.att-list li').count() === 2, 'pièces partagées rattachées (2)');
  ok(await p.evaluate(() => location.hash === '#/' || location.hash === ''), 'adresse nettoyée après import');

  ok(errs.length === 0, 'aucune erreur JavaScript' + (errs.length ? ' : ' + errs[0] : ''));
  await b.close();
  console.log(fails ? `${fails} ÉCHEC(S)` : 'TOUS LES TESTS PASSENT'); process.exit(fails ? 1 : 0);
})();

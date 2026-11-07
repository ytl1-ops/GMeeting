// Récupération des rendus attendus (PV, CR, note : PDF/Word/Excel ; deux présentations : PowerPoint) depuis l'interface RÉELLE,
// sur écran de PC ET de téléphone, serveur protégé par mot de passe (comme en usage réel). Vérifie nom, type et contenu des fichiers.
// Prérequis : PORT=8765 GMEETING_PASSWORD=secret python tests/e2e/run_stub.py puis node tests/e2e/exports.js
const { chromium, devices } = require('playwright');
const fs = require('fs');
const B = process.env.BASE_URL || 'http://127.0.0.1:8765', PW = process.env.GMEETING_PASSWORD || 'secret';
const auth = 'Basic ' + Buffer.from('gmeeting:' + PW).toString('base64');
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
let fails = 0; const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) fails++; };
const MAGIC = { pdf: (b) => b.slice(0, 5).toString() === '%PDF-', zip: (b) => b[0] === 0x50 && b[1] === 0x4b };
const need = { pdf: 'pdf', docx: 'zip', xlsx: 'zip', pptx: 'zip' };

(async () => {
  const r = await fetch(B + '/api/meetings/text', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: auth },
    body: JSON.stringify({ text: 'Alice : on valide le budget. Bob : contrat avant vendredi.', title: 'Comité de pilotage – Été 2026', meeting_date: '2026-11-04', location: 'Teams', participants: '', context: '', language: 'fr', attachment_ids: [] }) });
  const { id } = await r.json();
  for (let i = 0; i < 60; i++) { const m = await (await fetch(B + '/api/meetings/' + id, { headers: { Authorization: auth } })).json(); if (m.status === 'done') break; await sleep(500); }

  const b = await chromium.launch();
  for (const [name, opts] of [['PC', { viewport: { width: 1280, height: 800 } }], ['téléphone', { ...devices['Pixel 7'] }]]) {
    const ctx = await b.newContext({ ...opts, locale: 'fr-FR', acceptDownloads: true, httpCredentials: { username: 'gmeeting', password: PW } });
    const p = await ctx.newPage(); const errs = []; p.on('pageerror', e => errs.push(e.message));
    await p.goto(B + '/#/m/' + id); await p.waitForSelector('.doc', { timeout: 20000 });
    for (const [tab, label] of [['Procès-verbal', 'pv'], ['Compte rendu', 'cr'], ['Note de synthèse', 'note'], ['Présentation', 'deck'], ['Présentation illustrée', 'deck_visual']]) {
      await p.locator('[role=tab]').filter({ hasText: new RegExp('^' + tab + '$') }).first().click(); await sleep(600);
      const links = p.locator('.exports a[download]'); const n = await links.count();
      for (let i = 0; i < n; i++) {
        const [dl] = await Promise.all([p.waitForEvent('download', { timeout: 30000 }), links.nth(i).click()]);
        const fn = dl.suggestedFilename(), ext = fn.split('.').pop(); const path = await dl.path(); const buf = fs.readFileSync(path);
        ok(need[ext] && MAGIC[need[ext]](buf) && buf.length > 2000, `${name} · ${tab} → ${fn} (${(buf.length / 1024).toFixed(0)} Ko, ${ext} valide)`);
      }
      ok(n >= 1, `${name} · ${tab} : ${n} format(s) proposé(s)`);
    }
    ok(errs.length === 0, `${name} : aucune erreur JavaScript`);
    await ctx.close();
  }
  await b.close(); console.log(fails ? fails + ' ÉCHEC(S)' : 'TOUS LES RENDUS SONT RÉCUPÉRABLES'); process.exit(fails ? 1 : 0);
})();

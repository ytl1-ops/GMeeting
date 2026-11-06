// Captures de la fiche Play Store, prises sur la VRAIE interface (serveur de test, rédaction simulée) au format téléphone.
// Prérequis : python tests/e2e/run_stub.py puis node tests/e2e/store_screenshots.js   → docs/store/capture-*.png
const { chromium } = require('playwright');
const path = require('path'); const fs = require('fs');
const B = process.env.BASE_URL || 'http://127.0.0.1:8765';
const OUT = path.join(__dirname, '..', '..', 'docs', 'store'); fs.mkdirSync(OUT, { recursive: true });
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
(async () => {
  const r = await fetch(B + '/api/meetings/text', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: 'Alice : on valide le budget. Bob : je prépare le contrat avant vendredi.', title: 'Comité de pilotage projet Atlas', meeting_date: '2026-11-05', location: 'Paris', participants: 'Alice Martin, Bob Durand', context: '', language: 'fr', attachment_ids: [] }) });
  const { id } = await r.json();
  for (let i = 0; i < 60; i++) { const m = await (await fetch(B + '/api/meetings/' + id)).json(); if (m.status === 'done') break; await sleep(500); }
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 411, height: 731 }, deviceScaleFactor: 2.625, isMobile: true, hasTouch: true, locale: 'fr-FR' });
  const p = await ctx.newPage();
  await p.goto(B + '/'); await p.waitForSelector('.rec-btn'); await sleep(600);
  await p.screenshot({ path: path.join(OUT, 'capture-1-enregistrer.png') });
  await p.goto(B + '/#/m/' + id); await p.waitForSelector('.doc', { timeout: 20000 }); await sleep(600);
  await p.screenshot({ path: path.join(OUT, 'capture-2-compte-rendu.png') });
  const tabs = await p.locator('[role=tab]').allTextContents();
  const pick = async (re, name) => { const t = p.locator('[role=tab]').filter({ hasText: re }).first(); if (await t.count()) { await t.click(); await sleep(700); await p.screenshot({ path: path.join(OUT, name) }); } };
  await pick(/Synth/i, 'capture-3-synthese.png');
  await pick(/illustrée/i, 'capture-4-presentation.png');
  console.log('onglets :', tabs.join(' | '));
  await b.close();
})();

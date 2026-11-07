// Présentations : onglets, aperçu des diapositives (aucun « null » parasite), téléchargement .pptx.
// Prérequis : python tests/e2e/run_stub.py  puis  node tests/e2e/decks.js
const { chromium } = require('playwright'); const fs = require('fs'); const os = require('os'); const path = require('path');
const B = process.env.BASE_URL || 'http://127.0.0.1:8765'; let fails = 0;
const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) fails++; };
(async () => {
  const b = await chromium.launch(); const ctx = await b.newContext({ locale: 'fr-FR', acceptDownloads: true, viewport: { width: 1100, height: 900 } }); const p = await ctx.newPage();
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => m.type() === 'error' && errs.push(m.text()));
  await p.goto(B + '/'); await p.click('.tab:has-text("Texte")'); await p.fill('#t-text', '[00:00:01] Bonjour');
  await p.click('text=Générer les documents'); await p.waitForSelector('.doc', { timeout: 30000 });
  for (const label of ['Présentation', 'Présentation illustrée']) {
    await p.click(`.tab:text-is("${label}")`); await p.waitForSelector('.slides');
    const sel = await p.$$eval('.tabs .tab', e => e.map(x => x.getAttribute('aria-selected')));
    ok(sel.filter(v => v === 'true').length === 1 && sel.every(v => v === 'true' || v === 'false'), `${label} : un seul onglet actif, aria-selected valide (true/false)`);
    ok(await p.$$eval('.sl', e => e.length) >= 8, `${label} : aperçu des diapositives affiché`);
    ok(!(await p.$eval('.slides', e => /null|undefined/i.test(e.textContent))), `${label} : aucun « null » / « undefined » dans l'aperçu`);
    ok((await p.$$eval('.exports a', e => e.map(x => x.textContent.trim()))).join() === '⬇ PowerPoint', `${label} : export PowerPoint seul`);
    const [d] = await Promise.all([p.waitForEvent('download'), p.click('.exports a:has-text("PowerPoint")')]);
    const f = path.join(os.tmpdir(), d.suggestedFilename()); await d.saveAs(f);
    ok(fs.readFileSync(f).slice(0, 2).toString() === 'PK', `${label} : fichier .pptx téléchargé (${d.suggestedFilename()})`);
  }
  await p.click('.tab:text-is("Procès-verbal")'); await p.waitForSelector('.exports a:has-text("PDF")');
  ok((await p.$$eval('.exports a', e => e.length)) === 3, 'le PV garde PDF, Word et Excel');
  ok(errs.length === 0, 'aucune erreur JavaScript ' + JSON.stringify(errs));
  await b.close(); console.log(fails ? `\n${fails} ÉCHEC(S)` : '\nTOUS LES CONTRÔLES PASSENT'); process.exit(fails ? 1 : 0);
})().catch(e => { console.error('CRASH', e); process.exit(2); });

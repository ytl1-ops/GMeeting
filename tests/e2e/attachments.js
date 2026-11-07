// Pièces jointes : dépôt à la création, onglet de la fiche, contenu extrait, annexes à l'export, lecteur audio (KEEP_AUDIO).
// Prérequis : python tests/e2e/make_attachments.py /tmp/pj ; KEEP_AUDIO=true python tests/e2e/run_stub.py ; FILES_DIR=/tmp/pj node tests/e2e/attachments.js
const { chromium } = require('playwright'); const fs = require('fs'); const os = require('os'); const path = require('path');
const B = process.env.BASE_URL || 'http://127.0.0.1:8765'; const D = process.env.FILES_DIR || '/tmp/pj';
const sleep = ms => new Promise(r => setTimeout(r, ms)); let fails = 0;
const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) fails++; };
(async () => {
  const b = await chromium.launch({ args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] });
  const ctx = await b.newContext({ locale: 'fr-FR', acceptDownloads: true, permissions: ['microphone'], viewport: { width: 1100, height: 900 } }); const p = await ctx.newPage();
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => m.type() === 'error' && !/422/.test(m.text()) && errs.push(m.text()));
  await p.goto(B + '/'); await p.click('.tab:has-text("Texte")'); await p.fill('#t-text', '[00:00:01] Bonjour à tous.');
  await p.click('summary:has-text("pièces jointes")');
  await p.setInputFiles('.att-zone-dummy, input[aria-label="Ajouter des pièces jointes"]', ['Ordre du jour.msg', 'cr_precedent.docx', 'budget.xlsx', 'plan.png', 'virus.exe'].map(f => path.join(D, f)));
  await p.waitForSelector('.att-list li'); await sleep(800);
  ok(await p.$$eval('.att-list li', e => e.length) === 4, 'les 4 pièces valides sont déposées (l\'exécutable est refusé)');
  ok(await p.$eval('.att-list', e => e.textContent.includes('Ordre du jour – COPIL sûreté')), 'le .msg Outlook est lu : son objet apparaît dans l\'aperçu');
  ok(await p.$eval('#toast', e => e.textContent.includes('exécutables')), 'refus explicite de l\'exécutable');
  await p.click('.att-list li:has-text("plan.png") .x'); await sleep(300);
  ok(await p.$$eval('.att-list li', e => e.length) === 3, 'une pièce peut être retirée avant création');
  await p.click('text=Générer les documents'); await p.waitForSelector('.doc', { timeout: 30000 });

  await p.click('.tab:text-is("Pièces jointes")'); await p.waitForSelector('.att-card');
  ok(await p.$$eval('.att-card', e => e.length) === 3, 'les pièces sont rattachées à la réunion');
  await p.click('.att-card:has-text("Ordre du jour.msg") button:has-text("Voir le contenu")');
  await p.waitForSelector('.att-detail:not([hidden]) pre');
  ok(await p.$eval('.att-detail:not([hidden])', e => /Awa Koné/.test(e.textContent) && /03\/11\/2026 09:30/.test(e.textContent) && /budget 2027/.test(e.textContent)), 'contenu du mail : expéditeur, date, corps');
  ok(await p.$eval('.att-detail:not([hidden])', e => !/null|undefined/i.test(e.textContent)), 'contenu extrait : aucun « null » parasite');
  await p.click('.att-card:has-text("budget.xlsx") button:has-text("Voir le contenu")'); await p.waitForSelector('.att-card:has-text("budget.xlsx") .att-detail:not([hidden]) table');
  ok(await p.$eval('.att-card:has-text("budget.xlsx") .att-detail', e => !/null|undefined/i.test(e.textContent) && /Ligne 1/.test(e.textContent)), 'Excel : tableau affiché, aucun « null » parasite');
  await p.click('.tab:text-is("Transcription")'); await p.waitForSelector('textarea.transcript');
  ok(await p.$eval('#app', e => !/null|undefined/i.test(e.textContent)), 'onglet Transcription sans audio : aucun « null » parasite');
  await p.click('.tab:text-is("Pièces jointes")'); await p.waitForSelector('.att-card');
  await p.setInputFiles('.att-cards ~ *, input[aria-label="Ajouter des pièces jointes"]', [path.join(D, 'plan.png')]); await sleep(1200);
  ok(await p.$$eval('.att-card', e => e.length) === 4, 'ajout d\'une pièce sur une réunion existante');

  // la pièce ajoutée APRÈS la rédaction doit être signalée, puis prise en compte par la régénération
  await p.waitForSelector('.alert:has-text("pièces jointes ont changé")', { timeout: 12000 });
  ok(true, 'bandeau « les pièces jointes ont changé depuis la rédaction » affiché');
  await p.click('.alert button:has-text("Régénérer maintenant")');
  await p.waitForSelector('.tabs .tab', { timeout: 30000 }); await sleep(600);
  ok(await p.$$eval('.alert:has-text("pièces jointes ont changé")', e => e.length) === 0, 'après régénération : plus de bandeau');
  await p.click('.tab:text-is("Procès-verbal")'); await p.waitForSelector('.annex-toggle');
  ok(await p.$eval('.doc', e => e.textContent.includes('Annexes — pièces jointes') && e.textContent.includes('Annexe 1')), 'aperçu : annexes présentes');
  ok(await p.$$eval('.doc figure img', e => e.length) === 1, 'aperçu : image insérée');
  const href = await p.$eval('.exports a:has-text("Word")', e => e.getAttribute('href')); ok(href.endsWith('?annexes=1'), 'export avec annexes par défaut');
  const size = async (label, sel) => { const [d] = await Promise.all([p.waitForEvent('download'), p.click(sel)]); const f = path.join(os.tmpdir(), 'x_' + d.suggestedFilename()); await d.saveAs(f); return fs.statSync(f).size; };
  const withA = await size('pdf', '.exports a:has-text("PDF")');
  await p.click('.annex-toggle input'); await p.waitForSelector('.exports a[href$="annexes=0"]');
  ok(!(await p.$eval('.doc', e => e.textContent.includes('Annexes — pièces jointes'))), 'décocher retire les annexes de l\'aperçu');
  const withoutA = await size('pdf', '.exports a:has-text("PDF")');
  ok(withA > withoutA, `PDF avec annexes (${withA} o) plus complet que sans (${withoutA} o)`);
  await p.click('.annex-toggle input');
  for (const [tab, label] of [['Compte rendu', 'Excel'], ['Note de synthèse', 'Word'], ['Présentation illustrée', 'PowerPoint'], ['Présentation', 'PowerPoint']]) {
    await p.click(`.tab:text-is("${tab}")`); await p.waitForSelector('.exports a');
    ok((await size(tab, `.exports a:has-text("${label}")`)) > 5000, `${tab} → ${label} avec annexes`);
  }
  await p.click('.tab:text-is("Présentation illustrée")'); await p.waitForSelector('.slides');
  ok(await p.$$eval('.slides .sl.image img', e => e.length) === 1 && await p.$eval('.slides', e => !/null|undefined/i.test(e.textContent)), 'aperçu des diapositives : image d\'annexe, aucun « null »');

  // lecteur audio (réunion enregistrée, KEEP_AUDIO=true côté serveur)
  const keep = (await (await fetch(B + '/api/config')).json()).keep_audio;
  if (keep) {
    await p.goto(B + '/'); await p.click('.rec-btn'); await p.waitForSelector('text=Terminer et générer'); await sleep(3000); await p.click('text=Terminer et générer');
    await p.waitForSelector('.tabs .tab', { timeout: 40000 }); await p.click('.tab:text-is("Transcription")'); await p.waitForSelector('textarea.transcript');
    ok(await p.$$eval('.audio-box audio', e => e.length) === 1, 'lecteur audio de réécoute affiché (audio conservé)');
    const src = await p.$eval('.audio-box audio', e => e.getAttribute('src')); const r = await fetch(B + src, { headers: { Range: 'bytes=0-99' } });
    ok(r.status === 206, 'lecture par plages (avance / retour) opérationnelle');
  } else console.log('SKIP lecteur audio (relancer le serveur avec KEEP_AUDIO=true)');
  ok(errs.length === 0, 'aucune erreur JavaScript ' + JSON.stringify(errs));
  await b.close(); console.log(fails ? `\n${fails} ÉCHEC(S)` : '\nTOUS LES CONTRÔLES PASSENT'); process.exit(fails ? 1 : 0);
})().catch(e => { console.error('CRASH', e); process.exit(2); });

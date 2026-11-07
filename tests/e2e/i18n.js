// Couverture de la traduction : l'interface est parcourue en ANGLAIS ; tout texte visible resté en français (hors contenu des réunions) est signalé.
// Vérifie aussi le français (rien ne change), la bascule FR | EN, la langue par défaut selon le navigateur.
// Prérequis : python tests/e2e/run_stub.py puis node tests/e2e/i18n.js
const { chromium } = require('playwright');
const B = process.env.BASE_URL || 'http://127.0.0.1:8765';
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
let fails = 0; const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) fails++; };
const FR = /[àâçéèêëîïôûùüÿœ]|\b(le|la|les|des|une|vous|votre|pour|avec|dans|sur|aucun|aucune|réunion|enregistr\w*|fichier|texte|lien|pièce|jointe\w*|supprimer|retour|ajouter|choisissez|collez|erreur|tout|cette|cet|sont|n'|l')\b/i;
// textes d'interface restés en français : on collecte les nœuds texte visibles hors contenu utilisateur
const collect = () => {
  const skip = 'script,style,textarea,input,code,pre,.doc:not(.sample),[data-notr],.slides,option[value=""]';
  const out = []; const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n; (n = w.nextNode());) { const t = n.nodeValue.trim(); const e = n.parentElement; if (t && e && !e.closest(skip) && e.offsetParent !== null) out.push(t); }
  document.querySelectorAll('[placeholder],[aria-label],[title]').forEach(e => { if (e.closest('[data-notr]')) return; for (const a of ['placeholder', 'aria-label', 'title']) { const v = e.getAttribute(a); if (v) out.push(a + ':' + v); } });
  return out;
};
(async () => {
  const r = await fetch(B + '/api/meetings/text', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: 'Alice : budget validé. Bob : contrat vendredi.', title: 'Comité de pilotage', meeting_date: '2026-11-04', location: 'Teams', participants: '', context: '', language: 'fr', attachment_ids: [] }) });
  const { id } = await r.json();
  for (let i = 0; i < 60; i++) { if ((await (await fetch(B + '/api/meetings/' + id)).json()).status === 'done') break; await sleep(500); }
  const b = await chromium.launch({ args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] });

  // --- langue par défaut selon le navigateur
  for (const [loc, want] of [['fr-FR', 'fr'], ['en-US', 'en'], ['de-DE', 'en']]) {
    const c = await b.newContext({ locale: loc }); const p = await c.newPage(); await p.goto(B + '/'); await p.waitForSelector('.rec-btn');
    ok(await p.evaluate(() => document.documentElement.lang) === want, `navigateur ${loc} → interface ${want}`); await c.close();
  }

  // --- français : rien ne change
  { const c = await b.newContext({ locale: 'fr-FR' }); const p = await c.newPage(); await p.goto(B + '/'); await p.waitForSelector('.rec-btn');
    ok((await p.innerText('main')).includes('Nouvelle réunion'), 'FR : « Nouvelle réunion » inchangé'); await c.close(); }

  // --- anglais : parcours des écrans
  const c = await b.newContext({ locale: 'en-US', viewport: { width: 420, height: 900 }, permissions: ['microphone'] }); const p = await c.newPage(); const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto(B + '/'); await p.waitForSelector('.rec-btn');
  const residue = new Map(); const scan = async (where) => { for (const t of await p.evaluate(collect)) if (FR.test(t) && !/^Comité de pilotage/.test(t)) residue.set(t, where); /* titre = contenu de la réunion */ };
  await scan('accueil'); ok((await p.innerText('main')).includes('New meeting'), 'EN : « New meeting » affiché');
  for (const tab of ['🔗 Video link', '📁 File', '📝 Text', '🎙 Record']) { await p.getByRole('tab', { name: tab }).click().catch(() => {}); await sleep(250); await scan('accueil/' + tab); }
  await p.selectOption('select >> nth=1', { index: 0 }).catch(() => {}); await scan('accueil/audio');
  await p.goto(B + '/#/m/' + id); await p.waitForSelector('[role=tab]', { timeout: 20000 }); await sleep(500); await scan('réunion');
  for (const tab of await p.locator('[role=tab]').allTextContents()) { await p.locator('[role=tab]').filter({ hasText: tab }).first().click(); await sleep(600); await scan('réunion/' + tab); }
  await p.goto(B + '/#/brand'); await sleep(900); await scan('gabarit');
  await p.goto(B + '/'); await sleep(500);
  await p.click('.rec-btn'); await p.waitForSelector('text=Finish and generate'); await sleep(900); await scan('enregistrement');
  await p.click('text=Pause'); await sleep(400); await scan('pause'); await p.click('text=Resume'); await sleep(300);
  await p.evaluate(() => { live.micTrack.dispatchEvent(new Event('mute')); }); await sleep(300); await scan('appel'); await p.evaluate(() => { live.micTrack.dispatchEvent(new Event('unmute')); }); await sleep(2200); await scan('reprise');
  await p.click('text=Mark'); await sleep(200); await scan('repère');
  await p.click('text=Finish and generate'); await p.waitForSelector('[role=tab]', { timeout: 40000 }).catch(async () => { console.log('ÉTAT FINAL :', JSON.stringify((await p.innerText('main')).slice(0, 400)), await p.evaluate(() => location.hash), JSON.stringify(errs)); throw new Error('fin d\'enregistrement'); }); await sleep(500);
  await p.evaluate(() => { try { toast("Réunion introuvable"); } catch {} }); await sleep(200); await scan('toast');
  for (const [t, where] of residue) console.log('  FRANÇAIS RÉSIDUEL [' + where + '] ' + JSON.stringify(t.slice(0, 120)));
  ok(residue.size === 0, `anglais : aucun texte d'interface resté en français (${residue.size} trouvé(s))`);
  ok(await p.evaluate(() => GM_T('Supprimer « x » ?') === 'Delete “x”?'), 'motifs : texte à valeurs traduit');
  // le contenu de la réunion n'est jamais traduit
  await p.goto(B + '/#/m/' + id); await p.waitForSelector('[role=tab]'); await p.locator('[role=tab]').first().click(); await p.waitForSelector('.doc'); await sleep(400);
  ok((await p.innerText('.doc')).includes('PROCÈS-VERBAL DE RÉUNION'), 'le compte rendu (contenu) reste tel que généré');
  // langue du rapport : créée depuis l'interface anglaise, la réunion produit des documents en anglais ; depuis l'interface française, en français
  for (const [loc, tabName, btn, want, other] of [['en-US', '📝 Text', 'Generate the documents', 'MEETING MINUTES', 'PROCÈS-VERBAL'], ['fr-FR', '📝 Texte', 'Générer les documents', 'PROCÈS-VERBAL DE RÉUNION', 'MEETING MINUTES']]) {
    const c2 = await b.newContext({ locale: loc }); const q = await c2.newPage(); await q.goto(B + '/'); await q.waitForSelector('.rec-btn');
    await q.getByRole('tab', { name: tabName }).click(); await q.fill('textarea >> visible=true', 'Alice: budget approved. Bob: contract by Friday.');
    await q.getByRole('button', { name: btn }).click(); await q.waitForSelector('[role=tab]', { timeout: 30000 });
    await q.locator('[role=tab]').first().click(); await q.waitForSelector('.doc', { timeout: 30000 }); const doc = await q.innerText('.doc');
    ok(doc.includes(want) && !doc.includes(other), `${loc} : documents créés dans la langue de l'interface (${want})`); await c2.close();
  }
  // bascule
  await p.click('#gm-lang button[lang=fr]'); await p.waitForSelector('[role=tab]'); await sleep(500);
  ok(await p.evaluate(() => document.documentElement.lang) === 'fr', 'bascule EN → FR');
  ok(errs.length === 0, 'aucune erreur JavaScript' + (errs[0] ? ' : ' + errs[0] : ''));
  await b.close(); console.log(fails ? fails + ' ÉCHEC(S)' : 'INTERFACE BILINGUE OK'); process.exit(fails ? 1 : 0);
})();

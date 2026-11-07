// Profils de qualité audio : le débit demandé est appliqué (mono) et le poids brut envoyé reste très inférieur au défaut du navigateur.
// Prérequis : python tests/e2e/run_stub.py  puis  node tests/e2e/audio.js
const { chromium } = require('playwright'); const B = process.env.BASE_URL || 'http://127.0.0.1:8765';
const sleep = ms => new Promise(r => setTimeout(r, ms)); let fails = 0;
const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) fails++; };
(async () => {
  const b = await chromium.launch({ args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] });
  const ctx = await b.newContext({ locale: 'fr-FR', permissions: ['microphone'] }); const p = await ctx.newPage();
  await p.goto(B + '/'); await p.waitForSelector('.rec-btn');
  const base = await p.evaluate(async () => { const s = await navigator.mediaDevices.getUserMedia({ audio: true }); const r = new MediaRecorder(s); let n = 0;
    r.ondataavailable = e => n += e.data.size; r.start(1000); await new Promise(x => setTimeout(x, 6000)); r.stop(); await new Promise(x => setTimeout(x, 300)); s.getTracks().forEach(t => t.stop()); return n; });
  const baseKbps = base * 8 / 6 / 1000; console.log(`défaut navigateur : ${baseKbps.toFixed(0)} kbps`);
  const want = { eco: 24, equilibre: 32, haute: 64 }; const got = {};
  for (const prof of Object.keys(want)) {
    await p.goto(B + '/'); await p.waitForSelector('.rec-btn'); await p.selectOption('#rec-quality', prof);
    await p.click('.rec-btn'); await p.waitForSelector('text=Terminer et générer'); await sleep(6500);
    const i = await p.evaluate(() => ({ bps: live.rec.audioBitsPerSecond, ch: live.dest.channelCount, id: live.id }));
    await p.evaluate(() => GRec.flush(live.id)); const m = await (await fetch(B + '/api/meetings/' + i.id)).json();
    const kbps = m.rec_info.bytes * 8 / 6.5 / 1000; got[prof] = kbps;
    ok(i.bps === want[prof] * 1000 && i.ch === 1, `${prof} : ${want[prof]} kbps demandés, mono`);
    ok(kbps > want[prof] * 0.5 && kbps < want[prof] * 1.2, `${prof} : débit réel ${kbps.toFixed(0)} kbps proche de la cible`);
    await p.evaluate(() => live.cancel());
  }
  ok(got.equilibre < baseKbps * 0.4, `Équilibré = ${(100 - got.equilibre / baseKbps * 100).toFixed(0)} % de données en moins que le défaut du navigateur`);
  ok(got.eco < got.equilibre && got.equilibre < got.haute, 'les trois profils sont ordonnés');
  ok(await p.evaluate(() => localStorage.getItem('gm_audio_profile')) === 'haute', 'le dernier choix est mémorisé');
  await b.close(); console.log(fails ? `\n${fails} ÉCHEC(S)` : '\nTOUS LES CONTRÔLES PASSENT'); process.exit(fails ? 1 : 0);
})().catch(e => { console.error('CRASH', e); process.exit(2); });

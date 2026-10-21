import { load, esc, setTitle, hashParams, setHashParams, info, statTile, seg, wireSeg, nf } from '../lib.js';

const fmtMd = v => `${(v / 1e9).toLocaleString('fr-FR', { maximumFractionDigits: v >= 1e10 ? 0 : 1 })} Md€`;
const fmtPct = v => `${v.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} %`;
const sign = v => (v > 0 ? '+' : '') + v.toLocaleString('fr-FR', { maximumFractionDigits: 0 }) + ' %';

function shade(hex, i) {
  // Variantes d'une même couleur de domaine pour distinguer ses missions
  if (!i) return hex;
  const mix = [0, 35, -25, 55, -40, 70][i % 6];
  return mix > 0 ? `color-mix(in srgb, ${hex} ${100 - mix}%, #ffffff)` : `color-mix(in srgb, ${hex} ${100 + mix}%, #000000)`;
}

function niceTicks(max, n = 5) {
  if (max <= 0) return [0];
  const raw = max / n;
  const p = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map(m => m * p).find(s => s >= raw);
  const out = [];
  for (let v = 0; v <= max + step * 0.001; v += step) out.push(v);
  if (out[out.length - 1] < max) out.push(out[out.length - 1] + step);
  return out;
}

export async function render(el) {
  setTitle('Budget de l’État');
  let B;
  try { B = await load('budget'); } catch (e) {
    el.innerHTML = '<div class="page"><div class="page-head"><h1>Budget de l’État</h1></div><div class="empty">Les données budgétaires ne sont pas disponibles pour le moment.</div></div>';
    return;
  }
  const years = B.annees;
  const ref = B.ipcReference;
  const last = years[years.length - 1];
  const p = hashParams();
  const st = {
    niveau: p.niveau === 'missions' ? 'missions' : 'domaines',
    mesure: p.mesure === 'part' ? 'part' : 'montant',
    euros: p.euros === 'constants' ? 'constants' : 'courants',
    forme: p.forme === 'empile' ? 'empile' : 'courbes',
    annee: years.includes(+p.annee) ? +p.annee : last,
    sel: { domaines: null, missions: null },
  };

  // Séries avec couleur fixe (la couleur suit l'entité, jamais son rang)
  const domColor = Object.fromEntries(B.domaines.map(d => [d.key, d.couleur]));
  const counter = {};
  const series = {
    domaines: B.domaines.map(d => ({ key: d.key, label: d.label, color: d.couleur, values: d.values })),
    missions: B.missions.map(m => {
      const i = counter[m.domaine] = (counter[m.domaine] ?? -1) + 1;
      return { key: m.key, label: m.label, color: shade(domColor[m.domaine] || '#94a3b8', i), values: m.values, anciens: m.anciens, domaine: m.domaine };
    }),
  };
  st.sel.domaines = new Set(p.sel && st.niveau === 'domaines' ? p.sel.split(',') : series.domaines.slice(0, 7).map(s => s.key));
  st.sel.missions = new Set(p.sel && st.niveau === 'missions' ? p.sel.split(',') : series.missions.slice(0, 8).map(s => s.key));

  const value = (s, y) => {
    let v = s.values[String(y)] || 0;
    if (st.euros === 'constants' && B.ipc[String(y)]) v *= B.ipc[String(ref)] / B.ipc[String(y)];
    if (st.mesure === 'part') v = (100 * (s.values[String(y)] || 0)) / B.total[String(y)];
    return v;
  };
  const totalReal = y => B.total[String(y)] * (B.ipc[String(ref)] / B.ipc[String(y)]);
  const t0 = B.total[String(years[0])], t1 = B.total[String(last)];
  const growNom = 100 * (t1 / t0 - 1), growReal = 100 * (totalReal(last) / totalReal(years[0]) - 1);
  const domGrowth = series.domaines.map(d => ({ d, g: 100 * ((d.values[String(last)] * B.ipc[String(ref)] / B.ipc[String(last)]) / (d.values[String(years[0])] * B.ipc[String(ref)] / B.ipc[String(years[0])]) - 1) }))
    .filter(x => x.d.values[String(years[0])] > 2e9).sort((a, b) => b.g - a.g);
  const top = series.domaines[0];

  el.innerHTML = `<div class="page">
    <div class="page-head"><h1>Budget de l’État</h1>
      <p class="lead">Les crédits votés chaque année par le Parlement, domaine par domaine, depuis ${years[0]}.</p></div>

    <div class="grid g4">
      ${statTile(fmtMd(t1), `budget ${last} ${info(B.perimetre)}`, B.nature[String(last)] === 'PLF' ? 'projet de loi de finances' : 'loi de finances initiale', null, 'loi')}
      ${statTile(sign(growNom), `depuis ${years[0]}`, `${sign(growReal)} une fois l’inflation déduite`, null, 'an')}
      ${statTile(sign(domGrowth[0].g), `${esc(domGrowth[0].d.label)}`, `plus forte hausse hors inflation depuis ${years[0]}`, null, 'loi')}
      ${statTile(fmtPct((100 * top.values[String(last)]) / t1), `pour ${esc(top.label.toLowerCase())}`, `premier poste du budget en ${last}`, null, 'gouv')}
    </div>

    <section class="panel" style="margin-top:18px">
      <div class="chart-controls">
        <div class="field"><span>Niveau</span>${seg('niveau', [['domaines', 'Grands domaines'], ['missions', 'Missions']], st.niveau)}</div>
        <div class="field"><span>Mesure</span>${seg('mesure', [['montant', 'Montants'], ['part', 'Part du budget']], st.mesure)}</div>
        <div class="field"><span>Inflation</span>${seg('euros', [['courants', 'Euros courants'], ['constants', `Euros de ${ref}`]], st.euros)}</div>
        <div class="field"><span>Graphique</span>${seg('forme', [['courbes', 'Courbes'], ['empile', 'Empilé']], st.forme)}</div>
      </div>
      <div id="b-chart" class="bchart"></div>
      <div id="b-legend" class="blegend"></div>
    </section>

    <section class="panel">
      <header><h2>En <select id="b-year" class="inline-select">${years.slice().reverse().map(y => `<option value="${y}"${y === st.annee ? ' selected' : ''}>${y}</option>`).join('')}</select></h2>
        <span class="muted small" id="b-year-note"></span></header>
      <div id="b-table"></div>
    </section>

    <section class="panel">
      <header><h2>À savoir</h2></header>
      <ul class="small" style="margin:0;padding-left:18px;line-height:1.7">
        <li>${esc(B.perimetre)}</li>
        ${B.notes.map(n => `<li>${esc(n)}</li>`).join('')}
        <li>Euros constants : montants corrigés de l’inflation (indice des prix à la consommation de l’INSEE, moyenne annuelle), exprimés en euros de ${ref}.</li>
      </ul>
      <p class="small muted" style="margin:10px 0 0">Sources : <a href="https://data.economie.gouv.fr" target="_blank" rel="noopener">data.economie.gouv.fr</a> (lois de finances, par année :
        ${B.sources.map(s => `<a href="${esc(s.url)}" target="_blank" rel="noopener">${s.annee}</a>`).join(', ')}) ·
        <a href="https://www.insee.fr/fr/statistiques/serie/001759970" target="_blank" rel="noopener">INSEE, indice des prix</a>.</p>
    </section>
  </div>`;

  const chartBox = el.querySelector('#b-chart');
  const legendBox = el.querySelector('#b-legend');
  const tableBox = el.querySelector('#b-table');

  function save() {
    setHashParams({
      niveau: st.niveau === 'domaines' ? '' : st.niveau, mesure: st.mesure === 'montant' ? '' : st.mesure,
      euros: st.euros === 'courants' ? '' : st.euros, forme: st.forme === 'courbes' ? '' : st.forme,
      annee: st.annee === last ? '' : st.annee,
    });
  }

  function drawChart() {
    const all = series[st.niveau];
    const sel = all.filter(s => st.sel[st.niveau].has(s.key));
    const W = 960, H = 420, m = { l: 64, r: 18, t: 16, b: 34 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const x = i => m.l + (iw * i) / (years.length - 1);
    const stacked = st.forme === 'empile';
    let maxV = 0;
    const stacks = years.map(() => 0);
    const pts = sel.map(s => years.map((y, i) => {
      const v = value(s, y);
      const base = stacked ? stacks[i] : 0;
      if (stacked) stacks[i] += v;
      maxV = Math.max(maxV, base + v);
      return { y, v, base, top: base + v };
    }));
    const ticks = niceTicks(maxV || 1);
    const yMax = ticks[ticks.length - 1];
    const yy = v => m.t + ih - (ih * v) / yMax;
    const unit = st.mesure === 'part' ? '%' : 'Md€';
    const fmt = v => (st.mesure === 'part' ? fmtPct(v) : fmtMd(v));
    const tickLabel = v => (st.mesure === 'part' ? `${v} %` : `${(v / 1e9).toLocaleString('fr-FR')}`);
    const plfIdx = years.map((y, i) => (B.nature[String(y)] === 'PLF' ? i : -1)).filter(i => i >= 0);

    const grid = ticks.map(t => `<line x1="${m.l}" x2="${W - m.r}" y1="${yy(t)}" y2="${yy(t)}" class="bc-grid"/><text x="${m.l - 8}" y="${yy(t) + 4}" text-anchor="end" class="bc-axis">${tickLabel(t)}</text>`).join('');
    const xlab = years.map((y, i) => `<text x="${x(i)}" y="${H - 10}" text-anchor="middle" class="bc-axis${B.nature[String(y)] === 'PLF' ? ' plf' : ''}">${y}</text>`).join('');
    let marks = '';
    if (stacked) {
      marks = pts.map((serie, k) => {
        const top = serie.map((p, i) => `${x(i)},${yy(p.top)}`).join(' ');
        const bot = serie.slice().reverse().map((p, j) => `${x(serie.length - 1 - j)},${yy(p.base)}`).join(' ');
        return `<polygon points="${top} ${bot}" fill="${sel[k].color}" class="bc-area" data-k="${esc(sel[k].key)}"/>`;
      }).join('');
    } else {
      marks = pts.map((serie, k) => {
        const d = serie.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${yy(p.v).toFixed(1)}`).join('');
        const dots = serie.map((p, i) => `<circle cx="${x(i)}" cy="${yy(p.v)}" r="${plfIdx.includes(i) ? 3.5 : 3}" fill="${plfIdx.includes(i) ? 'var(--surface)' : sel[k].color}" stroke="${sel[k].color}" stroke-width="2"/>`).join('');
        return `<g class="bc-line" data-k="${esc(sel[k].key)}"><path d="${d}" fill="none" stroke="${sel[k].color}" stroke-width="2.25" stroke-linejoin="round"/>${dots}</g>`;
      }).join('');
    }
    chartBox.innerHTML = sel.length ? `<svg viewBox="0 0 ${W} ${H}" class="bc" role="img" aria-label="Évolution du budget par ${st.niveau === 'domaines' ? 'domaine' : 'mission'}">
      ${grid}${xlab}<text x="${m.l}" y="${m.t - 4}" class="bc-axis">${unit === '%' ? '% du budget' : st.euros === 'constants' ? `Md€ de ${ref}` : 'Md€'}</text>
      ${marks}<line class="bc-cursor" x1="0" x2="0" y1="${m.t}" y2="${m.t + ih}" style="display:none"/>
      <rect x="${m.l}" y="${m.t}" width="${iw}" height="${ih}" fill="transparent" class="bc-hit"/></svg>
      <div class="bc-tip" hidden></div>` : '<div class="empty">Choisissez au moins une série dans la légende.</div>';
    if (!sel.length) return;

    const svg = chartBox.querySelector('svg');
    const tip = chartBox.querySelector('.bc-tip');
    const cursor = chartBox.querySelector('.bc-cursor');
    const hit = chartBox.querySelector('.bc-hit');
    const show = evt => {
      const r = svg.getBoundingClientRect();
      const px = ((evt.clientX - r.left) / r.width) * W;
      const i = Math.max(0, Math.min(years.length - 1, Math.round(((px - m.l) / iw) * (years.length - 1))));
      cursor.setAttribute('x1', x(i)); cursor.setAttribute('x2', x(i)); cursor.style.display = '';
      const rows = sel.map((s, k) => ({ s, v: pts[k][i].v })).sort((a, b) => b.v - a.v);
      const y = years[i];
      tip.innerHTML = `<b>${y}${B.nature[String(y)] === 'PLF' ? ' <span class="muted">(projet de loi)</span>' : ''}</b>
        ${rows.map(({ s, v }) => `<div><i style="background:${s.color}"></i><span>${esc(s.label)}</span><b>${fmt(v)}</b></div>`).join('')}`;
      tip.hidden = false;
      const left = (x(i) / W) * r.width;
      tip.style.left = `${left > r.width * 0.6 ? left - tip.offsetWidth - 14 : left + 14}px`;
      tip.style.top = `${Math.max(0, ((evt.clientY - r.top) / r.height) * r.height - 40)}px`;
    };
    hit.addEventListener('mousemove', show);
    hit.addEventListener('mouseleave', () => { tip.hidden = true; cursor.style.display = 'none'; });
    hit.addEventListener('click', evt => {
      const r = svg.getBoundingClientRect();
      const i = Math.max(0, Math.min(years.length - 1, Math.round(((((evt.clientX - r.left) / r.width) * W - m.l) / iw) * (years.length - 1))));
      st.annee = years[i]; el.querySelector('#b-year').value = st.annee; drawTable(); save();
    });
  }

  function drawLegend() {
    const all = series[st.niveau];
    const set = st.sel[st.niveau];
    legendBox.innerHTML = `<div class="blegend-actions"><button type="button" class="linkbtn" data-all>Tout afficher</button><button type="button" class="linkbtn" data-none>Tout masquer</button>
      <span class="muted tiny">Cliquez sur une série pour l’afficher ou la masquer · ronds blancs : projet de loi</span></div>
      <div class="blegend-items">${all.map(s => `<button type="button" class="bl-item" aria-pressed="${set.has(s.key)}" data-key="${esc(s.key)}" ${s.anciens?.length ? `data-tip="Anciennement : ${esc(s.anciens.join(' ; '))}"` : ''}><i style="background:${s.color}"></i>${esc(s.label)}</button>`).join('')}</div>`;
  }

  function drawTable() {
    const all = series[st.niveau];
    const y = st.annee, y0 = years[0];
    const prev = years[years.indexOf(y) - 1];
    const defl = yr => (B.ipc[String(ref)] / B.ipc[String(yr)]);
    const rows = all.map(s => {
      const v = s.values[String(y)] || 0;
      const vp = prev ? s.values[String(prev)] || 0 : 0;
      const v0 = s.values[String(y0)] || 0;
      return { s, v, part: (100 * v) / B.total[String(y)], dPrev: vp ? 100 * ((v * defl(y)) / (vp * defl(prev)) - 1) : null, d0: v0 ? 100 * ((v * defl(y)) / (v0 * defl(y0)) - 1) : null };
    }).filter(r => r.v > 0).sort((a, b) => b.v - a.v);
    el.querySelector('#b-year-note').textContent = `${B.nature[String(y)] === 'PLF' ? 'Projet de loi de finances' : 'Loi de finances initiale'} · total ${fmtMd(B.total[String(y)])}`;
    const delta = d => (d == null ? '<span class="muted">–</span>' : `<span class="${d >= 0 ? 'up' : 'down'}">${sign(d)}</span>`);
    tableBox.innerHTML = `<div class="tbl-wrap"><table class="tbl btable">
      <thead><tr><th>${st.niveau === 'domaines' ? 'Domaine' : 'Mission'}</th><th class="n">Crédits</th><th>Part du budget</th><th class="n">Sur un an ${info('Évolution hors inflation par rapport à l’année précédente')}</th><th class="n">Depuis ${y0} ${info('Évolution hors inflation depuis ' + y0)}</th></tr></thead>
      <tbody>${rows.map(r => `<tr><td><span class="ent"><i style="background:${r.s.color}"></i>${esc(r.s.label)}</span></td><td class="n">${fmtMd(r.v)}</td>
        <td><span class="mini-bar" style="width:120px"><span style="width:${Math.min(100, r.part * 4)}%;background:${r.s.color}"></span></span> ${fmtPct(r.part)}</td>
        <td class="n">${delta(r.dPrev)}</td><td class="n">${delta(r.d0)}</td></tr>`).join('')}</tbody></table></div>`;
  }

  const redraw = () => { drawLegend(); drawChart(); drawTable(); save(); };
  wireSeg(el, 'niveau', v => { st.niveau = v; redraw(); });
  wireSeg(el, 'mesure', v => { st.mesure = v; drawChart(); save(); });
  wireSeg(el, 'euros', v => { st.euros = v; drawChart(); save(); });
  wireSeg(el, 'forme', v => { st.forme = v; drawChart(); save(); });
  legendBox.addEventListener('click', e => {
    const set = st.sel[st.niveau];
    if (e.target.closest('[data-all]')) series[st.niveau].forEach(s => set.add(s.key));
    else if (e.target.closest('[data-none]')) set.clear();
    else {
      const b = e.target.closest('.bl-item');
      if (!b) return;
      if (set.has(b.dataset.key)) set.delete(b.dataset.key); else set.add(b.dataset.key);
    }
    drawLegend(); drawChart();
  });
  el.querySelector('#b-year').addEventListener('change', e => { st.annee = +e.target.value; drawTable(); save(); });
  redraw();
}

import {
  ctx, deputes, scrutinsIndex, dossiersIndex, load, esc, nf, pct, fdate, norm, debounce, setTitle, hashParams, setHashParams,
  info, avatar, KIND, plural, tabsHtml, wireTabs, THEME_COLOR,
} from '../lib.js';

const POSL = { p: 'Pour', c: 'Contre', a: 'Abstention' };
const POSC = { p: 'var(--pour)', c: 'var(--contre)', a: 'var(--abst)' };
const KINDS = [['finaux', 'Votes sur l’ensemble d’un texte'], ['tous', 'Tous les votes'], ['amendements', 'Amendements et articles']];

function inScope(s, kind) {
  if (s.kind === 'censure' || s.kind === 'declaration') return false;
  if (kind === 'finaux') return s.kind === 'ensemble';
  if (kind === 'amendements') return s.kind === 'amendement' || s.kind === 'article';
  return true;
}
function tally(pos, idxs) {
  let p = 0, c = 0, a = 0;
  for (const i of idxs) { const x = pos[i]; if (x === 'p') p++; else if (x === 'c') c++; else if (x === 'a') a++; }
  return { p, c, a, n: p + c + a };
}
function agreement(pa, pb, idxs) {
  let same = 0, tot = 0;
  for (const i of idxs) {
    const x = pa[i], y = pb[i];
    if ((x === 'p' || x === 'c' || x === 'a') && (y === 'p' || y === 'c' || y === 'a')) { tot++; if (x === y) same++; }
  }
  return tot >= 3 ? { v: (100 * same) / tot, n: tot } : null;
}
const chipOf = e => `<span class="ent"><i style="background:${e.color}"></i>${esc(e.label)}</span>`;

// ─────────────────────────────────────────── Carte des proximités
/** Positionne les entités dans le plan : proches si elles votent souvent pareil (MDS classique). */
function mds(D) {
  const n = D.length;
  if (n < 2) return D.map(() => [0, 0]);
  const D2 = D.map(r => r.map(x => x * x));
  const rowM = D2.map(r => r.reduce((a, b) => a + b, 0) / n);
  const allM = rowM.reduce((a, b) => a + b, 0) / n;
  const B = D2.map((r, i) => r.map((x, j) => -0.5 * (x - rowM[i] - rowM[j] + allM)));
  const eig = deflate => {
    let v = Array.from({ length: n }, (_, i) => Math.sin(i + 1) + 0.5);
    let lambda = 0;
    for (let it = 0; it < 200; it++) {
      let w = B.map(r => r.reduce((s, x, j) => s + x * v[j], 0));
      if (deflate) { const d = deflate.v.reduce((s, x, j) => s + x * w[j], 0); w = w.map((x, j) => x - d * deflate.v[j]); }
      const norm_ = Math.hypot(...w) || 1;
      lambda = norm_;
      v = w.map(x => x / norm_);
    }
    return { v, lambda };
  };
  const e1 = eig(), e2 = eig(e1);
  return e1.v.map((x, i) => [x * Math.sqrt(e1.lambda), e2.v[i] * Math.sqrt(e2.lambda)]);
}

function proximityMap(ents, idx, refKey) {
  const n = ents.length;
  const ag = ents.map(a => ents.map(b => (a === b ? { v: 100 } : agreement(a.pos, b.pos, idx))));
  const known = ag.flat().filter(Boolean).map(x => x.v);
  const mean = known.reduce((s, x) => s + x, 0) / (known.length || 1);
  const D = ag.map(r => r.map(x => 1 - (x ? x.v : mean) / 100));
  let P = mds(D);
  // Orientation : la gauche de l'hémicycle à gauche
  const ord = ents.map(e => e.ordre ?? 50);
  const mo = ord.reduce((s, x) => s + x, 0) / n, mx = P.reduce((s, p) => s + p[0], 0) / n;
  if (P.reduce((s, p, i) => s + (p[0] - mx) * (ord[i] - mo), 0) < 0) P = P.map(([x, y]) => [-x, y]);
  // Mise à l'échelle (même échelle sur les deux axes)
  const W = 680, H = 460, pad = 60;
  const xs = P.map(p => p[0]), ys = P.map(p => p[1]);
  const span = Math.max(Math.max(...xs) - Math.min(...xs), (Math.max(...ys) - Math.min(...ys)) * (W - 2 * pad) / (H - 2 * pad), 1e-6);
  const k = (W - 2 * pad) / span;
  const cx = (Math.max(...xs) + Math.min(...xs)) / 2, cy = (Math.max(...ys) + Math.min(...ys)) / 2;
  const maxSeats = Math.max(...ents.map(e => e.seats || 1));
  const nodes = ents.map((e, i) => ({
    e, i, x: W / 2 + (P[i][0] - cx) * k, y: H / 2 + (P[i][1] - cy) * k,
    r: e.seats ? 9 + 22 * Math.sqrt(e.seats / maxSeats) : 8,
  }));
  // Évite que les bulles se chevauchent
  for (let it = 0; it < 200; it++) {
    for (const a of nodes) for (const b of nodes) {
      if (a === b) continue;
      const dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || 0.01, min = a.r + b.r + 22;
      if (d < min) { const m = (min - d) / 2; a.x -= (dx / d) * m; a.y -= (dy / d) * m; b.x += (dx / d) * m; b.y += (dy / d) * m; }
    }
    for (const a of nodes) { a.x = Math.max(a.r + 4, Math.min(W - a.r - 4, a.x)); a.y = Math.max(a.r + 16, Math.min(H - a.r - 4, a.y)); }
  }
  // Étiquettes : au-dessus, en dessous, à droite ou à gauche, là où elles ne cachent rien
  const boxes = nodes.map(nd => ({ x: nd.x - nd.r, y: nd.y - nd.r, w: 2 * nd.r, h: 2 * nd.r }));
  const hit = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
  for (const nd of [...nodes].sort((a, b) => b.r - a.r)) {
    const w = nd.e.label.length * 7.6 + 6, h = 15;
    const cands = [[nd.x - w / 2, nd.y - nd.r - h - 3, 'middle'], [nd.x - w / 2, nd.y + nd.r + 3, 'middle'],
      [nd.x + nd.r + 4, nd.y - h / 2, 'start'], [nd.x - nd.r - 4 - w, nd.y - h / 2, 'end']];
    let pick = cands[0];
    for (const cnd of cands) {
      const b = { x: cnd[0], y: cnd[1], w, h };
      if (b.x < 0 || b.x + w > W || b.y < 0 || b.y + h > H) continue;
      if (!boxes.some(o => hit(o, b))) { pick = cnd; break; }
    }
    boxes.push({ x: pick[0], y: pick[1], w, h });
    nd.lx = pick[2] === 'middle' ? pick[0] + w / 2 : pick[2] === 'start' ? pick[0] : pick[0] + w;
    nd.ly = pick[1] + 12; nd.la = pick[2];
  }
  const ref = nodes.find(nd => nd.e.key === refKey);
  const edges = [];
  for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
    const v = ag[i][j]?.v;
    if (v == null) continue;
    const touchesRef = ref && (i === ref.i || j === ref.i);
    if (v < 70 && !touchesRef) continue;
    edges.push({ a: nodes[i], b: nodes[j], v, touchesRef });
  }
  const line = ({ a, b, v, touchesRef }) => {
    const t = Math.max(0, (v - 40) / 60);
    return `<line x1="${a.x.toFixed(1)}" y1="${a.y.toFixed(1)}" x2="${b.x.toFixed(1)}" y2="${b.y.toFixed(1)}" class="pm-edge${touchesRef ? ' ref' : ''}"
      style="stroke-width:${(1 + t * 6).toFixed(1)};opacity:${touchesRef ? 0.25 + t * 0.6 : 0.12 + t * 0.35}"/>`;
  };
  const node = nd => {
    const others = nodes.filter(o => o !== nd && ag[nd.i][o.i]).sort((x, y) => ag[nd.i][y.i].v - ag[nd.i][x.i].v);
    const tip = `${nd.e.long} — vote le plus souvent comme ${others.slice(0, 3).map(o => `${o.e.label} (${Math.round(ag[nd.i][o.i].v)} %)`).join(', ')}`;
    return `<g class="pm-node${ref && nd === ref ? ' on' : ''}" data-ref="${esc(nd.e.key)}" data-tip="${esc(tip)}" tabindex="0" role="button" aria-label="${esc(nd.e.long)}">
      <circle cx="${nd.x.toFixed(1)}" cy="${nd.y.toFixed(1)}" r="${nd.r.toFixed(1)}" fill="${esc(nd.e.color)}"/>
      <text x="${nd.lx.toFixed(1)}" y="${nd.ly.toFixed(1)}" text-anchor="${nd.la}">${esc(nd.e.label)}</text></g>`;
  };
  return `<svg class="pmap" viewBox="0 0 ${W} ${H}" role="img" aria-label="Carte des proximités de vote">
    ${edges.filter(x => !x.touchesRef).map(line).join('')}${edges.filter(x => x.touchesRef).map(line).join('')}
    ${nodes.map(node).join('')}</svg>`;
}

// ─────────────────────────────────────────── Tableau à double entrée des accords
function agreeMatrix(ents, idx, refKey) {
  if (ents.length < 2) return '<p class="muted small">Sélectionnez au moins deux groupes ou députés.</p>';
  const color = v => {
    const t = Math.max(0, Math.min(1, (v - 40) / 60)) ** 1.6;  // accentue les écarts entre 60 % et 100 %
    return `background:color-mix(in srgb, var(--cmp) ${Math.round(4 + t * 86)}%, var(--surface));color:${t > 0.45 ? '#fff' : 'var(--ink)'}`;
  };
  const head = e => `<th scope="col" class="mx-col${e.key === refKey ? ' on' : ''}" style="--gc:${esc(e.color)}" data-tip="${esc(e.long)}"><span>${esc(e.label)}</span></th>`;
  return `<div class="mx-wrap"><table class="mx">
    <thead><tr><th class="mx-corner"></th>${ents.map(head).join('')}</tr></thead>
    <tbody>${ents.map(a => `<tr class="${a.key === refKey ? 'on' : ''}"><th scope="row"><button type="button" class="mx-row" data-ref="${esc(a.key)}" style="--gc:${esc(a.color)}">${esc(a.label)}</button></th>${ents.map(b => {
      if (a.key === b.key) return '<td class="mx-self"></td>';
      const ag = agreement(a.pos, b.pos, idx);
      if (!ag) return '<td><span class="mx-cell empty" data-tip="Pas assez de votes en commun">·</span></td>';
      return `<td><span class="mx-cell" style="${color(ag.v)}" data-tip="${esc(a.long)} et ${esc(b.long)} : même position dans ${Math.round(ag.v)} % des ${nf(ag.n)} votes comparés">${Math.round(ag.v)}</span></td>`;
    }).join('')}</tr>`).join('')}</tbody></table></div>
    <div class="mx-legend"><span>40 % ou moins</span><i></i><span>100 % : votent toujours pareil</span></div>`;
}

// ─────────────────────────────────────────── Positions par thème : diagramme en points
function dotPlot(ents, cols, current) {
  const rows = cols.map(([k, t, ix]) => {
    const dots = ents.map(e => ({ e, r: tally(e.pos, ix) })).filter(x => x.r.n >= 2)
      .map(x => ({ ...x, v: (100 * x.r.p) / x.r.n })).sort((a, b) => a.v - b.v);
    // Étage les points trop proches pour qu'aucun ne soit caché
    const lanes = [0, -1, 1, -2, 2], last = {};
    for (const dt of dots) {
      dt.lane = lanes.find(l => last[l] == null || dt.v - last[l] > 2.4) ?? 0;
      last[dt.lane] = dt.v;
    }
    return { k, t, ix, dots };
  }).filter(r => r.dots.length);
  if (!rows.length) return '<div class="empty">Pas assez de votes par thème avec ces filtres.</div>';
  return `<div class="dotplot">
    <div class="dp-axis"><span></span><div class="dp-scale"><span>vote surtout contre</span><span>50 %</span><span>vote surtout pour</span></div></div>
    ${rows.map(({ k, t, ix, dots }) => `<button type="button" class="dp-row${k === current ? ' on' : ''}" data-t="${k}">
      <span class="dp-label"><i style="background:${THEME_COLOR[k] || '#94a3b8'}"></i>${esc(t.label)}<small>${nf(ix.length)}</small></span>
      <span class="dp-track">${dots.map(({ e, r, v, lane }) => `<span class="dp-dot" style="left:${v.toFixed(1)}%;top:calc(50% + ${lane * 13}px);background:${esc(e.color)}" data-tip="${esc(e.long)} · ${esc(t.label)} : ${Math.round(v)} % pour (${r.p} pour, ${r.c} contre, ${r.a} abst.)"></span>`).join('')}</span>
    </button>`).join('')}
  </div>`;
}

export async function render(el) {
  setTitle('Comparer les votes');
  const [c, deps, scr, dos] = await Promise.all([ctx(), deputes(), scrutinsIndex(), dossiersIndex()]);
  const p = hashParams();
  const st = {
    theme: p.theme || '',
    q: p.q || '',
    kind: KINDS.some(([k]) => k === p.k) ? p.k : 'finaux',
    groups: p.g === 'aucun' ? [] : p.g ? p.g.split(',').filter(id => c.groupes.has(id)) : c.an.map(g => g.id),
    deps: p.d ? p.d.split(',').filter(id => deps._index.has(id)) : [],
    divise: p.divise === '1',
    tab: ['alliances', 'sujets', 'votes'].includes(p.tab) ? p.tab : 'alliances',
    ref: p.ref || '',
  };
  const chrono = scr.chrono;
  const themeOf = chrono.map(s => (s.dossier && dos._index.get(s.dossier)?.theme) || null);
  const textOf = chrono.map(s => norm(`${s.titre} ${(s.dossier && dos._index.get(s.dossier)?.titre) || ''}`));
  const depVotes = new Map();
  const themes = Object.entries(dos.themes).filter(([k]) => k !== 'autre').sort((a, b) => a[1].label.localeCompare(b[1].label, 'fr'));
  const depLabel = new Map(deps.filter(d => d.actif).map(d => [`${d.prenom} ${d.nom} — ${c.groupes.get(d.groupe)?.sigle || ''}, ${d.departement || ''}`, d.id]));

  el.innerHTML = `<div class="page">
    <div class="page-head"><h1>Comparer les votes</h1>
      <p class="lead">Qui vote avec qui, et comment chaque groupe se positionne selon les sujets.</p></div>

    <div class="toolbar">
      <label class="field"><span>Sujet</span>
        <select id="c-theme"><option value="">Tous les sujets</option>${themes.map(([k, t]) => `<option value="${k}"${k === st.theme ? ' selected' : ''}>${esc(t.label)}</option>`).join('')}</select></label>
      <label class="field grow"><span>Mot-clé</span><input type="search" id="c-q" placeholder="retraites, police, logement…" value="${esc(st.q)}"></label>
      <label class="field"><span>Votes ${info('Par défaut, seuls les votes sur l’ensemble d’un texte sont comparés : ce sont eux qui montrent si un groupe soutient une loi. Les amendements, très nombreux, sont souvent techniques.')}</span>
        <select id="c-kind">${KINDS.map(([k, l]) => `<option value="${k}"${k === st.kind ? ' selected' : ''}>${l}</option>`).join('')}</select></label>
      <details class="dd field" id="c-gdd"><summary><span>Groupes</span><b id="c-gsum"></b></summary>
        <div class="dd-panel">
          <div class="dd-actions"><button type="button" class="linkbtn" id="c-all">Tout cocher</button><button type="button" class="linkbtn" id="c-none">Tout décocher</button></div>
          ${c.an.map(g => `<label class="dd-item"><input type="checkbox" value="${g.id}"${st.groups.includes(g.id) ? ' checked' : ''}><i style="background:${g.couleur}"></i><b>${esc(g.sigle)}</b><span>${esc(g.nom)}</span></label>`).join('')}
        </div>
      </details>
      <label class="field"><span>Ajouter un député</span><input type="search" id="c-dep" list="c-deplist" placeholder="Nom…"></label>
      <datalist id="c-deplist">${[...depLabel.keys()].map(k => `<option value="${esc(k)}"></option>`).join('')}</datalist>
    </div>
    <div class="pill-row" id="c-deps" style="margin:-6px 0 14px"></div>

    <div id="c-out"></div>
  </div>`;

  async function entities() {
    const out = st.groups.map(id => {
      const g = c.groupes.get(id);
      return { key: id, label: g.sigle, long: g.nom, color: g.couleur, pos: c.gdata.positions[id] || '', seats: g.effectif, ordre: g.ordre };
    });
    for (const id of st.deps) {
      if (!depVotes.has(id)) {
        try { depVotes.set(id, (await load(`votes/${id}`)).v); } catch (e) { depVotes.set(id, ''); }
      }
      const d = deps._index.get(id);
      const g = c.groupes.get(d.groupe);
      out.push({ key: id, label: `${d.prenom[0]}. ${d.nom}`, long: `${d.prenom} ${d.nom} (${g?.sigle || ''})`, color: g?.couleur || '#888', pos: depVotes.get(id), ordre: g?.ordre, dep: true });
    }
    return out;
  }
  const scope = (theme, words) => {
    const idx = [];
    for (let i = 0; i < chrono.length; i++) {
      if (!inScope(chrono[i], st.kind)) continue;
      if (theme && themeOf[i] !== theme) continue;
      if (words.length && !words.every(w => textOf[i].includes(w))) continue;
      idx.push(i);
    }
    return idx;
  };

  async function draw() {
    const allGroups = st.groups.length === c.an.length;
    setHashParams({
      theme: st.theme, q: st.q, k: st.kind === 'finaux' ? '' : st.kind,
      g: allGroups ? '' : st.groups.length ? st.groups.join(',') : 'aucun',
      d: st.deps.join(','), divise: st.divise ? '1' : '', tab: st.tab === 'alliances' ? '' : st.tab, ref: st.ref,
    });
    el.querySelector('#c-gsum').textContent = allGroups ? 'Tous' : st.groups.length ? `${st.groups.length} sélectionné${st.groups.length > 1 ? 's' : ''}` : 'Aucun';
    el.querySelector('#c-deps').innerHTML = st.deps.map(id => {
      const d = deps._index.get(id);
      return `<span class="tag">${avatar(d, 'AN', c.groupes.get(d.groupe), 'sm')}${esc(d.prenom)} ${esc(d.nom)}<button type="button" data-rm="${id}" aria-label="Retirer ${esc(d.nom)}">×</button></span>`;
    }).join('');

    const ents = await entities();
    const out = el.querySelector('#c-out');
    if (!ents.length) { out.innerHTML = '<div class="empty">Sélectionnez au moins un groupe ou un député.</div>'; return; }
    const words = norm(st.q).split(/\s+/).filter(w => w.length > 1);
    const idx = scope(st.theme, words);
    const subj = words.length ? `« ${esc(st.q)} »` : st.theme ? esc(dos.themes[st.theme].label.toLowerCase()) : 'tous les sujets';
    if (!ents.some(e => e.key === st.ref)) st.ref = (ents.find(e => e.dep) || [...ents].sort((a, b) => (b.seats || 0) - (a.seats || 0))[0]).key;
    const ref = ents.find(e => e.key === st.ref);
    const kindLabel = { finaux: 'votes sur l’ensemble d’un texte', tous: 'votes', amendements: 'votes d’amendements et d’articles' }[st.kind];

    // Classement des alliés du groupe (ou député) de référence
    const others = ents.filter(e => e.key !== ref.key).map(e => ({ e, ag: agreement(ref.pos, e.pos, idx) })).filter(x => x.ag).sort((a, b) => b.ag.v - a.ag.v);
    const refChart = others.length ? others.map(({ e, ag }) => `<button type="button" class="rank-row" data-ref="${esc(e.key)}" data-tip="${esc(ref.long)} et ${esc(e.long)} : même position dans ${pct(ag.v)} des ${nf(ag.n)} votes comparés">
        ${chipOf(e)}<div class="rank-track"><span style="width:${ag.v}%;background:${e.color}"></span><i style="left:50%"></i></div><b>${Math.round(ag.v)} %</b></button>`).join('')
      : '<p class="muted small">Sélectionnez au moins deux groupes ou députés.</p>';
    const pairs = [];
    for (let i = 0; i < ents.length; i++) for (let j = i + 1; j < ents.length; j++) {
      const ag = agreement(ents[i].pos, ents[j].pos, idx);
      if (ag) pairs.push({ a: ents[i], b: ents[j], ...ag });
    }
    pairs.sort((x, y) => y.v - x.v);
    const nTop = Math.min(5, Math.ceil(pairs.length / 2));
    const pairList = list => list.map(x => `<li>${chipOf(x.a)}<span class="muted">et</span>${chipOf(x.b)}<b>${Math.round(x.v)} %</b></li>`).join('');

    const cols = themes.map(([k, t]) => [k, t, scope(k, words)]).filter(([, , ix]) => ix.length >= 3);

    // Vote par vote
    let vidx = [...idx].reverse();
    if (st.divise) vidx = vidx.filter(i => new Set(ents.map(e => e.pos[i]).filter(x => x === 'p' || x === 'c' || x === 'a')).size > 1);

    out.innerHTML = `
      ${tabsHtml('c', [['alliances', 'Qui vote avec qui'], ['sujets', 'Positions par sujet'], ['votes', `Vote par vote · ${nf(vidx.length)}`]], st.tab)}
      <div data-panel-of="c" data-panel="alliances">
        <div class="cmp-grid">
          <section class="panel">
            <header><h2>La carte des proximités</h2><span class="muted small">${nf(idx.length)} ${kindLabel} · ${subj}</span></header>
            ${ents.length >= 3 ? proximityMap(ents, idx, ref.key) : '<p class="muted small">Ajoutez au moins trois groupes ou députés pour dessiner la carte.</p>'}
            <p class="note">Plus deux bulles sont proches, plus ces groupes votent souvent de la même façon. Les traits relient ceux qui votent pareil au moins 7 fois sur 10 ; la taille d’une bulle suit le nombre de députés. Cliquez sur une bulle pour voir ses alliés.</p>
          </section>
          <section class="panel">
            <header><h2>Avec qui vote <select id="c-ref" class="inline-select">${ents.map(e => `<option value="${esc(e.key)}"${e.key === ref.key ? ' selected' : ''}>${esc(e.label)}</option>`).join('')}</select></h2></header>
            <p class="small muted" style="margin:-4px 0 10px">Part des votes où ${esc(ref.long)} et l’autre groupe ont la même position.</p>
            <div class="rank">${refChart}</div>
          </section>
        </div>
        <section class="panel">
          <header><h2>Le tableau des accords</h2>
            <label class="mx-theme"><span class="muted small">Thème</span><select id="c-mx-theme" class="inline-select"><option value="">Tous les sujets</option>${themes.map(([k, t]) => `<option value="${k}"${k === st.theme ? ' selected' : ''}>${esc(t.label)}</option>`).join('')}</select></label></header>
          <p class="small muted" style="margin:-4px 0 12px">Chaque case : la part des ${esc(kindLabel)} où les deux groupes ont eu la même position (pour, contre ou abstention)${st.theme || words.length ? `, sur ${subj}` : ''} · ${nf(idx.length)} votes.</p>
          ${agreeMatrix(ents, idx, ref.key)}
        </section>
        ${pairs.length > 1 ? `<div class="grid g2">
          <section class="panel"><header><h2>Les plus proches</h2></header><ul class="pairs">${pairList(pairs.slice(0, nTop))}</ul></section>
          <section class="panel"><header><h2>Les plus éloignés</h2></header><ul class="pairs">${pairList(pairs.slice(nTop).slice(-5).reverse())}</ul></section>
        </div>` : ''}
      </div>
      <div data-panel-of="c" data-panel="sujets">
        <section class="panel">
          <header><h2>Thème par thème</h2><span class="muted small">chaque point : la part de votes « pour » d’un groupe · cliquez sur un thème pour filtrer</span></header>
          <div class="dp-legend">${ents.map(chipOf).join('')}</div>
          ${dotPlot(ents, cols, st.theme)}
        </section>
      </div>
      <div data-panel-of="c" data-panel="votes">
        <div class="votes-bar"><span class="legend"><span><i style="background:var(--pour)"></i>Pour</span><span><i style="background:var(--contre)"></i>Contre</span><span><i style="background:var(--abst)"></i>Abstention</span></span>
          <label class="check"><input type="checkbox" id="c-div"${st.divise ? ' checked' : ''}> Seulement les votes qui les divisent</label></div>
        <div id="c-grid"></div>
      </div>`;
    wireTabs(out, 'c', k => { st.tab = k; });

    const grid = out.querySelector('#c-grid');
    let shown = 40;
    const drawGrid = () => {
      const slice = vidx.slice(0, shown);
      grid.innerHTML = vidx.length ? `<div class="tbl-wrap"><table class="tbl vgrid">
        <thead><tr><th>Scrutin</th>${ents.map(e => `<th class="c" data-tip="${esc(e.long)}">${chipOf(e)}</th>`).join('')}</tr></thead>
        <tbody>${slice.map(i => {
          const s = chrono[i];
          const th = themeOf[i] && dos.themes[themeOf[i]];
          return `<tr><td class="vt"><a href="vote/${s.num}">${esc(s.titre.length > 120 ? s.titre.slice(0, 118) + '…' : s.titre)}</a>
            <div class="tiny muted">${fdate(s.date, true)} · ${esc(KIND[s.kind] || '')}${th ? ` · ${esc(th.label)}` : ''} · ${s.adopte ? 'adopté' : 'rejeté'}</div></td>
            ${ents.map(e => { const x = e.pos[i]; return `<td class="c">${x === 'p' || x === 'c' || x === 'a' ? `<span class="vdot" style="background:${POSC[x]}" data-tip="${esc(e.label)} : ${POSL[x]}"></span>` : '<span class="vdot none" data-tip="Pas de vote"></span>'}</td>`; }).join('')}</tr>`;
        }).join('')}</tbody></table></div>
        ${vidx.length > shown ? '<div class="more"><button class="btn" id="c-more">Afficher plus</button></div>' : ''}` : '<div class="empty">Aucun vote à afficher.</div>';
      grid.querySelector('#c-more')?.addEventListener('click', () => { shown += 60; drawGrid(); });
    };
    drawGrid();
    out.querySelector('#c-div').addEventListener('change', e => { st.divise = e.target.checked; draw(); });
    out.querySelector('#c-ref')?.addEventListener('change', e => { st.ref = e.target.value; draw(); });
    const pickRef = e => {
      const t = e.target.closest('[data-ref]');
      if (!t || (e.type === 'keydown' && e.key !== 'Enter' && e.key !== ' ')) return;
      e.preventDefault();
      st.ref = t.dataset.ref;
      draw();
    };
    out.querySelector('#c-mx-theme')?.addEventListener('change', e => { st.theme = e.target.value; el.querySelector('#c-theme').value = st.theme; draw(); });
    out.querySelectorAll('.pmap, .rank, .mx').forEach(x => { x.addEventListener('click', pickRef); x.addEventListener('keydown', pickRef); });
    out.querySelectorAll('.dp-row').forEach(b => b.addEventListener('click', () => {
      st.theme = st.theme === b.dataset.t ? '' : b.dataset.t;
      el.querySelector('#c-theme').value = st.theme;
      draw();
    }));
  }

  el.querySelector('#c-theme').addEventListener('change', e => { st.theme = e.target.value; draw(); });
  el.querySelector('#c-kind').addEventListener('change', e => { st.kind = e.target.value; draw(); });
  el.querySelector('#c-q').addEventListener('input', debounce(e => { st.q = e.target.value; draw(); }, 300));
  const gdd = el.querySelector('#c-gdd');
  gdd.addEventListener('change', e => {
    if (e.target.type !== 'checkbox') return;
    st.groups = [...gdd.querySelectorAll('input:checked')].map(x => x.value);
    draw();
  });
  const setAll = on => { gdd.querySelectorAll('input').forEach(x => { x.checked = on; }); st.groups = on ? c.an.map(g => g.id) : []; draw(); };
  el.querySelector('#c-all').addEventListener('click', () => setAll(true));
  el.querySelector('#c-none').addEventListener('click', () => setAll(false));
  const closeDd = e => { if (!document.body.contains(gdd)) document.removeEventListener('click', closeDd); else if (!gdd.contains(e.target)) gdd.open = false; };
  document.addEventListener('click', closeDd);
  el.querySelector('#c-dep').addEventListener('change', e => {
    const id = depLabel.get(e.target.value);
    if (id && !st.deps.includes(id) && st.deps.length < 8) { st.deps.push(id); st.ref = id; draw(); }
    e.target.value = '';
  });
  el.querySelector('#c-deps').addEventListener('click', e => {
    const b = e.target.closest('[data-rm]');
    if (b) { st.deps = st.deps.filter(x => x !== b.dataset.rm); draw(); }
  });
  draw();
}

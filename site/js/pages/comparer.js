import {
  ctx, deputes, scrutinsIndex, dossiersIndex, load, esc, nf, pct, fdate, norm, debounce, setTitle, hashParams, setHashParams,
  info, avatar, KIND, plural, tabsHtml, wireTabs,
} from '../lib.js';

const POSL = { p: 'Pour', c: 'Contre', a: 'Abstention' };
const POSC = { p: 'var(--pour)', c: 'var(--contre)', a: 'var(--abst)' };
const KINDS = [['tous', 'Tous les votes'], ['finaux', 'Votes finaux sur un texte'], ['amendements', 'Amendements et articles']];

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
/** Échelle divergente sobre : rouge (contre) → neutre → vert (pour). */
function divColor(net) {
  const t = Math.round(Math.abs(net) * 70);
  return `color-mix(in srgb, ${net >= 0 ? 'var(--pour)' : 'var(--contre)'} ${t}%, var(--surface-2))`;
}
const chipOf = e => `<span class="ent"><i style="background:${e.color}"></i>${esc(e.label)}</span>`;

export async function render(el) {
  setTitle('Comparer les votes');
  const [c, deps, scr, dos] = await Promise.all([ctx(), deputes(), scrutinsIndex(), dossiersIndex()]);
  const p = hashParams();
  const st = {
    theme: p.theme || '',
    q: p.q || '',
    kind: p.k || 'tous',
    groups: p.g === 'aucun' ? [] : p.g ? p.g.split(',').filter(id => c.groupes.has(id)) : c.an.map(g => g.id),
    deps: p.d ? p.d.split(',').filter(id => deps._index.has(id)) : [],
    divise: p.divise === '1',
    tab: ['sujets', 'alliances', 'votes'].includes(p.tab) ? p.tab : 'sujets',
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
      <p class="lead">Choisissez un sujet, puis les groupes ou les députés à comparer.</p></div>

    <div class="toolbar">
      <label class="field"><span>Sujet</span>
        <select id="c-theme"><option value="">Tous les sujets</option>${themes.map(([k, t]) => `<option value="${k}"${k === st.theme ? ' selected' : ''}>${esc(t.label)}</option>`).join('')}</select></label>
      <label class="field grow"><span>Mot-clé</span><input type="search" id="c-q" placeholder="retraites, police, logement…" value="${esc(st.q)}"></label>
      <label class="field"><span>Votes</span>
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
      return { key: id, label: g.sigle, long: g.nom, color: g.couleur, pos: c.gdata.positions[id] || '' };
    });
    for (const id of st.deps) {
      if (!depVotes.has(id)) {
        try { depVotes.set(id, (await load(`votes/${id}`)).v); } catch (e) { depVotes.set(id, ''); }
      }
      const d = deps._index.get(id);
      const g = c.groupes.get(d.groupe);
      out.push({ key: id, label: `${d.prenom[0]}. ${d.nom}`, long: `${d.prenom} ${d.nom} (${g?.sigle || ''})`, color: g?.couleur || '#888', pos: depVotes.get(id) });
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
      theme: st.theme, q: st.q, k: st.kind === 'tous' ? '' : st.kind,
      g: allGroups ? '' : st.groups.length ? st.groups.join(',') : 'aucun',
      d: st.deps.join(','), divise: st.divise ? '1' : '', tab: st.tab === 'sujets' ? '' : st.tab, ref: st.ref,
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
    if (!ents.some(e => e.key === st.ref)) st.ref = ents[0].key;
    const ref = ents.find(e => e.key === st.ref);

    // Positions sur le sujet : barres divergentes
    const rows = ents.map(e => ({ e, r: tally(e.pos, idx) })).filter(x => x.r.n)
      .sort((a, b) => (b.r.p - b.r.c) / b.r.n - (a.r.p - a.r.c) / a.r.n);
    const diverging = rows.length ? `<div class="div-chart">
      <div class="div-row div-head"><span></span><div class="div-track"><span>Contre</span><span>Pour</span></div><span></span></div>
      ${rows.map(({ e, r }) => {
        const pp = (100 * r.p) / r.n, cc = (100 * r.c) / r.n, aa = (100 * r.a) / r.n;
        return `<div class="div-row" data-tip="${esc(e.long)} : ${r.p} pour, ${r.c} contre, ${r.a} abstentions sur ${r.n} votes">
          ${chipOf(e)}
          <div class="div-track"><div class="half left"><span style="width:${cc}%"></span></div><div class="half right"><span style="width:${pp}%"></span></div></div>
          <span class="div-val"><b>${Math.round(pp)} %</b> pour${aa >= 5 ? ` <span class="muted">· ${Math.round(aa)} % abst.</span>` : ''}</span>
        </div>`;
      }).join('')}</div>` : '<div class="empty">Aucun vote sur ce sujet avec ces filtres.</div>';

    // Vue par thème
    const cols = themes.map(([k, t]) => [k, t, scope(k, [])]).filter(([, , ix]) => ix.length >= 3);
    const heat = `<div class="hm-wrap"><table class="hm"><thead><tr><th></th>${cols.map(([k, t, ix]) => `<th><button type="button" class="hm-col${k === st.theme ? ' on' : ''}" data-t="${k}" data-tip="${esc(t.label)} · ${plural(ix.length, 'vote')}"><span>${esc(t.label)}</span></button></th>`).join('')}</tr></thead>
      <tbody>${ents.map(e => `<tr><th scope="row">${chipOf(e)}</th>${cols.map(([k, t, ix]) => {
        const r = tally(e.pos, ix);
        if (r.n < 2) return '<td><span class="hm-cell empty"></span></td>';
        const net = (r.p - r.c) / r.n;
        return `<td><span class="hm-cell${k === st.theme ? ' on' : ''}" style="background:${divColor(net)}" data-tip="${esc(e.long)} · ${esc(t.label)} : ${r.p} pour, ${r.c} contre, ${r.a} abst.">${Math.round((100 * r.p) / r.n)}</span></td>`;
      }).join('')}</tr>`).join('')}</tbody></table></div>`;

    // Accords
    const others = ents.filter(e => e.key !== ref.key).map(e => ({ e, ag: agreement(ref.pos, e.pos, idx) })).filter(x => x.ag).sort((a, b) => b.ag.v - a.ag.v);
    const refChart = others.length ? others.map(({ e, ag }) => `<div class="rank-row" data-tip="${esc(ref.long)} et ${esc(e.long)} : même position dans ${pct(ag.v)} des ${nf(ag.n)} votes comparés">
        ${chipOf(e)}<div class="rank-track"><span style="width:${ag.v}%;background:${e.color}"></span></div><b>${Math.round(ag.v)} %</b></div>`).join('')
      : '<p class="muted small">Sélectionnez au moins deux groupes ou députés.</p>';
    const pairs = [];
    for (let i = 0; i < ents.length; i++) for (let j = i + 1; j < ents.length; j++) {
      const ag = agreement(ents[i].pos, ents[j].pos, idx);
      if (ag) pairs.push({ a: ents[i], b: ents[j], ...ag });
    }
    pairs.sort((x, y) => y.v - x.v);
    const nTop = Math.min(5, Math.ceil(pairs.length / 2));
    const pairList = list => list.map(x => `<li>${chipOf(x.a)}<span class="muted">et</span>${chipOf(x.b)}<b>${Math.round(x.v)} %</b></li>`).join('');
    const matrix = ents.length >= 2 && ents.length <= 16 ? `<div class="hm-wrap"><table class="hm"><thead><tr><th></th>${ents.map(e => `<th><span class="hm-colh">${esc(e.label)}</span></th>`).join('')}</tr></thead><tbody>${ents.map(a => `<tr><th scope="row">${chipOf(a)}</th>${ents.map(b => {
      if (a.key === b.key) return '<td><span class="hm-cell empty"></span></td>';
      const ag = agreement(a.pos, b.pos, idx);
      if (!ag) return '<td><span class="hm-cell empty"></span></td>';
      const t = Math.max(0, Math.min(1, (ag.v - 20) / 80));
      return `<td><span class="hm-cell" style="background:color-mix(in srgb, var(--v-blue) ${Math.round(5 + t * 70)}%, var(--surface-2));color:${t > 0.6 ? '#fff' : 'var(--ink)'}" data-tip="${esc(a.long)} et ${esc(b.long)} : ${pct(ag.v)} (${nf(ag.n)} votes)">${Math.round(ag.v)}</span></td>`;
    }).join('')}</tr>`).join('')}</tbody></table></div>` : '';

    // Vote par vote
    let vidx = [...idx].reverse();
    if (st.divise) vidx = vidx.filter(i => new Set(ents.map(e => e.pos[i]).filter(x => x === 'p' || x === 'c' || x === 'a')).size > 1);

    out.innerHTML = `
      ${tabsHtml('c', [['sujets', 'Positions'], ['alliances', 'Qui vote avec qui'], ['votes', `Vote par vote · ${nf(vidx.length)}`]], st.tab)}
      <div data-panel-of="c" data-panel="sujets">
        <section class="panel">
          <header><h2>Sur ${subj}</h2><span class="muted small">${plural(idx.length, 'vote')} · du plus favorable au plus opposé</span></header>
          ${diverging}
        </section>
        <section class="panel">
          <header><h2>Par thème</h2><span class="muted small">% de votes « pour » · cliquez sur un thème ${info('Vert : vote surtout pour. Rouge : vote surtout contre. Parmi les votes exprimés.')}</span></header>
          ${heat}
        </section>
      </div>
      <div data-panel-of="c" data-panel="alliances">
        <section class="panel">
          <header><h2>Qui vote comme <select id="c-ref" class="inline-select">${ents.map(e => `<option value="${esc(e.key)}"${e.key === ref.key ? ' selected' : ''}>${esc(e.label)}</option>`).join('')}</select></h2>
            <span class="muted small">${subj} · part des votes où la position est identique</span></header>
          <div class="rank">${refChart}</div>
        </section>
        ${pairs.length > 1 ? `<div class="grid g2">
          <section class="panel"><header><h2>Les plus proches</h2></header><ul class="pairs">${pairList(pairs.slice(0, nTop))}</ul></section>
          <section class="panel"><header><h2>Les plus éloignés</h2></header><ul class="pairs">${pairList(pairs.slice(nTop).slice(-5).reverse())}</ul></section>
        </div>` : ''}
        ${matrix ? `<details class="panel fold"><summary><h2>Toutes les paires</h2><span class="muted small">matrice des accords</span></summary>${matrix}</details>` : ''}
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
    out.querySelectorAll('.hm-col').forEach(b => b.addEventListener('click', () => {
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
    if (id && !st.deps.includes(id) && st.deps.length < 8) { st.deps.push(id); draw(); }
    e.target.value = '';
  });
  el.querySelector('#c-deps').addEventListener('click', e => {
    const b = e.target.closest('[data-rm]');
    if (b) { st.deps = st.deps.filter(x => x !== b.dataset.rm); draw(); }
  });
  draw();
}

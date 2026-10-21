import {
  load, ctx, deputes, scrutinsIndex, dossiersIndex, esc, nf, fdate, norm, paged, seg, wireSeg, debounce, setTitle,
  hashParams, setHashParams, hemicycle, wireHemicycle, voteBar, voteLabels, resChip, term, KIND, gchip, plural, statTile, ttl, info,
} from '../lib.js';
import { scrutinRow } from './home.js';

const KINDS = [
  ['important', 'Votes importants'], ['ensemble', 'Sur l\'ensemble d\'un texte'], ['censure', 'Motions de censure'],
  ['motion', 'Motions de procédure'], ['article', 'Articles'], ['amendement', 'Amendements'], ['', 'Tous'],
];

export async function list(el) {
  setTitle('Votes');
  const [scr, dos] = await Promise.all([scrutinsIndex(), dossiersIndex()]);
  const p = hashParams();
  const st = { kind: p.kind ?? 'important', q: p.q || '', res: p.res || '', solennel: p.solennel === '1' };
  el.innerHTML = `<div class="page">
    <div class="page-head"><h1>Votes</h1>
      <p class="lead">Chaque ${term('scrutin', 'scrutin public')} de l'Assemblée, député par député. ${info("La plupart des votes se font à main levée, sans trace individuelle : seuls les scrutins publics sont ici. Les votes nominatifs du Sénat ne sont pas dans les données ouvertes utilisées.")}</p>
    </div>
    <div class="filters">${seg('kind', KINDS, st.kind)}</div>
    <div class="filters">
      <input type="search" id="f-q" placeholder="Rechercher (texte, auteur d'amendement…)" value="${esc(st.q)}">
      <select id="f-res"><option value="">Adoptés et rejetés</option><option value="1"${st.res === '1' ? ' selected' : ''}>Adoptés</option><option value="0"${st.res === '0' ? ' selected' : ''}>Rejetés</option></select>
      <label class="check"><input type="checkbox" id="f-sol"${st.solennel ? ' checked' : ''}> ${term('solennel', 'Scrutins solennels')} uniquement</label>
    </div>
    <div class="count-line" id="count"></div><div id="results"></div></div>`;
  const update = () => {
    setHashParams({ kind: st.kind === 'important' ? '' : st.kind || 'tous', q: st.q, res: st.res, solennel: st.solennel ? '1' : '' });
    const q = norm(st.q).split(/\s+/).filter(Boolean);
    const kind = st.kind === 'tous' ? '' : st.kind;
    const items = scr.list.filter(s => {
      if (kind === 'important' && !(['ensemble', 'censure', 'motion', 'declaration'].includes(s.kind) || s.type === 'SPS')) return false;
      if (kind && kind !== 'important' && s.kind !== kind) return false;
      if (st.res && String(+s.adopte) !== st.res) return false;
      if (st.solennel && s.type !== 'SPS') return false;
      if (q.length) { const t = norm(s.titre); if (!q.every(w => t.includes(w))) return false; }
      return true;
    });
    el.querySelector('#count').textContent = plural(items.length, 'scrutin');
    paged(el.querySelector('#results'), items, s => scrutinRow(s, dos._index));
  };
  wireSeg(el, 'kind', v => { st.kind = v || 'tous'; update(); });
  el.querySelector('#f-q').addEventListener('input', debounce(e => { st.q = e.target.value; update(); }));
  el.querySelector('#f-res').addEventListener('change', e => { st.res = e.target.value; update(); });
  el.querySelector('#f-sol').addEventListener('change', e => { st.solennel = e.target.checked; update(); });
  update();
}

const ORDER = { p: 0, a: 1, c: 2, nv: 3, x: 4 };
const COLORS = { p: 'var(--pour)', c: 'var(--contre)', a: 'var(--abst)', nv: 'var(--nv)', x: 'var(--absent)' };
const LBL = { p: 'Pour', c: 'Contre', a: 'Abstention', nv: 'Non-votant', x: 'Absent' };

export async function detail(el, num) {
  const [s, c, deps, dos] = await Promise.all([load(`scrutins/${num}`), ctx(), deputes(), dossiersIndex()]);
  setTitle(`Scrutin n° ${num}`);
  const dmap = deps._index;
  const name = id => { const d = dmap.get(id); return d ? `${d.prenom} ${d.nom}` : id; };
  const groups = s.groupes.map(g => ({ ...g, info: c.groupes.get(g.g) })).filter(g => g.info).sort((a, b) => a.info.ordre - b.info.ordre);
  const dossier = s.dossier && dos._index.get(s.dossier);
  const deleg = new Set(groups.flatMap(g => g.d || []));

  // Sièges : par groupe, puis par position
  const seats = [];
  for (const g of groups) {
    const absent = Math.max(0, g.n - g.p.length - g.c.length - g.a.length - g.nv.length);
    for (const k of ['p', 'a', 'c', 'nv']) {
      for (const id of g[k]) seats.push({ k, g, id, tip: `${name(id)} (${g.info.sigle}) — ${LBL[k]}${deleg.has(id) ? ' (par délégation)' : ''}`, href: `#/depute/${id}` });
    }
    for (let i = 0; i < absent; i++) seats.push({ k: 'x', g, tip: `${g.info.sigle} — absent ou n'a pas pris part au vote` });
  }
  const seatsBy = mode => seats.map(x => ({ ...x, color: mode === 'groupe' ? (x.k === 'x' ? 'var(--absent)' : x.g.info.couleur) : COLORS[x.k], key: mode === 'groupe' ? x.g.g : x.k }));

  // Dissidents
  const rebels = [];
  for (const g of groups) {
    if (!['p', 'c', 'a'].includes(g.pos)) continue;
    for (const k of ['p', 'c', 'a']) if (k !== g.pos) for (const id of g[k]) rebels.push({ id, g, k });
  }
  const totalAbs = seats.filter(x => x.k === 'x').length;
  const isCensure = s.kind === 'censure';

  el.innerHTML = `<div class="page">
    <div class="crumbs"><a href="#/votes">Votes</a> › Scrutin n° ${s.num}</div>
    <div class="page-head">
      <div class="pill-row" style="margin-bottom:10px"><span class="chip">${esc(KIND[s.kind] || 'Vote')}</span><span class="chip">${esc(s.typeLabel || '')}</span><span class="chip">${fdate(s.date)}</span></div>
      <h1 style="font-size:clamp(1.15rem,2.2vw,1.4rem);line-height:1.35">${esc(s.titre)}</h1>
      ${dossier ? `<p>Texte concerné : <a href="#/loi/${dossier.uid}">${esc(dossier.titre)}</a></p>` : ''}
    </div>
    <div class="grid g4" style="margin-bottom:18px">
      ${statTile(s.adopte ? '✓ Adopté' : '✕ Rejeté', esc(s.annonce || ''), '', null, s.adopte ? 'green' : 'red', s.adopte ? '' : '')}
      ${statTile(nf(s.pour), 'pour', isCensure ? `${nf(s.requis)} nécessaires pour renverser` : `majorité : ${nf(s.requis)}`, null, 'green', '')}
      ${statTile(nf(s.contre), 'contre', isCensure ? 'seuls les « pour » comptent' : '', null, 'red', '')}
      ${statTile(nf(s.abstention), 'abstentions', `${nf(s.votants)} votants`, null, 'yellow', '')}
    </div>
    <div class="two-col">
      <div>
        <section class="card">
          <div class="section-title">${ttl('', 'Qui a voté quoi ?', 'violet', 'h3')}${seg('mode', [['vote', 'Par vote'], ['groupe', 'Par groupe']], 'vote')}</div>
          <div id="hemi">${hemicycle(seatsBy('vote'), { label: nf(s.pour), sub: `pour · ${nf(s.contre)} contre` })}</div>
          <div class="legend" id="hemi-legend">${['p', 'c', 'a', 'nv', 'x'].map(k => `<button data-hl="${k}"><i style="background:${COLORS[k]}"></i>${LBL[k]} (${nf(seats.filter(x => x.k === k).length)})</button>`).join('')}</div>
          <p class="note" style="margin-top:8px">1 point = 1 député ${info("Groupés de la gauche vers la droite. Survolez un point pour le nom, cliquez pour la fiche. « Absent » : n'a pas pris part au scrutin.")}</p>
        </section>

        <section class="block">
          ${ttl('', 'Le vote des groupes', 'pink')}<div style="height:12px"></div>
          <div class="tbl-wrap"><table class="tbl">
            <thead><tr><th>Groupe</th><th>Position</th><th style="min-width:160px">Répartition</th><th class="n">Pour</th><th class="n">Contre</th><th class="n">Abst.</th><th class="n">Absents</th></tr></thead>
            <tbody>${groups.map(g => {
              const abs = Math.max(0, g.n - g.p.length - g.c.length - g.a.length - g.nv.length);
              return `<tr><td>${gchip(g.info)}</td><td>${{ p: '<span class="pos pos-p">Pour</span>', c: '<span class="pos pos-c">Contre</span>', a: '<span class="pos pos-a">Abstention</span>' }[g.pos] || '<span class="pos pos-n">—</span>'}</td>
                <td>${voteBar(g.p.length, g.c.length, g.a.length, abs)}</td><td class="n">${g.p.length}</td><td class="n">${g.c.length}</td><td class="n">${g.a.length}</td><td class="n muted">${abs}</td></tr>`;
            }).join('')}</tbody></table></div>
        </section>

        ${rebels.length ? `<section class="block">
          ${ttl('', `Ils ont voté autrement que leur groupe (${rebels.length})`, 'orange')}<div style="height:12px"></div>
          <div class="people">${rebels.map(r => `<a class="card link person" href="#/depute/${r.id}" style="padding:10px 12px"><span><span class="pname">${esc(name(r.id))}</span><br><span class="pmeta">${esc(r.g.info.sigle)} majoritairement ${LBL[r.g.pos].toLowerCase()} · a voté <b>${LBL[r.k].toLowerCase()}</b></span></span></a>`).join('')}</div>
        </section>` : ''}

        <section class="block">
          ${ttl('', 'Le détail nominatif', 'blue')}<div style="height:12px"></div>
          <div class="tabs" role="tablist">${['p', 'c', 'a', 'nv'].map((k, i) => `<button role="tab" data-tab="${k}" aria-selected="${i === 0}">${LBL[k]} (${nf(groups.reduce((n, g) => n + g[k].length, 0))})</button>`).join('')}</div>
          <div id="nominatif"></div>
        </section>
      </div>
      <aside>
        <section class="card">
          ${ttl('', 'Ce scrutin', 'orange', 'h3')}
          <dl class="kv small" style="margin-top:10px">
            <dt>Numéro</dt><dd>${s.num}</dd>
            <dt>Date</dt><dd>${fdate(s.date)}</dd>
            <dt>Type</dt><dd>${esc(s.typeLabel)}</dd>
            ${s.demandeur ? `<dt>Demandé par</dt><dd>${esc(s.demandeur)}</dd>` : ''}
            <dt>Votants</dt><dd>${nf(s.votants)} (${nf(s.exprimes)} exprimés)</dd>
            ${s.lieu ? `<dt>Lieu</dt><dd>${esc(s.lieu)}</dd>` : ''}
          </dl>
          <p class="small" style="margin-top:12px"><a class="ext" href="https://www.assemblee-nationale.fr/dyn/17/scrutins/${s.num}" target="_blank" rel="noopener">Voir sur le site de l'Assemblée</a></p>
        </section>
        <section class="card" style="margin-top:16px">
          ${ttl('', 'Comment le lire ?', 'teal', 'h3')}
          <p class="small">${isCensure
            ? `Une ${term('censure', 'motion de censure')} n'est adoptée que si elle obtient la ${term('majabs', 'majorité absolue')} des députés. Seuls les votes « pour » sont décomptés : ne pas voter revient à soutenir le Gouvernement.`
            : `Un texte ou un amendement est adopté s'il recueille plus de voix « pour » que « contre ». Les abstentions ne comptent pas dans les suffrages exprimés. Un député peut voter ${term('delegation', 'par délégation')} pour un collègue absent.`}</p>
          <p class="small">Les « non-votants » sont des députés présents qui ne participent pas au vote, comme le président de séance.</p>
        </section>
      </aside>
    </div>
  </div>`;

  wireHemicycle(el.querySelector('#hemi').parentElement);
  wireSeg(el, 'mode', mode => {
    el.querySelector('#hemi').innerHTML = hemicycle(seatsBy(mode), { label: nf(s.pour), sub: `pour · ${nf(s.contre)} contre` });
    el.querySelector('#hemi-legend').innerHTML = mode === 'groupe'
      ? groups.map(g => `<button data-hl="${g.g}"><i style="background:${g.info.couleur}"></i>${esc(g.info.sigle)}</button>`).join('')
      : ['p', 'c', 'a', 'nv', 'x'].map(k => `<button data-hl="${k}"><i style="background:${COLORS[k]}"></i>${LBL[k]} (${nf(seats.filter(x => x.k === k).length)})</button>`).join('');
    wireHemicycle(el.querySelector('#hemi').parentElement);
  });
  const nomi = el.querySelector('#nominatif');
  const showTab = k => {
    el.querySelectorAll('[data-tab]').forEach(b => b.setAttribute('aria-selected', b.dataset.tab === k));
    const blocks = groups.filter(g => g[k].length).map(g => `<div style="margin-bottom:14px"><div style="margin-bottom:6px">${gchip(g.info)} <span class="muted small">${g[k].length}</span></div>
      <div class="small" style="line-height:1.9">${g[k].map(id => `<a href="#/depute/${id}">${esc(name(id))}</a>${deleg.has(id) ? '<span class="muted" data-tip="Vote par délégation">*</span>' : ''}`).join(', ')}</div></div>`);
    nomi.innerHTML = blocks.join('') || '<p class="muted">Personne.</p>';
    if (deleg.size) nomi.insertAdjacentHTML('beforeend', '<p class="note">* vote par délégation</p>');
  };
  el.querySelector('.tabs').addEventListener('click', e => { const b = e.target.closest('[data-tab]'); if (b) showTab(b.dataset.tab); });
  showTab('p');
}

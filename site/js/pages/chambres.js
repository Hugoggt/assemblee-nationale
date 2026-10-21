import {
  ctx, deputes, senateurs, scrutinsIndex, dossiersIndex, esc, nf, pct, fdate, age, hemicycle, wireHemicycle, gchip, term,
  statTile, setTitle, plural, KIND, resChip, ttl, info, avatar, loiCard, norm, debounce, seg, wireSeg, tabsHtml, wireTabs, hashParams,
} from '../lib.js';
import { groupSeats } from './home.js';

const BLOCS = [['Gauche', '#e0435a'], ['Centre', '#f2a93b'], ['Droite', '#3b6fd6'], ['Extrême droite', '#1f2a5c'], ['Non-inscrits', '#9aa0a6']];

function memberSeats(members, groups, total, chamber) {
  const order = new Map(groups.map(g => [g.id, g]));
  const sorted = members.filter(m => order.has(m.groupe)).sort((a, b) => order.get(a.groupe).ordre - order.get(b.groupe).ordre || a.tri.localeCompare(b.tri));
  const seats = sorted.map(m => {
    const g = order.get(m.groupe);
    return { color: g.couleur, key: g.id, href: chamber === 'AN' ? `#/depute/${m.id}` : `#/senateur/${m.id}`, tip: `${m.prenom} ${m.nom} · ${g.sigle} · ${m.departement || ''}` };
  });
  while (seats.length < total) seats.push({ color: 'var(--absent)', tip: 'Siège vacant' });
  return seats;
}

function builder(groups, total) {
  const maj = Math.floor(total / 2) + 1;
  return `<section class="card">
    ${ttl('', 'Construisez une majorité', 'violet', 'h3')}
    <p class="small muted" style="margin:6px 0 0">Objectif : <b>${nf(maj)}</b> sièges ${info(`La majorité absolue : plus de la moitié des ${total} sièges. Nécessaire pour gouverner sereinement et pour une motion de censure.`)}</p>
    <div class="builder" data-total="${total}">${groups.map(g => `<button type="button" aria-pressed="false" data-g="${g.id}" data-n="${g.effectif}" data-c="${esc(g.couleur)}"><i style="background:${esc(g.couleur)}"></i>${esc(g.sigle)} <small>${g.effectif}</small></button>`).join('')}</div>
    <div class="majbar" aria-hidden="true"><span class="line" style="left:${(100 * maj) / total}%"></span></div>
    <div class="majresult" aria-live="polite">Cliquez sur des groupes </div>
  </section>`;
}
function wireBuilder(root) {
  const b = root.querySelector('.builder');
  if (!b) return;
  const total = +b.dataset.total, maj = Math.floor(total / 2) + 1;
  const bar = root.querySelector('.majbar'), res = root.querySelector('.majresult');
  b.addEventListener('click', e => {
    const btn = e.target.closest('button');
    if (!btn) return;
    btn.setAttribute('aria-pressed', btn.getAttribute('aria-pressed') !== 'true');
    const on = [...b.querySelectorAll('[aria-pressed="true"]')];
    const sum = on.reduce((s, x) => s + +x.dataset.n, 0);
    bar.innerHTML = on.map(x => `<div style="width:${(100 * +x.dataset.n) / total}%;background:${x.dataset.c}"></div>`).join('') + `<span class="line" style="left:${(100 * maj) / total}%"></span>`;
    res.className = 'majresult' + (sum >= maj ? ' ok' : '');
    res.textContent = !on.length ? 'Cliquez sur des groupes ' : sum >= maj
      ? `${nf(sum)} sièges : majorité absolue (+${sum - maj + 1})`
      : `${nf(sum)} sièges : il en manque ${nf(maj - sum)}`;
  });
}

function groupCard(g, total) {
  return `<a class="gcard" href="#/groupe/${g.id}" style="--gc:${esc(g.couleur)}">
    <div class="gtop"><span class="gsig">${esc(g.sigle)}</span><span class="gn">${g.effectif}</span></div>
    <div class="gname">${esc(g.nom)}</div>
    ${g.pitch ? `<div class="gpitch">${esc(g.pitch)}</div>` : ''}
    <div class="seatbar"><span style="width:${(100 * g.effectif) / (total * 0.4)}%"></span></div>
    <div class="tiny muted">${g.president ? `${esc(g.president.nom)}` : ''}</div>
  </a>`;
}

function hbars(items, total, color) {
  return items.map(([l, k, c]) => `<div class="hbar" style="--bc:${c || color || 'var(--accent)'}"><span>${esc(l)}</span><span class="num muted">${nf(k)}</span><div class="track"><span style="width:${(100 * k) / (total || 1)}%"></span></div></div>`).join('');
}

function portrait(members) {
  const n = members.length || 1;
  const femmes = members.filter(m => m.femme).length;
  const ages = members.map(m => age(m.naissance)).filter(a => a != null);
  const moy = ages.reduce((a, b) => a + b, 0) / (ages.length || 1);
  const cats = {};
  members.forEach(m => { const k = m.categorie || 'Non renseigné'; cats[k] = (cats[k] || 0) + 1; });
  const unknown = cats['Non renseigné'] || 0;
  delete cats['Non renseigné'];
  const top = Object.entries(cats).sort((a, b) => b[1] - a[1]).slice(0, 6);
  const tranches = [['Moins de 40 ans', a => a < 40, '#06b6d4'], ['40 à 54 ans', a => a >= 40 && a < 55, '#3b5bfd'], ['55 à 69 ans', a => a >= 55 && a < 70, '#8b5cf6'], ['70 ans et plus', a => a >= 70, '#ec4899']];
  return `<div class="grid g4" style="margin-bottom:14px">
      ${statTile(pct((100 * femmes) / n), 'de femmes', `${nf(femmes)} sur ${nf(members.length)}`, null, 'pink', '')}
      ${statTile(`${Math.round(moy)} ans`, 'âge moyen', `de ${Math.min(...ages)} à ${Math.max(...ages)} ans`, null, 'violet', '')}
      ${statTile(nf(members.filter(m => m.premiereElection).length) || '–', 'nouveaux élus', 'premier mandat', null, 'teal', '')}
      ${statTile(nf(new Set(members.map(m => m.departement)).size), 'départements représentés', '', null, 'orange', '')}
    </div>
    <div class="grid g2">
      <div class="card">${ttl('', 'Par âge', 'violet', 'h3')}${hbars(tranches.map(([l, f, c]) => [l, ages.filter(f).length, c]), n)}</div>
      <div class="card">${ttl('', 'Avant leur mandat', 'orange', 'h3')}
        ${unknown < n / 2 ? hbars(top, n, 'var(--v-orange)') : '<p class="small muted">Profession non renseignée dans les données.</p>'}</div>
    </div>`;
}

function heatmap(groups, prox) {
  const head = groups.map(g => `<th scope="col" data-tip="${esc(g.nom)}"><span class="gchip" style="padding:1px 7px 1px 3px"><i style="background:${g.couleur}"></i>${esc(g.sigle)}</span></th>`).join('');
  const rows = groups.map(a => `<tr><th scope="row" style="text-align:right" data-tip="${esc(a.nom)}">${esc(a.sigle)}</th>${groups.map(b => {
    const v = prox[a.id]?.[b.id];
    if (a.id === b.id) return '<td style="background:var(--surface-2)" aria-label="même groupe"></td>';
    if (v == null) return '<td>–</td>';
    const t = Math.max(0, Math.min(1, (v - 20) / 80));
    return `<td style="background:color-mix(in srgb, var(--v-violet) ${Math.round(6 + t * 86)}%, var(--surface));color:${t > 0.5 ? '#fff' : 'var(--ink)'}" data-tip="${esc(a.sigle)} et ${esc(b.sigle)} votent pareil dans ${pct(v)} des scrutins">${Math.round(v)}</td>`;
  }).join('')}</tr>`).join('');
  return `<div style="overflow-x:auto"><table class="heat"><thead><tr><th></th>${head}</tr></thead><tbody>${rows}</tbody></table></div>
    <div class="heat-scale" style="--heat-0:color-mix(in srgb, var(--v-violet) 6%, var(--surface));--heat-1:var(--v-violet)">rarement d'accord<span></span>presque toujours d'accord</div>`;
}

function blocsCard(groups, total) {
  const blocs = BLOCS.map(([b, col]) => [b, groups.filter(g => g.bloc === b).reduce((s, g) => s + g.effectif, 0), col]).filter(([, n]) => n);
  return `<section class="card" style="margin-top:16px">${ttl('', 'Les grands blocs', 'blue', 'h3')} ${info("Regroupement indicatif, selon l'orientation habituellement attribuée aux groupes.")}
    <div class="vbar lg" style="margin-top:12px">${blocs.map(([b, n, col]) => `<span style="width:${(100 * n) / total}%;background:${col}" data-tip="${b} : ${n}"></span>`).join('')}</div>
    <div class="legend">${blocs.map(([b, n, col]) => `<span><i style="background:${col}"></i>${b} <b>${n}</b></span>`).join('')}</div></section>`;
}

export async function assemblee(el) {
  setTitle('Assemblée nationale');
  const [c, deps] = await Promise.all([ctx(), deputes()]);
  const actifs = deps.filter(d => d.actif);
  const groups = c.an;
  el.innerHTML = `<div class="page">
    <div class="page-head"><h1>Assemblée nationale</h1>
      <p class="lead">577 députés élus pour 5 ans. Elle vote la loi, contrôle le Gouvernement et peut le renverser.</p>
      <div class="pill-row"><a class="btn small" href="#/deputes">Les députés</a><a class="btn small" href="#/votes">Les votes</a><a class="btn small" href="#/lois?origine=AN">Ses textes</a></div>
    </div>
    ${tabsHtml('ch', [['hemicycle', 'Hémicycle'], ['groupes', `Groupes (${groups.length})`], ['alliances', 'Qui vote avec qui'], ['portrait', 'Portrait']], ['hemicycle', 'groupes', 'alliances', 'portrait'].includes(hashParams().tab) ? hashParams().tab : 'hemicycle')}
    <div data-panel-of="ch" data-panel="hemicycle">
    <div class="two-col">
      <section class="card" id="hemi-an">
        ${ttl('', 'L’hémicycle', 'blue', 'h3')} ${info('Survolez un groupe pour le mettre en évidence, cliquez sur un point pour ouvrir la fiche du député. Les groupes sont placés de la gauche vers la droite.')}
        ${hemicycle(memberSeats(actifs, groups, 577, 'AN'), { label: nf(actifs.length), sub: 'députés' })}
        <div class="legend">${groups.map(g => `<button data-hl="${g.id}"><i style="background:${g.couleur}"></i>${esc(g.sigle)} ${g.effectif}</button>`).join('')}</div>
      </section>
      <div>${builder(groups, 577)}${blocsCard(groups, 577)}</div>
    </div>
    </div>

    <div data-panel-of="ch" data-panel="groupes">
      <p class="muted small">Il faut au moins 15 députés pour former un groupe ${info("Un groupe donne du temps de parole, des moyens et des postes.")}</p>
      <div class="grid cards">${groups.map(g => groupCard(g, 577)).join('')}</div>
    </div>

    <div data-panel-of="ch" data-panel="alliances">
      <div class="section-title"><p class="muted small" style="margin:0">Part des scrutins publics où deux groupes ont eu la même position.</p><a class="btn small" href="#/comparer?tab=alliances">Comparer par sujet →</a></div>
      <div class="card">${heatmap(groups, c.gdata.proximite)}</div>
    </div>

    <div data-panel-of="ch" data-panel="portrait">${portrait(actifs)}</div>
  </div>`;
  wireTabs(el, 'ch');
  wireHemicycle(el.querySelector('#hemi-an'));
  wireBuilder(el);
}

export async function senat(el) {
  setTitle('Sénat');
  const [c, sens] = await Promise.all([ctx(), senateurs()]);
  const groups = c.sn;
  el.innerHTML = `<div class="page">
    <div class="page-head"><h1>Sénat</h1>
      <p class="lead">348 sénateurs élus pour 6 ans par les ${term('senatoriales', 'grands électeurs')}. Il représente les territoires.</p>
      <div class="pill-row"><a class="btn small" href="#/senateurs">Les sénateurs</a><a class="btn small" href="#/lois?origine=SN">Ses textes</a></div>
    </div>
    ${tabsHtml('ch', [['hemicycle', 'Hémicycle'], ['groupes', `Groupes (${groups.length})`], ['portrait', 'Portrait']], ['hemicycle', 'groupes', 'alliances', 'portrait'].includes(hashParams().tab) ? hashParams().tab : 'hemicycle')}
    <div data-panel-of="ch" data-panel="hemicycle">
    <div class="two-col">
      <section class="card" id="hemi-sn">
        ${ttl('', 'L’hémicycle du Luxembourg', 'red', 'h3')}
        ${hemicycle(memberSeats(sens, groups, 348, 'SN'), { label: nf(sens.length), sub: 'sénateurs' })}
        <div class="legend">${groups.map(g => `<button data-hl="${g.id}"><i style="background:${g.couleur}"></i>${esc(g.sigle)} ${g.effectif}</button>`).join('')}</div>
      </section>
      <div>
        ${builder(groups, 348)}
        ${blocsCard(groups, 348)}
        <section class="card" style="margin-top:16px">${ttl('', 'Son pouvoir', 'orange', 'h3')}
          <div class="facts3"><div class="fact tone-green"><b>Amende la loi</b><span>tous les textes passent par lui</span></div>
          <div class="fact tone-red"><b>Veto</b><span>sur la Constitution</span></div>
          <div class="fact tone-slate"><b>Pas de censure</b><span>l'Assemblée a le dernier mot</span></div></div>
          <a class="small" href="#/comprendre/dernier-mot">En savoir plus →</a>
        </section>
      </div>
    </div>
    </div>
    <div data-panel-of="ch" data-panel="groupes">
      <p class="muted small">Il faut au moins 10 sénateurs pour former un groupe.</p>
      <div class="grid cards">${groups.map(g => groupCard(g, 348)).join('')}</div>
    </div>
    <div data-panel-of="ch" data-panel="portrait">
      <p class="note">Votes nominatifs non disponibles ${info("Les votes nominatifs des sénateurs ne figurent pas dans les données ouvertes utilisées : les décisions du Sénat sont suivies texte par texte.")}</p>
      ${portrait(sens)}
    </div>
  </div>`;
  wireTabs(el, 'ch');
  wireHemicycle(el.querySelector('#hemi-sn'));
  wireBuilder(el);
}

// ─────────────────────────────────────────── Page d'un groupe

function isLight(hex) {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex || '');
  if (!m) return false;
  const n = parseInt(m[1], 16), r = n >> 16, g = (n >> 8) & 255, b = n & 255;
  return (0.299 * r + 0.587 * g + 0.114 * b) > 165;
}

const AWARDS = [
  ['assidu', '', 'Le plus assidu', 'green', v => `${pct(v)} de participation`],
  ['frondeur', '', 'L’esprit libre', 'orange', v => `vote avec son groupe à ${pct(v)}`],
  ['plume', '', 'La plume', 'blue', v => plural(v, 'texte déposé', 'textes déposés')],
  ['benjamin', '', 'Le benjamin', 'teal', v => `${v} ans`],
  ['doyen', '', 'Le doyen', 'violet', v => `${v} ans`],
];

function memberTable(list, g, isAN) {
  return `<div class="tbl-wrap"><table class="tbl mtable">
    <thead><tr><th data-sort="nom">Nom</th><th data-sort="dep">Département</th>${isAN ? '<th data-sort="part" class="n">Participation</th><th data-sort="loy" class="n">Avec le groupe</th>' : ''}<th data-sort="textes" class="n">Textes</th><th data-sort="age" class="n">Âge</th></tr></thead>
    <tbody>${list.map(m => `<tr data-nom="${esc(m.tri)}" data-dep="${esc(m.departement || '')}" data-part="${m.stats?.participation ?? -1}" data-loy="${m.stats?.loyaute ?? -1}" data-textes="${m.roles?.auteur?.length || 0}" data-age="${age(m.naissance) ?? 0}">
      <td><a class="person" href="#/${isAN ? 'depute' : 'senateur'}/${m.id}">${avatar(m, g.chambre, g, 'sm')}<span><span class="pname">${esc(m.prenom)} ${esc(m.nom)}</span>${m.presidentGroupe ? ' <span class="role-pill">Président·e</span>' : ''}${m.apparente || m.rattache ? ' <span class="chip" style="font-size:.7rem">apparenté</span>' : ''}${(m.fonctions || []).slice(0, 1).map(f => `<br><span class="role-pill">${esc(f.length > 48 ? f.slice(0, 46) + '…' : f)}</span>`).join('')}</span></a></td>
      <td class="small">${esc(m.departement || '')}</td>
      ${isAN ? `<td class="n small"><span class="mini-bar"><span style="width:${m.stats?.participation || 0}%"></span></span>${pct(m.stats?.participation)}</td><td class="n small">${pct(m.stats?.loyaute)}</td>` : ''}
      <td class="n small">${m.roles?.auteur?.length || 0}</td><td class="n small">${age(m.naissance) ?? ''}</td></tr>`).join('')}</tbody></table></div>`;
}

export async function groupe(el, id) {
  const c = await ctx();
  const g = c.groupes.get(id);
  if (!g) { el.innerHTML = '<div class="page"><h1>Groupe introuvable</h1></div>'; return; }
  setTitle(g.nom);
  const isAN = g.chambre === 'AN';
  const total = isAN ? 577 : 348;
  const [members, scr, dos] = await Promise.all([isAN ? deputes() : senateurs(), isAN ? scrutinsIndex() : null, dossiersIndex()]);
  const list = members.filter(m => m.groupe === id && m.actif).sort((a, b) => (b.presidentGroupe - a.presidentGroupe) || a.tri.localeCompare(b.tri));
  const chamberGroups = isAN ? c.an : c.sn;
  const others = chamberGroups.filter(o => o.id !== id);
  const prox = isAN && c.gdata.proximite[id] ? others.map(o => [o, c.gdata.proximite[id][o.id]]).filter(([, v]) => v != null).sort((a, b) => b[1] - a[1]) : [];
  const n = g.effectif || 1;
  const partis = (g.partis || []).filter(([p]) => p !== 'Sans parti déclaré');
  const lois = (g.loisPromulguees || []).map(u => dos._index.get(u)).filter(Boolean);
  const ens = g.ensemble;
  const ensTot = ens ? ens.pour + ens.contre + ens.abstention : 0;
  const tops = AWARDS.filter(([k]) => g.tops?.[k]);

  let keyVotes = '';
  const pos = c.gdata.positions[id];
  if (isAN && pos) {
    const key = scr.chrono.map((s, i) => [s, pos[i]]).filter(([s, p]) => (s.kind === 'ensemble' || s.kind === 'censure') && 'pca'.includes(p)).slice(-8).reverse();
    keyVotes = `<section class="block">${ttl('', 'Ses derniers grands votes', 'violet')}<div class="list" style="margin-top:12px">${key.map(([s, p]) => `<a class="row striped" href="#/vote/${s.num}" style="--stripe:${{ p: 'var(--pour)', c: 'var(--contre)', a: 'var(--abst)' }[p]}"><div class="grow"><div class="title small">${esc(s.titre)}</div><div class="meta"><span>${fdate(s.date, true)}</span>${resChip(s.adopte)}</div></div><div class="side"><span class="pos pos-${p}">${{ p: 'Pour', c: 'Contre', a: 'Abstention' }[p]}</span></div></a>`).join('')}</div></section>`;
  }

  el.innerHTML = `<div class="page">
    <div class="gbanner${isLight(g.couleur) ? ' light' : ''}" style="--gc:${esc(g.couleur)}">
      <div class="gb-grid">
        <div>
          <div class="crumbs"><a href="#/${isAN ? 'assemblee' : 'senat'}">${isAN ? 'Assemblée nationale' : 'Sénat'}</a> › Groupes</div>
          <div class="sig">${esc(g.sigle)}</div>
          <h1>${esc(g.nom)}</h1>
          ${g.pitch ? `<p>${esc(g.pitch)}</p>` : ''}
          <div class="gb-chips">
            <span>${esc(g.bloc)}</span>
            <span>${plural(g.effectif, 'siège')} · ${pct((100 * g.effectif) / total, 1)}</span>
            ${g.president ? `<a href="#/${isAN ? 'depute' : 'senateur'}/${g.president.id}">${esc(g.president.nom)}</a>` : ''}
            ${isAN && g.debut ? `<span>depuis ${fdate(g.debut, true)}</span>` : ''}
            ${isAN ? `<a href="#/comparer?g=${[id, ...prox.slice(0, 2).map(([o]) => o.id), prox.length ? prox[prox.length - 1][0].id : ''].filter(Boolean).join(',')}">Comparer ses votes</a>` : ''}
          </div>
        </div>
        <div class="hemi-box">${hemicycle(groupSeats(chamberGroups, total, id), { label: String(g.effectif), sub: `sur ${total}` })}</div>
      </div>
    </div>

    ${tabsHtml('g', [['apercu', 'Vue d’ensemble'], ['membres', `Membres (${g.effectif})`], ...(isAN ? [['votes', 'Votes']] : []), ['composition', 'Composition']], ['apercu', 'membres', 'votes', 'composition'].includes(hashParams().tab) ? hashParams().tab : 'apercu')}
    <div data-panel-of="g" data-panel="apercu">
    <div class="grid g4">
      ${statTile(pct((100 * g.femmes) / n), 'de femmes', `${g.femmes} sur ${g.effectif}`, null, 'pink', '')}
      ${statTile(g.ageMoyen ? `${Math.round(g.ageMoyen)} ans` : '–', 'âge moyen', g.tops?.benjamin ? `de ${g.tops.benjamin.v} à ${g.tops.doyen.v} ans` : '', null, 'violet', '')}
      ${isAN ? statTile(pct(g.cohesion), 'de cohésion', 'membres votant comme le groupe', null, 'green', '') : statTile(nf(g.apparentes || 0), 'rattachés ou apparentés', '', null, 'green', '')}
      ${statTile(nf(g.textes || 0), 'textes déposés', lois.length ? `dont ${lois.length} devenus loi` : '', null, 'orange', '')}
    </div>
    ${isAN ? `<section class="block" style="margin-top:14px"><div class="kv-badges">
      ${g.censures ? `<div class="kvb"><div class="k">Face au Gouvernement</div><div class="v">${g.censures.pour} / ${g.censures.total} censures votées</div>
        <div class="vbar"><span style="width:${(100 * g.censures.pour) / (g.censures.total || 1)}%;background:var(--v-red)"></span><span style="width:${(100 * g.censures.partiel) / (g.censures.total || 1)}%;background:color-mix(in srgb, var(--v-red) 35%, var(--surface))"></span></div>
        <div class="tiny muted" style="margin-top:6px">${g.censures.pour === 0 && !g.censures.partiel ? 'n’a jamais voté de motion de censure' : g.censures.partiel ? `+ ${g.censures.partiel} votées par une partie du groupe` : 'motions soutenues par la majorité du groupe'}</div></div>` : ''}
      ${ensTot ? `<div class="kvb"><div class="k">Sur les votes finaux</div><div class="v">${Math.round((100 * ens.pour) / ensTot)} % de « pour »</div>
        ${voteBarSimple(ens.pour, ens.contre, ens.abstention)}<div class="tiny muted" style="margin-top:6px">${ens.pour} pour · ${ens.contre} contre · ${ens.abstention} abst. sur ${ensTot} textes</div></div>` : ''}
      ${prox.length ? `<div class="kvb"><div class="k">Plus proches alliés</div><div class="v">${prox.slice(0, 2).map(([o]) => esc(o.sigle)).join(' & ')}</div>
        <div class="pill-row">${prox.slice(0, 3).map(([o, v]) => `${gchip(o)} <span class="tiny muted">${Math.round(v)} %</span>`).join(' ')}</div>
        <div class="tiny muted" style="margin-top:6px">le plus éloigné : ${esc(prox[prox.length - 1][0].sigle)} (${Math.round(prox[prox.length - 1][1])} %)</div></div>` : ''}
    </div></section>` : ''}

    ${tops.length ? `<section class="block" style="margin-top:22px">${ttl('', 'Le palmarès', 'yellow')}<div class="awards" style="margin-top:12px">${tops.map(([k, e, l, tone, f]) => {
      const t = g.tops[k];
      return `<a class="award tone-${tone}" href="#/${isAN ? 'depute' : 'senateur'}/${t.id}"><span class="ae">${e}</span><span style="min-width:0"><span class="al">${l}</span><br><span class="an">${esc(t.nom)}</span><br><span class="av">${f(t.v)}</span></span></a>`;
    }).join('')}</div></section>` : ''}
    ${lois.length ? `<section class="block">${ttl('', 'Ses textes devenus loi', 'green')}<div class="lcards" style="margin-top:12px">${lois.slice(0, 6).map(d => loiCard(d, dos.themes)).join('')}</div></section>` : ''}
    </div>
    <div data-panel-of="g" data-panel="membres">
    <section class="block">
      <div class="section-title">${ttl('', `Les ${g.effectif} membres`, 'pink')}<div class="filters" style="margin:0">${seg('mview', [['grid', 'Cartes'], ['table', 'Tableau']], 'grid')}<input type="search" id="m-q" placeholder="Filtrer…" style="max-width:200px"></div></div>
      <div id="members"></div>
    </section>
    </div>
    <div data-panel-of="g" data-panel="votes">

    ${keyVotes}
    </div>
    <div data-panel-of="g" data-panel="composition">
    <div class="grid g2" style="margin-top:8px">
      ${g.postes?.length ? `<section class="card">${ttl('', 'Postes clés', 'yellow', 'h3')}<div class="list small" style="margin-top:10px;gap:8px">${g.postes.slice(0, 10).map(p => `<div><a href="#/${isAN ? 'depute' : 'senateur'}/${p.id}"><b>${esc(p.nom)}</b></a><br><span class="muted">${esc(p.fonction)}</span></div>`).join('')}</div></section>` : ''}
      ${partis.length ? `<section class="card">${ttl('', 'Partis représentés', 'pink', 'h3')}${hbars(partis, n, g.couleur)}</section>` : ''}
      ${g.commissions?.length ? `<section class="card">${ttl('', 'Dans les commissions', 'teal', 'h3')}${hbars(g.commissions.slice(0, 8).map(([l, k]) => [l.replace(/^Commission (des |de la |de l’|de l'|du )?/i, ''), k]), n, 'var(--v-teal)')}</section>` : ''}
      ${g.regions?.length ? `<section class="card">${ttl('', 'D’où viennent-ils ?', 'orange', 'h3')}${hbars(g.regions, n, 'var(--v-orange)')}</section>` : ''}
    </div>

    ${(g.arrivees?.length || g.departs?.length) ? `<section class="block">${ttl('', 'Arrivées et départs', 'blue')}<div class="grid g2" style="margin-top:12px">
      <div class="card"><h3 class="small muted">Ont rejoint le groupe</h3><div class="moves">${(g.arrivees || []).map(a => `<div><a href="#/depute/${a.id}">${esc(a.nom)}</a><span class="tiny muted">${fdate(a.date, true)}${a.de ? ` · venant de ${esc(a.de)}` : ' · nouveau député'}</span></div>`).join('') || '<span class="muted small">Personne depuis la création.</span>'}</div></div>
      <div class="card"><h3 class="small muted">Ont quitté le groupe</h3><div class="moves">${(g.departs || []).map(a => `<div><a href="#/depute/${a.id}">${esc(a.nom)}</a><span class="tiny muted">${fdate(a.date, true)} · ${a.vers ? `vers ${esc(a.vers)}` : 'a quitté l’Assemblée'}</span></div>`).join('') || '<span class="muted small">Aucun départ.</span>'}</div></div>
    </div></section>` : ''}
    </div>
  </div>`;

  wireTabs(el, 'g');
  const box = el.querySelector('#members');
  let view = 'grid', q = '';
  const cardHtml = m => `<a class="card link person" href="#/${isAN ? 'depute' : 'senateur'}/${m.id}" style="padding:12px 14px">${avatar(m, g.chambre, g)}<span style="min-width:0"><span class="pname">${esc(m.prenom)} ${esc(m.nom)}</span><br><span class="pmeta">${esc(m.departement || '')}${isAN && m.stats?.participation != null ? ` · ${pct(m.stats.participation)} présence` : ''}</span>${m.presidentGroupe ? '<br><span class="role-pill">Président·e du groupe</span>' : (m.fonctions || []).length ? `<br><span class="role-pill">${esc(m.fonctions[0].split(' de la ')[0])}</span>` : ''}</span></a>`;
  const draw = () => {
    const words = norm(q).split(/\s+/).filter(Boolean);
    const items = list.filter(m => !words.length || words.every(w => norm(`${m.prenom} ${m.nom} ${m.departement} ${m.parti || ''}`).includes(w)));
    box.innerHTML = view === 'grid' ? `<div class="people">${items.map(cardHtml).join('')}</div>` : memberTable(items, g, isAN);
    if (view === 'table') wireSort(box);
  };
  wireSeg(el, 'mview', v => { view = v; draw(); });
  el.querySelector('#m-q').addEventListener('input', debounce(e => { q = e.target.value; draw(); }));
  draw();
}

function voteBarSimple(p, c, a) {
  const t = p + c + a || 1;
  return `<div class="vbar"><span class="vp" style="width:${(100 * p) / t}%"></span><span class="vc" style="width:${(100 * c) / t}%"></span><span class="va" style="width:${(100 * a) / t}%"></span></div>`;
}

function wireSort(root) {
  const tbody = root.querySelector('tbody');
  root.querySelectorAll('th[data-sort]').forEach(th => th.addEventListener('click', () => {
    const k = th.dataset.sort;
    const asc = th.getAttribute('aria-sort') !== 'ascending';
    root.querySelectorAll('th').forEach(x => x.removeAttribute('aria-sort'));
    th.setAttribute('aria-sort', asc ? 'ascending' : 'descending');
    const rows = [...tbody.rows];
    const num = !['nom', 'dep'].includes(k);
    rows.sort((a, b) => {
      const x = a.dataset[k], y = b.dataset[k];
      const r = num ? (+x - +y) : x.localeCompare(y, 'fr');
      return asc ? r : -r;
    });
    rows.forEach(r => tbody.appendChild(r));
  }));
}

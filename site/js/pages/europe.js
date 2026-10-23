// Parlement européen : les eurodéputés élus en France, leurs votes, les textes et le calendrier.
import {
  load, esc, nf, pct, fdate, fdateDay, age, norm, debounce, paged, seg, wireSeg, setTitle, statTile, voteBar, voteLabels, resChip,
  posChip, hashParams, setHashParams, plural, ttl, info, tabsHtml, wireTabs, shareBtn, hemicycle, wireHemicycle, THEME_COLOR, daysAgo,
} from '../lib.js';

// ─────────────────────────────────────────── Données
let dataP;
/** Données de la rubrique : eurodéputés, groupes, partis, votes, positions individuelles. */
export function europe() {
  if (!dataP) {
    dataP = Promise.all([load('europe/europe'), load('europe/votes'), load('europe/positions')]).then(([e, votes, pos]) => {
      const meps = new Map(e.meps.map(d => [d.id, d]));
      const bySlug = new Map(e.meps.map(d => [d.slug, d]));
      // Listes ordonnées, consultables aussi par code : E.groupes.get('EPP')
      const indexed = (list, key) => {
        const m = new Map(list.map(x => [x[key], x]));
        return Object.defineProperty(list, 'get', { value: k => m.get(k) });
      };
      const groupes = indexed(e.groupes, 'code');
      const partis = indexed(e.partis, 'id');
      const vById = new Map(votes.map(v => [v.id, v]));
      const vIndex = new Map(pos.votes.map((id, i) => [id, i]));
      return { ...e, meps, bySlug, groupes, partis, votes, vById, vIndex, chains: pos.meps, chrono: pos.votes };
    }).catch(err => { dataP = null; throw err; });
  }
  return dataP;
}
let textesP;
function textes() {
  if (!textesP) textesP = load('europe/textes').then(t => ({ list: t, bySlug: new Map(t.map(x => [x.slug, x])) }));
  return textesP;
}

// ─────────────────────────────────────────── Adresses et petits composants
export const LE = {
  mep: d => `eurodepute/${d.slug || d}`,
  vote: v => `europe/vote/${v.id || v}`,
  texte: t => `europe/texte/${t.slug || t}`,
};
const PHOTO = id => `https://www.europarl.europa.eu/mepphoto/${id}.jpg`;
const LBL = { p: 'Pour', c: 'Contre', a: 'Abstention', '.': 'Absent' };
const COLORS = { p: 'var(--pour)', c: 'var(--contre)', a: 'var(--abst)', '.': 'var(--absent)' };

function majority([p, c, a]) {
  const m = Math.max(p, c, a);
  if (!m) return null;
  return m === p ? 'p' : m === c ? 'c' : 'a';
}
function mepAvatar(d, g, size = '') {
  const ini = `${(d.prenom || '?')[0]}${(d.nom || '?').replace(/^(de |d'|du |le |la )/i, '')[0] || ''}`.toUpperCase();
  return `<span class="avatar ${size}" style="background:${esc(g?.couleur || '#888')}">${esc(ini)}<img src="${PHOTO(d.id)}" alt="" loading="lazy" onerror="this.remove()"></span>`;
}
function grpChip(g, link = true) {
  if (!g) return '';
  const inner = `<i style="background:${esc(g.couleur)}"></i>${esc(g.sigle)}`;
  return link ? `<a class="gchip" href="europe/eurodeputes?groupe=${g.code}" data-tip="${esc(g.nom)}">${inner}</a>` : `<span class="gchip" data-tip="${esc(g.nom)}">${inner}</span>`;
}
function partiChip(p, link = true) {
  if (!p) return '';
  const inner = `<i style="background:${esc(p.couleur)}"></i>${esc(p.sigle)}`;
  return link ? `<a class="gchip" href="europe/eurodeputes?parti=${encodeURIComponent(p.id)}" data-tip="${esc(p.nom)}">${inner}</a>` : `<span class="gchip" data-tip="${esc(p.nom)}">${inner}</span>`;
}
function themeChip(key, E) {
  const l = E.themes[key];
  return l ? `<span class="chip theme" style="--tc:${THEME_COLOR[key] || '#94a3b8'}">${esc(l)}</span>` : '';
}
function typeChip(type, E) {
  const t = E.types[type];
  return t ? `<span class="chip" data-tip="${esc(t[1])}">${esc(t[0])}</span>` : '';
}
const eu = (s, n = 70) => (s && s.length > n ? s.slice(0, n - 1) + '…' : s);

/** Barre d'onglets-liens commune à la rubrique. */
function subnav(active) {
  const items = [['europe', 'Vue d’ensemble'], ['europe/eurodeputes', 'Eurodéputés'], ['europe/votes', 'Votes'], ['europe/textes', 'Textes'], ['europe/calendrier', 'Calendrier']];
  return `<nav class="subnav" aria-label="Parlement européen">${items.map(([h, l]) => `<a href="${h}"${h === active ? ' aria-current="page"' : ''}>${l}</a>`).join('')}</nav>`;
}
function head(title, lead, active, crumbs = '') {
  return `${crumbs ? `<div class="crumbs">${crumbs}</div>` : ''}<div class="page-head"><h1>${title}</h1>${lead ? `<p class="lead">${lead}</p>` : ''}${subnav(active)}</div>`;
}
const SOURCE_NOTE = `<p class="note src-note">Votes : <a href="https://howtheyvote.eu" target="_blank" rel="noopener">HowTheyVote.eu</a> (licence <a href="https://opendatacommons.org/licenses/odbl/1-0/" target="_blank" rel="noopener">ODbL</a>) · titres, parcours et fonctions : <a href="https://data.europarl.europa.eu" target="_blank" rel="noopener">open data du Parlement européen</a> · photos © Union européenne – Parlement européen.</p>`;

/** Ligne d'un vote : résultat du Parlement + vote des Français. */
function voteRow(v, E, extra = '') {
  const [fp, fc, fa] = v.fr;
  return `<a class="row striped" href="${LE.vote(v)}" style="--stripe:${v.adopte ? 'var(--pour)' : 'var(--contre)'}">
    <div class="grow">
      <div class="title">${esc(v.titre)}</div>
      <div class="meta"><span>${fdate(v.date, true)}</span>${typeChip(v.type, E)}${themeChip(v.theme, E)}${extra}</div>
    </div>
    <div class="side" style="min-width:190px">
      ${resChip(v.adopte)}
      <div style="margin-top:6px">${voteBar(v.p, v.c, v.a)}</div>
      <div class="tiny muted num" style="margin-top:4px">Français : ${nf(fp)} pour · ${nf(fc)} contre · ${nf(fa)} abst.</div>
    </div>
  </a>`;
}

function mepCard(d, E, extra = '') {
  const g = E.groupes.get(d.groupe), p = E.partis.get(d.parti);
  return `<a class="card link person" href="${LE.mep(d)}">${mepAvatar(d, g)}<span style="min-width:0"><span class="pname">${esc(d.prenom)} ${esc(d.nom)}</span><br>
    <span class="pmeta">${grpChip(g, false)} ${p ? esc(p.sigle) : ''}</span>${!d.actif ? `<br><span class="pmeta">${d.femme ? 'Ancienne eurodéputée' : 'Ancien eurodéputé'}</span>` : ''}${extra ? `<br><span class="pmeta"><b>${extra}</b></span>` : ''}</span></a>`;
}

/** Hémicycle du Parlement européen : 720 sièges par groupe, ceux des Français en couleur. */
function euSeats(E, mode) {
  const seats = [];
  for (const g of E.groupes) {
    const fr = [...E.meps.values()].filter(d => d.actif && d.groupe === g.code).sort((a, b) => (a.parti || '').localeCompare(b.parti || '') || a.nom.localeCompare(b.nom));
    for (const d of fr) {
      const p = E.partis.get(d.parti);
      seats.push({ color: mode === 'parti' && p ? p.couleur : g.couleur, key: g.code, href: LE.mep(d), tip: `${d.prenom} ${d.nom} · ${p?.sigle || ''} · ${g.sigle}` });
    }
    for (let i = fr.length; i < g.sieges; i++) {
      seats.push({ color: `color-mix(in srgb, ${g.couleur} 22%, var(--surface-2))`, key: g.code, tip: `${g.sigle} · eurodéputé d'un autre pays` });
    }
  }
  return seats;
}

// ─────────────────────────────────────────── Vue d'ensemble
export async function overview(el) {
  setTitle('Parlement européen');
  const E = await europe();
  const actifs = [...E.meps.values()].filter(d => d.actif);
  const today = new Date().toISOString().slice(0, 10);
  const next = E.sessions.filter(s => s.fin >= today);
  const lois = E.votes.filter(v => v.type === 'COD');
  const partis = E.partis.filter(p => p.n).sort((a, b) => b.n - a.n);
  const accord = E.accord;
  const pk = accord.partis.map(k => E.partis.get(k)).filter(Boolean);

  el.innerHTML = `<div class="page">
    ${head('Parlement européen', `Les ${nf(E.meta.fr)} eurodéputés élus en France, ce qu’ils votent et les textes européens. ${info("Le Parlement européen compte 720 membres élus pour 5 ans dans les 27 pays. Ils ne siègent pas par pays mais dans des groupes politiques européens. Seuls les votes finaux en séance plénière sont recensés ici, pas les milliers d’amendements.")}`, 'europe')}
    <div class="grid g4">
      ${statTile(nf(E.meta.fr), 'eurodéputés élus en France', `sur ${nf(E.meta.sieges)} au Parlement`, 'europe/eurodeputes', 'ue', '')}
      ${statTile(nf(E.votes.length), 'votes finaux', `depuis le ${fdate(E.meta.debut, true)}`, 'europe/votes', 'an', '')}
      ${statTile(nf(lois.filter(v => v.adopte).length), 'textes législatifs adoptés', 'règlements et directives', 'europe/textes?type=COD', 'loi', '')}
      ${statTile(next[0] ? fdate(next[0].debut, true) : '–', 'prochaine session plénière', next[0] ? `${esc(next[0].lieu || '')}${next[0].lieu ? ' · ' : ''}${relSession(next[0])}` : '', 'europe/calendrier', 'cc', '')}
    </div>

    <div class="two-col" style="margin-top:20px">
      <section class="card">
        <div class="section-title">${ttl('', 'Où siègent les Français', 'ue', 'h3')}${seg('hm', [['groupe', 'Par groupe'], ['parti', 'Par parti']], 'groupe')}</div>
        <div id="eu-hemi">${hemicycle(euSeats(E, 'groupe'), { label: nf(E.meta.fr), sub: `Français sur ${nf(E.meta.sieges)}` })}</div>
        <div class="legend">${E.groupes.filter(g => g.sieges).map(g => `<button data-hl="${g.code}" data-tip="${esc(g.nom)}"><i style="background:${g.couleur}"></i>${esc(g.sigle)} <span class="muted">${g.fr} / ${g.sieges}</span></button>`).join('')}</div>
        <p class="note" style="margin-top:8px">En couleur : les élus français. Les groupes vont de la gauche vers la droite de l’hémicycle.</p>
      </section>
      <aside>
        <section class="card">${ttl('', 'La délégation française', 'ue', 'h3')}
          <div style="margin-top:10px">${partis.map(p => `<a class="hbar link" href="europe/eurodeputes?parti=${encodeURIComponent(p.id)}" style="--bc:${p.couleur}"><span>${esc(p.sigle)} <span class="muted tiny">${esc(E.groupes.get(p.groupe)?.sigle || '')}</span></span><span class="num muted">${p.n}</span><div class="track"><span style="width:${(100 * p.n) / partis[0].n}%"></span></div></a>`).join('')}</div>
          <p class="note">Les partis français rejoignent un groupe européen : le RN siège chez les Patriotes, Renaissance chez Renew, LR au PPE…</p>
        </section>
      </aside>
    </div>

    <section class="block">
      <div class="section-title">${ttl('', 'Les derniers votes', 'an')}<a class="small" href="europe/votes">Tous les votes →</a></div>
      <div class="list">${E.votes.slice(0, 6).map(v => voteRow(v, E)).join('')}</div>
    </section>

    ${pk.length > 2 ? `<section class="block">
      <div class="section-title">${ttl('', 'Qui vote avec qui chez les Français', 'cmp')}</div>
      <p class="small muted" style="margin:-4px 0 12px">Part des votes finaux où les élus de deux partis ont eu la même position majoritaire. ${info('Calculé sur les votes où les deux partis ont voté. La position d’un parti est celle de la majorité de ses eurodéputés.')}</p>
      <div class="hm-wrap"><table class="hm"><thead><tr><th></th>${pk.map(p => `<th><span class="hm-colh">${esc(p.sigle)}</span></th>`).join('')}</tr></thead>
      <tbody>${pk.map((a, i) => `<tr><th scope="row">${partiChip(a)}</th>${pk.map((b, j) => {
        const v = accord.m[i][j];
        if (i === j || v == null) return '<td><span class="hm-cell empty"></span></td>';
        const t = Math.max(0, (v - 30) / 70);
        return `<td><span class="hm-cell" style="background:color-mix(in srgb, var(--cmp) ${Math.round(5 + t * 75)}%, var(--surface-2));color:${t > 0.6 ? '#fff' : 'var(--ink)'}" data-tip="${esc(a.sigle)} et ${esc(b.sigle)} : même position dans ${v} % des votes">${v}</span></td>`;
      }).join('')}</tr>`).join('')}</tbody></table></div>
    </section>` : ''}

    <div class="grid g2 block">
      <section class="card">${ttl('', 'Prochaines sessions', 'cc', 'h3')}
        <div class="list" style="margin-top:10px">${next.slice(0, 4).map(s => sessionRow(s)).join('') || '<p class="muted small">Calendrier non publié.</p>'}</div>
        <a class="small" href="europe/calendrier" style="display:inline-block;margin-top:10px">Tout le calendrier →</a>
      </section>
      <section class="card">${ttl('', 'Comment ça marche', 'gouv', 'h3')}
        <ul class="small explain">
          <li>La <b>Commission européenne</b> propose les lois de l’Union.</li>
          <li>Le <b>Parlement</b> (élu par les citoyens) et le <b>Conseil</b> (les ministres des 27 pays) les amendent et les votent, souvent après une négociation à trois appelée <b>trilogue</b>.</li>
          <li>Un <b>règlement</b> s’applique directement en France ; une <b>directive</b> doit être transposée par une loi française, votée à l’Assemblée et au Sénat.</li>
          <li>Le Parlement vote aussi le <b>budget</b> de l’Union, approuve les accords commerciaux et adopte des <b>résolutions</b> sur l’actualité.</li>
        </ul>
      </section>
    </div>
    ${SOURCE_NOTE}
  </div>`;
  const box = el.querySelector('#eu-hemi').parentElement;
  wireHemicycle(box);
  wireSeg(el, 'hm', mode => {
    el.querySelector('#eu-hemi').innerHTML = hemicycle(euSeats(E, mode), { label: nf(E.meta.fr), sub: `Français sur ${nf(E.meta.sieges)}` });
  });
}

function relSession(s) {
  const n = -daysAgo(s.debut);
  if (n <= 0 && s.fin >= new Date().toISOString().slice(0, 10)) return 'en cours';
  return n === 1 ? 'demain' : `dans ${n} jours`;
}
function sessionRow(s) {
  const same = s.debut === s.fin;
  const when = same ? fdateDay(s.debut) : `Du ${fdate(s.debut).replace(/ \d{4}$/, '')} au ${fdate(s.fin)}`;
  return `<${s.votes ? `a href="europe/votes?du=${s.debut}&au=${s.fin}"` : 'div'} class="row" style="padding:10px 14px">
    <div class="grow"><div class="small" style="font-weight:600;color:var(--ink)">${when}</div>
      <div class="meta">${s.lieu ? `<span class="chip ${s.lieu === 'Strasbourg' ? 'ue' : ''}">${esc(s.lieu)}</span>` : ''}${s.avenir ? `<span>${relSession(s)}</span>` : ''}</div></div>
    <div class="side small muted">${s.votes ? plural(s.votes, 'vote final', 'votes finaux') : s.avenir ? '' : '—'}</div>
  </${s.votes ? 'a' : 'div'}>`;
}

// ─────────────────────────────────────────── Eurodéputés
export async function meps(el) {
  setTitle('Eurodéputés français');
  const E = await europe();
  const p = hashParams();
  const st = { q: p.q || '', parti: p.parti || '', groupe: p.groupe || '', tri: p.tri || 'nom', anciens: p.anciens === '1' };
  const all = [...E.meps.values()];
  el.innerHTML = `<div class="page">
    ${head('Eurodéputés élus en France', 'Leur groupe européen, leur parti, leur présence et leur loyauté.', 'europe/eurodeputes', '<a href="europe">Parlement européen</a>')}
    <div class="filters">
      <input type="search" id="f-q" placeholder="Nom, parti, commission…" value="${esc(st.q)}">
      <select id="f-p"><option value="">Tous les partis</option>${E.partis.filter(x => x.n).map(x => `<option value="${esc(x.id)}"${x.id === st.parti ? ' selected' : ''}>${esc(x.sigle)} — ${esc(x.nom)}</option>`).join('')}</select>
      <select id="f-g"><option value="">Tous les groupes</option>${E.groupes.filter(g => g.fr).map(g => `<option value="${g.code}"${g.code === st.groupe ? ' selected' : ''}>${esc(g.sigle)} — ${esc(g.nom)}</option>`).join('')}</select>
      <select id="f-tri"><option value="nom">Ordre alphabétique</option><option value="participation"${st.tri === 'participation' ? ' selected' : ''}>Participation aux votes</option><option value="groupe"${st.tri === 'groupe' ? ' selected' : ''}>Les plus indépendants de leur groupe</option><option value="parti"${st.tri === 'parti' ? ' selected' : ''}>Les plus indépendants de leur parti</option><option value="age"${st.tri === 'age' ? ' selected' : ''}>Âge</option></select>
      <label class="check"><input type="checkbox" id="f-anc"${st.anciens ? ' checked' : ''}> Inclure les anciens eurodéputés</label>
    </div>
    <div class="count-line" id="count"></div><div id="results"></div>
    ${SOURCE_NOTE}
  </div>`;
  const update = () => {
    setHashParams({ ...st, tri: st.tri === 'nom' ? '' : st.tri, anciens: st.anciens ? '1' : '' });
    const q = norm(st.q).split(/\s+/).filter(Boolean);
    let items = all.filter(d => (st.anciens || d.actif) && (!st.parti || d.parti === st.parti) && (!st.groupe || d.groupe === st.groupe) &&
      (!q.length || q.every(w => norm(`${d.prenom} ${d.nom} ${E.partis.get(d.parti)?.sigle || ''} ${E.partis.get(d.parti)?.nom || ''} ${E.groupes.get(d.groupe)?.sigle || ''} ${d.commissions.map(c => c.nom).join(' ')}`).includes(w))));
    const s = d => d.stats;
    if (st.tri === 'participation') items = items.filter(d => s(d).participation != null).sort((a, b) => s(b).participation - s(a).participation);
    if (st.tri === 'groupe') items = items.filter(d => s(d).loyauteGroupe != null).sort((a, b) => s(a).loyauteGroupe - s(b).loyauteGroupe);
    if (st.tri === 'parti') items = items.filter(d => s(d).loyautePartie != null).sort((a, b) => s(a).loyautePartie - s(b).loyautePartie);
    if (st.tri === 'age') items.sort((a, b) => (a.naissance || '9').localeCompare(b.naissance || '9'));
    el.querySelector('#count').textContent = plural(items.length, 'eurodéputé');
    const extra = d => st.tri === 'participation' ? `participation ${pct(s(d).participation)}` : st.tri === 'groupe' ? `vote comme son groupe : ${pct(s(d).loyauteGroupe)}` : st.tri === 'parti' ? `vote comme son parti : ${pct(s(d).loyautePartie)}` : st.tri === 'age' && d.naissance ? `${age(d.naissance)} ans` : '';
    paged(el.querySelector('#results'), items, d => mepCard(d, E, extra(d)), 48, 'people');
  };
  el.querySelector('#f-q').addEventListener('input', debounce(e => { st.q = e.target.value; update(); }));
  for (const [id, k] of [['f-p', 'parti'], ['f-g', 'groupe'], ['f-tri', 'tri']]) el.querySelector('#' + id).addEventListener('change', e => { st[k] = e.target.value; update(); });
  el.querySelector('#f-anc').addEventListener('change', e => { st.anciens = e.target.checked; update(); });
  update();
}

export async function mep(el, slug) {
  const E = await europe();
  const d = E.bySlug.get(slug) || E.meps.get(slug);
  if (!d) { el.innerHTML = '<div class="page"><h1>Eurodéputé introuvable</h1><p><a href="europe/eurodeputes">Tous les eurodéputés français</a></p></div>'; return; }
  setTitle(`${d.prenom} ${d.nom}, eurodéputé${d.femme ? 'e' : ''}`);
  const g = E.groupes.get(d.groupe), p = E.partis.get(d.parti);
  const s = d.stats;
  const T = await textes();
  const rapports = (d.rapports || []).map(([sl, role]) => [T.bySlug.get(sl), role]).filter(([t]) => t);
  const titre = d.femme ? 'Eurodéputée' : 'Eurodéputé';
  const tab = ['apercu', 'votes', 'rapports'].includes(hashParams().tab) ? hashParams().tab : 'apercu';
  const titulaires = d.commissions.filter(c => c.titulaire);
  el.innerHTML = `<div class="page">
    <div class="crumbs"><a href="europe">Parlement européen</a> › <a href="europe/eurodeputes">Eurodéputés</a></div>
    <div class="profile page-head">
      ${mepAvatar(d, g, 'lg')}
      <div class="info">
        <h1>${esc(d.prenom)} ${esc(d.nom)}</h1>
        <div class="facts">
          <span>${titre}${d.actif ? '' : d.femme ? ' (ancienne)' : ' (ancien)'} élu${d.femme ? 'e' : ''} en France</span>
          ${g ? `<span>${grpChip(g)} ${esc(g.nom)}</span>` : ''}
          ${p ? `<span>${partiChip(p)} ${esc(p.nom)}</span>` : ''}
        </div>
        <div class="facts small muted" style="margin-top:6px">
          ${d.naissance ? `<span>${age(d.naissance)} ans</span>` : ''}
          ${d.debut ? `<span>Au Parlement depuis le ${fdate(d.debut)}</span>` : ''}
          ${!d.actif && d.fin ? `<span>Mandat terminé le ${fdate(d.fin)}</span>` : ''}
        </div>
        ${d.fonctions?.length ? `<div style="margin-top:8px">${d.fonctions.map(f => `<span class="role-pill">${esc(f)}</span>`).join('')}</div>` : ''}
        <div class="head-actions">${shareBtn()}<a class="btn small" href="https://www.europarl.europa.eu/meps/fr/${d.id}" target="_blank" rel="noopener">Fiche officielle</a></div>
      </div>
    </div>
    ${tabsHtml('m', [['apercu', 'Vue d’ensemble'], ['votes', 'Votes'], ['rapports', `Rapports (${rapports.length})`]], tab)}
    <div data-panel-of="m" data-panel="apercu">
      <div class="grid g4">
        ${statTile(pct(s.participation), `présence aux votes ${info('Part des votes finaux en séance plénière auxquels l’eurodéputé a pris part, depuis le début de son mandat.')}`, `${nf(s.votes)} votes sur ${nf(s.total)}`, null, 'loi', '')}
        ${statTile(pct(s.loyauteGroupe), `vote comme son groupe ${info('Part des votes où sa position est celle de la majorité de son groupe européen (tous pays confondus).')}`, g ? esc(g.sigle) : '', null, 'ue', '')}
        ${statTile(pct(s.loyautePartie), `vote comme son parti ${info('Part des votes où sa position est celle de la majorité des eurodéputés français de son parti.')}`, p ? esc(p.sigle) : '', null, 'cmp', '')}
        ${statTile(nf(rapports.filter(([, r]) => r === 'rapporteur').length), 'textes comme rapporteur', rapports.length ? `et ${plural(rapports.filter(([, r]) => r !== 'rapporteur').length, 'comme rapporteur fictif', 'comme rapporteur fictif')}` : '', null, 'cc', '')}
      </div>
      <div class="two-col" style="margin-top:20px">
        <div>
          <section class="card">${ttl('', 'Ses votes en un coup d’œil', 'cmp', 'h3')}
            ${voteBar(s.pour, s.contre, s.abstention, 0, true)}${voteLabels(s.pour, s.contre, s.abstention)}</section>
          <section class="block">
            <div class="section-title">${ttl('', 'Ses derniers votes', 'an')}<a class="small" href="${LE.mep(d)}?tab=votes" data-goto="votes">Tous ses votes →</a></div>
            <div id="last"></div>
          </section>
        </div>
        <aside>
          <section class="card">${ttl('', 'En bref', 'cc', 'h3')}
            <dl class="kv small" style="margin-top:10px">
              ${g ? `<dt>Groupe</dt><dd>${esc(g.nom)}</dd>` : ''}
              ${p ? `<dt>Parti</dt><dd>${esc(p.nom)}</dd>` : ''}
              ${titulaires.length ? `<dt>Commissions</dt><dd>${titulaires.map(c => `${esc(c.nom)}${c.role !== 'Membre' ? ` <span class="muted">(${esc(c.role.toLowerCase())})</span>` : ''}`).join('<br>')}</dd>` : ''}
              ${d.commissions.length > titulaires.length ? `<dt>Suppléant${d.femme ? 'e' : ''}</dt><dd>${d.commissions.filter(c => !c.titulaire).map(c => esc(c.nom)).join('<br>')}</dd>` : ''}
              ${d.naissance ? `<dt>Naissance</dt><dd>${fdate(d.naissance)}${d.lieuNaissance ? `<br><span class="muted">${esc(d.lieuNaissance)}</span>` : ''}</dd>` : ''}
              ${d.historiqueGroupes?.length ? `<dt>Groupes</dt><dd>${d.historiqueGroupes.map(([c, a, b]) => `${esc(E.groupes.get(c)?.sigle || c)} <span class="muted">· ${fdate(a, true)} → ${b ? fdate(b, true) : "aujourd'hui"}</span>`).join('<br>')}</dd>` : ''}
            </dl>
            <p class="small" style="margin-top:12px">
              ${d.email ? `<a href="mailto:${esc(d.email)}">${esc(d.email)}</a><br>` : ''}
              <a class="ext" href="https://www.europarl.europa.eu/meps/fr/${d.id}" target="_blank" rel="noopener">Fiche sur le site du Parlement européen</a><br>
              <a class="ext" href="https://howtheyvote.eu/members/${d.id}" target="_blank" rel="noopener">Tous ses votes sur HowTheyVote.eu</a></p>
          </section>
        </aside>
      </div>
    </div>
    <div data-panel-of="m" data-panel="votes">
      <div class="filters">${seg('vf', [['tous', 'Tous'], ['groupe', 'Autrement que son groupe'], ['parti', 'Autrement que son parti'], ['absent', 'Absences']], 'tous')}
        <select id="f-th"><option value="">Tous les thèmes</option>${Object.entries(E.themes).map(([k, l]) => `<option value="${k}">${esc(l)}</option>`).join('')}</select></div>
      <div id="mvotes"></div>
    </div>
    <div data-panel-of="m" data-panel="rapports">
      ${rapports.length ? `<div class="list">${rapports.map(([t, role]) => texteRow(t, E, `<span class="chip">${esc(role)}</span>`)).join('')}</div>
        <p class="note">Le rapporteur prépare la position du Parlement sur un texte au nom de sa commission. Les rapporteurs fictifs suivent le texte pour les autres groupes.</p>`
        : '<div class="empty">Aucun rapport sur un texte voté en séance depuis le début de la législature.</div>'}
    </div>
    ${SOURCE_NOTE}
  </div>`;
  wireTabs(el, 'm');
  el.querySelector('[data-goto]')?.addEventListener('click', e => { e.preventDefault(); el.querySelector('[data-tab="votes"]').click(); scrollTo(0, 0); });

  const chain = E.chains[d.id] || '';
  const rows = [];
  for (let i = E.chrono.length - 1; i >= 0; i--) {
    const k = chain[i];
    if (!k || k === '-') continue;
    const v = E.vById.get(E.chrono[i]);
    const gp = v.g[d.groupe] ? majority(v.g[d.groupe]) : null;
    const pp = v.partis[d.parti];
    rows.push({ v, k, horsGroupe: k !== '.' && gp && gp !== k, horsParti: k !== '.' && pp && pp !== k, gp, pp });
  }
  const line = r => `<a class="row" href="${LE.vote(r.v)}" style="padding:10px 14px">
      <div class="grow"><div class="small" style="color:var(--ink);font-weight:550">${esc(r.v.titre)}</div>
        <div class="meta"><span>${fdate(r.v.date, true)}</span>${typeChip(r.v.type, E)}${resChip(r.v.adopte)}${r.horsGroupe ? `<span class="chip" style="color:var(--warn)" data-tip="Son groupe a voté majoritairement ${LBL[r.gp].toLowerCase()}">≠ son groupe</span>` : ''}${r.horsParti ? `<span class="chip" style="color:var(--warn)" data-tip="Son parti a voté majoritairement ${LBL[r.pp].toLowerCase()}">≠ son parti</span>` : ''}</div></div>
      <div class="side" style="min-width:110px">${posChip(r.k)}</div></a>`;
  el.querySelector('#last').innerHTML = `<div class="list">${rows.slice(0, 5).map(line).join('') || '<div class="empty">Aucun vote.</div>'}</div>`;
  const st = { f: 'tous', th: '' };
  const draw = () => {
    const items = rows.filter(r => (!st.th || r.v.theme === st.th) && (st.f === 'tous' || (st.f === 'groupe' && r.horsGroupe) || (st.f === 'parti' && r.horsParti) || (st.f === 'absent' && r.k === '.')));
    paged(el.querySelector('#mvotes'), items, line, 20);
  };
  wireSeg(el, 'vf', v => { st.f = v; draw(); });
  el.querySelector('#f-th').addEventListener('change', e => { st.th = e.target.value; draw(); });
  draw();
}

// ─────────────────────────────────────────── Votes
const VTYPES = [['', 'Tous'], ['COD', 'Législation'], ['RSP', 'Résolutions'], ['INI', 'Rapports'], ['NLE', 'Approbations'], ['BUD', 'Budget']];
export async function votesList(el) {
  setTitle('Votes du Parlement européen');
  const E = await europe();
  const p = hashParams();
  const st = { type: p.type || '', theme: p.theme || '', q: p.q || '', res: p.res || '', du: p.du || '', au: p.au || '', fr: p.fr || '' };
  el.innerHTML = `<div class="page">
    ${head('Votes du Parlement européen', `Chaque vote final en séance plénière, avec la position des eurodéputés français. ${info('Un vote « final » porte sur l’ensemble d’un texte (ou sur l’accord trouvé avec le Conseil). Les votes sur les amendements ne sont pas repris ici.')}`, 'europe/votes', '<a href="europe">Parlement européen</a>')}
    <div class="filters">${seg('type', VTYPES, st.type)}</div>
    <div class="filters">
      <input type="search" id="f-q" placeholder="Rechercher un texte…" value="${esc(st.q)}">
      <select id="f-th"><option value="">Tous les thèmes</option>${Object.entries(E.themes).map(([k, l]) => `<option value="${k}"${k === st.theme ? ' selected' : ''}>${esc(l)}</option>`).join('')}</select>
      <select id="f-res"><option value="">Adoptés et rejetés</option><option value="1"${st.res === '1' ? ' selected' : ''}>Adoptés</option><option value="0"${st.res === '0' ? ' selected' : ''}>Rejetés</option></select>
      <select id="f-fr"><option value="">Tous les votes</option><option value="divise"${st.fr === 'divise' ? ' selected' : ''}>Les Français divisés</option><option value="contre"${st.fr === 'contre' ? ' selected' : ''}>Les Français contre, le Parlement pour</option></select>
    </div>
    ${st.du ? `<p class="note">Session du ${fdate(st.du)}${st.au && st.au !== st.du ? ` au ${fdate(st.au)}` : ''} · <a href="europe/votes" id="clear-s">voir toutes les sessions</a></p>` : ''}
    <div class="count-line" id="count"></div><div id="results"></div>
    ${SOURCE_NOTE}
  </div>`;
  const update = () => {
    setHashParams(st);
    const q = norm(st.q).split(/\s+/).filter(Boolean);
    const items = E.votes.filter(v => {
      if (st.type && !(v.type === st.type || (st.type === 'BUD' && ['BUD', 'BUI', 'DEC'].includes(v.type)) || (st.type === 'NLE' && ['NLE', 'APP', 'CNS'].includes(v.type)))) return false;
      if (st.theme && v.theme !== st.theme) return false;
      if (st.res && String(+v.adopte) !== st.res) return false;
      if (st.du && (v.date < st.du || v.date > (st.au || st.du))) return false;
      if (st.fr === 'divise') { const [fp, fc] = v.fr; if (Math.min(fp, fc) < 0.3 * (fp + fc) || fp + fc < 10) return false; }
      if (st.fr === 'contre' && !(v.adopte && v.fr[1] > v.fr[0])) return false;
      if (q.length) { const t = norm(`${v.titre} ${v.titreEn} ${v.ref || ''}`); if (!q.every(w => t.includes(w))) return false; }
      return true;
    });
    el.querySelector('#count').textContent = plural(items.length, 'vote');
    paged(el.querySelector('#results'), items, v => voteRow(v, E));
  };
  wireSeg(el, 'type', v => { st.type = v; update(); });
  el.querySelector('#f-q').addEventListener('input', debounce(e => { st.q = e.target.value; update(); }));
  for (const [id, k] of [['f-th', 'theme'], ['f-res', 'res'], ['f-fr', 'fr']]) el.querySelector('#' + id).addEventListener('change', e => { st[k] = e.target.value; update(); });
  update();
}

function docUrl(ta) {
  // P10_TA(2026)0328 → TA-10-2026-0328
  const m = /P(\d+)_TA\((\d{4})\)(\d+)/.exec(ta || '');
  return m ? `https://www.europarl.europa.eu/doceo/document/TA-${m[1]}-${m[2]}-${m[3].padStart(4, '0')}_FR.html` : null;
}
const oeil = ref => `https://oeil.secure.europarl.europa.eu/oeil/fr/procedure-file?reference=${encodeURIComponent(ref)}`;

export async function voteDetail(el, id) {
  const E = await europe();
  const v = E.vById.get(+id);
  if (!v) { el.innerHTML = '<div class="page"><h1>Vote introuvable</h1><p><a href="europe/votes">Tous les votes</a></p></div>'; return; }
  setTitle(eu(v.titre, 80));
  const idx = E.vIndex.get(v.id);
  const fr = [];
  for (const d of E.meps.values()) {
    const k = (E.chains[d.id] || '')[idx];
    if (k && k !== '-') fr.push({ d, k });
  }
  const byParti = new Map();
  for (const x of fr) {
    const key = x.d.parti || 'Sans parti';
    if (!byParti.has(key)) byParti.set(key, []);
    byParti.get(key).push(x);
  }
  const partis = [...byParti].map(([k, xs]) => ({ p: E.partis.get(k) || { id: k, sigle: k, nom: k, couleur: '#999' }, xs }))
    .sort((a, b) => (E.groupes.get(a.p.groupe)?.ordre ?? 99) - (E.groupes.get(b.p.groupe)?.ordre ?? 99) || b.xs.length - a.xs.length);
  const groups = E.groupes.filter(g => v.g[g.code]);
  const seats = [];
  for (const g of groups) {
    const [p, c, a, n] = v.g[g.code];
    for (const [k, m] of [['p', p], ['a', a], ['c', c], ['.', n]]) for (let i = 0; i < m; i++) seats.push({ k, g, tip: `${g.sigle} — ${LBL[k]}` });
  }
  const seatsBy = mode => seats.map(x => ({ ...x, color: mode === 'groupe' ? (x.k === '.' ? 'var(--absent)' : x.g.couleur) : COLORS[x.k], key: mode === 'groupe' ? x.g.code : x.k }));
  const T = await textes();
  const t = v.texte && T.bySlug.get(v.texte);
  const [fp, fc, fa, fn] = v.fr;
  const rebels = [];
  for (const { p, xs } of partis) {
    const pm = v.partis[p.id];
    if (!pm) continue;
    for (const x of xs) if (x.k !== '.' && x.k !== pm) rebels.push({ ...x, pm, p });
  }
  const ta = docUrl(v.ta);
  el.innerHTML = `<div class="page">
    <div class="crumbs"><a href="europe">Parlement européen</a> › <a href="europe/votes">Votes</a></div>
    <div class="page-head">
      <div class="pill-row" style="margin-bottom:10px">${typeChip(v.type, E)}${themeChip(v.theme, E)}<span class="chip">${fdate(v.date)}</span></div>
      <h1 style="font-size:clamp(1.15rem,2.2vw,1.4rem);line-height:1.35">${esc(v.titre)}</h1>
      ${t && t.votes.length > 1 ? `<p>Texte concerné : <a href="${LE.texte(t)}">${esc(eu(t.titre, 120))}</a></p>` : ''}
      <div class="head-actions">${shareBtn()}${t ? `<a class="btn small" href="${LE.texte(t)}">Parcours du texte</a>` : ''}</div>
    </div>
    <div class="grid g4" style="margin-bottom:18px">
      ${statTile(v.adopte ? '✓ Adopté' : '✕ Rejeté', 'par le Parlement européen', '', null, v.adopte ? 'loi' : 'contre', '')}
      ${statTile(nf(v.p), 'pour', `dont ${nf(fp)} Français`, null, 'pour', '')}
      ${statTile(nf(v.c), 'contre', `dont ${nf(fc)} Français`, null, 'contre', '')}
      ${statTile(nf(v.a), 'abstentions', `dont ${nf(fa)} Français`, null, 'abst', '')}
    </div>
    <div class="two-col">
      <div>
        <section class="card">
          <div class="section-title">${ttl('', 'Comment ont voté les Français ?', 'ue', 'h3')}</div>
          ${voteBar(fp, fc, fa, fn, true)}${voteLabels(fp, fc, fa)}
          <div class="tbl-wrap" style="margin-top:14px"><table class="tbl">
            <thead><tr><th>Parti</th><th>Position</th><th style="min-width:140px">Répartition</th><th class="n">Pour</th><th class="n">Contre</th><th class="n">Abst.</th><th class="n">Absents</th></tr></thead>
            <tbody>${partis.map(({ p, xs }) => {
              const n = k => xs.filter(x => x.k === k).length;
              const pm = v.partis[p.id];
              return `<tr><td>${partiChip(p)} <span class="tiny muted">${esc(E.groupes.get(p.groupe)?.sigle || '')}</span></td><td>${pm ? posChip(pm) : '<span class="pos pos-n">—</span>'}</td>
                <td>${voteBar(n('p'), n('c'), n('a'), n('.'))}</td><td class="n">${n('p')}</td><td class="n">${n('c')}</td><td class="n">${n('a')}</td><td class="n muted">${n('.')}</td></tr>`;
            }).join('')}</tbody></table></div>
        </section>

        ${rebels.length ? `<section class="block">
          ${ttl('', `Ils ont voté autrement que leur parti (${rebels.length})`, 'cc')}<div style="height:12px"></div>
          <div class="people">${rebels.map(r => `<a class="card link person" href="${LE.mep(r.d)}" style="padding:10px 12px"><span><span class="pname">${esc(r.d.prenom)} ${esc(r.d.nom)}</span><br><span class="pmeta">${esc(r.p.sigle)} majoritairement ${LBL[r.pm].toLowerCase()} · a voté <b>${LBL[r.k].toLowerCase()}</b></span></span></a>`).join('')}</div>
        </section>` : ''}

        <section class="block">
          ${ttl('', 'Le détail nominatif des Français', 'an')}<div style="height:12px"></div>
          ${tabsHtml('nom', ['p', 'c', 'a', '.'].map(k => [k === '.' ? 'x' : k, `${LBL[k]} (${fr.filter(x => x.k === k).length})`]), 'p')}
          ${['p', 'c', 'a', '.'].map(k => `<div data-panel-of="nom" data-panel="${k === '.' ? 'x' : k}">${partis.filter(({ xs }) => xs.some(x => x.k === k)).map(({ p, xs }) => `<div style="margin-bottom:14px"><div style="margin-bottom:6px">${partiChip(p)} <span class="muted small">${xs.filter(x => x.k === k).length}</span></div>
            <div class="small" style="line-height:1.9">${xs.filter(x => x.k === k).map(x => `<a href="${LE.mep(x.d)}">${esc(x.d.prenom)} ${esc(x.d.nom)}</a>`).join(', ')}</div></div>`).join('') || '<p class="muted">Personne.</p>'}</div>`).join('')}
        </section>

        <section class="block card">
          <div class="section-title">${ttl('', 'Tout le Parlement', 'gouv', 'h3')}${seg('mode', [['vote', 'Par vote'], ['groupe', 'Par groupe']], 'vote')}</div>
          <div id="hemi">${hemicycle(seatsBy('vote'), { label: nf(v.p), sub: `pour · ${nf(v.c)} contre` })}</div>
          <div class="tbl-wrap" style="margin-top:10px"><table class="tbl">
            <thead><tr><th>Groupe</th><th>Position</th><th style="min-width:140px">Répartition</th><th class="n">Pour</th><th class="n">Contre</th><th class="n">Abst.</th></tr></thead>
            <tbody>${groups.map(g => { const [p, c, a, n] = v.g[g.code]; const m = majority(v.g[g.code]); return `<tr><td>${grpChip(g)} <span class="tiny muted">${esc(g.nom)}</span></td><td>${m ? posChip(m) : '—'}</td><td>${voteBar(p, c, a, n)}</td><td class="n">${p}</td><td class="n">${c}</td><td class="n">${a}</td></tr>`; }).join('')}</tbody></table></div>
        </section>
      </div>
      <aside>
        <section class="card">${ttl('', 'Ce vote', 'cc', 'h3')}
          <dl class="kv small" style="margin-top:10px">
            <dt>Date</dt><dd>${fdate(v.date)} à ${v.heure.replace(':', 'h')}</dd>
            ${v.type ? `<dt>Procédure</dt><dd>${esc(E.types[v.type]?.[0] || v.type)}<br><span class="muted">${esc(E.types[v.type]?.[1] || '')}</span></dd>` : ''}
            ${v.lecture ? `<dt>Étape</dt><dd>${{ OLP_FIRST_READING: 'Première lecture', OLP_SECOND_READING: 'Deuxième lecture', OLP_THIRD_READING: 'Troisième lecture' }[v.lecture] || ''}</dd>` : ''}
            ${v.commission ? `<dt>Commission</dt><dd>${esc(E.commissions[v.commission] || v.commission)}</dd>` : ''}
            ${v.ref ? `<dt>Référence</dt><dd>${esc(v.ref)}</dd>` : ''}
            <dt>Votants</dt><dd>${nf(v.p + v.c + v.a)} sur ${nf(v.p + v.c + v.a + v.nv)}</dd>
          </dl>
          <p class="small" style="margin-top:12px">
            ${ta ? `<a class="ext" href="${ta}" target="_blank" rel="noopener">Texte adopté</a><br>` : ''}
            ${v.ref ? `<a class="ext" href="${oeil(v.ref)}" target="_blank" rel="noopener">Fiche de procédure (Observatoire législatif)</a><br>` : ''}
            <a class="ext" href="https://howtheyvote.eu/votes/${v.id}" target="_blank" rel="noopener">Le vote sur HowTheyVote.eu</a></p>
          ${v.titreEn && v.titreEn !== v.titre ? `<p class="tiny muted">Titre anglais : ${esc(v.titreEn)}</p>` : ''}
        </section>
        <section class="card" style="margin-top:16px">${ttl('', 'Comment le lire ?', 'gouv', 'h3')}
          <p class="small">Un texte est adopté s’il recueille plus de voix « pour » que « contre ». La position d’un parti est celle de la majorité de ses eurodéputés français.</p>
          <p class="small">Le Parlement vote souvent l’accord négocié avec le Conseil : pour qu’une loi européenne entre en vigueur, le Conseil (les gouvernements) doit aussi l’adopter.</p>
        </section>
      </aside>
    </div>
    ${SOURCE_NOTE}
  </div>`;
  wireTabs(el, 'nom');
  wireSeg(el, 'mode', mode => { el.querySelector('#hemi').innerHTML = hemicycle(seatsBy(mode), { label: nf(v.p), sub: `pour · ${nf(v.c)} contre` }); });
}

// ─────────────────────────────────────────── Textes
function texteRow(t, E, extra = '') {
  return `<a class="row striped" href="${LE.texte(t)}" style="--stripe:${t.adopte ? 'var(--pour)' : 'var(--contre)'}">
    <div class="grow"><div class="title">${esc(t.titre)}</div>
      <div class="meta">${typeChip(t.type, E)}${themeChip(t.theme, E)}<span>dernier vote le ${fdate(t.date, true)}</span>${t.votes.length > 1 ? `<span>${t.votes.length} votes</span>` : ''}${extra}</div></div>
    <div class="side">${resChip(t.adopte)}</div></a>`;
}
const TTYPES = [['', 'Tous'], ['COD', 'Législation'], ['RSP', 'Résolutions'], ['INI', 'Rapports'], ['NLE', 'Approbations'], ['BUD', 'Budget']];
export async function textesList(el) {
  setTitle('Textes européens');
  const [E, T] = await Promise.all([europe(), textes()]);
  const p = hashParams();
  const st = { type: p.type ?? 'COD', theme: p.theme || '', q: p.q || '' };
  el.innerHTML = `<div class="page">
    ${head('Textes européens', `Les lois, budgets, accords et résolutions votés par le Parlement européen. ${info('Les règlements et directives (« législation ») sont co-décidés avec le Conseil, qui réunit les ministres des 27 pays. Les résolutions et rapports d’initiative expriment la position du Parlement sans créer de règle.')}`, 'europe/textes', '<a href="europe">Parlement européen</a>')}
    <div class="filters">${seg('type', TTYPES, st.type)}</div>
    <div class="filters">
      <input type="search" id="f-q" placeholder="Rechercher un texte…" value="${esc(st.q)}">
      <select id="f-th"><option value="">Tous les thèmes</option>${Object.entries(E.themes).map(([k, l]) => `<option value="${k}"${k === st.theme ? ' selected' : ''}>${esc(l)}</option>`).join('')}</select>
    </div>
    <div class="count-line" id="count"></div><div id="results"></div>
    ${SOURCE_NOTE}
  </div>`;
  const update = () => {
    setHashParams({ ...st, type: st.type === 'COD' ? '' : st.type || 'tous' });
    const q = norm(st.q).split(/\s+/).filter(Boolean);
    const type = st.type === 'tous' ? '' : st.type;
    const items = T.list.filter(t => (!type || t.type === type || (type === 'BUD' && ['BUD', 'BUI', 'DEC'].includes(t.type)) || (type === 'NLE' && ['NLE', 'APP', 'CNS'].includes(t.type))) &&
      (!st.theme || t.theme === st.theme) && (!q.length || q.every(w => norm(`${t.titre} ${t.titreEn} ${t.ref}`).includes(w))));
    el.querySelector('#count').textContent = plural(items.length, 'texte');
    paged(el.querySelector('#results'), items, t => texteRow(t, E));
  };
  wireSeg(el, 'type', v => { st.type = v || 'tous'; update(); });
  el.querySelector('#f-q').addEventListener('input', debounce(e => { st.q = e.target.value; update(); }));
  el.querySelector('#f-th').addEventListener('change', e => { st.theme = e.target.value; update(); });
  update();
}

const ACTEUR = { commission: ['Commission parlementaire', 'var(--ue)'], pe: ['Séance plénière', 'var(--an)'], trilogue: ['Négociation', 'var(--cmp)'], conseil: ['Conseil de l’UE', 'var(--gouv)'], fin: ['Adoption finale', 'var(--loi)'] };
const STEPS_COD = [['Proposition', 'La Commission européenne propose le texte'], ['Commission parlementaire', 'Un rapporteur prépare la position du Parlement'], ['Plénière', 'Les 720 eurodéputés votent'], ['Trilogue', 'Parlement, Conseil et Commission négocient un compromis'], ['Adoption', 'Le Parlement et le Conseil adoptent le texte final']];

export async function texte(el, slug) {
  const [E, T] = await Promise.all([europe(), textes()]);
  const t = T.bySlug.get(slug);
  if (!t) { el.innerHTML = '<div class="page"><h1>Texte introuvable</h1><p><a href="europe/textes">Tous les textes</a></p></div>'; return; }
  setTitle(eu(t.titre, 80));
  const vs = t.votes.map(id => E.vById.get(id)).filter(Boolean).sort((a, b) => a.date.localeCompare(b.date) || a.heure.localeCompare(b.heure));
  const last = vs[vs.length - 1];
  // Frise : étapes de procédure + votes en plénière
  const items = t.etapes.filter(([, l]) => !/^Vote en séance|^Position adoptée|^Décision en séance|^Texte déposé/.test(l)).map(([d, l, a]) => ({ d, l, a }));
  for (const v of vs) items.push({ d: v.date, l: v.adopte ? 'Adopté en séance plénière' : 'Rejeté en séance plénière', a: 'pe', v });
  items.sort((a, b) => a.d.localeCompare(b.d) || (a.v ? 1 : 0) - (b.v ? 1 : 0));
  const isCod = t.type === 'COD';
  const done = isCod ? (t.etapes.some(([, , a]) => a === 'fin') ? 5 : t.etapes.some(([, , a]) => a === 'trilogue') || t.lecture === 'OLP_SECOND_READING' ? (last?.adopte ? 4 : 3) : last ? 3 : 2) : 0;
  const rapp = t.rapporteurs.filter(r => r.role === 'rapporteur');
  const shadows = t.rapporteurs.filter(r => r.role !== 'rapporteur');
  el.innerHTML = `<div class="page">
    <div class="crumbs"><a href="europe">Parlement européen</a> › <a href="europe/textes">Textes</a></div>
    <div class="page-head">
      <div class="pill-row" style="margin-bottom:10px">${typeChip(t.type, E)}${themeChip(t.theme, E)}<span class="chip">${esc(t.ref)}</span></div>
      <h1 style="font-size:clamp(1.2rem,2.4vw,1.6rem);line-height:1.3">${esc(t.titre)}</h1>
      <p class="lead small">${esc(E.types[t.type]?.[1] || '')}</p>
      <div class="head-actions">${shareBtn()}<a class="btn small" href="${oeil(t.ref)}" target="_blank" rel="noopener">Fiche officielle</a></div>
    </div>
    ${isCod ? `<section class="card eu-path">
      ${ttl('', 'Où en est ce texte ?', 'ue', 'h3')}
      <ol class="eu-steps">${STEPS_COD.map(([l, s], i) => `<li class="${i < done ? 'done' : i === done ? 'now' : ''}"><b>${l}</b><span>${s}</span></li>`).join('')}</ol>
      <p class="note">${done >= 5 ? 'Le texte a été définitivement adopté.' : last?.adopte && done === 4 ? 'Le Parlement a approuvé le compromis : le Conseil doit encore l’adopter formellement avant publication au Journal officiel de l’UE.' : last?.adopte ? 'Le Parlement a adopté sa position. La négociation avec le Conseil se poursuit.' : 'Le Parlement a rejeté le texte lors de son dernier vote.'}</p>
    </section>` : ''}
    <div class="two-col" style="margin-top:18px">
      <div>
        <section class="card">${ttl('', 'Le parcours', 'ue', 'h3')}
          <div class="eu-tl">${items.map(x => `<div class="eu-tl-i" style="--c:${ACTEUR[x.a]?.[1] || 'var(--gouv)'}"><span class="d">${fdate(x.d, true)}</span><span class="dot"></span>
            <div>${x.v ? `<a href="${LE.vote(x.v)}"><b>${esc(x.l)}</b></a> <span class="muted small">${nf(x.v.p)} pour · ${nf(x.v.c)} contre · ${nf(x.v.a)} abst. — Français : ${nf(x.v.fr[0])} pour, ${nf(x.v.fr[1])} contre</span>${vs.length > 1 && x.v.titre !== t.titre ? `<div class="tiny muted">${esc(eu(x.v.titre, 120))}</div>` : ''}` : `<b>${esc(x.l)}</b>`}
            <div class="tiny muted">${esc(ACTEUR[x.a]?.[0] || '')}</div></div></div>`).join('')}</div>
        </section>
        ${last ? `<section class="block">
          ${ttl('', 'Le vote des Français au dernier vote', 'an')}<div style="height:10px"></div>
          ${voteRow(last, E)}
        </section>` : ''}
      </div>
      <aside>
        <section class="card">${ttl('', 'Ce texte', 'cc', 'h3')}
          <dl class="kv small" style="margin-top:10px">
            <dt>Procédure</dt><dd>${esc(E.types[t.type]?.[0] || t.type || '')} <span class="muted">(${esc(t.ref)})</span></dd>
            ${t.commission ? `<dt>Commission</dt><dd>${esc(E.commissions[t.commission] || t.commission)}</dd>` : ''}
            ${rapp.length ? `<dt>Rapporteur${rapp.length > 1 ? 's' : ''}</dt><dd>${rapp.map(r => rapporteur(r, E)).join('<br>')}</dd>` : ''}
            ${shadows.length ? `<dt>Rapporteurs fictifs français</dt><dd>${shadows.map(r => rapporteur(r, E)).join('<br>')}</dd>` : ''}
          </dl>
          ${t.titreEn && t.titreEn !== t.titre ? `<p class="tiny muted" style="margin-top:10px">Titre anglais : ${esc(t.titreEn)}</p>` : ''}
          <p class="small" style="margin-top:12px"><a class="ext" href="${oeil(t.ref)}" target="_blank" rel="noopener">Observatoire législatif du Parlement</a></p>
        </section>
        ${isCod ? `<section class="card" style="margin-top:16px">${ttl('', 'Et en France ?', 'gouv', 'h3')}
          <p class="small">Un <b>règlement</b> s’applique tel quel dans tous les pays. Une <b>directive</b> fixe des objectifs : la France doit l’intégrer dans son droit par une loi ou un décret, en général dans un délai de deux ans.</p></section>` : ''}
      </aside>
    </div>
    ${SOURCE_NOTE}
  </div>`;
}
function rapporteur(r, E) {
  const d = r.fr && E.meps.get(r.id);
  const g = E.groupes.get(r.groupe);
  return d ? `<a href="${LE.mep(d)}">${esc(d.prenom)} ${esc(d.nom)}</a> <span class="muted">(${esc(E.partis.get(d.parti)?.sigle || g?.sigle || '')})</span>` : `${esc(r.nom || '—')}${g ? ` <span class="muted">(${esc(g.sigle)})</span>` : ''}`;
}

// ─────────────────────────────────────────── Calendrier
export async function calendrier(el) {
  setTitle('Calendrier du Parlement européen');
  const E = await europe();
  const today = new Date().toISOString().slice(0, 10);
  const next = E.sessions.filter(s => s.fin >= today);
  const past = E.sessions.filter(s => s.fin < today).reverse();
  const byYear = list => {
    const m = new Map();
    for (const s of list) { const y = s.debut.slice(0, 4); if (!m.has(y)) m.set(y, []); m.get(y).push(s); }
    return [...m];
  };
  el.innerHTML = `<div class="page">
    ${head('Calendrier', `Les sessions plénières, où les 720 eurodéputés se réunissent pour voter. ${info('Le Parlement siège en principe 12 fois par an à Strasbourg pendant 4 jours, et quelques sessions plus courtes ont lieu à Bruxelles. Le reste du temps : réunions de commissions et de groupes politiques.')}`, 'europe/calendrier', '<a href="europe">Parlement européen</a>')}
    <div class="grid g2">
      <section>${ttl('', 'À venir', 'cc')}
        <div class="list" style="margin-top:12px">${next.map(sessionRow).join('') || '<div class="empty">Calendrier non publié.</div>'}</div></section>
      <section>${ttl('', 'Sessions passées', 'an')}
        ${byYear(past).map(([y, ss]) => `<h3 class="small muted" style="margin:14px 0 6px">${y}</h3><div class="list">${ss.map(sessionRow).join('')}</div>`).join('')}</section>
    </div>
    ${SOURCE_NOTE}
  </div>`;
}

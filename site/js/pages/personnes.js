import {
  ctx, deputes, senateurs, scrutinsIndex, dossiersIndex, load, esc, nf, pct, fdate, age, norm, debounce, paged, seg, wireSeg,
  setTitle, gchip, avatar, statTile, voteBar, voteLabels, resChip, posChip, term, KIND, hashParams, setHashParams, plural, ttl, info, tabsHtml, wireTabs,
} from '../lib.js';
import { loiRow } from './home.js';

const ordinal = n => (n === '1' || n === 1 ? '1re' : `${n}e`);
const fem = p => p.femme;

function circo(p) {
  if (!p.departement) return '';
  return p.circo ? `${ordinal(p.circo)} circonscription · ${p.departement}` : p.departement;
}

function personCard(p, chambre, g) {
  const href = chambre === 'AN' ? `#/depute/${p.id}` : `#/senateur/${p.id}`;
  const sub = chambre === 'AN' ? circo(p) : p.departement || '';
  return `<a class="card link person" href="${href}">${avatar(p, chambre, g)}<span style="min-width:0"><span class="pname">${esc(p.prenom)} ${esc(p.nom)}</span><br>
    <span class="pmeta">${gchip(g, { link: false })} ${esc(sub)}</span>${!p.actif ? '<br><span class="pmeta">Ancien député</span>' : ''}</span></a>`;
}

async function listPage(el, chambre) {
  const isAN = chambre === 'AN';
  setTitle(isAN ? 'Députés' : 'Sénateurs');
  const [c, all] = await Promise.all([ctx(), isAN ? deputes() : senateurs()]);
  const p = hashParams();
  const st = { q: p.q || '', g: p.g || '', dep: p.dep || '', tri: p.tri || 'nom', anciens: p.anciens === '1' };
  const groups = isAN ? c.an : c.sn;
  const depts = [...new Set(all.map(d => d.departement).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'fr'));
  el.innerHTML = `<div class="page">
    <div class="crumbs"><a href="#/${isAN ? 'assemblee' : 'senat'}">${isAN ? 'Assemblée nationale' : 'Sénat'}</a></div>
    <div class="page-head"><h1>${isAN ? 'Députés' : 'Sénateurs'}</h1>
      <p class="lead">${isAN ? 'Trouvez votre député : groupe, votes, présence, textes.' : 'Trouvez les sénateurs de votre département.'}</p></div>
    <div class="filters">
      <input type="search" id="f-q" placeholder="Nom, département, profession…" value="${esc(st.q)}">
      <select id="f-g"><option value="">Tous les groupes</option>${groups.map(g => `<option value="${g.id}"${g.id === st.g ? ' selected' : ''}>${esc(g.sigle)} — ${esc(g.nom)}</option>`).join('')}</select>
      <select id="f-dep"><option value="">Tous les départements</option>${depts.map(d => `<option${d === st.dep ? ' selected' : ''}>${esc(d)}</option>`).join('')}</select>
      <select id="f-tri"><option value="nom">Ordre alphabétique</option>${isAN ? `<option value="participation"${st.tri === 'participation' ? ' selected' : ''}>Participation aux votes</option><option value="loyaute"${st.tri === 'loyaute' ? ' selected' : ''}>Les plus indépendants de leur groupe</option><option value="textes"${st.tri === 'textes' ? ' selected' : ''}>Textes déposés</option>` : ''}<option value="age"${st.tri === 'age' ? ' selected' : ''}>Âge</option></select>
      ${isAN ? `<label class="check"><input type="checkbox" id="f-anc"${st.anciens ? ' checked' : ''}> Inclure les anciens députés de la législature</label>` : ''}
    </div>
    <div class="count-line" id="count"></div><div id="results"></div></div>`;
  const update = () => {
    setHashParams({ ...st, tri: st.tri === 'nom' ? '' : st.tri, anciens: st.anciens ? '1' : '' });
    const q = norm(st.q).split(/\s+/).filter(Boolean);
    let items = all.filter(d => (st.anciens || d.actif) && (!st.g || d.groupe === st.g) && (!st.dep || d.departement === st.dep) &&
      (!q.length || q.every(w => norm(`${d.prenom} ${d.nom} ${d.departement} ${d.profession || ''} ${c.groupes.get(d.groupe)?.sigle || ''}`).includes(w))));
    if (st.tri === 'participation') items = items.filter(d => d.stats?.participation != null).sort((a, b) => b.stats.participation - a.stats.participation);
    if (st.tri === 'loyaute') items = items.filter(d => d.stats?.loyaute != null).sort((a, b) => a.stats.loyaute - b.stats.loyaute);
    if (st.tri === 'textes') items.sort((a, b) => (b.roles?.auteur?.length || 0) - (a.roles?.auteur?.length || 0));
    if (st.tri === 'age') items.sort((a, b) => (a.naissance || '').localeCompare(b.naissance || ''));
    el.querySelector('#count').textContent = plural(items.length, isAN ? 'député' : 'sénateur');
    const extra = d => st.tri === 'participation' ? `participation ${pct(d.stats.participation)}` : st.tri === 'loyaute' ? `vote comme son groupe : ${pct(d.stats.loyaute)}` : st.tri === 'textes' ? plural(d.roles?.auteur?.length || 0, 'texte déposé', 'textes déposés') : st.tri === 'age' ? `${age(d.naissance)} ans` : '';
    paged(el.querySelector('#results'), items, d => {
      const card = personCard(d, chambre, c.groupes.get(d.groupe));
      const x = extra(d);
      return x ? card.replace('</span></a>', `<br><span class="pmeta"><b>${x}</b></span></span></a>`) : card;
    }, 48, 'people');
  };
  el.querySelector('#f-q').addEventListener('input', debounce(e => { st.q = e.target.value; update(); }));
  for (const [id, k] of [['f-g', 'g'], ['f-dep', 'dep'], ['f-tri', 'tri']]) el.querySelector('#' + id).addEventListener('change', e => { st[k] = e.target.value; update(); });
  el.querySelector('#f-anc')?.addEventListener('change', e => { st.anciens = e.target.checked; update(); });
  update();
}
export function deputesPage(el) { return listPage(el, 'AN'); }
export { deputesPage as deputes };
export function senateursPage(el) { return listPage(el, 'SN'); }
export { senateursPage as senateurs };

function dossiersBlock(title, uids, dos, empty) {
  const items = (uids || []).map(u => dos._index.get(u)).filter(Boolean).sort((a, b) => (b.maj || '').localeCompare(a.maj || ''));
  if (!items.length) return empty ? `<section class="block"><h2>${title}</h2><p class="muted">${empty}</p></section>` : '';
  const shown = items.slice(0, 8);
  return `<section class="block"><h2>${title} <span class="muted" style="font-weight:500">(${items.length})</span></h2>
    <div class="list">${shown.map(d => loiRow(d, dos.themes)).join('')}</div>
    ${items.length > 8 ? `<details class="more-box"><summary>Voir les ${items.length - 8} autres</summary><div class="list" style="margin-top:8px">${items.slice(8).map(d => loiRow(d, dos.themes)).join('')}</div></details>` : ''}</section>`;
}

function commissionsHtml(p) {
  if (!p.commissions?.length) return '';
  return p.commissions.map(cm => `${esc(cm.nom)}${cm.role && !/^membre$/i.test(cm.role) ? ` <span class="muted">(${esc(cm.role.toLowerCase())})</span>` : ''}`).join('<br>');
}

export async function depute(el, id) {
  const [c, deps, dos, scr] = await Promise.all([ctx(), deputes(), dossiersIndex(), scrutinsIndex()]);
  const d = deps._index.get(id);
  if (!d) { el.innerHTML = '<div class="page"><h1>Député introuvable</h1></div>'; return; }
  setTitle(`${d.prenom} ${d.nom}`);
  const g = c.groupes.get(d.groupe);
  const s = d.stats || {};
  const title = fem(d) ? 'Députée' : 'Député';
  el.innerHTML = `<div class="page">
    <div class="crumbs"><a href="#/assemblee">Assemblée nationale</a> › <a href="#/deputes">Députés</a></div>
    <div class="profile page-head">
      ${avatar(d, 'AN', g, 'lg')}
      <div class="info">
        <h1>${esc(d.prenom)} ${esc(d.nom)}</h1>
        <div class="facts">
          <span>${title}${d.actif ? '' : fem(d) ? ' (ancienne)' : ' (ancien)'} de la ${esc(circo(d))}</span>
          ${g ? `<span>${gchip(g)} ${esc(g.nom)}${d.apparente ? ' (apparenté)' : ''}${d.presidentGroupe ? ' · <b>présidence du groupe</b>' : ''}</span>` : ''}
        </div>
        <div class="facts small muted" style="margin-top:6px">
          ${d.naissance ? `<span>${age(d.naissance)} ans</span>` : ''}${d.profession ? `<span>${esc(d.profession)}</span>` : ''}
          <span>Élu${fem(d) ? 'e' : ''} le ${fdate(d.debut)}${d.premiereElection ? ' · premier mandat' : ''}</span>
          ${!d.actif && d.fin ? `<span>Mandat terminé le ${fdate(d.fin)}${d.causeFin ? ` (${esc(d.causeFin.split(' prévue')[0].toLowerCase())})` : ''}</span>` : ''}
        </div>
        ${d.fonctions?.length ? `<div style="margin-top:8px">${d.fonctions.map(f => `<span class="role-pill">${esc(f)}</span>`).join('')}</div>` : ''}
      </div>
    </div>

    ${tabsHtml('d', [['apercu', 'Vue d’ensemble'], ['votes', 'Votes'], ['textes', `Textes (${(d.roles?.auteur?.length || 0) + (d.roles?.rapporteur?.length || 0)})`]], ['apercu', 'votes', 'textes'].includes(hashParams().tab) ? hashParams().tab : 'apercu')}
    <div data-panel-of="d" data-panel="apercu">
    <div class="grid g4">
      ${statTile(pct(s.participation), `présence aux votes ${info("Part des scrutins publics auxquels le député a pris part. Beaucoup ont lieu pendant les réunions de commission : un taux bas ne veut pas dire qu'il ne travaille pas.")}`, `${nf(s.votes)} votes sur ${nf(s.scrutins)}`, null, 'green', '')}
      ${statTile(pct(s.loyaute), 'vote comme son groupe', `${plural(s.dissidences || 0, 'écart')} sur des votes importants`, null, 'violet', '')}
      ${statTile(nf(d.roles?.auteur?.length || 0), 'textes déposés', `et ${nf(d.cosignatures || 0)} cosignés`, null, 'orange', '')}
      ${statTile(nf(d.roles?.rapporteur?.length || 0), `fois ${term('rapporteur', 'rapporteur')}`, '', null, 'teal', '')}
    </div>

    <div class="two-col" style="margin-top:20px">
      <div>
        <section class="card">${ttl('', 'Ses votes en un coup d’œil', 'violet', 'h3')}
          ${voteBar(s.pour || 0, s.contre || 0, s.abstention || 0, 0, true)}${voteLabels(s.pour || 0, s.contre || 0, s.abstention || 0)}</section>
      </div>
      <aside>
        <section class="card">${ttl('', 'En bref', 'orange', 'h3')}
          <dl class="kv small" style="margin-top:10px">
            <dt>Circonscription</dt><dd>${esc(circo(d))}${d.region ? `<br><span class="muted">${esc(d.region)}</span>` : ''}</dd>
            ${d.parti ? `<dt>Parti</dt><dd>${esc(d.parti)}</dd>` : ''}
            ${d.commissions?.length ? `<dt>${term('commission', 'Commission')}</dt><dd>${commissionsHtml(d)}</dd>` : ''}
            ${d.lieuNaissance ? `<dt>Naissance</dt><dd>${fdate(d.naissance)}<br><span class="muted">${esc(d.lieuNaissance)}</span></dd>` : ''}
            ${d.place ? `<dt>Place</dt><dd>siège n° ${esc(d.place)} dans l'hémicycle</dd>` : ''}
          </dl>
          ${d.historiqueGroupes?.length > 1 ? `<h4 class="small muted" style="margin:14px 0 6px">Groupes pendant la législature</h4>
            <div class="small">${d.historiqueGroupes.map(([sg, a, b]) => `<div>${esc(sg || '?')} <span class="muted">· ${fdate(a, true)} → ${b ? fdate(b, true) : "aujourd'hui"}</span></div>`).join('')}</div>` : ''}
          <a class="btn small primary" href="#/comparer?d=${d.id}${g ? `&g=${g.id}` : ''}" style="margin-top:14px">Comparer ses votes</a>
          <p class="small" style="margin-top:12px"><a class="ext" href="https://www.assemblee-nationale.fr/dyn/deputes/${d.id}" target="_blank" rel="noopener">Fiche officielle sur le site de l'Assemblée</a></p>
        </section>
      </aside>
    </div>
    </div>
    <div data-panel-of="d" data-panel="votes">
        <section>
          <div class="section-title">${ttl('', 'Ses votes', 'blue')}${seg('vf', [['grands', 'Grands votes'], ['dissid', 'Contre l’avis de son groupe'], ['tous', 'Tous']], 'grands')}</div>
          <div id="dvotes"><div class="loading">Chargement des votes…</div></div>
        </section>
    </div>
    <div data-panel-of="d" data-panel="textes">
        ${dossiersBlock('Les textes qu’il a déposés'.replace('qu’il', fem(d) ? 'qu’elle' : 'qu’il'), d.roles?.auteur, dos, 'Aucun texte déposé en tant que premier signataire.')}
        ${dossiersBlock(`Les textes dont ${fem(d) ? 'elle' : 'il'} est rapporteur`, d.roles?.rapporteur, dos)}
    </div>
  </div>`;

  wireTabs(el, 'd');
  // Votes : chaîne d'une lettre par scrutin, dans l'ordre chronologique
  let v;
  try { v = await load(`votes/${id}`); } catch (e) { el.querySelector('#dvotes').innerHTML = '<p class="muted">Votes indisponibles.</p>'; return; }
  const dis = new Set(v.dissidences);
  const box = el.querySelector('#dvotes');
  const draw = mode => {
    const rows = [];
    for (let i = scr.chrono.length - 1; i >= 0; i--) {
      const ch = v.v[i];
      if (!'pca'.includes(ch)) continue;
      const s = scr.chrono[i];
      if (mode === 'grands' && !['ensemble', 'censure', 'motion', 'declaration'].includes(s.kind) && s.type !== 'SPS') continue;
      if (mode === 'dissid' && !dis.has(s.num)) continue;
      rows.push([s, ch]);
    }
    paged(box, rows, ([s, ch]) => `<a class="row" href="#/vote/${s.num}" style="padding:10px 14px">
      <div class="grow"><div class="small" style="color:var(--ink);font-weight:550">${esc(s.titre)}</div>
        <div class="meta"><span>${fdate(s.date, true)}</span><span>${esc(KIND[s.kind] || '')}</span>${resChip(s.adopte)}${dis.has(s.num) ? '<span class="chip" style="color:var(--warn)">≠ son groupe</span>' : ''}</div></div>
      <div class="side" style="min-width:110px">${posChip(ch)}</div></a>`, 15);
    if (!rows.length) box.innerHTML = `<div class="empty">${mode === 'dissid' ? 'Aucun vote important contre la position de son groupe.' : 'Aucun vote enregistré.'}</div>`;
  };
  wireSeg(el, 'vf', draw);
  draw('grands');
}

export async function senateur(el, id) {
  const [c, sens, dos] = await Promise.all([ctx(), senateurs(), dossiersIndex()]);
  const d = sens._index.get(id);
  if (!d) { el.innerHTML = '<div class="page"><h1>Sénateur introuvable</h1><p>Seuls les sénateurs en exercice sont recensés.</p></div>'; return; }
  setTitle(`${d.prenom} ${d.nom}`);
  const g = c.groupes.get(d.groupe);
  el.innerHTML = `<div class="page">
    <div class="crumbs"><a href="#/senat">Sénat</a> › <a href="#/senateurs">Sénateurs</a></div>
    <div class="profile page-head">
      ${avatar(d, 'SN', g, 'lg')}
      <div class="info">
        <h1>${esc(d.prenom)} ${esc(d.nom)}</h1>
        <div class="facts"><span>${fem(d) ? 'Sénatrice' : 'Sénateur'} · ${esc(d.departement || '')}</span>
          ${g ? `<span>${gchip(g)} ${esc(g.nom)}${d.rattache ? ' (rattaché)' : ''}${d.presidentGroupe ? ' · <b>présidence du groupe</b>' : ''}</span>` : ''}</div>
        <div class="facts small muted" style="margin-top:6px">
          ${d.naissance ? `<span>${age(d.naissance)} ans</span>` : ''}${d.profession ? `<span>${esc(d.profession)}</span>` : ''}
          <span>Au Sénat depuis le ${fdate(d.premierMandat)}</span>${d.ancienDepute ? `<span>${fem(d) ? 'Ancienne députée' : 'Ancien député'}</span>` : ''}
        </div>
        ${d.fonctions?.length ? `<div style="margin-top:8px">${d.fonctions.map(f => `<span class="role-pill">${esc(f)}</span>`).join('')}</div>` : ''}
      </div>
    </div>
    <div class="grid g4">
      ${statTile(nf(d.roles?.auteur?.length || 0), 'textes déposés', '', null, 'orange', '')}
      ${statTile(nf(d.roles?.rapporteur?.length || 0), `fois ${term('rapporteur', 'rapporteur')}`, '', null, 'teal', '')}
      ${statTile(fdate(d.debut, true), 'début du mandat', 'pour 6 ans', null, 'violet', '')}
      ${statTile(nf(d.cosignatures || 0), 'cosignatures', '', null, 'pink', '')}
    </div>
    <div class="two-col" style="margin-top:20px">
      <div>
        <p class="note">Votes individuels non disponibles ${info("Les votes nominatifs des sénateurs ne font pas partie des données ouvertes utilisées. Ci-dessous : les textes suivis par l'Assemblée dont ce sénateur est auteur ou rapporteur.")}</p>
        ${dossiersBlock(`Les textes dont ${fem(d) ? 'elle' : 'il'} est rapporteur`, d.roles?.rapporteur, dos)}
        ${dossiersBlock('Ses textes', d.roles?.auteur, dos)}
        ${!d.roles?.rapporteur?.length && !d.roles?.auteur?.length ? '<p class="muted">Aucun texte suivi par l’Assemblée pour le moment.</p>' : ''}
      </div>
      <aside><section class="card">${ttl('', 'En bref', 'orange', 'h3')}
        <dl class="kv small" style="margin-top:10px">
          <dt>Département</dt><dd>${esc(d.departement || '')}</dd>
          ${d.parti ? `<dt>Parti</dt><dd>${esc(d.parti)}</dd>` : ''}
          ${d.commissions?.length ? `<dt>${term('commission', 'Commission')}</dt><dd>${commissionsHtml(d)}</dd>` : ''}
          ${d.lieuNaissance ? `<dt>Naissance</dt><dd>${fdate(d.naissance)}<br><span class="muted">${esc(d.lieuNaissance)}</span></dd>` : ''}
        </dl>
        <p class="small" style="margin-top:12px"><a class="ext" href="https://www.senat.fr/senateurs/senatl.html" target="_blank" rel="noopener">Liste officielle sur le site du Sénat</a></p>
      </section></aside>
    </div>
  </div>`;
}

import { dossiersIndex, ctx, esc, nf, norm, paged, seg, wireSeg, debounce, setTitle, hashParams, setHashParams, term, info } from '../lib.js';
import { loiRow } from './home.js';

const STATUTS = [
  ['', 'Tous'], ['navette', 'En cours'], ['adoptee', 'Adoptés'], ['promulguee', 'Promulgués'],
  ['rejetee', 'Rejetés'], ['deposee', 'Jamais examinés'], ['retiree', 'Retirés'],
];
const TYPES = [
  ['', 'Tous les types'], ['gouv', 'Projets du Gouvernement'], ['PPL', 'Propositions de parlementaires'],
  ['budget', 'Budgets (État, Sécu, comptes)'], ['CONST', 'Révisions constitutionnelles'], ['ORGA', 'Lois organiques'], ['TRAITE', 'Traités et conventions'],
];
const CATS = [['loi', 'Lois'], ['resolution', 'Résolutions'], ['controle', 'Contrôle et enquêtes']];

export async function render(el) {
  setTitle('Lois');
  const [dos] = await Promise.all([dossiersIndex(), ctx()]);
  const p = hashParams();
  const st = { q: p.q || '', statut: p.statut || '', type: p.type || '', theme: p.theme || '', origine: p.origine || '', tri: p.tri || 'maj', cat: p.cat || 'loi', tout: p.tout === '1' };
  const themeOpts = Object.entries(dos.themes).sort((a, b) => a[1].label.localeCompare(b[1].label));

  el.innerHTML = `<div class="page">
    <div class="page-head">
      <h1>Lois</h1>
      <p class="lead">Chaque texte et sa ${term('navette', 'navette')}, étape par étape.</p>
    </div>
    <div class="filters">${seg('cat', CATS, st.cat)}</div>
    <div class="filters">
      <input type="search" id="f-q" placeholder="Rechercher dans les titres…" value="${esc(st.q)}" aria-label="Rechercher">
      <select id="f-type" aria-label="Type de texte">${TYPES.map(([v, l]) => `<option value="${v}"${v === st.type ? ' selected' : ''}>${l}</option>`).join('')}</select>
      <select id="f-theme" aria-label="Thème"><option value="">Tous les thèmes</option>${themeOpts.map(([k, t]) => `<option value="${k}"${k === st.theme ? ' selected' : ''}>${t.emoji} ${esc(t.label)}</option>`).join('')}</select>
      <select id="f-origine" aria-label="Chambre de dépôt"><option value="">Déposés à l'AN ou au Sénat</option><option value="AN"${st.origine === 'AN' ? ' selected' : ''}>Déposés à l'Assemblée</option><option value="SN"${st.origine === 'SN' ? ' selected' : ''}>Déposés au Sénat</option></select>
      <select id="f-tri" aria-label="Trier"><option value="maj">Activité récente</option><option value="depot"${st.tri === 'depot' ? ' selected' : ''}>Date de dépôt</option><option value="auteurs"${st.tri === 'auteurs' ? ' selected' : ''}>Nombre de signataires</option></select>
    </div>
    <div class="filters">${seg('statut', STATUTS, st.statut)}
      <label class="check"><input type="checkbox" id="f-tout"${st.tout ? ' checked' : ''}> Inclure les textes jamais examinés</label>
    </div>
    <div class="count-line" id="count"></div>
    <div id="results"></div>
  </div>`;

  const update = () => {
    setHashParams({ ...st, tri: st.tri === 'maj' ? '' : st.tri, cat: st.cat === 'loi' ? '' : st.cat, tout: st.tout ? '1' : '' });
    const q = norm(st.q).split(/\s+/).filter(Boolean);
    const showAll = st.tout || st.statut === 'deposee' || st.statut === 'retiree' || q.length > 0;
    let items = dos.dossiers.filter(d => {
      if (d.cat !== st.cat) return false;
      if (st.statut && d.statut !== st.statut) return false;
      if (!showAll && st.cat !== 'controle' && d.statut === 'deposee') return false;
      if (st.theme && d.theme !== st.theme) return false;
      if (st.origine && d.origine !== st.origine) return false;
      if (st.type === 'gouv' && !d.gouv) return false;
      if (st.type === 'PPL' && d.gouv) return false;
      if (st.type === 'budget' && !['PLF', 'PLFR', 'PLFSS', 'PLRG'].includes(d.type)) return false;
      if (['CONST', 'ORGA', 'TRAITE'].includes(st.type) && d.type !== st.type) return false;
      if (q.length) {
        const t = norm(`${d.titre} ${d.auteur?.nom || ''} ${d.loi || ''}`);
        if (!q.every(w => t.includes(w))) return false;
      }
      return true;
    });
    if (st.tri === 'depot') items.sort((a, b) => (b.depot || '').localeCompare(a.depot || ''));
    else if (st.tri === 'auteurs') items.sort((a, b) => b.nbAuteurs - a.nbAuteurs);
    else items.sort((a, b) => (b.maj || '').localeCompare(a.maj || ''));
    const hidden = !showAll && st.cat !== 'controle' ? dos.dossiers.filter(d => d.cat === st.cat && d.statut === 'deposee').length : 0;
    el.querySelector('#count').innerHTML = `${nf(items.length)} texte${items.length > 1 ? 's' : ''}` +
      (hidden && !st.statut ? ` · <span class="muted">${nf(hidden)} jamais examinés masqués</span> ${info("La plupart des propositions de loi ne sont jamais inscrites à l'ordre du jour. Cochez « Inclure les textes jamais examinés » pour les voir.")}` : '');
    paged(el.querySelector('#results'), items, d => loiRow(d, dos.themes));
  };

  wireSeg(el, 'statut', v => { st.statut = v; update(); });
  wireSeg(el, 'cat', v => { st.cat = v; update(); });
  el.querySelector('#f-q').addEventListener('input', debounce(e => { st.q = e.target.value; update(); }));
  for (const [id, key] of [['f-type', 'type'], ['f-theme', 'theme'], ['f-origine', 'origine'], ['f-tri', 'tri']]) {
    el.querySelector('#' + id).addEventListener('change', e => { st[key] = e.target.value; update(); });
  }
  el.querySelector('#f-tout').addEventListener('change', e => { st.tout = e.target.checked; update(); });
  update();
}

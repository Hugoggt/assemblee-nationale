import {
  ctx, deputes, senateurs, dossiersIndex, esc, norm, setTitle, hashParams, gchip, avatar, plural, L,
} from '../lib.js';
import { loiRow } from './home.js';

export async function render(el) {
  const q = (hashParams().q || '').trim();
  setTitle(`Recherche : ${q}`);
  const [c, deps, sens, dos] = await Promise.all([ctx(), deputes(), senateurs(), dossiersIndex()]);
  const words = norm(q).split(/\s+/).filter(Boolean);
  const match = t => words.length && words.every(w => norm(t).includes(w));
  const pd = deps.filter(d => match(`${d.prenom} ${d.nom} ${d.departement}`)).sort((a, b) => b.actif - a.actif).slice(0, 24);
  const ps = sens.filter(d => match(`${d.prenom} ${d.nom} ${d.departement}`)).slice(0, 24);
  const gs = [...c.an, ...c.sn].filter(g => match(`${g.sigle} ${g.nom}`));
  const ls = dos.dossiers.filter(d => match(`${d.titre} ${d.loi || ''}`)).sort((a, b) => (b.examine - a.examine) || (b.maj || '').localeCompare(a.maj || '')).slice(0, 40);
  const person = (d, ch) => `<a class="card link person" href="${(ch === 'AN' ? L.dep : L.sen)(d)}">${avatar(d, ch, c.groupes.get(d.groupe))}<span><span class="pname">${esc(d.prenom)} ${esc(d.nom)}</span><br><span class="pmeta">${gchip(c.groupes.get(d.groupe), { link: false })} ${ch === 'AN' ? (d.actif ? 'Député·e' : 'Ancien·ne député·e') : 'Sénateur·rice'} · ${esc(d.departement || '')}</span></span></a>`;
  const total = pd.length + ps.length + gs.length + ls.length;
  el.innerHTML = `<div class="page">
    <h1>Résultats pour « ${esc(q)} »</h1>
    <p class="muted">${plural(total, 'résultat')}</p>
    ${gs.length ? `<section class="block"><h2>Groupes</h2><div class="pill-row">${gs.map(g => `${gchip(g)} <span class="small">${esc(g.nom)} (${g.chambre === 'AN' ? 'Assemblée' : 'Sénat'})</span>`).join('&nbsp;&nbsp;')}</div></section>` : ''}
    ${pd.length ? `<section class="block"><h2>Députés</h2><div class="people">${pd.map(d => person(d, 'AN')).join('')}</div></section>` : ''}
    ${ps.length ? `<section class="block"><h2>Sénateurs</h2><div class="people">${ps.map(d => person(d, 'SN')).join('')}</div></section>` : ''}
    ${ls.length ? `<section class="block"><h2>Textes</h2><div class="list">${ls.map(d => loiRow(d, dos.themes)).join('')}</div>
      <p class="small"><a href="lois?q=${encodeURIComponent(q)}&tout=1">Affiner dans la liste des lois →</a></p></section>` : ''}
    ${!total ? '<div class="empty">Aucun résultat. Essayez un nom de famille, un département ou un mot du titre d’une loi.</div>' : ''}
  </div>`;
  const input = document.getElementById('q');
  if (input) input.value = q;
}

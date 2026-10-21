import {
  ctx, scrutinsIndex, dossiersIndex, esc, nf, fdate, term, setTitle, statTile, plural, ucfirst, avatar, ttl, L,
} from '../lib.js';
import { loiRow } from './home.js';

const short = p => ucfirst((p || '').replace(/^Ministère (délégué )?(de l['’]|de la |du |des |de |auprès )/i, '').replace(/^Ministère /i, ''));

export async function render(el) {
  setTitle('Gouvernement');
  const [c, scr, dos] = await Promise.all([ctx(), scrutinsIndex(), dossiersIndex()]);
  const g = c.meta.gouvernement;
  const pm = g.membres.find(m => m.fonction === 'Premier ministre');
  const others = g.membres.filter(m => m !== pm);
  const byFn = {};
  others.forEach(m => { const k = /délégué|secrétaire/i.test(m.fonction) ? m.fonction : 'Ministre'; (byFn[k] = byFn[k] || []).push(m); });
  byFn.Ministre?.sort((a, b) => (a.fonction === 'Ministre') - (b.fonction === 'Ministre') || a.nom.localeCompare(b.nom));
  const censures = scr.list.filter(s => s.kind === 'censure').sort((a, b) => a.num - b.num);
  const adopted = censures.filter(s => s.adopte);
  const govs = g.historique.filter(x => !x.fin || x.fin >= c.meta.debutLegislature);
  const u493 = dos.dossiers.filter(d => d.art493 > 0).sort((a, b) => (b.maj || '').localeCompare(a.maj || ''));
  const days = (a, b) => Math.round((new Date(b || Date.now()) - new Date(a)) / 864e5);

  el.innerHTML = `<div class="page">
    <div class="page-head"><h1>Gouvernement</h1>
      <p class="lead">Il conduit la politique du pays et peut être renversé par l'Assemblée via une ${term('censure', 'motion de censure')}.</p></div>

    ${pm ? `<section class="card" style="display:flex;gap:18px;align-items:center;flex-wrap:wrap;margin-bottom:18px">
      <span class="avatar lg" style="background:var(--gouv)">${esc(pm.prenom[0] + pm.nom[0])}</span>
      <div><div class="muted small">Premier ministre depuis le ${fdate(g.historique.find(h => h.pmId === pm.id)?.debut || pm.debut)}</div><h2 style="margin:2px 0">${esc(pm.prenom)} ${esc(pm.nom)}</h2>
      <div class="small muted">${plural(others.length, 'autre membre', 'autres membres')} du Gouvernement · ${others.filter(m => m.femme).length + (pm.femme ? 1 : 0)} femmes au total</div></div>
    </section>` : ''}

    ${Object.entries(byFn).map(([fn, ms]) => `<section class="block"><h2 class="ttl tone-blue"><span class="b">${fn === 'Ministre' ? '' : ''}</span>${esc(fn === 'Ministre' ? 'Ministres' : fn === 'Ministre délégué' ? 'Ministres délégués' : fn === "Secrétaire d'État" ? "Secrétaires d'État" : fn)} <span class="muted" style="font-weight:500">(${ms.length})</span></h2>
      <div class="people">${ms.map(m => `<div class="card"><div class="person">${m.depute ? avatar(m, 'AN', { couleur: 'var(--gouv)' }) : `<span class="avatar" style="background:var(--gouv)">${esc(m.prenom[0] + m.nom[0])}</span>`}<span style="min-width:0">
        <span class="pname">${m.depute ? `<a href="${L.dep(m)}">${esc(m.prenom)} ${esc(m.nom)}</a>` : `${esc(m.prenom)} ${esc(m.nom)}`}</span><br>
        <span class="pmeta">${m.fonction !== 'Ministre' && !/délégué/i.test(m.fonction) ? `<b>${esc(m.fonction)}</b> · ` : ''}${esc(short(m.portefeuille))}</span>${m.depute ? `<br><span class="pmeta">${m.femme ? 'ancienne députée' : 'ancien député'} (17e législature)</span>` : ''}</span></div></div>`).join('')}</div></section>`).join('')}

    <section class="block">${ttl('', 'Les gouvernements depuis 2024', 'blue')}<div style="height:12px"></div>
      <div class="list">${govs.map(x => {
        const fall = adopted.find(s => x.fin && Math.abs(days(s.date, x.fin)) <= 10);
        return `<div class="row"><div class="grow"><div class="title">Gouvernement ${esc(x.pm ? x.pm.split(' ').slice(-1)[0] : '')}${govs.filter(y => y.pm === x.pm).length > 1 ? ` (${govs.filter(y => y.pm === x.pm).indexOf(x) + 1})` : ''}</div>
          <div class="meta"><span>Premier ministre : ${esc(x.pm || '?')}</span><span>${fdate(x.debut)} → ${x.fin ? fdate(x.fin) : "aujourd'hui"}</span><span>${nf(days(x.debut, x.fin))} jours</span>
          ${fall ? `<a class="chip" style="color:var(--bad)" href="vote/${fall.num}">Renversé par une motion de censure le ${fdate(fall.date)}</a>` : ''}</div></div></div>`;
      }).join('')}</div></section>

    <section class="block">${ttl('', 'L’arme du Parlement : la censure', 'red')}<div style="height:12px"></div>
      <div class="grid g3" style="margin-bottom:14px">
        ${statTile(nf(censures.length), 'motions de censure', 'depuis juillet 2024', null, 'red', '')}
        ${statTile(nf(adopted.length), 'adoptée' + (adopted.length > 1 ? 's' : ''), adopted.length ? 'Gouvernement renversé' : '', null, 'orange', '')}
        ${statTile(nf(c.meta.chiffres.art493), `${term('art493', '49.3')}`, 'textes adoptés sans vote', null, 'violet', '')}
      </div>
      <p class="small muted">Objectif : 289 voix. Chaque tentative :</p>
      <div class="list">${censures.slice().reverse().map(s => `<a class="row" href="vote/${s.num}">
        <div class="grow"><div class="title small">${esc(s.titre)}</div><div class="meta"><span>${fdate(s.date)}</span>${s.adopte ? '<span class="res ko">Adoptée — Gouvernement renversé</span>' : `<span>il a manqué ${nf(Math.max(0, s.requis - s.pour))} voix</span>`}</div></div>
        <div class="side" style="min-width:200px"><div class="vbar lg" style="position:relative"><span style="width:${Math.min(100, (100 * s.pour) / 577)}%;background:${s.adopte ? 'var(--bad)' : 'var(--contre)'}"></span></div>
        <div class="tiny muted num" style="margin-top:4px">${nf(s.pour)} / ${nf(s.requis)} voix nécessaires</div></div></a>`).join('')}</div>
    </section>

    ${u493.length ? `<section class="block">${ttl('', 'Les textes passés au 49.3', 'violet')}<div style="height:12px"></div><div class="list">${u493.map(d => loiRow(d, dos.themes)).join('')}</div></section>` : ''}
  </div>`;
}

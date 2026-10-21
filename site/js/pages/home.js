import {
  ctx, dossiersIndex, scrutinsIndex, load, esc, nf, fdate, relDate, fdateDay, hemicycle, wireHemicycle, statusChip, miniParcours, voteBar, resChip, term, statTile, setTitle, KIND, ttl, loiCard, THEME_COLOR, norm, L, navigate,
} from '../lib.js';

export function groupSeats(groups, total, highlight, onColor, offColor = 'rgba(127,127,127,.28)') {
  const seats = [];
  for (const g of groups) {
    const on = !highlight || g.id === highlight;
    for (let i = 0; i < g.effectif; i++) seats.push({ color: on ? (highlight && onColor) || g.couleur : offColor, tip: `${g.sigle} · ${g.nom} — ${g.effectif} sièges`, href: `${L.grp(g)}`, key: g.id });
  }
  while (seats.length < total) seats.push({ color: 'var(--absent)', tip: 'Siège vacant' });
  return seats;
}

const STRIPE = { promulguee: 'var(--v-green)', adoptee: 'var(--v-teal)', navette: 'var(--v-blue)', rejetee: 'var(--v-red)', censuree: 'var(--v-red)' };

export function loiRow(d, themes) {
  const th = themes[d.theme];
  return `<a class="row striped" href="${L.loi(d)}" style="--stripe:${STRIPE[d.statut] || 'var(--border)'}">
    <div class="grow">
      <div class="title">${esc(d.titre)}</div>
      <div class="meta">
        ${statusChip(d.statut, d.statutLabel)}
        ${th ? `<span class="chip theme" style="--tc:${THEME_COLOR[d.theme]}">${th.emoji} ${esc(th.label)}</span>` : ''}
        <span>${d.gouv ? 'Gouvernement' : d.auteur ? esc(d.auteur.nom) + (d.auteur.groupe ? ` · ${esc(d.auteur.groupe)}` : '') : ''}</span>
      </div>
    </div>
    <div class="side">
      ${miniParcours(d.parcours, d.statut)}
      <div class="tiny muted" style="margin-top:6px">${d.maj ? relDate(d.maj) : ''}</div>
    </div>
  </a>`;
}

export function scrutinRow(s, dossiers) {
  const d = s.dossier && dossiers.get(s.dossier);
  return `<a class="row striped" href="vote/${s.num}" style="--stripe:${s.adopte ? 'var(--pour)' : 'var(--contre)'}">
    <div class="grow">
      <div class="title">${esc(s.titre)}</div>
      <div class="meta"><span>${fdate(s.date, true)}</span><span class="chip">${esc(KIND[s.kind] || '')}${s.type === 'SPS' ? ' · solennel' : ''}</span>${d ? `<span>${esc(d.titre.slice(0, 60))}${d.titre.length > 60 ? '…' : ''}</span>` : ''}</div>
    </div>
    <div class="side" style="min-width:170px">
      ${resChip(s.adopte)}
      <div style="margin-top:6px">${voteBar(s.pour, s.contre, s.abstention)}</div>
      <div class="tiny muted num" style="margin-top:4px">${nf(s.pour)} pour · ${nf(s.contre)} contre</div>
    </div>
  </a>`;
}

export async function render(el) {
  setTitle('');
  const [c, dos, agenda] = await Promise.all([ctx(), dossiersIndex(), load('agenda')]);
  const { meta } = c;
  const k = meta.chiffres;
  const lois = dos.dossiers.filter(d => d.cat === 'loi');
  const byMaj = (a, b) => (b.maj || '').localeCompare(a.maj || '');
  const promulguees = lois.filter(d => d.statut === 'promulguee').sort(byMaj).slice(0, 6);
  const seen = new Set();
  const upcoming = [];
  for (const ev of agenda.filter(a => a.type === 'seance')) {
    for (const pt of ev.points) {
      const label = pt.objet.replace(/^(vote solennel sur |explications de vote et vote par scrutin public sur |suite de la discussion |discussion |suite de l'examen |examen )/i, '').replace(/^(le |la |les |l'|du |de la |de l'|des )/i, '');
      const key = norm(label).replace(/\(.*?\)/g, '').slice(0, 70).trim();
      if (seen.has(key) || (pt.dossiers[0] && seen.has(pt.dossiers[0])) || /^questions au gouvernement/i.test(pt.objet)) continue;
      seen.add(key); if (pt.dossiers[0]) seen.add(pt.dossiers[0]);
      if (upcoming.length >= 5) break;
      upcoming.push({ date: ev.date, objet: label.replace(/^./, ch => ch.toUpperCase()), dossier: pt.dossiers[0] });
    }
    if (upcoming.length >= 5) break;
  }
  const biggest = [...c.an].sort((a, b) => b.effectif - a.effectif)[0];

  el.innerHTML = `
  <div class="hero"><div class="wrap">
    <div>
      <h1>Suivre le Parlement<span class="dot">.</span></h1>
      <p class="lead">Composition, lois et votes de l'Assemblée nationale et du Sénat.</p>
      <div class="intro">
        <p>Ce qui se vote au Parlement est public, mais rarement clair : des milliers de scrutins, des textes qui passent d'une chambre à l'autre, des procédures que peu de gens connaissent.</p>
        <p><b>Hémicycle</b> est un site indépendant et gratuit qui rassemble les données officielles pour rendre lisible ce qui se joue dans les deux hémicycles : où en est chaque loi, qui a voté quoi, qui vote avec qui. <a href="a-propos">En savoir plus</a></p>
      </div>
      <form class="hero-search" id="hero-search"><input type="search" name="q" placeholder="Un député, un sénateur, une loi…" aria-label="Rechercher"><button class="btn primary">Chercher</button></form>
    </div>
    <div class="hero-chambers">
      <a href="assemblee">${hemicycle(groupSeats(c.an, 577), { label: '577', sub: 'députés' })}<b>Assemblée</b><span class="small muted">${c.an.length} groupes · 1er : ${esc(biggest.sigle)}</span></a>
      <a href="senat">${hemicycle(groupSeats(c.sn, 348), { label: '348', sub: 'sénateurs' })}<b>Sénat</b><span class="small muted">${c.sn.length} groupes</span></a>
    </div>
  </div></div>

  <div class="page">
    <section class="block" style="margin-top:0">
      <div class="grid g4">
        ${statTile(nf(k.promulguees), 'lois promulguées', `depuis ${fdate(meta.debutLegislature, true)}`, 'lois?statut=promulguee', 'loi', '')}
        ${statTile(`${Math.round((100 * k.examines) / k.textes)} %`, 'des textes déposés sont débattus', `${nf(k.examines)} sur ${nf(k.textes)}`, 'lois', 'loi', '')}
        ${statTile(nf(k.art493), `${term('art493', '49.3')} utilisés`, `${k.censures} ${term('censure', 'censures')} votées, ${k.censuresAdoptees} adoptée${k.censuresAdoptees > 1 ? 's' : ''}`, 'gouvernement', 'gouv', '')}
        ${statTile(nf(k.scrutins), 'votes nominatifs', 'député par député', 'votes', 'an', '')}
      </div>
    </section>

    <div class="two-col">
      <div>
        <section class="block" style="margin-top:0">
          <div class="section-title">${ttl('', 'Lois récemment promulguées', 'green')}<a href="lois?statut=promulguee">Tout voir →</a></div>
          <div class="lcards">${promulguees.map(d => loiCard(d, dos.themes)).join('')}</div>
        </section>
      </div>
      <aside>
        <section class="card">
          ${ttl('', 'À l’ordre du jour', 'teal', 'h3')}
          ${upcoming.length ? `<ul class="agenda-mini">${upcoming.map(u => `<li><span class="tiny muted">${fdateDay(u.date)} · ${u.date.slice(11, 16).replace(':', 'h')}</span>
            ${u.dossier ? `<a href="${L.loi(u.dossier)}">${esc(u.objet)}</a>` : `<span>${esc(u.objet)}</span>`}</li>`).join('')}</ul>` : '<p class="muted small">Rien de programmé pour le moment.</p>'}
          <a class="small" href="agenda">Tout l'agenda →</a>
        </section>
      </aside>
    </div>
  </div>`;

  el.querySelectorAll('.hero-chambers a').forEach(a => a.addEventListener('click', e => {
    if (e.target.closest('circle')) e.preventDefault();
  }));
  wireHemicycle(el);
  el.querySelector('#hero-search').addEventListener('submit', e => {
    e.preventDefault();
    const q = new FormData(e.target).get('q').trim();
    if (q) navigate(`recherche?q=${encodeURIComponent(q)}`);
  });
}

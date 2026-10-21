import {
  load, ctx, dossiersIndex, esc, nf, fdate, fdateDay, relDate, statusChip, chamberChip, term, actorLink, voteBar, voteLabels, resChip, setTitle, CHAMBRE, RESULT_TXT, RESULT_ICON, KIND, seg, wireSeg, ucfirst, plural, ttl, info, themeChip, tabsHtml, wireTabs, hashParams, shareBtn,
} from '../lib.js';

const READING = s => ['AN', 'SN'].includes(s.chambre) && !/^(AN20|AN21|AN-APPLI)/.test(s.code);
const PARCOURS = s => ['AN', 'SN', 'CMP', 'CC', 'PROM'].includes(s.chambre) && !/^(AN20|AN21|AN-APPLI)/.test(s.code);

const EV_ICON = {
  depot: '', transmission: '', procacc: '', info: 'ℹ', saisine: '', saisine_avis: '', rapporteur: '',
  commission: '', rapport: '', seance: '', motion: '', cmp_convocation: '', cmp_decision: '', cc_saisine: '',
  cc_decision: '', promulgation: '', retrait: '↩', art493: '', censure_depot: '', censure: '',
};
const OK = ['adopte', 'conforme', 'modifie', 'adopte493', 'accord'];
const KO = ['rejete', 'rejete493', 'motion_adoptee', 'desaccord'];

function decIcon(o) {
  if (o === 'adopte493') return '';
  if (OK.includes(o)) return '';
  if (KO.includes(o)) return '';
  return '•';
}

// ─────────────────────────────────────────── Récit en moments clés
const CH_COLOR = { AN: 'var(--an)', SN: 'var(--sn)', CMP: 'var(--cmp)', CC: 'var(--cc)', PROM: 'var(--prom)' };

function moments(d) {
  const out = [];
  const push = (icon, ch, html, date) => out.push({ icon, c: CH_COLOR[ch] || 'var(--accent)', html, date });
  const steps = d.steps;
  const readings = steps.filter(READING);
  const first = readings[0];
  const Who = c => ucfirst(CHAMBRE[c]?.art || c);
  if (first) {
    const by = d.gouv ? 'le Gouvernement' : d.auteurs?.[0] ? `${esc(d.auteurs[0].nom)}${d.auteurs[0].groupe ? ` (${esc(d.auteurs[0].groupe)})` : ''}` : '';
    push('', first.chambre, `Déposé ${CHAMBRE[first.chambre].a}${by ? ` par ${by}` : ''}${!d.gouv && d.cosignataires ? ` <span class="muted">+ ${nf(d.cosignataires)} cosignataires</span>` : ''}`, d.depot);
  }
  if (d.procAcc) push('', 'AN', `${term('procacc', 'Procédure accélérée')} : une seule lecture par chambre`);
  for (const s of steps) {
    if (READING(s)) {
      const lect = s === first || (/1$/.test(s.code) && readings.indexOf(s) === 1) ? '' :
        s.code === 'ANLDEF' ? ` en ${term('lecturedef', 'lecture définitive')}` : /NLEC$/.test(s.code) ? ` en ${term('nouvellelecture', 'nouvelle lecture')}` : ` en ${s.label.toLowerCase()}`;
      const w = Who(s.chambre);
      const txt = {
        adopte: ['', `${w} l'adopte${lect}`],
        modifie: ['', `${w} le modifie${lect} → retour en ${term('navette', 'navette')}`],
        conforme: ['', `${w} l'adopte tel quel${lect} : ${term('conforme', 'adoption définitive')}`],
        rejete: ['', `${w} le rejette${lect}`],
        rejete493: ['', `${w} le rejette${lect}`],
        motion_adoptee: ['', `${w} le rejette d'emblée${lect} (${term('motionrejet', 'motion de rejet')})`],
        adopte493: ['', `${w} l'adopte sans vote${lect} grâce au ${term('art493', '49.3')}`],
      }[s.resultat];
      if (txt) push(txt[0], s.chambre, txt[1], s.fin);
      else if (s === steps[steps.length - 1]) push('', s.chambre, `${w} l'examine${lect}`, s.debut);
      if (s.code === 'ANLDEF' && OK.includes(s.resultat)) push('', 'AN', "L'Assemblée a eu le dernier mot");
    } else if (s.chambre === 'CMP') {
      push('', 'CMP', `${term('cmp', 'CMP')} (7 députés + 7 sénateurs) : ${s.cmp === 'accord' ? '<b>compromis trouvé</b>' : s.cmp === 'desaccord' ? '<b>échec</b>' : 'convoquée'}`, s.fin);
      if (OK.includes(s.voteAN) && OK.includes(s.voteSN)) push('', 'CMP', `Compromis voté par les deux chambres${s.voteAN === 'adopte493' ? ' (49.3 à l’Assemblée)' : ''}`);
      else if (KO.includes(s.voteAN) || KO.includes(s.voteSN)) push('', 'CMP', `Compromis rejeté par ${KO.includes(s.voteAN) ? "l'Assemblée" : 'le Sénat'}`);
    } else if (s.chambre === 'CC') {
      const cc = d.conseilConstitutionnel;
      const r = (cc?.resultat || '').toLowerCase();
      push('', 'CC', cc?.resultat ? `${term('cc', 'Conseil constitutionnel')} : « ${esc(r)} »${r.includes('partiellement') || (r.includes('non conforme') && d.statut === 'promulguee') ? ' — une partie censurée' : ''}` : `${term('cc', 'Conseil constitutionnel')} saisi, décision attendue`, cc?.date || s.debut);
    } else if (s.chambre === 'PROM' && d.promulgation) {
      push('', 'PROM', `<b>Loi n° ${esc(d.promulgation.numero)}</b> promulguée`, d.promulgation.date);
    }
  }
  if (d.statut === 'adoptee' && d.type !== 'CONST') push('', 'PROM', `Attend sa ${term('promulgation', 'promulgation')} (15 jours max.)`);
  if (d.statut === 'deposee') push('', 'AN', 'Pas encore inscrit à l’ordre du jour');
  if (d.statut === 'retiree') push('↩', 'AN', 'Retiré par son auteur');
  return `<ul class="moments">${out.map(m => `<li style="--c:${m.c}"><span class="mi">${m.icon}</span><span>${m.html}${m.date ? `<span class="md">${fdate(m.date)}</span>` : ''}</span></li>`).join('')}</ul>`;
}

function months(a, b) {
  const m = Math.round((new Date(b) - new Date(a)) / (864e5 * 30.4));
  return m < 1 ? 'moins d’un mois' : m === 1 ? '1 mois' : m < 24 ? `${m} mois` : `${Math.round(m / 12)} ans`;
}

function banner(d) {
  const B = {
    promulguee: ['green', '', `Promulguée le ${fdate(d.promulgation?.date || d.maj)}`, d.depot && d.promulgation ? `Loi n° ${esc(d.promulgation.numero)} · ${months(d.depot, d.promulgation.date)} entre le dépôt et la loi` : ''],
    adoptee: ['teal', '', 'Adoptée définitivement', esc(d.etape || '')],
    navette: ['blue', '', 'En cours d’examen', esc(d.etape || '')],
    rejetee: ['red', '', 'Rejetée', esc(d.etape || '')],
    censuree: ['red', '', 'Censurée', 'par le Conseil constitutionnel'],
    deposee: ['slate', '', 'Déposée, jamais débattue', 'comme la majorité des propositions de loi'],
    retiree: ['slate', '↩', 'Retirée', 'par son auteur'],
  }[d.statut];
  if (!B) return '';
  return `<div class="banner tone-${B[0]}" style="--t:var(--v-${B[0]})"><span class="big">${B[1]}</span><div><b>${B[2]}</b><div class="sub">${B[3]}</div></div></div>`;
}

// ─────────────────────────────────────────── Parcours « ligne de métro »
function metro(d) {
  const steps = d.steps.map((s, i) => ({ ...s, _i: i })).filter(PARCOURS);
  const ongoing = ['navette', 'deposee'].includes(d.statut);
  const st = steps.map((s, i) => {
    let res = s.resultat, resLabel = res ? RESULT_TXT[res] : '';
    if (s.chambre === 'CMP') {
      res = s.cmp === 'desaccord' ? 'desaccord' : (OK.includes(s.voteAN) && OK.includes(s.voteSN)) ? 'accord' : s.cmp;
      resLabel = s.cmp === 'accord' ? (res === 'accord' ? 'Accord, texte voté' : 'Accord') : s.cmp === 'desaccord' ? 'Échec' : 'Convoquée';
    }
    if (s.chambre === 'CC') { resLabel = d.conseilConstitutionnel?.resultat || 'Saisi'; res = /non conforme/i.test(resLabel) ? 'rejete' : 'adopte'; }
    if (s.chambre === 'PROM') { resLabel = d.promulgation ? `Loi ${d.promulgation.numero}` : ''; res = 'adopte'; }
    const current = ongoing && i === steps.length - 1;
    const color = KO.includes(res) ? 'var(--bad)' : OK.includes(res) ? 'var(--ok)' : 'var(--muted)';
    const node = s.chambre === 'AN' ? 'AN' : s.chambre === 'SN' ? 'S' : s.chambre === 'CMP' ? 'CMP' : s.chambre === 'CC' ? '' : '✓';
    return `<a class="station done c-${s.chambre}${current ? ' current' : ''}" href="#step-${s._i}" style="--line:var(--c);color:inherit;text-decoration:none">
      <div class="node">${node}</div>${res && RESULT_ICON[res] && s.chambre !== 'PROM' ? `<span class="badge" style="color:${color}">${RESULT_ICON[res]}</span>` : ''}
      <div class="sw">${esc(CHAMBRE[s.chambre]?.court || s.chambre)}</div>
      <div class="sl">${esc(s.chambre === 'AN' || s.chambre === 'SN' ? s.label : CHAMBRE[s.chambre].nom)}</div>
      <div class="sd">${s.fin ? fdate(s.fin, true) : s.debut ? 'depuis ' + fdate(s.debut, true) : ''}</div>
      ${resLabel ? `<div class="sr" style="color:${color}">${esc(resLabel)}</div>` : current ? '<div class="sr" style="color:var(--c)">En cours</div>' : ''}
    </a>`;
  });
  for (const g of d.suite || []) {
    st.push(`<div class="station ghost c-${g.chambre}">
      <div class="node">${g.chambre === 'AN' ? 'AN' : g.chambre === 'SN' ? 'S' : g.chambre === 'CMP' ? 'CMP' : g.chambre === 'CC' ? '' : g.chambre === 'CONGRES' ? '' : '✓'}</div>
      <div class="sw">${esc(CHAMBRE[g.chambre]?.court || '')}</div><div class="sl">${esc(g.label)}</div><div class="sd">${g.optionnel ? 'éventuellement' : 'à venir'}</div></div>`);
  }
  return `<div class="metro" aria-label="Parcours du texte">${st.join('')}</div>`;
}

// ─────────────────────────────────────────── Chronologie détaillée
function timeline(d, groupes) {
  const steps = d.steps;
  return `<div class="timeline">${steps.map((s, i) => {
    const where = CHAMBRE[s.chambre]?.nom || '';
    const title = READING(s) ? s.label : s.chambre === 'CMP' || s.chambre === 'CC' || s.chambre === 'PROM' ? CHAMBRE[s.chambre].nom : s.label;
    const MINOR = ['rapporteur', 'saisine_avis', 'info', 'saisine', 'rapport'];
    const renderEv = e => {
      const key = ['decision', 'cmp_decision', 'cc_decision', 'promulgation', 'art493', 'censure'].includes(e.type);
      let extra = '';
      if (e.personnes) extra = ' : ' + e.personnes.slice(0, 8).map(p => actorLink(p, groupes)).join(', ') + (e.personnes.length > 8 ? ` et ${e.personnes.length - 8} autres` : '');
      if (e.type === 'seance' && e.dates?.length > 1) extra = ` <span class="muted small">(${e.dates.map(x => fdate(x, true)).join(', ')})</span>`;
      if (e.url) extra += ` · <a class="ext" href="${esc(e.url.replace('http://', 'https://'))}" target="_blank" rel="noopener">${e.type === 'promulgation' ? 'Légifrance' : 'Décision'}</a>`;
      if (e.type === 'procacc') return evRow(e, `${term('procacc', 'Procédure accélérée')} engagée par le Gouvernement`, false);
      if (e.type === 'cmp_convocation') return evRow(e, `Convocation d'une ${term('cmp', 'commission mixte paritaire')}`, false);
      const scr = e.scrutins?.length ? `<div data-vote="${e.scrutins[e.scrutins.length - 1]}"></div>` : '';
      return evRow(e, esc(e.titre) + extra, key, e.type === 'decision' || e.type === 'censure' ? decIcon(e.outcome) : null) + scr;
    };
    const major = s.events.filter(e => !MINOR.includes(e.type));
    const minor = s.events.filter(e => MINOR.includes(e.type));
    const evs = major.map(renderEv).join('') + (minor.length ? `<details class="more-box small"><summary>${minor.length} détail${minor.length > 1 ? 's' : ''} technique${minor.length > 1 ? 's' : ''} (commissions saisies, rapporteurs…)</summary>${minor.map(renderEv).join('')}</details>` : '');
    const hasVoteCard = s.events.some(e => e.scrutins?.length);
    const keyVote = !hasVoteCard && s.scrutinCle ? `<div data-vote="${s.scrutinCle}"></div>` : '';
    const nScr = s.scrutins?.length || 0;
    return `<div class="tl-step c-${s.chambre}" id="step-${i}">
      <span class="tl-dot"></span>
      <div class="tl-head"><span class="where">${esc(where)}</span><h3>${esc(title)}</h3><span class="muted small">${s.debut ? fdate(s.debut, true) : ''}${s.fin && s.fin !== s.debut ? ' → ' + fdate(s.fin, true) : ''}</span></div>
      <div class="tl-body">${evs || '<p class="muted small">Pas encore d’étape enregistrée.</p>'}${keyVote}
        ${nScr ? `<p class="small" style="margin-top:6px"><a href="#votes-list" data-filter-step="${i}">${plural(nScr, 'scrutin public', 'scrutins publics')} pendant cette lecture →</a></p>` : ''}
        ${s.chambre === 'SN' && s.resultat ? `<p class="note">Vote du Sénat ${info('Le détail nominatif des votes du Sénat n’est pas publié dans les données ouvertes utilisées ici.')}</p>` : ''}
      </div>
    </div>`;
  }).join('')}</div>`;
}
function evRow(e, html, key, icon) {
  return `<div class="ev${key ? ' key' : ''}"><span class="d">${e.date ? fdate(e.date, true) : ''}</span><span class="i" aria-hidden="true">${icon || EV_ICON[e.type] || '•'}</span><span class="t">${html}</span></div>`;
}

// ─────────────────────────────────────────── Carte de vote (chargée à la demande)
export async function voteCard(num, groupes) {
  const s = await load(`scrutins/${num}`);
  const gs = s.groupes.map(g => ({ ...g, info: groupes.get(g.g) })).filter(g => g.info).sort((a, b) => a.info.ordre - b.info.ordre);
  const posName = { p: 'pour', c: 'contre', a: 'abstention', n: 'pas de position' };
  return `<div class="vote-card">
    <div class="vh"><a href="vote/${s.num}"><b>Scrutin n° ${s.num}</b></a><span>${resChip(s.adopte)} · <span class="muted">${fdate(s.date)}</span></span></div>
    <div class="small" style="margin-bottom:8px">${esc(s.titre)}</div>
    ${voteBar(s.pour, s.contre, s.abstention, 0, true)}
    ${voteLabels(s.pour, s.contre, s.abstention)}
    <div class="gpos" aria-label="Position des groupes">${gs.map(g => `<span class="${g.pos}" data-tip="${esc(g.info.nom)} : majoritairement ${posName[g.pos]} (${g.p.length} pour, ${g.c.length} contre, ${g.a.length} abst.)"><i style="background:${g.info.couleur}"></i>${esc(g.info.sigle)} <b>${{ p: 'POUR', c: 'CONTRE', a: 'ABST', n: '–' }[g.pos]}</b></span>`).join('')}</div>
  </div>`;
}

// ─────────────────────────────────────────── Page
export async function render(el, uid) {
  const [d, c, dos] = await Promise.all([load(`dossiers/${uid}`), ctx(), dossiersIndex()]);
  setTitle(d.titre);
  const th = dos.themes[d.theme];
  const isLoi = d.cat === 'loi';
  const scr = d.scrutins || [];
  const kinds = {};
  scr.forEach(s => { kinds[s[2]] = (kinds[s[2]] || 0) + 1; });

  el.innerHTML = `<div class="page">
    <div class="crumbs"><a href="lois">Lois</a> › ${esc(d.typeLabel)}</div>
    <div class="page-head">
      <div class="pill-row" style="margin-bottom:10px">
        <span class="chip">${esc(d.typeLabel)}</span>
        ${themeChip(d.theme, dos.themes)}
        ${d.procAcc ? `<span class="chip gouv">${term('procacc', 'Procédure accélérée')}</span>` : ''}
        ${d.art493 ? `<span class="chip gouv">${term('art493', '49.3')} utilisé${d.art493 > 1 ? ` ${d.art493} fois` : ''}</span>` : ''}
        ${d.cmp ? `<span class="chip cmp">${term('cmp', 'CMP')} ${d.cmp === 'accord' ? 'conclusive' : d.cmp === 'desaccord' ? 'en échec' : 'convoquée'}</span>` : ''}
      </div>
      <h1>${esc(d.titre)}</h1>
      ${d.titreLong && d.titreLong.toLowerCase() !== d.titre.toLowerCase() ? `<p class="lead">${esc(ucfirst(d.titreLong))}</p>` : ''}
      <div class="head-actions">${shareBtn()}${d.urlAN ? `<a class="btn small" href="${esc(d.urlAN)}" target="_blank" rel="noopener">Dossier officiel ↗</a>` : ''}</div>
    </div>
    ${banner(d)}

    ${tabsHtml('l', [['parcours', 'Parcours'], ['etapes', 'Étape par étape'], ...(scr.length ? [['votes', `Votes (${nf(scr.length)})`]] : []), ['fiche', 'Fiche']], ['parcours', 'etapes', 'votes', 'fiche'].includes(hashParams().tab) ? hashParams().tab : 'parcours')}

    <div data-panel-of="l" data-panel="parcours">
    ${isLoi && d.steps.some(PARCOURS) ? `<section class="card" style="margin-bottom:18px">${ttl('', 'Le parcours', 'teal', 'h3')}${metro(d)}
      <div class="legend"><span><i style="background:var(--an)"></i>Assemblée</span><span><i style="background:var(--sn)"></i>Sénat</span><span><i style="background:var(--cmp)"></i>CMP</span><span><i style="background:var(--cc)"></i>Conseil const.</span><span><i style="background:var(--prom)"></i>Promulgation</span><span><i style="border:2px dashed var(--muted)"></i>À venir</span></div>
    </section>` : ''}
      <div class="two-col">
        <div>
        <section class="card">${ttl('', 'L’histoire du texte', 'blue', 'h3')}<div style="margin-top:12px">${moments(d)}</div></section>
        ${d.prochain ? `<div class="next-box"><div><b>Prochain rendez-vous : <span>${fdateDay(d.prochain.date)}</span> à ${d.prochain.date.slice(11, 16).replace(':', 'h')}</b><br><span class="small">${esc(d.prochain.organe || '')} — ${esc(d.prochain.objet || '')}</span></div></div>` : ''}
        </div>
        <aside>
        ${scr.length ? `<section class="card" style="margin-top:0">
          ${ttl('', 'Les votes', 'violet', 'h3')}
          <p class="small muted">${plural(scr.length, 'scrutin public', 'scrutins publics')} à l'Assemblée sur ce texte.</p>
          ${Object.entries(kinds).sort((a, b) => b[1] - a[1]).map(([k, n]) => {
            const adopt = scr.filter(s => s[2] === k && s[3]).length;
            return `<div class="small" style="display:flex;justify-content:space-between;gap:8px;margin:4px 0"><span>${esc(KIND[k] || k)}</span><span class="num">${n} · <span class="res ok">${adopt} ✓</span> <span class="res ko">${n - adopt} ✕</span></span></div>`;
          }).join('')}
        </section>` : ''}
        </aside>
      </div>
    </div>

    <div data-panel-of="l" data-panel="etapes">
      <p class="muted small" style="margin-top:0">Le détail de chaque lecture : commission, séance, votes.</p>
      ${timeline(d, c.groupes)}
    </div>

    <div data-panel-of="l" data-panel="votes" id="votes-list">
          <div class="filters">${seg('vk', [['', 'Tous'], ...Object.entries(kinds).sort((a, b) => b[1] - a[1]).map(([k, n]) => [k, `${KIND[k] || k} (${n})`])], '')}</div>
          <div id="vlist" class="list"></div>
    </div>

    <div data-panel-of="l" data-panel="fiche" style="max-width:720px">
        <section class="card">
          ${ttl('', 'Fiche', 'orange', 'h3')}
          <dl class="kv small" style="margin-top:10px">
            <dt>Type</dt><dd>${esc(d.typeLabel)}${d.procedure && d.procedure !== d.typeLabel ? `<br><span class="muted">${esc(d.procedure)}</span>` : ''}</dd>
            ${d.depot ? `<dt>Dépôt</dt><dd>${fdate(d.depot)}${d.origine ? ` ${CHAMBRE[d.origine].a}` : ''}</dd>` : ''}
            ${d.auteurs?.length ? `<dt>${d.gouv ? 'Présenté par' : d.auteurs.length > 1 ? 'Auteurs' : 'Auteur'}</dt><dd>${d.auteurs.map(a => actorLink(a, c.groupes)).join('<br>')}${d.cosignataires ? `<br><span class="muted">+ ${plural(d.cosignataires, 'cosignataire')}</span>` : ''}</dd>` : ''}
            ${d.rapporteurs?.length ? `<dt>${term('rapporteur', d.rapporteurs.length > 1 ? 'Rapporteurs' : 'Rapporteur')}</dt><dd>${d.rapporteurs.slice(0, 6).map(a => actorLink(a, c.groupes)).join('<br>')}${d.rapporteurs.length > 6 ? `<details class="more-box"><summary>et ${d.rapporteurs.length - 6} autres</summary>${d.rapporteurs.slice(6).map(a => actorLink(a, c.groupes)).join('<br>')}</details>` : ''}</dd>` : ''}
            ${d.commission ? `<dt>${term('commission', 'Commission')}</dt><dd>${esc(d.commission)}</dd>` : ''}
            ${d.promulgation ? `<dt>Loi</dt><dd>n° ${esc(d.promulgation.numero)} du ${fdate(d.promulgation.date)}</dd>` : ''}
            ${d.conseilConstitutionnel ? `<dt>Conseil const.</dt><dd>${esc(d.conseilConstitutionnel.resultat || 'saisi')}${d.conseilConstitutionnel.numero ? `<br><span class="muted">Décision ${esc(d.conseilConstitutionnel.numero)}</span>` : ''}</dd>` : ''}
            ${d.maj ? `<dt>Dernière étape</dt><dd>${fdate(d.maj)}${Math.abs((Date.now() - new Date(d.maj)) / 864e5) < 30 ? ` (${relDate(d.maj)})` : ''}</dd>` : ''}
          </dl>
          <div class="list small" style="margin-top:14px;gap:6px">
            ${d.urlAN ? `<a class="ext" href="${esc(d.urlAN)}" target="_blank" rel="noopener">Dossier sur le site de l'Assemblée</a>` : ''}
            ${d.urlSenat ? `<a class="ext" href="${esc(d.urlSenat)}" target="_blank" rel="noopener">Dossier sur le site du Sénat</a>` : ''}
            ${d.promulgation?.url ? `<a class="ext" href="${esc(d.promulgation.url.replace('http://', 'https://'))}" target="_blank" rel="noopener">Texte de la loi sur Légifrance</a>` : ''}
            ${d.conseilConstitutionnel?.url ? `<a class="ext" href="${esc(d.conseilConstitutionnel.url.replace('http://', 'https://'))}" target="_blank" rel="noopener">Décision du Conseil constitutionnel</a>` : ''}
          </div>
        </section>
    </div>
  </div>`;

  let showTab = () => {};
  wireTabs(el, 'l');
  showTab = k => el.querySelector(`[data-tabs="l"] [data-tab="${k}"]`)?.click();
  // Cartes de vote
  el.querySelectorAll('[data-vote]').forEach(async box => {
    try { box.innerHTML = await voteCard(box.dataset.vote, c.groupes); } catch (e) { box.remove(); }
  });

  // Liste des scrutins
  if (scr.length) {
    let kind = '', stepFilter = null;
    const vlist = el.querySelector('#vlist');
    const draw = () => {
      let items = [...scr].sort((a, b) => b[0] - a[0]);
      if (kind) items = items.filter(s => s[2] === kind);
      if (stepFilter) items = items.filter(s => stepFilter.has(s[0]));
      vlist.innerHTML = (stepFilter ? `<div class="small">Filtré sur une lecture · <a href="#" data-clear>tout afficher</a></div>` : '') +
        items.slice(0, 400).map(s => `<a class="row" href="vote/${s[0]}" style="padding:10px 14px">
          <div class="grow"><div class="small" style="color:var(--ink)">${esc(s[7])}</div><div class="meta"><span>${fdate(s[1], true)}</span><span>${esc(KIND[s[2]] || '')}</span></div></div>
          <div class="side" style="min-width:150px">${resChip(s[3])}<div style="margin-top:5px">${voteBar(s[4], s[5], s[6])}</div></div></a>`).join('') +
        (items.length > 400 ? `<p class="muted small">… et ${nf(items.length - 400)} autres.</p>` : '');
    };
    wireSeg(el, 'vk', v => { kind = v; draw(); });
    vlist.addEventListener('click', e => { if (e.target.closest('[data-clear]')) { e.preventDefault(); stepFilter = null; draw(); } });
    el.querySelectorAll('[data-filter-step]').forEach(a => a.addEventListener('click', e => {
      e.preventDefault();
      stepFilter = new Set(d.steps[a.dataset.filterStep].scrutins);
      draw();
      showTab('votes');
      el.querySelector('#votes-list').scrollIntoView({ behavior: 'smooth' });
    }));
    draw();
  }
  // Liens internes vers les étapes (sans casser le routeur)
  el.querySelectorAll('a.station').forEach(a => a.addEventListener('click', e => {
    e.preventDefault();
    showTab('etapes');
    el.querySelector(a.getAttribute('href'))?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }));
}

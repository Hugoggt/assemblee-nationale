// Bibliothèque commune : données, formatage, composants HTML, hémicycle, glossaire.

// ─────────────────────────────────────────── Données
const cache = new Map();
export function load(name) {
  if (!cache.has(name)) {
    cache.set(name, fetch(`data/${name}.json`).then(r => {
      if (!r.ok) throw new Error(`${name} : ${r.status}`);
      return r.json();
    }).catch(e => { cache.delete(name); throw e; }));
  }
  return cache.get(name);
}

let ctxPromise;
/** Données communes à presque toutes les pages : méta + groupes. */
export function ctx() {
  if (!ctxPromise) {
    ctxPromise = Promise.all([load('meta'), load('groupes')]).then(([meta, g]) => {
      const groupes = new Map(g.groupes.map(x => [x.id, x]));
      const actifs = c => g.groupes.filter(x => x.chambre === c && x.effectif > 0).sort((a, b) => a.ordre - b.ordre);
      return { meta, groupes, gdata: g, an: actifs('AN'), sn: actifs('SN') };
    });
  }
  return ctxPromise;
}

export async function deputes() {
  const list = await load('deputes');
  if (!list._index) Object.defineProperty(list, '_index', { value: new Map(list.map(d => [d.id, d])) });
  return list;
}
export async function senateurs() {
  const list = await load('senateurs');
  if (!list._index) Object.defineProperty(list, '_index', { value: new Map(list.map(d => [d.id, d])) });
  return list;
}
export async function scrutinsIndex() {
  const s = await load('scrutins');
  if (!s._byNum) {
    const rows = s.rows.map(r => ({
      num: r[0], date: r[1], kind: r[2], type: r[3], adopte: !!r[4], pour: r[5], contre: r[6],
      abstention: r[7], votants: r[8], titre: r[9], dossier: r[10], requis: r[11],
    }));
    Object.defineProperty(s, 'list', { value: rows });
    Object.defineProperty(s, '_byNum', { value: new Map(rows.map(r => [r.num, r])) });
    // ordre chronologique (index des chaînes de votes)
    const chrono = [...rows].sort((a, b) => a.num - b.num);
    Object.defineProperty(s, 'chrono', { value: chrono });
  }
  return s;
}
export async function dossiersIndex() {
  const d = await load('dossiers');
  if (!d._index) Object.defineProperty(d, '_index', { value: new Map(d.dossiers.map(x => [x.uid, x])) });
  return d;
}

// ─────────────────────────────────────────── Formatage
const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
export const esc = s => (s == null ? '' : String(s).replace(/[&<>"']/g, c => ESC[c]));
const MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'];
const MOIS_C = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];
export function fdate(d, short = false) {
  if (!d) return '';
  const [y, m, j] = d.slice(0, 10).split('-').map(Number);
  return `${j === 1 ? '1er' : j} ${(short ? MOIS_C : MOIS)[m - 1]} ${y}`;
}
export function fdateDay(d) {
  const dt = new Date(d.slice(0, 10) + 'T12:00:00');
  const s = dt.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' });
  return s[0].toUpperCase() + s.slice(1);
}
export const nf = n => (n == null ? '–' : Number(n).toLocaleString('fr-FR'));
export const pct = (n, d = 0) => (n == null ? '–' : `${Number(n).toLocaleString('fr-FR', { maximumFractionDigits: d })} %`);
export function age(d) {
  if (!d) return null;
  const b = new Date(d), t = new Date();
  return t.getFullYear() - b.getFullYear() - ((t.getMonth() < b.getMonth() || (t.getMonth() === b.getMonth() && t.getDate() < b.getDate())) ? 1 : 0);
}
export function daysAgo(d) {
  return Math.round((Date.now() - new Date(d.slice(0, 10) + 'T12:00:00')) / 864e5);
}
export function relDate(d) {
  const n = daysAgo(d);
  if (n === 0) return "aujourd'hui";
  if (n === 1) return 'hier';
  if (n === -1) return 'demain';
  if (n < 0) return `dans ${-n} jours`;
  if (n < 30) return `il y a ${n} jours`;
  return fdate(d, true);
}
export const plural = (n, s, p) => `${nf(n)} ${n > 1 ? (p || s + 's') : s}`;
export const ucfirst = s => (s ? s[0].toUpperCase() + s.slice(1) : s);
export function norm(s) {
  return (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}
export function debounce(fn, ms = 180) {
  let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

// ─────────────────────────────────────────── Libellés
export const CHAMBRE = {
  AN: { nom: 'Assemblée nationale', court: 'Assemblée', art: "l'Assemblée", a: "à l'Assemblée" },
  SN: { nom: 'Sénat', court: 'Sénat', art: 'le Sénat', a: 'au Sénat' },
  CMP: { nom: 'Commission mixte paritaire', court: 'CMP', art: 'la CMP', a: 'en CMP' },
  CC: { nom: 'Conseil constitutionnel', court: 'Conseil const.', art: 'le Conseil constitutionnel', a: 'au Conseil constitutionnel' },
  PROM: { nom: 'Promulgation', court: 'Promulgation', art: 'le Président de la République', a: 'au Journal officiel' },
  CONGRES: { nom: 'Congrès', court: 'Congrès', art: 'le Congrès', a: 'au Congrès' },
};
export const KIND = {
  ensemble: 'Vote sur l\'ensemble', censure: 'Motion de censure', motion: 'Motion de procédure', article: 'Vote d\'un article',
  amendement: 'Amendement', declaration: 'Déclaration du Gouvernement', resolution: 'Résolution', autre: 'Autre vote',
};
export const RESULT_TXT = {
  adopte: 'Adopté', conforme: 'Adopté conforme', modifie: 'Modifié', rejete: 'Rejeté', adopte493: '49.3',
  rejete493: 'Rejeté', motion_adoptee: 'Rejeté', accord: 'Accord', desaccord: 'Désaccord',
};
export const RESULT_ICON = {
  adopte: '✓', conforme: '✓', modifie: '✎', rejete: '✕', adopte493: '', rejete493: '✕', motion_adoptee: '✕', accord: '', desaccord: '✕',
};
export const POS = { p: 'Pour', c: 'Contre', a: 'Abstention', n: 'Non-votant', '.': 'Absent', '-': '—' };

// ─────────────────────────────────────────── Composants
export function gchip(g, opts = {}) {
  if (!g) return '<span class="gchip"><i style="background:var(--absent)"></i>—</span>';
  const inner = `<i style="background:${esc(g.couleur)}"></i>${esc(g.sigle)}`;
  const tip = `data-tip="${esc(g.nom)}"`;
  return opts.link === false ? `<span class="gchip" ${tip}>${inner}</span>` : `<a class="gchip" href="#/groupe/${g.id}" ${tip}>${inner}</a>`;
}
export function statusChip(statut, label) {
  if (!label) return '';
  return `<span class="status st-${esc(statut)}">${esc(label)}</span>`;
}
export function chamberChip(c, label) {
  return `<span class="chip ${c.toLowerCase()}">${esc(label || CHAMBRE[c]?.court || c)}</span>`;
}
export function miniParcours(parcours = [], statut) {
  const short = { AN: 'AN', SN: 'S', CMP: 'CMP', CC: 'CC', PROM: '✓' };
  const out = parcours.map(([code, ch, res]) => {
    const ko = ['rejete', 'motion_adoptee', 'rejete493', 'desaccord'].includes(res);
    const tip = `${CHAMBRE[ch]?.nom || ch} · ${code}${res ? ' · ' + (RESULT_TXT[res] || res) : ''}`;
    return `<span class="m-${ch}${ko ? ' ko' : ''}" data-tip="${esc(tip)}">${ch === 'CMP' ? 'C' : short[ch] || ''}</span>`;
  });
  if (statut === 'navette' || statut === 'deposee') out.push('<span class="pending" data-tip="Suite à venir"></span>');
  return `<span class="mini" aria-label="Parcours">${out.join('')}</span>`;
}
export function voteBar(p, c, a, n = 0, lg = false) {
  const t = p + c + a + n || 1;
  const seg = (v, cls, l) => (v ? `<span class="${cls}" style="width:${(100 * v) / t}%" data-tip="${l} : ${nf(v)}"></span>` : '');
  return `<div class="vbar${lg ? ' lg' : ''}" role="img" aria-label="Pour ${p}, contre ${c}, abstention ${a}">${seg(p, 'vp', 'Pour')}${seg(c, 'vc', 'Contre')}${seg(a, 'va', 'Abstention')}${seg(n, 'vn', 'Non-votants')}</div>`;
}
export function voteLabels(p, c, a, n) {
  return `<div class="vlabels"><span><i class="vp"></i>Pour <b>${nf(p)}</b></span><span><i class="vc"></i>Contre <b>${nf(c)}</b></span><span><i class="va"></i>Abstention <b>${nf(a)}</b></span>${n != null ? `<span><i class="vn"></i>Non-votants <b>${nf(n)}</b></span>` : ''}</div>`;
}
export function posChip(ch) {
  return `<span class="pos pos-${ch === '.' ? 'x' : ch}">${POS[ch] || ch}</span>`;
}
export function resChip(adopte) {
  return adopte ? '<span class="res ok">✓ Adopté</span>' : '<span class="res ko">✕ Rejeté</span>';
}

const PHOTO = id => `https://www.assemblee-nationale.fr/dyn/static/tribun/17/photos/carre/${id.slice(2)}.jpg`;
export function avatar(p, chambre, g, size = '') {
  const ini = `${(p.prenom || '?')[0]}${(p.nom || '?').replace(/^(de |d'|du |le |la )/i, '')[0] || ''}`.toUpperCase();
  const bg = g?.couleur || '#888';
  const img = chambre === 'AN' ? `<img src="${PHOTO(p.id)}" alt="" loading="lazy" onerror="this.remove()">` : '';
  return `<span class="avatar ${size}" style="background:${esc(bg)}">${esc(ini)}${img}</span>`;
}
export function personLink(p, chambre, g, sub) {
  const href = chambre === 'AN' ? `#/depute/${p.id}` : `#/senateur/${p.id}`;
  return `<a class="person" href="${href}">${avatar(p, chambre, g)}<span><span class="pname">${esc(p.prenom)} ${esc(p.nom)}</span><br><span class="pmeta">${sub || ''}</span></span></a>`;
}
/** Lien vers une personne citée dans un dossier (rapporteur, auteur…). */
export function actorLink(a, groupes) {
  if (!a) return '';
  const href = a.chambre === 'AN' ? `#/depute/${a.id}` : a.chambre === 'SN' ? `#/senateur/${a.id}` : null;
  const name = href ? `<a href="${href}">${esc(a.nom)}</a>` : esc(a.nom);
  const extra = a.gouv ? ` <span class="muted">(${esc(a.fonction || 'Gouvernement')})</span>` : a.groupe ? ` <span class="muted">(${esc(a.groupe)}${a.chambre === 'SN' ? ', Sénat' : ''})</span>` : '';
  return name + extra;
}

export function statTile(v, l, s, href, tone, ico) {
  // Pas de <a> englobant : le libellé peut contenir des termes du glossaire (liens).
  return `<div class="stat${tone ? ' tone-' + tone : ''}">${ico ? `<span class="ico" aria-hidden="true">${ico}</span>` : ''}<div class="v">${v}</div><div class="l">${l}</div>${s ? `<div class="s">${s}</div>` : ''}${href ? `<a class="small" href="${href}" style="display:inline-block;margin-top:6px;font-weight:600">Voir →</a>` : ''}</div>`;
}

/** Titre de section avec pastille emoji colorée. */
export function ttl(emoji, text, tone = 'blue', tag = 'h2') {
  return `<${tag} class="ttl tone-${tone}"><span class="b" aria-hidden="true">${emoji}</span>${text}</${tag}>`;
}
/** Petite pastille ⓘ : l'explication reste disponible au survol sans encombrer la page. */
export const info = tip => `<i class="ibtn" tabindex="0" data-tip="${esc(tip)}" aria-label="${esc(tip)}">i</i>`;

export const THEME_COLOR = {
  budget: '#f59e0b', sante: '#ef4444', social: '#ec4899', travail: '#8b5cf6', education: '#3b82f6', justice: '#64748b',
  immigration: '#14b8a6', environnement: '#10b981', logement: '#f97316', transports: '#0ea5e9', agriculture: '#65a30d',
  numerique: '#6366f1', outremer: '#06b6d4', institutions: '#1d4ed8', economie: '#ca8a04', international: '#0891b2',
  culture: '#d946ef', europe: '#2563eb', autre: '#94a3b8',
};
export function themeChip(key, themes) {
  const t = themes[key];
  if (!t) return '';
  return `<a class="chip theme" style="--tc:${THEME_COLOR[key] || '#94a3b8'}" href="#/lois?theme=${key}">${t.emoji} ${esc(t.label)}</a>`;
}
/** Carte compacte d'un texte (grilles de l'accueil, des groupes…). */
export function loiCard(d, themes) {
  const auteur = d.gouv ? 'Gouvernement' : d.auteur ? `${d.auteur.nom}${d.auteur.groupe ? ` (${d.auteur.groupe})` : ''}` : '';
  return `<a class="lcard" href="#/loi/${d.uid}" style="--tc:${THEME_COLOR[d.theme] || 'var(--accent)'}">
    <div class="pill-row">${statusChip(d.statut, d.statutLabel)}<span class="chip theme" style="--tc:${THEME_COLOR[d.theme] || '#94a3b8'}">${themes[d.theme]?.emoji || ''} ${esc(themes[d.theme]?.label || '')}</span></div>
    <div class="lt">${esc(d.titre)}</div>
    <div class="lf"><span>${esc(auteur)}</span>${miniParcours(d.parcours, d.statut)}</div>
  </a>`;
}

// ─────────────────────────────────────────── Hémicycle
/**
 * seats : [{ color, tip, href, key }] déjà triés de la gauche vers la droite.
 * Renvoie un SVG en demi-cercle (places réparties par rangées).
 */
export function hemicycle(seats, { label = '', sub = '', inner = 0.38 } = {}) {
  const n = seats.length;
  let R = 4, radii = [], counts = [];
  for (R = 4; R < 40; R++) {
    const gap = (1 - inner) / (R - 1);
    radii = Array.from({ length: R }, (_, i) => inner + i * gap);
    const cap = radii.reduce((s, r) => s + Math.floor((Math.PI * r) / gap) + 1, 0);
    if (cap >= n) break;
  }
  const gap = (1 - inner) / (R - 1);
  const tot = radii.reduce((s, r) => s + r, 0);
  const raw = radii.map(r => (n * r) / tot);
  counts = raw.map(Math.floor);
  let rest = n - counts.reduce((a, b) => a + b, 0);
  raw.map((v, i) => [v - Math.floor(v), i]).sort((a, b) => b[0] - a[0]).slice(0, rest).forEach(([, i]) => counts[i]++);
  const pos = [];
  radii.forEach((r, i) => {
    const m = counts[i];
    for (let k = 0; k < m; k++) {
      const th = m === 1 ? Math.PI / 2 : Math.PI - (k * Math.PI) / (m - 1);
      pos.push({ th, r });
    }
  });
  pos.sort((a, b) => b.th - a.th || a.r - b.r);
  const S = 200, dot = Math.min(gap * 0.42, 0.04) * S;
  const circles = seats.map((s, i) => {
    const p = pos[i];
    const x = (p.r * Math.cos(p.th) * S).toFixed(1), y = (-p.r * Math.sin(p.th) * S).toFixed(1);
    return `<circle cx="${x}" cy="${y}" r="${dot.toFixed(2)}" fill="${esc(s.color)}" data-tip="${esc(s.tip || '')}"${s.href ? ` data-href="${esc(s.href)}"` : ''}${s.key ? ` data-k="${esc(s.key)}"` : ''}/>`;
  }).join('');
  return `<svg class="hemi" viewBox="-206 -206 412 214" role="img" aria-label="${esc(label + ' ' + sub)}">
    ${circles}
    <text class="center-label" x="0" y="-22" text-anchor="middle">${esc(label)}</text>
    <text class="center-sub" x="0" y="-2" text-anchor="middle">${esc(sub)}</text>
  </svg>`;
}

/** Active les clics et la mise en évidence par groupe d'un hémicycle. */
export function wireHemicycle(root) {
  root.addEventListener('click', e => {
    const c = e.target.closest('circle[data-href]');
    if (c) location.hash = c.dataset.href;
  });
  root.querySelectorAll('[data-hl]').forEach(b => {
    const on = () => root.querySelectorAll('circle[data-k]').forEach(c => c.classList.toggle('dim', c.dataset.k !== b.dataset.hl));
    const off = () => root.querySelectorAll('circle.dim').forEach(c => c.classList.remove('dim'));
    b.addEventListener('mouseenter', on); b.addEventListener('focus', on);
    b.addEventListener('mouseleave', off); b.addEventListener('blur', off);
  });
}

// ─────────────────────────────────────────── Glossaire
export const GLOSSARY = {
  navette: ['Navette', "Le va-et-vient d'un texte entre l'Assemblée nationale et le Sénat. Une loi doit être votée dans les mêmes termes par les deux chambres : tant qu'elles ne sont pas d'accord, le texte « fait la navette ».", 'parcours'],
  cmp: ['Commission mixte paritaire (CMP)', "7 députés et 7 sénateurs réunis pour trouver un compromis quand les deux chambres ne sont pas d'accord. Le Premier ministre (ou, pour une proposition de loi, les présidents des deux chambres) peut la convoquer après deux lectures dans chaque chambre, ou une seule en procédure accélérée.", 'cmp'],
  procacc: ['Procédure accélérée', "Le Gouvernement peut l'engager pour aller plus vite : une seule lecture par chambre suffit avant de convoquer une commission mixte paritaire, au lieu de deux.", 'acceleree'],
  art493: ['Article 49.3', "Le Gouvernement engage sa responsabilité sur un texte : celui-ci est considéré comme adopté sans vote, sauf si une motion de censure, déposée dans les 24 heures, est adoptée. Utilisable sans limite sur les budgets, et pour un seul autre texte par session.", 'arme'],
  censure: ['Motion de censure', "Vote par lequel les députés peuvent renverser le Gouvernement. Elle doit être signée par au moins 58 députés (1/10e) et recueillir la majorité absolue des députés (289 voix) : seuls les votes « pour » sont comptés.", 'arme'],
  lecturedef: ['Lecture définitive', "Si le désaccord persiste après la CMP et une nouvelle lecture, le Gouvernement peut demander à l'Assemblée nationale de statuer définitivement : c'est elle qui a le dernier mot.", 'dernier-mot'],
  nouvellelecture: ['Nouvelle lecture', "Après l'échec d'une CMP, chaque chambre réexamine le texte une nouvelle fois avant une éventuelle lecture définitive à l'Assemblée.", 'dernier-mot'],
  cc: ['Conseil constitutionnel', "Vérifie qu'une loi respecte la Constitution avant sa promulgation. Il peut être saisi par le Président de la République, le Premier ministre, les présidents des deux chambres, 60 députés ou 60 sénateurs. Il peut censurer tout ou partie du texte.", 'cc'],
  promulgation: ['Promulgation', "Le Président de la République signe la loi dans les 15 jours qui suivent son adoption définitive, puis elle est publiée au Journal officiel. Elle devient alors applicable.", 'cc'],
  ppl: ['Proposition de loi', "Un texte de loi déposé par des parlementaires (députés ou sénateurs). La grande majorité n'est jamais inscrite à l'ordre du jour.", 'origine'],
  pjl: ['Projet de loi', "Un texte de loi déposé par le Gouvernement, après avis du Conseil d'État et délibération en Conseil des ministres.", 'origine'],
  commission: ['Commission permanente', "Chaque député et chaque sénateur siège dans une commission spécialisée (affaires sociales, finances, lois…). C'est là que le texte est examiné en premier et amendé, avant la séance publique.", 'parcours'],
  rapporteur: ['Rapporteur', "Le parlementaire chargé d'étudier un texte au nom de sa commission, de proposer des modifications et de présenter le résultat en séance.", 'parcours'],
  amendement: ['Amendement', "Une proposition de modification d'un texte en discussion. Députés, sénateurs et Gouvernement peuvent en déposer : il est voté avant l'article qu'il modifie.", 'parcours'],
  scrutin: ['Scrutin public', "Un vote où le choix de chaque député est enregistré nominativement. La plupart des votes se font à main levée et ne laissent pas de trace individuelle : seuls les scrutins publics sont détaillés ici.", 'vote'],
  solennel: ['Scrutin public solennel', "Un vote nominatif annoncé à l'avance, généralement sur l'ensemble d'un texte important, pour que tous les députés puissent être présents.", 'vote'],
  motionrejet: ['Motion de rejet préalable', "Proposée avant l'examen des articles : si elle est adoptée, le texte est rejeté sans être discuté. À l'Assemblée, cela envoie directement le texte au Sénat (ou met fin à son examen en première lecture).", 'vote'],
  niche: ['Niche parlementaire', "Une journée par mois réservée à l'ordre du jour d'un groupe d'opposition ou minoritaire, qui y fait examiner ses propres textes.", 'origine'],
  groupe: ['Groupe parlementaire', "Les élus qui partagent des affinités politiques se regroupent. Il faut au moins 15 députés ou 10 sénateurs pour former un groupe, qui obtient alors temps de parole, moyens et postes.", 'groupes'],
  conforme: ['Vote conforme', "Quand une chambre adopte un texte exactement dans la version votée par l'autre chambre : la navette s'arrête, la loi est adoptée définitivement.", 'parcours'],
  loiorga: ['Loi organique', "Une loi qui précise l'organisation des pouvoirs publics prévue par la Constitution. Elle est toujours contrôlée par le Conseil constitutionnel, et doit être votée dans les mêmes termes par le Sénat si elle le concerne.", 'speciales'],
  loiconst: ['Révision constitutionnelle', "Modifier la Constitution exige que les deux chambres votent le même texte, puis une approbation par référendum ou par le Congrès (les deux chambres réunies à Versailles, majorité des 3/5).", 'speciales'],
  plf: ['Projet de loi de finances', "Le budget de l'État pour l'année suivante. Le Parlement dispose de 70 jours ; passé ce délai, le Gouvernement peut l'appliquer par ordonnance.", 'speciales'],
  plfss: ['Loi de financement de la Sécurité sociale', "Le budget de la Sécu (santé, retraites, famille…). Le Parlement dispose de 50 jours pour l'examiner.", 'speciales'],
  majabs: ['Majorité absolue', "Plus de la moitié des sièges : 289 sur 577 à l'Assemblée, 175 sur 348 au Sénat. Elle est nécessaire pour une motion de censure ; une loi, elle, est adoptée à la majorité des suffrages exprimés.", 'groupes'],
  delegation: ['Vote par délégation', "Un député absent peut confier son vote à un collègue, qui ne peut recevoir qu'une seule délégation.", 'vote'],
  senatoriales: ['Élections sénatoriales', "Les sénateurs sont élus pour 6 ans au suffrage indirect, par environ 160 000 grands électeurs (surtout des délégués des conseils municipaux). La moitié du Sénat est renouvelée tous les 3 ans.", 'chambres'],
};
export function term(key, text) {
  const g = GLOSSARY[key];
  if (!g) return esc(text);
  return `<a class="term" role="button" tabindex="0" data-term="${key}">${esc(text || g[0])}</a>`;
}

// ─────────────────────────────────────────── Tooltip et popover globaux
export function initOverlays() {
  const tip = document.getElementById('tooltip');
  const pop = document.getElementById('popover');
  let tipTarget = null;
  const place = (el, x, y) => {
    const r = el.getBoundingClientRect();
    let left = x + 14, top = y + 14;
    if (left + r.width > innerWidth - 8) left = x - r.width - 14;
    if (top + r.height > innerHeight - 8) top = y - r.height - 14;
    el.style.left = Math.max(8, left) + 'px';
    el.style.top = Math.max(8, top) + 'px';
  };
  document.addEventListener('pointerover', e => {
    const t = e.target.closest?.('[data-tip]');
    if (!t || !t.dataset.tip) { tip.hidden = true; tipTarget = null; return; }
    tipTarget = t;
    tip.textContent = t.dataset.tip;
    tip.hidden = false;
    place(tip, e.clientX, e.clientY);
  });
  document.addEventListener('pointermove', e => { if (tipTarget) place(tip, e.clientX, e.clientY); });
  document.addEventListener('scroll', () => { tip.hidden = true; }, { passive: true });

  const openTerm = el => {
    const g = GLOSSARY[el.dataset.term];
    if (!g) return;
    pop.innerHTML = `<b>${esc(g[0])}</b>${esc(g[1])}<div style="margin-top:8px"><a href="#/comprendre/${g[2]}">En savoir plus →</a></div>`;
    pop.hidden = false;
    const r = el.getBoundingClientRect();
    const pr = pop.getBoundingClientRect();
    let left = Math.min(r.left, innerWidth - pr.width - 16);
    let top = r.bottom + 8;
    if (top + pr.height > innerHeight - 8) top = r.top - pr.height - 8;
    pop.style.left = Math.max(16, left) + 'px';
    pop.style.top = Math.max(8, top) + 'px';
  };
  document.addEventListener('click', e => {
    const t = e.target.closest('[data-term]');
    if (t) { e.preventDefault(); openTerm(t); return; }
    if (!e.target.closest('#popover')) pop.hidden = true;
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') pop.hidden = true;
    const t = e.target.closest?.('[data-term]');
    if (t && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); openTerm(t); }
  });
  addEventListener('hashchange', () => { pop.hidden = true; tip.hidden = true; });
}

// ─────────────────────────────────────────── Divers
/** Affiche une liste par tranches avec un bouton « Afficher plus ». */
export function paged(container, items, renderItem, step = 30, wrapClass = 'list') {
  let shown = 0;
  container.innerHTML = `<div class="${wrapClass}"></div><div class="more"></div>`;
  const listEl = container.firstElementChild, moreEl = container.lastElementChild;
  const next = () => {
    const chunk = items.slice(shown, shown + step);
    listEl.insertAdjacentHTML('beforeend', chunk.map(renderItem).join(''));
    shown += chunk.length;
    moreEl.innerHTML = shown < items.length ? `<button class="btn">Afficher plus (${nf(items.length - shown)} restants)</button>` : '';
  };
  moreEl.addEventListener('click', e => { if (e.target.closest('button')) next(); });
  if (!items.length) listEl.innerHTML = '<div class="empty">Aucun résultat avec ces filtres.</div>';
  else next();
}

export function seg(name, options, value) {
  return `<div class="seg" role="group" data-seg="${name}">${options.map(([v, l]) => `<button type="button" data-v="${esc(v)}" aria-pressed="${v === value}">${l}</button>`).join('')}</div>`;
}
export function wireSeg(root, name, onChange) {
  const el = root.querySelector(`[data-seg="${name}"]`);
  el.addEventListener('click', e => {
    const b = e.target.closest('button');
    if (!b) return;
    el.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', x === b));
    onChange(b.dataset.v);
  });
}

export function setTitle(t) {
  document.title = t ? `${t} · Hémicycle` : 'Hémicycle · Assemblée nationale et Sénat';
}

/** Lit/écrit des paramètres de filtre dans le hash (#/lois?statut=navette). */
export function hashParams() {
  const q = location.hash.split('?')[1] || '';
  return Object.fromEntries(new URLSearchParams(q));
}
export function setHashParams(params) {
  const base = location.hash.split('?')[0];
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v != null && v !== false)).toString();
  history.replaceState(null, '', base + (qs ? '?' + qs : ''));
}

// ─────────────────────────────────────────── Onglets
/** Barre d'onglets ; les panneaux portent data-panel-of="<name>" data-panel="<clé>". */
export function tabsHtml(name, items, active) {
  return `<div class="tabs" role="tablist" data-tabs="${name}">${items.map(([k, l]) => `<button type="button" role="tab" data-tab="${k}" aria-selected="${k === active}">${l}</button>`).join('')}</div>`;
}
export function wireTabs(root, name, onChange) {
  const bar = root.querySelector(`[data-tabs="${name}"]`);
  if (!bar) return;
  const show = k => {
    bar.querySelectorAll('[data-tab]').forEach(b => b.setAttribute('aria-selected', b.dataset.tab === k));
    root.querySelectorAll(`[data-panel-of="${name}"]`).forEach(p => { p.hidden = p.dataset.panel !== k; });
    onChange?.(k);
  };
  bar.addEventListener('click', e => {
    const b = e.target.closest('[data-tab]');
    if (!b) return;
    show(b.dataset.tab);
    setHashParams({ ...hashParams(), tab: b.dataset.tab });
  });
  show(bar.querySelector('[aria-selected="true"]')?.dataset.tab || bar.querySelector('[data-tab]').dataset.tab);
}

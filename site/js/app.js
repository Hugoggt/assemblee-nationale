import { initOverlays, ctx, esc, fdate } from './lib.js';
import * as home from './pages/home.js';
import * as lois from './pages/lois.js';
import * as loi from './pages/loi.js';
import * as votes from './pages/votes.js';
import * as chambres from './pages/chambres.js';
import * as personnes from './pages/personnes.js';
import * as gouv from './pages/gouvernement.js';
import * as agenda from './pages/agenda.js';
import * as comprendre from './pages/comprendre.js';
import * as recherche from './pages/recherche.js';
import * as comparer from './pages/comparer.js';
import * as apropos from './pages/apropos.js';
import { SITE } from './config.js';

const routes = [
  [/^\/?$/, home.render, ''],
  [/^\/lois$/, lois.render, 'lois'],
  [/^\/loi\/(\w+)$/, loi.render, 'lois'],
  [/^\/votes$/, votes.list, 'votes'],
  [/^\/vote\/(\d+)$/, votes.detail, 'votes'],
  [/^\/assemblee$/, chambres.assemblee, 'assemblee'],
  [/^\/senat$/, chambres.senat, 'senat'],
  [/^\/groupe\/(\w+)$/, chambres.groupe, null],
  [/^\/deputes$/, personnes.deputes, 'assemblee'],
  [/^\/depute\/(\w+)$/, personnes.depute, 'assemblee'],
  [/^\/senateurs$/, personnes.senateurs, 'senat'],
  [/^\/senateur\/(\w+)$/, personnes.senateur, 'senat'],
  [/^\/gouvernement$/, gouv.render, 'gouvernement'],
  [/^\/agenda$/, agenda.render, 'agenda'],
  [/^\/comprendre(?:\/([\w-]+))?$/, comprendre.render, 'comprendre'],
  [/^\/recherche$/, recherche.render, null],
  [/^\/comparer$/, comparer.render, 'comparer'],
  [/^\/a-propos$/, apropos.render, null],
];

const main = document.getElementById('main');
let lastPath = null;

async function route() {
  const raw = location.hash.slice(1) || '/';
  const path = raw.split('?')[0];
  const fromLearn = lastPath?.startsWith('/comprendre') && path.startsWith('/comprendre');
  lastPath = path;
  const match = routes.map(([rx, fn, nav]) => [rx.exec(path), fn, nav]).find(([m]) => m);
  document.querySelectorAll('.mainnav a').forEach(a => {
    const key = a.getAttribute('href').slice(2);
    a.classList.toggle('active', !!match && match[2] === key);
  });
  document.getElementById('menu-toggle').setAttribute('aria-expanded', 'false');
  document.querySelector('.mainnav').classList.remove('open');
  if (fromLearn && main.querySelector('.learn')) {
    comprendre.scrollToSection(path.split('/')[2]); // navigation interne au guide
    return;
  }
  if (!match) {
    main.innerHTML = '<div class="page"><h1>Page introuvable</h1><p><a href="#/">Retour à l\'accueil</a></p></div>';
    return;
  }
  const [m, fn] = match;
  main.innerHTML = '<div class="loading">Chargement…</div>';
  try {
    await fn(main, ...m.slice(1));
  } catch (e) {
    console.error(e);
    main.innerHTML = `<div class="page"><h1>Oups</h1><p>Impossible d'afficher cette page.</p><pre class="note">${esc(e.message)}</pre>
      <p class="note">Les données sont-elles générées ? Lancez <code>python pipeline/fetch.py</code> puis <code>python pipeline/build.py</code>.</p></div>`;
  }
  if (!path.startsWith('/comprendre')) window.scrollTo(0, 0);
}

addEventListener('hashchange', route);
initOverlays();
route();

// En-tête : recherche, thème, menu mobile
document.getElementById('global-search').addEventListener('submit', e => {
  e.preventDefault();
  const q = document.getElementById('q').value.trim();
  if (q) location.hash = `#/recherche?q=${encodeURIComponent(q)}`;
});
document.getElementById('theme-toggle').addEventListener('click', () => {
  const root = document.documentElement;
  const dark = root.dataset.theme ? root.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
  root.dataset.theme = dark ? 'light' : 'dark';
  try { localStorage.setItem('theme', root.dataset.theme); } catch (e) { /* stockage indisponible */ }
});
document.getElementById('menu-toggle').addEventListener('click', e => {
  const nav = document.querySelector('.mainnav');
  nav.classList.toggle('open');
  e.currentTarget.setAttribute('aria-expanded', nav.classList.contains('open'));
});
ctx().then(({ meta }) => {
  document.getElementById('footer-meta').textContent = `Données mises à jour le ${fdate(meta.genere)} à ${meta.genere.slice(11, 16)}. ${meta.legislature}e législature de la Ve République.`;
}).catch(() => {});

// Pied de page : bouton de soutien si un lien est configuré
if (SITE.soutienUrl) {
  const box = document.getElementById('footer-support');
  if (box) box.innerHTML = `<a class="footer-support" href="${SITE.soutienUrl}" target="_blank" rel="noopener">${SITE.soutienLabel}</a>`;
}

import { initOverlays, initShare, ctx, esc, fdate, navigate, BASE, deputes, senateurs, dossiersIndex } from './lib.js';
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
import * as budget from './pages/budget.js';
import { SITE } from './config.js';

// Les pages acceptent un identifiant officiel ou une adresse lisible (slug).
const resolve = {
  loi: async k => (/^DLR\w+$/.test(k) ? k : (await dossiersIndex())._bySlug.get(k)?.uid),
  dep: async k => (/^PA\d+$/.test(k) ? k : (await deputes())._bySlug.get(k)?.id),
  sen: async k => (/^PA\d+$/.test(k) ? k : (await senateurs())._bySlug.get(k)?.id),
  grp: async k => (/^PO\d+$/.test(k) ? k : [...(await ctx()).groupes.values()].find(g => g.slug === k)?.id),
};

const routes = [
  [/^\/$/, home.render, ''],
  [/^\/lois$/, lois.render, 'lois'],
  [/^\/loi\/([\w-]+)$/, loi.render, 'lois', 'loi'],
  [/^\/votes$/, votes.list, 'votes'],
  [/^\/vote\/(\d+)$/, votes.detail, 'votes'],
  [/^\/comparer$/, comparer.render, 'comparer'],
  [/^\/budget$/, budget.render, 'budget'],
  [/^\/assemblee$/, chambres.assemblee, 'assemblee'],
  [/^\/senat$/, chambres.senat, 'senat'],
  [/^\/groupe\/([\w-]+)$/, chambres.groupe, null, 'grp'],
  [/^\/deputes$/, personnes.deputes, 'assemblee'],
  [/^\/depute\/([\w-]+)$/, personnes.depute, 'assemblee', 'dep'],
  [/^\/senateurs$/, personnes.senateurs, 'senat'],
  [/^\/senateur\/([\w-]+)$/, personnes.senateur, 'senat', 'sen'],
  [/^\/gouvernement$/, gouv.render, 'gouvernement'],
  [/^\/agenda$/, agenda.render, 'agenda'],
  [/^\/(?:guide|comprendre)(?:\/([\w-]+))?$/, comprendre.render, 'guide'],
  [/^\/recherche$/, recherche.render, null],
  [/^\/a-propos$/, apropos.render, null],
];

const main = document.getElementById('main');
let lastPath = null;
let first = true;

function currentPath() {
  let p = location.pathname;
  if (p.startsWith(BASE)) p = '/' + p.slice(BASE.length);
  p = p.replace(/\.html$/, '').replace(/\/index$/, '/');
  if (p.length > 1) p = p.replace(/\/$/, '');
  return p || '/';
}

async function route() {
  const path = currentPath();
  const fromLearn = lastPath?.startsWith('/guide') && path.startsWith('/guide');
  lastPath = path;
  const match = routes.map(([rx, fn, nav, res]) => [rx.exec(path), fn, nav, res]).find(([m]) => m);
  document.querySelectorAll('.mainnav a').forEach(a => {
    a.classList.toggle('active', !!match && match[2] === a.getAttribute('href'));
  });
  document.body.dataset.section = match ? (match[2] ?? '') : '';
  document.getElementById('menu-toggle').setAttribute('aria-expanded', 'false');
  document.querySelector('.mainnav').classList.remove('open');
  if (fromLearn && main.querySelector('.learn')) {
    comprendre.scrollToSection(path.split('/')[2]);
    return;
  }
  if (!match) {
    main.innerHTML = '<div class="page"><h1>Page introuvable</h1><p><a href="./">Retour à l\'accueil</a></p></div>';
    return;
  }
  const [m, fn, , res] = match;
  if (!first) main.innerHTML = '<div class="loading">Chargement…</div>';
  first = false;
  try {
    await ctx();
    const args = m.slice(1);
    if (res) {
      const id = await resolve[res](decodeURIComponent(args[0]));
      if (!id) {
        main.innerHTML = '<div class="page"><h1>Page introuvable</h1><p>Cette page n’existe pas ou plus. <a href="./">Retour à l’accueil</a></p></div>';
        return;
      }
      args[0] = id;
    }
    await fn(main, ...args);
  } catch (e) {
    console.error(e);
    main.innerHTML = `<div class="page"><h1>Oups</h1><p>Impossible d'afficher cette page.</p><pre class="note">${esc(e.message)}</pre></div>`;
  }
  if (!path.startsWith('/guide')) window.scrollTo(0, 0);
}

// Liens internes : navigation sans rechargement
document.addEventListener('click', e => {
  if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  const a = e.target.closest('a[href]');
  if (!a || a.target === '_blank' || a.hasAttribute('download')) return;
  const href = a.getAttribute('href');
  if (href.startsWith('#')) {
    // Ancre dans la page (la balise <base> la ferait pointer vers l'accueil)
    e.preventDefault();
    if (href.length > 1) document.getElementById(href.slice(1))?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    return;
  }
  if (href.startsWith('mailto:') || /^https?:/.test(href)) return;
  const url = new URL(href, document.baseURI);
  if (url.origin !== location.origin || !url.pathname.startsWith(BASE)) return;
  if (/\.(json|zip|xml|txt|png|jpg|svg|woff2?)$/.test(url.pathname)) return;
  e.preventDefault();
  if (url.pathname === location.pathname && url.search === location.search) return;
  history.pushState(null, '', url);
  route();
});
addEventListener('popstate', route);
addEventListener('app:navigate', route);
initOverlays();
initShare();
route();

// En-tête : recherche, thème, menu mobile
document.getElementById('global-search').addEventListener('submit', e => {
  e.preventDefault();
  const q = document.getElementById('q').value.trim();
  if (q) navigate(`recherche?q=${encodeURIComponent(q)}`);
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

if (SITE.soutienUrl) {
  const box = document.getElementById('footer-support');
  if (box) box.innerHTML = `<a class="footer-support" href="${SITE.soutienUrl}" target="_blank" rel="noopener">${SITE.soutienLabel}</a>`;
}

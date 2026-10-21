import { load, dossiersIndex, esc, fdateDay, setTitle, seg, wireSeg } from '../lib.js';

export async function render(el) {
  setTitle('Agenda');
  const [agenda, dos] = await Promise.all([load('agenda'), dossiersIndex()]);
  el.innerHTML = `<div class="page">
    <div class="page-head"><h1>Agenda</h1>
      <p class="lead">Séances dans l'hémicycle et réunions de commission à venir.</p></div>
    <div class="filters">${seg('t', [['', 'Tout'], ['seance', 'Séances publiques'], ['commission', 'Commissions']], '')}</div>
    <div id="days"></div>
    <p class="note">L'ordre du jour peut évoluer jusqu'au dernier moment. Le programme du Sénat n'est pas inclus dans les données utilisées.</p>
  </div>`;
  const draw = type => {
    const items = agenda.filter(a => !type || a.type === type);
    const byDay = new Map();
    items.forEach(a => { const k = a.date.slice(0, 10); if (!byDay.has(k)) byDay.set(k, []); byDay.get(k).push(a); });
    el.querySelector('#days').innerHTML = byDay.size ? [...byDay].map(([day, evs]) => `<div class="day"><h3>${fdateDay(day)}</h3>
      ${evs.map(a => `<div class="ag"><div><div class="h">${a.date.slice(11, 16).replace(':', 'h')}</div><span class="chip ${a.type === 'seance' ? 'an' : ''}">${a.type === 'seance' ? 'Séance' : 'Commission'}</span></div>
        <div style="min-width:0"><b>${esc(a.organe || '')}</b><ul class="small">${a.points.map(p => {
          const d = p.dossiers.map(u => dos._index.get(u)).find(Boolean);
          return `<li>${d ? `${esc(p.objet)} : <a href="#/loi/${d.uid}">${esc(d.titre)}</a>` : esc(p.objet)}</li>`;
        }).join('')}</ul></div></div>`).join('')}</div>`).join('') : '<div class="empty">Rien de programmé pour le moment.</div>';
  };
  wireSeg(el, 't', draw);
  draw('');
}

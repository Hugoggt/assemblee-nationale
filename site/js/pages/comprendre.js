import { ctx, dossiersIndex, esc, nf, fdate, term, setTitle, GLOSSARY, plural } from '../lib.js';

const FLOW = [
  ['AN', 'Dépôt', 'Le texte arrive', `Un <b>projet de loi</b> vient du Gouvernement (après avis du Conseil d'État et passage en Conseil des ministres). Une <b>proposition de loi</b> vient d'un ou plusieurs parlementaires. Le texte est déposé à l'Assemblée ou au Sénat — les projets de budget commencent toujours par l'Assemblée, ceux sur les collectivités territoriales par le Sénat.`],
  ['AN', 'Commission', 'Le travail de fond', `Le texte est envoyé à l'une des commissions permanentes (8 à l'Assemblée, 7 au Sénat). Un <b>rapporteur</b> est désigné, des personnes sont auditionnées, puis la commission examine les <b>amendements</b> et adopte sa propre version du texte. C'est elle qui sera discutée en séance.`],
  ['AN', 'Séance publique', 'Le débat dans l’hémicycle', `Discussion générale, puis examen article par article : chaque amendement est débattu et voté. Des motions peuvent interrompre l'examen (motion de rejet préalable). On termine par un vote sur l'ensemble du texte — parfois un <b>scrutin solennel</b>, où chaque vote est nominatif.`],
  ['SN', 'Navette', 'Au tour de l’autre chambre', `Le texte adopté est transmis à l'autre assemblée, qui refait tout le travail : commission puis séance. Si elle l'adopte <b>sans le modifier</b> (vote « conforme »), la loi est définitivement adoptée. Sinon, le texte repart dans l'autre sens : c'est la <b>navette</b>. Seuls les articles encore en désaccord sont rediscutés.`],
  ['CMP', 'CMP', 'Le compromis', `Après deux lectures dans chaque chambre (une seule en procédure accélérée), le Premier ministre peut convoquer une <b>commission mixte paritaire</b> : 7 députés et 7 sénateurs cherchent un texte commun. S'ils y parviennent, ce texte est soumis aux deux chambres, et le Gouvernement seul peut encore l'amender.`],
  ['AN', 'Dernier mot', 'Si le blocage persiste', `En cas d'échec de la CMP (ou de rejet de son texte), chaque chambre procède à une <b>nouvelle lecture</b>. Puis le Gouvernement peut demander à l'Assemblée de statuer en <b>lecture définitive</b> : elle tranche seule, en reprenant le texte de la CMP ou le sien.`],
  ['CC', 'Conseil constitutionnel', 'Le contrôle', `Avant la promulgation, la loi peut être déférée au Conseil constitutionnel par le Président de la République, le Premier ministre, les présidents des deux chambres, ou au moins 60 députés ou 60 sénateurs. Il a un mois (8 jours en cas d'urgence) pour juger : conforme, partiellement conforme (une partie est censurée) ou non conforme.`],
  ['PROM', 'Promulgation', 'La loi existe', `Le Président de la République promulgue la loi dans les 15 jours (il peut demander une nouvelle délibération, ce qui est rarissime). Elle est publiée au Journal officiel et entre en vigueur, souvent après des décrets d'application.`],
];

const QUIZ = [
  ['Combien y a-t-il de députés ?', ['348', '577', '925'], 1, "577 députés siègent à l'Assemblée nationale, un par circonscription. Les 348 sénateurs siègent au Sénat ; ensemble, réunis en Congrès, ils sont 925."],
  ['Qui élit les sénateurs ?', ['Tous les électeurs', 'Les députés', 'Les grands électeurs (surtout des élus locaux)'], 2, "Les sénateurs sont élus au suffrage indirect par environ 160 000 grands électeurs, essentiellement des délégués des conseils municipaux."],
  ['En cas de désaccord persistant entre les deux chambres sur une loi ordinaire, qui a le dernier mot ?', ['Le Sénat', "L'Assemblée nationale, si le Gouvernement le demande", 'Le Conseil constitutionnel'], 1, "Après l'échec de la CMP et une nouvelle lecture, le Gouvernement peut demander à l'Assemblée de statuer définitivement (art. 45 de la Constitution)."],
  ['Que se passe-t-il quand le Gouvernement utilise le 49.3 ?', ['Le texte est adopté sans vote, sauf si une motion de censure est votée', "L'Assemblée est dissoute", 'Le texte part directement au Sénat'], 0, "Le Gouvernement engage sa responsabilité : les députés ont 24 heures pour déposer une motion de censure, votée au moins 48 heures plus tard. Si elle n'obtient pas 289 voix, le texte est considéré comme adopté."],
  ['Combien de voix faut-il pour adopter une motion de censure ?', ['La majorité des votants', '289, la majorité absolue des députés', 'Les 3/5 des députés'], 1, "Il faut la majorité absolue des membres de l'Assemblée, soit 289 voix. Seuls les votes favorables à la motion sont comptés."],
  ['Combien de membres compte une commission mixte paritaire ?', ['7 députés et 7 sénateurs', '15 députés et 15 sénateurs', 'Tous les membres des deux commissions concernées'], 0, 'La CMP réunit 7 députés et 7 sénateurs (plus autant de suppléants), choisis pour refléter les équilibres politiques.'],
  ['Pour modifier la Constitution, il faut…', ['Une loi votée par l’Assemblée seule', 'Le même texte voté par les deux chambres, puis un référendum ou les 3/5 du Congrès', 'Un décret du Président'], 1, "Le Sénat a ici un vrai droit de veto : sans son accord sur un texte identique, la révision est impossible (art. 89)."],
  ['Que signifie un vote « conforme » ?', ['Le Conseil constitutionnel valide la loi', "Une chambre adopte le texte exactement tel que l'autre l'a voté", 'Tous les groupes votent pareil'], 1, "Quand la deuxième chambre adopte le texte sans le modifier, il n'y a plus de désaccord : la navette s'arrête et la loi est définitivement adoptée."],
];

/** Le guide s'affiche une partie à la fois, avec « précédent / suivant ». */
export function scrollToSection(id) {
  const learn = document.querySelector('.learn');
  if (!learn) return;
  const sections = [...learn.querySelectorAll(':scope > section')];
  const cur = sections.find(x => x.id === id) || sections[0];
  sections.forEach(x => { x.hidden = x !== cur; });
  document.querySelectorAll('.learn-nav a').forEach(a => a.classList.toggle('active', a.getAttribute('href') === `#/comprendre/${cur.id}`));
  const i = sections.indexOf(cur);
  const label = x => x.querySelector('h2')?.textContent.replace(/^\d+\.\s*/, '') || '';
  let pager = learn.querySelector('.learn-pager');
  if (!pager) { pager = document.createElement('div'); pager.className = 'learn-pager'; learn.appendChild(pager); }
  pager.innerHTML = `${i > 0 ? `<a class="btn" href="#/comprendre/${sections[i - 1].id}">← ${label(sections[i - 1])}</a>` : '<span></span>'}${i < sections.length - 1 ? `<a class="btn primary" href="#/comprendre/${sections[i + 1].id}">${label(sections[i + 1])} →</a>` : ''}`;
  window.scrollTo({ top: 0 });
}

export async function render(el, anchor) {
  setTitle('Comprendre le Parlement');
  const [c, dos] = await Promise.all([ctx(), dossiersIndex()]);
  const k = c.meta.chiffres;
  const lois = dos.dossiers.filter(d => d.cat === 'loi');
  const ex = lois.filter(d => d.statut === 'promulguee' && d.cmp === 'accord' && d.cc).sort((a, b) => (b.maj || '').localeCompare(a.maj || ''))[0];
  const exConforme = lois.filter(d => d.statut === 'promulguee' && !d.cmp && d.parcours.length === 3).sort((a, b) => (b.maj || '').localeCompare(a.maj || ''))[0];
  const exLdef = lois.find(d => d.parcours.some(p => p[0] === 'ANLDEF'));
  const ppl = lois.filter(d => d.type === 'PPL' && !d.gouv);
  const pplOk = ppl.filter(d => d.statut === 'promulguee').length;
  const pjl = lois.filter(d => d.gouv);
  const pjlOk = pjl.filter(d => d.statut === 'promulguee').length;
  const exLink = d => d ? `<a href="#/loi/${d.uid}">${esc(d.titre)}</a>` : '';

  const fact = (tone, e, b, t) => `<div class="fact tone-${tone}"><div class="fe">${e}</div><b>${b}</b><span>${t}</span></div>`;
  const more = (txt) => `<details class="more-box small"><summary>En savoir plus</summary><p style="margin-top:6px">${txt}</p></details>`;
  const H = (id, n, emoji, tone, title) => `<h2 class="ttl tone-${tone}"><span class="b">${emoji}</span>${n}. ${title}</h2>`;

  el.innerHTML = `<div class="page">
    <div class="page-head"><h1>Guide du Parlement</h1>
      <p class="lead">Le jeu parlementaire en 11 étapes, illustré par les vrais textes de la législature.</p></div>
    <div class="learn-layout">
      <nav class="learn-nav" aria-label="Sommaire">
        <a href="#/comprendre/chambres">Deux chambres</a><a href="#/comprendre/origine">D'où viennent les lois</a>
        <a href="#/comprendre/parcours">Le parcours</a><a href="#/comprendre/acceleree">Procédure accélérée</a>
        <a href="#/comprendre/cmp">La CMP</a><a href="#/comprendre/dernier-mot">Le dernier mot</a>
        <a href="#/comprendre/cc">Conseil constitutionnel</a><a href="#/comprendre/arme">49.3 et censure</a>
        <a href="#/comprendre/vote">Comment on vote</a><a href="#/comprendre/groupes">Groupes et majorité</a>
        <a href="#/comprendre/speciales">Les lois à part</a><a href="#/comprendre/quiz">Le quiz</a><a href="#/comprendre/glossaire">Glossaire</a>
      </nav>
      <div class="learn">
        <section id="chambres">${H('chambres', 1, '', 'blue', 'Deux chambres')}
          <div class="compare">
            <div class="card" style="--c:var(--an)"><h3>Assemblée nationale</h3>
              <div class="facts3">${fact('blue', '', '577 députés', 'élus par vous')}${fact('blue', '', '5 ans', 'sauf dissolution')}${fact('blue', '', 'Peut censurer', 'le Gouvernement')}</div>
              <a class="small" href="#/assemblee">Voir la composition →</a></div>
            <div class="card" style="--c:var(--sn)"><h3>Sénat</h3>
              <div class="facts3">${fact('pink', '', '348 sénateurs', 'élus par les élus locaux')}${fact('pink', '', '6 ans', 'moitié renouvelée tous les 3 ans')}${fact('pink', '', 'Les territoires', 'sa mission')}</div>
              <a class="small" href="#/senat">Voir la composition →</a></div>
          </div>
          <div class="callout"><b>La règle d'or</b>Une loi doit être votée <b>dans les mêmes termes</b> par les deux chambres.</div>
        </section>

        <section id="origine">${H('origine', 2, '', 'yellow', 'D’où viennent les lois ?')}
          <div class="compare">
            <div class="card" style="--c:var(--gouv)"><h3>Projet de loi</h3><p class="small">Écrit par le <b>Gouvernement</b>.</p>
              <div class="facts3">${fact('slate', '', nf(pjl.length), 'déposés')}${fact('green', '', `${Math.round((100 * pjlOk) / (pjl.length || 1))} %`, 'deviennent loi')}</div></div>
            <div class="card" style="--c:var(--accent)"><h3>Proposition de loi</h3><p class="small">Écrite par des <b>parlementaires</b>.</p>
              <div class="facts3">${fact('blue', '', nf(ppl.length), 'déposées')}${fact('orange', '', `${((100 * pplOk) / (ppl.length || 1)).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} %`, 'deviennent loi')}</div></div>
          </div>
          ${more(`Sur quatre semaines de séance, deux vont aux textes du Gouvernement, une au contrôle, une à l'ordre du jour choisi par l'assemblée. Une journée par mois est une ${term('niche', 'niche parlementaire')} pour l'opposition.`)}
        </section>

        <section id="parcours">${H('parcours', 3, '', 'teal', 'Le parcours d’une loi')}
          <p class="muted small">Cliquez sur chaque étape</p>
          <div class="flow" id="flow">${FLOW.map(([ch, t, s], i) => `<button type="button" class="c-${ch}" aria-pressed="${i === 0}" data-i="${i}"><b>${i + 1}. ${t}</b><small>${s}</small></button>`).join('')}</div>
          <div class="flow-detail" id="flow-detail" aria-live="polite"></div>
          <div class="facts3">
            ${ex ? `<a class="fact tone-violet" href="#/loi/${ex.uid}" style="color:inherit"><div class="fe"></div><b>Le parcours complet</b><span>${esc(ex.titre)}</span></a>` : ''}
            ${exConforme ? `<a class="fact tone-green" href="#/loi/${exConforme.uid}" style="color:inherit"><div class="fe"></div><b>Le parcours express</b><span>${esc(exConforme.titre)}</span></a>` : ''}
            ${fact('orange', '', `${Math.round(100 - (100 * k.examines) / k.textes)} %`, 'des textes ne sont jamais débattus')}
          </div>
        </section>

        <section id="acceleree">${H('acceleree', 4, '', 'orange', 'La procédure accélérée')}
          <p>Le Gouvernement peut raccourcir la navette pour aller plus vite.</p>
          <div class="facts3">${fact('slate', '', '2 lectures', 'par chambre normalement')}${fact('orange', '', '1 lecture', 'en procédure accélérée')}${fact('blue', '', nf(k.procAcc), 'textes concernés')}</div>
          ${more(`Le Gouvernement peut l'engager sur n'importe quel texte : une ${term('cmp', 'CMP')} peut alors être convoquée dès la première lecture terminée. Les deux chambres peuvent s'y opposer ensemble.`)}
        </section>

        <section id="cmp">${H('cmp', 5, '', 'violet', 'La commission mixte paritaire')}
          <p>Quand l'Assemblée et le Sénat ne s'accordent pas, une commission mixte paritaire cherche un texte de compromis, à huis clos.</p>
          <div class="facts3">${fact('blue', '', '7 députés', '')}${fact('pink', '', '7 sénateurs', '')}${fact('violet', '', '1 compromis', 'sur les articles en désaccord')}</div>
          <div class="facts3">${fact('green', '', `${nf(k.cmpAccord)} accords`, `sur ${nf(k.cmp)} CMP réunies`)}${fact('red', '', `${nf(k.cmp - k.cmpAccord)} échecs`, 'nouvelle lecture ensuite')}</div>
          ${more("En cas d'accord, le texte commun est voté par les deux chambres, qui ne peuvent plus l'amender sans l'accord du Gouvernement.")}
        </section>

        <section id="dernier-mot">${H('dernier-mot', 6, '', 'green', 'Qui a le dernier mot ?')}
          <p>Si le désaccord persiste, l'Assemblée nationale peut trancher seule, à la demande du Gouvernement.</p>
          <div class="facts3">${fact('violet', '1', 'Échec de la CMP', '')}${fact('blue', '2', 'Nouvelle lecture', 'dans chaque chambre')}${fact('green', '3', 'Lecture définitive', "l'Assemblée tranche")}</div>
          <div class="callout warn"><b>Sauf…</b>Pour réviser la <b>Constitution</b> ou voter une <b>loi organique sur le Sénat</b>, il faut l'accord du Sénat : il a un droit de veto.</div>
          ${exLdef ? `<p class="small">Exemple : <a href="#/loi/${exLdef.uid}">${esc(exLdef.titre)}</a></p>` : ''}
        </section>

        <section id="cc">${H('cc', 7, '', 'yellow', 'Conseil constitutionnel et promulgation')}
          <p>Avant d'entrer en vigueur, une loi peut être contrôlée par le Conseil constitutionnel, puis elle est promulguée.</p>
          <div class="facts3">${fact('yellow', '', '60 députés', 'ou 60 sénateurs peuvent le saisir')}${fact('yellow', '', '1 mois', 'pour décider')}${fact('red', '', 'Censure', 'tout ou partie du texte')}${fact('green', '', '15 jours', 'pour promulguer')}</div>
          ${more(`Il peut aussi être saisi par le Président de la République, le Premier ministre ou les présidents des deux chambres. Pendant la législature, ${plural(k.cc, 'loi')} lui ont été soumises. Le Président promulgue ensuite la loi, publiée au Journal officiel.`)}
        </section>

        <section id="arme">${H('arme', 8, '', 'red', 'Le 49.3 et la motion de censure')}
          <p>Le Gouvernement peut faire adopter un texte sans vote ; en retour, les députés peuvent le renverser.</p>
          <div class="compare">
            <div class="card" style="--c:var(--gouv)"><h3>Le 49.3</h3>
              <div class="facts3">${fact('violet', '', 'Sans vote', 'le texte est adopté')}${fact('red', '', '24 h', 'pour déposer une censure')}</div>
              <p class="small muted">Illimité sur les budgets, un seul autre texte par session.</p></div>
            <div class="card" style="--c:var(--bad)"><h3>La censure</h3>
              <div class="facts3">${fact('orange', '', '58', 'signatures')}${fact('red', '', '289 voix', 'pour renverser')}</div>
              <p class="small muted">Seuls les « pour » comptent.</p></div>
          </div>
          <div class="facts3">${fact('violet', '', nf(k.art493), '49.3 depuis 2024')}${fact('orange', '', nf(k.censures), 'censures votées')}${fact('red', '', nf(k.censuresAdoptees), 'gouvernement renversé')}</div>
          <a class="small" href="#/gouvernement">Voir chaque motion →</a>
        </section>

        <section id="vote">${H('vote', 9, '', 'blue', 'Comment on vote')}
          <p>Tous les votes ne laissent pas de trace : seuls les scrutins publics sont nominatifs.</p>
          <div class="facts3">${fact('slate', '', 'À main levée', 'la plupart des votes, sans trace')}${fact('blue', '', term('scrutin', 'Scrutin public'), 'chaque vote est publié')}${fact('violet', '', term('solennel', 'Solennel'), 'pour les grands textes')}</div>
          ${more(`Un texte est adopté s'il y a plus de « pour » que de « contre », quel que soit le nombre de présents. Un député absent peut voter ${term('delegation', 'par délégation')}. Avant le débat, l'opposition peut défendre une ${term('motionrejet', 'motion de rejet préalable')}.`)}
        </section>

        <section id="groupes">${H('groupes', 10, '', 'pink', 'Groupes et majorité')}
          <p>Les élus se regroupent par affinités politiques ; une majorité se construit entre groupes.</p>
          <div class="facts3">${fact('pink', '', '15 députés', 'pour former un groupe')}${fact('pink', '', '10 sénateurs', 'au Sénat')}${fact('violet', '', '289', 'majorité absolue')}</div>
          <a class="btn small" href="#/assemblee">Construisez une majorité</a>
        </section>

        <section id="speciales">${H('speciales', 11, '', 'slate', 'Les lois à part')}
          <p>Certaines lois suivent des règles particulières.</p>
          <div class="facts3">
            ${fact('yellow', '', term('plf', 'Budget'), "70 jours pour l'État, 50 pour la Sécu")}
            ${fact('blue', '', term('loiconst', 'Constitution'), 'mêmes termes + Congrès ou référendum')}
            ${fact('violet', '', term('loiorga', 'Lois organiques'), 'contrôle obligatoire du Conseil')}
            ${fact('teal', '', 'Traités', 'oui ou non, sans amendement')}
          </div>
        </section>

        <section id="quiz" class="quiz">${H('quiz', '', '', 'violet', 'Le quiz').replace('. ', '')}
          <p class="muted">${QUIZ.length} questions pour vérifier que vous avez tout compris.</p>
          ${QUIZ.map(([q, opts], i) => `<div class="q card" data-q="${i}"><b>${i + 1}. ${esc(q)}</b><div class="opts">${opts.map((o, j) => `<button type="button" data-j="${j}">${esc(o)}</button>`).join('')}</div><div class="expl" hidden></div></div>`).join('')}
          <p class="score" id="score"></p>
        </section>

        <section id="glossaire"><h2 class="ttl tone-teal"><span class="b"></span>Glossaire</h2>
          <div class="gloss">${Object.values(GLOSSARY).sort((a, b) => a[0].localeCompare(b[0], 'fr')).map(([t, d]) => `<div><b>${esc(t)}</b><span class="small">${esc(d)}</span></div>`).join('')}</div>
        </section>
      </div>
    </div>
  </div>`;

  const detail = el.querySelector('#flow-detail');
  const show = i => {
    const [ch, t, , txt] = FLOW[i];
    el.querySelectorAll('#flow button').forEach(b => b.setAttribute('aria-pressed', +b.dataset.i === i));
    detail.innerHTML = `<h3 class="c-${ch}" style="color:var(--c)">${i + 1}. ${t}</h3><p>${txt}</p>`;
  };
  el.querySelector('#flow').addEventListener('click', e => { const b = e.target.closest('button'); if (b) show(+b.dataset.i); });
  show(0);

  let good = 0, done = 0;
  el.querySelectorAll('.quiz .q').forEach(box => box.addEventListener('click', e => {
    const b = e.target.closest('button');
    if (!b || box.dataset.done) return;
    const [, , ans, expl] = QUIZ[+box.dataset.q];
    box.dataset.done = '1';
    done++;
    box.querySelectorAll('button').forEach(x => { x.disabled = true; if (+x.dataset.j === ans) x.classList.add('right'); });
    if (+b.dataset.j === ans) good++; else b.classList.add('wrong');
    const ex = box.querySelector('.expl');
    ex.hidden = false;
    ex.textContent = (+b.dataset.j === ans ? '✓ Bonne réponse. ' : '✕ Raté. ') + expl;
    if (done === QUIZ.length) {
      el.querySelector('#score').textContent = `Score : ${good} / ${QUIZ.length} — ${good === QUIZ.length ? 'parfait, vous pourriez présider la séance !' : good >= 6 ? 'excellent, un vrai connaisseur du Parlement.' : good >= 4 ? 'pas mal ! Relisez les sections sur la navette et le 49.3.' : 'le Parlement a encore des secrets pour vous, relisez le guide !'}`;
    }
  }));
  scrollToSection(anchor);
}

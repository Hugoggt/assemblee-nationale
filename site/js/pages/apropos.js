import { ctx, esc, fdate, setTitle, nf } from '../lib.js';
import { SITE } from '../config.js';

const R = 'https://data.assemblee-nationale.fr/static/openData/repository/17';

export async function render(el) {
  setTitle('À propos');
  const { meta } = await ctx();
  const mail = esc(SITE.contact);
  el.innerHTML = `<div class="page" style="max-width:820px">
    <div class="page-head"><h1>À propos</h1>
      <p class="lead">Un site indépendant pour suivre ce qui se décide à l'Assemblée nationale et au Sénat.</p></div>

    <section class="panel"><header><h2>Pourquoi ce site</h2></header>
      <p>Tout ce qui se vote au Parlement est public. Mais l'information est dispersée et difficile à lire : des milliers de scrutins, des textes qui font la navette entre les deux chambres, des procédures comme la commission mixte paritaire ou le 49.3 que peu de gens connaissent.</p>
      <p>${esc(SITE.nom)} rassemble ces données officielles et les présente simplement : où en est chaque loi, qui a voté quoi, qui vote avec qui. Le site est gratuit, sans publicité et sans affiliation politique.</p>
      <p><b>Ce n'est pas un site officiel.</b> Hémicycle n'a aucun lien avec l'Assemblée nationale, le Sénat, le Parlement européen, le Gouvernement ou un parti politique. Pour une information officielle, référez-vous aux sites de ces institutions.</p>
      <p>Le site a été conçu avec l'aide de Claude, l'assistant d'intelligence artificielle d'Anthropic, qui a contribué au code et au traitement des données. Les choix éditoriaux et la publication relèvent de l'auteur du site.</p>
      ${SITE.soutienUrl ? `<p><a class="btn primary" href="${esc(SITE.soutienUrl)}" target="_blank" rel="noopener">${esc(SITE.soutienLabel)}</a></p>` : ''}
    </section>

    <section class="panel"><header><h2>D'où viennent les données</h2></header>
      <p>Toutes les données proviennent de l'<a href="https://data.assemblee-nationale.fr" target="_blank" rel="noopener">open data de l'Assemblée nationale</a>, publié sous <a href="https://www.etalab.gouv.fr/licence-ouverte-open-licence/" target="_blank" rel="noopener">Licence Ouverte (Etalab 2.0)</a> :</p>
      <ul>
        <li><a href="https://data.assemblee-nationale.fr/travaux-parlementaires/dossiers-legislatifs" target="_blank" rel="noopener">dossiers législatifs</a> : toutes les étapes de chaque texte, y compris au Sénat ;</li>
        <li><a href="https://data.assemblee-nationale.fr/travaux-parlementaires/votes" target="_blank" rel="noopener">scrutins publics</a> : le vote de chaque député ;</li>
        <li><a href="https://data.assemblee-nationale.fr/acteurs/historique-des-deputes" target="_blank" rel="noopener">acteurs, mandats et organes</a> : députés, sénateurs, groupes, gouvernement ;</li>
        <li><a href="${R}/vp/reunions/Agenda.json.zip">agenda</a> des séances et des commissions.</li>
      </ul>
      <p>Pour le <b>Parlement européen</b> : les votes nominatifs viennent de <a href="https://howtheyvote.eu" target="_blank" rel="noopener">HowTheyVote.eu</a> (<a href="https://github.com/HowTheyVote/data" target="_blank" rel="noopener">jeu de données</a>), publié sous <a href="https://opendatacommons.org/licenses/odbl/1-0/" target="_blank" rel="noopener">Open Database License</a> — <i>Data source: HowTheyVote.eu (Open Database License)</i>. Les données dérivées affichées ici (positions des partis, taux de présence et de loyauté) sont partagées sous la même licence, dans les fichiers JSON du site. Les titres en français, le parcours des textes, les rapporteurs et les fonctions des eurodéputés viennent de l'<a href="https://data.europarl.europa.eu" target="_blank" rel="noopener">open data du Parlement européen</a> ; les photos sont celles du site du Parlement (© Union européenne).</p>
      <p>Le budget de l'État vient de <a href="https://data.economie.gouv.fr" target="_blank" rel="noopener">data.economie.gouv.fr</a> et l'indice des prix de l'<a href="https://www.insee.fr" target="_blank" rel="noopener">Insee</a>.</p>
      <p>Les données sont mises à jour automatiquement chaque jour. Dernière mise à jour : ${fdate(meta.genere)}. Les photos des députés sont affichées depuis le site de l'Assemblée nationale.</p>
    </section>

    <section class="panel"><header><h2>Méthode et limites</h2></header>
      <ul>
        <li>Le statut d'un texte (en cours, adopté, promulgué…) et son étape sont <b>calculés</b> à partir des actes de procédure publiés.</li>
        <li>Une partie des votes d'amendements n'est pas reliée à son texte dans la source : le site les rattache par le titre et la date de séance (environ 96 % des ${nf(meta.chiffres.scrutins)} scrutins).</li>
        <li>Les thèmes sont déduits du titre et de la commission saisie : c'est une indication, pas une classification officielle.</li>
        <li>Les votes nominatifs des sénateurs ne figurent pas dans les données utilisées.</li>
        <li>Au Parlement européen, seuls les votes finaux en séance plénière sont repris (un par texte et par étape), pas les votes sur les amendements. La position d'un parti français est celle de la majorité de ses eurodéputés présents.</li>
        <li>Les courtes présentations des groupes sont rédigées par l'auteur du site.</li>
      </ul>
      <p>En cas de doute, la source officielle fait foi. Vous avez repéré une erreur ? Écrivez à <a href="mailto:${mail}">${mail}</a>.</p>
    </section>

    <section class="panel" id="mentions"><header><h2>Mentions légales</h2></header>
      <p><b>Éditeur :</b> ${SITE.responsable ? `${esc(SITE.responsable)}, ` : ''}particulier, à titre non professionnel. Contact : <a href="mailto:${mail}">${mail}</a>.</p>
      <p><b>Hébergeur :</b> GitHub Inc. (GitHub Pages), 88 Colin P. Kelly Jr. Street, San Francisco, CA 94107, États-Unis.</p>
      <p><b>Propriété :</b> les données publiques réutilisées restent soumises à la Licence Ouverte. Le code du site est <a href="${esc(SITE.codeSource)}" target="_blank" rel="noopener">publié en ligne</a>.</p>
      <p><b>Indépendance :</b> ce site n'est affilié ni à l'Assemblée nationale, ni au Sénat, ni au Gouvernement, ni à aucun parti.</p>
    </section>

    <section class="panel" id="donnees"><header><h2>Données personnelles</h2></header>
      <p>Le site ne dépose aucun cookie, ne contient aucun outil de mesure d'audience ni publicité, et ne collecte aucune donnée personnelle. Seule votre préférence de thème clair ou sombre est enregistrée dans votre navigateur. Les polices de caractères sont servies par le site lui-même.</p>
      <p>Comme tout hébergeur, GitHub peut conserver des journaux techniques de connexion (adresse IP). Les photos des députés sont chargées depuis le site de l'Assemblée nationale.</p>
      <p>Les informations affichées sur les élus sont celles que les assemblées publient dans le cadre de leur mandat.</p>
    </section>
  </div>`;
}

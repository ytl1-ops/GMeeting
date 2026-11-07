# Offre GMeeting — indépendants et PME (méthode Hormozi)

Cadre utilisé : l'équation de valeur (résultat rêvé × probabilité perçue ÷ délai × effort) et l'empilement d'une offre (promesse, problèmes → solutions,
bonus, garantie, prix). **Tout ce qui est marqué « hypothèse » n'est pas mesuré** : prix, coûts d'IA, demande, taux de conversion. Aucun témoignage,
chiffre de marché ni prix de concurrent n'est cité ici faute de source vérifiée ; à compléter après de vrais essais.

## 1. Cible (avatar)
Indépendants (consultants, avocats, architectes, coachs, experts-comptables) et PME de 1 à 50 personnes qui font des réunions clients ou d'équipe
et rédigent ensuite à la main un compte rendu. Ils paient avec du **temps** (rédaction le soir) et de la **crédibilité** (compte rendu tardif ou flou).
Ils craignent de confier leurs échanges à un cloud inconnu (secret professionnel, RGPD).

## 2. Résultat promis (le « rêve »)
> **Sortez de la réunion : le compte rendu est déjà dans votre boîte.** PV, CR ou note de synthèse, à votre en-tête, en Word, PDF, Excel ou PowerPoint,
> sans rien taper, sans que vos clients soient exposés à un cloud tiers.

Promesse mesurable à valider en essai : **temps de rédaction après réunion réduit de X %** (X à mesurer sur 10 réunions réelles, pas à annoncer avant).

## 3. Problèmes → solutions (ce que l'application fait déjà)
| Problème vécu | Réponse dans GMeeting | Vérifié |
|---|---|---|
| « Je rédige le CR le soir, ça me prend des heures » | Transcription + rédaction automatiques du PV, du CR et de la note | oui (rédaction simulée dans les tests ; qualité réelle à juger) |
| « L'appel a coupé mon enregistrement » | Enregistrement qui reprend seul, journal des interruptions | navigateur : oui ; téléphone réel : non |
| « Je n'avais pas de réseau » | Mode avion : l'audio est gardé, envoyé au retour du réseau | navigateur : oui ; téléphone réel : non |
| « Les infos sont dans des mails et des Excel, pas dans la réunion » | Pièces jointes (Outlook, Word, Excel, PDF) qui enrichissent le rapport, avec sources | oui (fichiers réels de chaque format) |
| « Ça doit ressembler à mon cabinet » | Gabarit : logo, en-tête, couleur | oui |
| « Je ne veux pas envoyer mes clients dans un cloud inconnu » | Serveur auto-hébergé : les données restent chez vous | oui |
| « Je dois présenter la synthèse » | PowerPoint sobre ou illustré | oui |

## 4. Principal frein et comment le lever
**Il faut installer un serveur.** C'est le premier motif d'abandon probable (hypothèse). Trois niveaux d'offre, du plus simple au plus fidèle à la promesse
de confidentialité :

| Niveau | Pour qui | Ce que ça demande | État |
|---|---|---|---|
| **A. Auto-hébergé** | à l'aise avec Docker | `./deploy/install.sh` + `DEPLOY.md` | existe |
| **B. Installé pour vous** | indépendant ou PME sans informaticien | service d'installation sur le serveur du client | à définir (prestation, pas du code) |
| **C. Hébergé** (instance dédiée par client) | veut zéro technique | à construire : hébergement, supervision, facturation, mentions RGPD | **n'existe pas** |

Recommandation : valider la demande avec **B** (aucun développement) avant d'investir dans **C**.

## 5. Empilement de l'offre (hypothèse de contenu)
- **Cœur** : application Android + interface web + serveur, comptes rendus PV/CR/note.
- **Bonus 1 — Gabarit à votre image** posé à l'installation (logo, en-tête).
- **Bonus 2 — Modèle de réunion type** (ordre du jour → CR) pour votre métier ; à écrire par métier après les premiers essais.
- **Bonus 3 — Guide de mise en route en 15 minutes** (déjà en partie dans `docs/ESSAI_LOCAL.md`).
- **Bonus 4 — Premiers comptes rendus relus avec vous** pendant le mois d'essai (réglage des consignes de rédaction).

## 6. Garantie (hypothèse à décider avec vous)
Une garantie forte réduit le risque perçu. Proposition : **essai de 30 jours, remboursé sans discussion si, après 5 réunions, le compte rendu ne vous
fait pas gagner de temps.** À n'engager que si le niveau B ou C est vendu et si la qualité réelle (avec vraies clés IA) a été jugée.
À ne **pas** promettre : exactitude à 100 % (pas de reconnaissance des locuteurs ; relecture du PV avant diffusion, déjà indiquée dans l'application).

## 7. Prix (hypothèses, à tester, pas à afficher)
Principe : ancrer sur le **temps économisé** du client, pas sur le coût de l'outil. Méthode :
1. Chaque réunion coûte au client N minutes de rédaction × son taux horaire (à demander lors des entretiens).
2. Le prix doit représenter une petite fraction de ce coût mensuel.
3. Coûts à connaître avant de fixer un prix : API de transcription et de rédaction **par heure de réunion** (à mesurer avec de vraies clés sur 10 réunions),
   hébergement, temps d'installation et de support.
Structure suggérée à tester : paiement d'installation (niveau B) + abonnement mensuel pour le support et les mises à jour ; niveau C : abonnement mensuel
par instance. **Aucun montant n'est proposé ici** : il se déduit des entretiens et des coûts mesurés.

## 8. Rareté et urgence (seulement si réelles)
Capacité limitée et vraie : le nombre d'installations accompagnées par mois (temps humain). On peut l'annoncer tel quel. Ne pas inventer de compte à
rebours ni de « places limitées » artificielles.

## 9. Nom et accroche (à tester)
Accroche principale : **« Le compte rendu est prêt avant que vous ayez rangé votre ordinateur. »**
Sous-accroches : « Vos réunions restent chez vous. » · « Même sans réseau. » · « À l'en-tête de votre cabinet. »
Vérifier le nom « GMeeting » (confusion possible avec Google Meet) avant toute communication large.

## 10. Plan de validation (2 semaines, avant tout développement)
1. **Essai réel sur téléphone** (`docs/ESSAI_LOCAL.md`) : corriger ce qui casse. Sans cela, aucune promesse n'est crédible.
2. **10 entretiens** d'indépendants ou de dirigeants de PME : combien de réunions par semaine, temps de rédaction, outil actuel, ce qui les gênerait
   (installation, confidentialité, prix). Noter les mots exacts, ils servent de texte de vente.
3. **3 à 5 pilotes** en niveau B sur de vraies réunions : mesurer le temps gagné et les corrections nécessaires. Ces chiffres, et eux seuls, nourrissent
   la promesse, la garantie et les témoignages (avec accord écrit).
4. **Décision** : si au moins quelques pilotes paient ou s'engagent, construire le niveau C ; sinon ajuster l'offre.
5. En parallèle, tenir à jour `docs/store/FICHE.md` : la fiche Play Store reprend l'accroche et reste honnête (prérequis : un serveur).

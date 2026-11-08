# Du code au test interne Google Play — pas à pas

Objectif : installer sur vos téléphones, **via le Play Store**, la vraie version signée de GMeeting (celle que les utilisateurs auront), avant toute mise en production.
Le **test interne** est la piste la plus rapide : jusqu'à 100 testeurs (adresses Google), disponible en quelques minutes après l'envoi, sans examen long.

> **Ce qui est prêt dans ce dépôt** : le script de clé, le workflow de build signé avec ses contrôles, la cible Android 16 (API 36).
> **Ce qui ne peut être fait que par vous** : le compte Play, la clé (créée sur votre poste), les secrets GitHub, la création de l'application dans la console, l'envoi, l'invitation des testeurs.
> **Ce qui n'a jamais été essayé** : un envoi réel sur Google Play. Les écrans et l'ordre exact des étapes de la console évoluent : suivez les intitulés de la console en cas de différence.

## Prérequis
- Un **compte Google Play Console** (frais uniques, vérification d'identité). Pour un compte personnel récent, la **production** exige ensuite un test fermé (12 testeurs pendant 14 jours) ; le test interne, lui, n'a pas cette contrainte et ne compte pas dans les 14 jours.
- **Cible Android 16 (API 36)** : exigée par Google pour toute *nouvelle* application depuis le 31 août 2026 ([source Google](https://developer.android.com/google/play/requirements/target-sdk)). L'application cible l'API 36 depuis cette version (compilation vérifiée par la CI, voir « Vérifications »).
- Un **serveur en HTTPS** pour essayer l'application publiée : **la version du Play Store refuse le HTTP**. Le plus sûr : créer un serveur de démonstration (`docs/SERVEUR_DEMO.md` : une commande pour le préparer, une autre pour le vérifier). À défaut : votre domaine (`DEPLOY.md`) ou `./deploy/local.sh --tunnel` (lien HTTPS temporaire). Le HTTP local ne marche que dans l'APK de test (debug).

## 1. Décider l'identifiant d'application (définitif)
Par défaut `app.gmeeting.android`. **Il ne pourra plus jamais changer** une fois le premier bundle envoyé, et deux applications ne peuvent pas partager le même. Si vous voulez un identifiant à votre nom de domaine (recommandé), choisissez-le maintenant, par exemple `fr.mondomaine.gmeeting` ; il se donne au workflow (étape 4).
Vérifiez aussi que le nom affiché ne prête pas à confusion avec une marque existante (voir `docs/PLAYSTORE.md`).

## 2. Créer la clé d'envoi (sur VOTRE poste)
```bash
./android/tools/make-upload-key.sh            # crée ~/gmeeting-upload-key/ (droits 700)
```
- `upload.jks` : la clé. **Sauvegardez-la** (coffre de mots de passe + copie chiffrée hors du poste).
- `secrets-github.txt` : les 4 valeurs à copier dans GitHub à l'étape suivante. **Supprimez ce fichier ensuite.**
- Ne la créez jamais dans le dépôt, ne la transmettez jamais par message. Elle n'est pas dans le dépôt (`.gitignore`).
Avec **Play App Signing** (étape 5), Google garde la clé de signature définitive ; la clé d'envoi sert seulement à prouver que l'envoi vient de vous et peut être réinitialisée par le support Google en cas de perte.

## 3. Créer les 4 secrets GitHub
Dépôt → Settings → Secrets and variables → Actions → *New repository secret* : `ANDROID_KEYSTORE_B64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD` (valeurs de `secrets-github.txt`).
Le dépôt doit rester **privé** ou, au minimum, aucun contributeur de confiance limitée ne doit pouvoir modifier les workflows.

## 4. Construire le bundle signé
GitHub → Actions → **android-release** → *Run workflow* :
- `version_name` : par ex. `1.0.0` (affichée aux utilisateurs) ;
- `version_code` : laisser **vide** (numéro d'exécution, toujours croissant) ou donner un entier **supérieur** au dernier envoyé ;
- `app_id` : vide = `app.gmeeting.android`, sinon l'identifiant choisi à l'étape 1.

Le workflow : contrôle les protections de la version publiée (HTTPS obligatoire, pas de sauvegarde cloud, cible API 36…), compile, **vérifie que le bundle est bien signé**, affiche dans le résumé du job l'**identifiant, le versionCode, la taille et l'empreinte du certificat**, puis efface la clé du poste de build.
Téléchargez l'artefact **gmeeting-release-aab** (un zip contenant `app-release.aab`).

## 5. Créer l'application dans la Play Console
1. *Créer une application* : nom, langue par défaut (français), type *Application*, *Gratuite*, acceptation des déclarations.
2. **Test interne** (menu *Tests* → *Test interne*) → *Créer une release* :
   - **Signature de l'application par Google Play** : accepter (recommandé). Le premier envoi enregistre votre clé d'envoi.
   - Importer `app-release.aab`. Vérifiez que l'empreinte du certificat affichée par la console est celle du résumé du workflow.
   - Nom et notes de version (« Première version de test »).
3. Onglet **Testeurs** : créer une liste d'adresses Google (les adresses des personnes qui testent), l'enregistrer.
4. *Examiner la release* puis *Lancer le déploiement* du test interne.
5. Copier le **lien d'adhésion** du test interne : chaque testeur l'ouvre **sur son téléphone, connecté avec l'adresse invitée**, accepte, puis installe depuis le Play Store.

### Déclarations à prévoir dans la console
Le test interne peut parfois démarrer sans tout renseigner, mais la **production** exige tout, et Google peut réclamer certaines déclarations dès l'envoi. Dans *Contenu de l'application* :
- **Politique de confidentialité** (URL publique) : `docs/PRIVACY_POLICY.md`, à héberger avec l'éditeur et le contact renseignés.
- **Sécurité des données** : réponses proposées dans `docs/PLAYSTORE.md` (point délicat : l'audio et les fichiers sont transmis hors de l'appareil, vers *votre* serveur).
- **Accès à l'application** : fournir l'adresse d'un **serveur de démonstration** et son mot de passe (sans cela l'application est inutilisable pour le relecteur) : `docs/SERVEUR_DEMO.md` produit le fichier `DEMO_ACCESS.txt` à coller.
- **Autorisation de service de premier plan « micro »** : description + courte **vidéo** (démarrer l'enregistrement, verrouiller l'écran, notification visible, arrêter).
- Publicités (aucune), classification du contenu, public cible (adultes, usage professionnel).
- **Fiche** (textes, icône, bannière, captures) : `docs/store/FICHE.md` et `docs/store/` ; pour le test interne, la fiche peut rester sommaire.

## 6. Premier essai de la version publiée
Suivez `docs/TESTS_TELEPHONE.md`, en particulier **H8** : sur la version du Play Store, l'écran est **protégé par défaut** (aperçu masqué, captures bloquées) et le **HTTP est refusé** (une adresse `http://…` doit échouer ; une adresse HTTPS doit fonctionner).

## 7. Envois suivants
Relancer le workflow : le `versionCode` doit être **strictement supérieur** à celui du dernier bundle accepté (la valeur par défaut, le numéro d'exécution, augmente toute seule). Ne rejouez jamais un `versionCode` déjà utilisé.

## Si ça bloque
| Message ou symptôme | Cause probable | Solution |
|---|---|---|
| Le workflow s'arrête sur « Secrets de signature manquants » | secrets absents ou mal nommés | refaire l'étape 3 (noms exacts, 4 secrets) |
| « La clé ne s'ouvre pas avec ces secrets » | mot de passe ou alias différent du fichier | recopier les valeurs de `secrets-github.txt` ; l'alias par défaut est `upload` |
| Le contrôle « version publiée » échoue | une protection (HTTPS, sauvegarde, cible API) a été modifiée | lire le message ; ne pas contourner : corriger la source |
| « Le nom de package existe déjà » | identifiant déjà pris sur Google Play | choisir un autre `app_id` (étape 1) |
| « Le code de version a déjà été utilisé » | `versionCode` non croissant | fournir un `version_code` plus grand |
| « Vous devez cibler au moins le niveau d'API … » | exigence de Google relevée | relever `targetSdk` / `compileSdk` (et la version d'AGP si besoin) ; `android/tools/check-release.sh` donne le minimum attendu |
| « Autorisation FOREGROUND_SERVICE_MICROPHONE : déclaration requise » | service de premier plan de type micro | remplir la déclaration et fournir la vidéo (étape 5) |
| L'application installée refuse l'adresse du serveur | version publiée = HTTPS obligatoire | utiliser une adresse HTTPS (domaine ou `--tunnel`) |
| Le test échoue avec « signature différente » | l'ancien APK de test (debug) est installé | le désinstaller : les deux ont des identifiants et des signatures différents |

## Vérifications faites / non faites
| | État |
|---|---|
| Script de clé : droits 700/600, mot de passe aléatoire, aller-retour base64, refus d'écraser | testé |
| Contrôle de la version publiée : 6 dégradations volontaires détectées (HTTP, sauvegarde, cible, suffixe, config réseau, service micro) | testé |
| Validation des paramètres du workflow (versionCode, versionName, identifiant) | testée |
| Compilation avec la cible API 36 (AGP 8.9.1, Gradle 8.11.1) : APK debug, lint, bundle de la version publiée, et contrôle de son manifeste fusionné (HTTP refusé, non débogable) | vérifiée en CI (run vert) |
| Signature réelle du bundle, empreinte, envoi sur Google Play, installation depuis le Play Store | **jamais essayés** (demandent votre clé et votre compte) |
| Comportement sur téléphone (affichage bord à bord de l'API 36, geste « retour », écran protégé) | **jamais essayé** : `docs/TESTS_TELEPHONE.md` |

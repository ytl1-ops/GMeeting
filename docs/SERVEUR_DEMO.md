# Créer le serveur de démonstration (HTTPS)

Il sert à trois choses : **essayer la version publiée** de l'application (qui refuse le HTTP), fournir aux **relecteurs Google Play** un accès de démonstration (« Accès à l'application »), et faire des **démos** à des clients.

> **Ce que ce dépôt fait pour vous** : prépare un serveur neuf en une commande, l'installe en HTTPS, le vérifie de l'extérieur, et écrit le texte à coller dans la Play Console.
> **Ce que seul vous pouvez faire** : ouvrir un compte chez un hébergeur, louer le serveur, créer l'enregistrement DNS, fournir des clés d'IA. Je ne peux ni louer ni piloter un serveur, ni joindre Internet depuis mon environnement de travail.

## Ce qu'il faut
- Un **serveur Linux** (VPS) chez l'hébergeur de votre choix : **Ubuntu 22.04/24.04 ou Debian 12**, adresse IPv4 publique, au minimum **2 vCPU, 4 Go de mémoire, 20 Go de disque**. Pour une démonstration, la transcription par le service OpenAI évite d'installer un modèle local lourd. Le coût dépend de l'hébergeur (souvent quelques euros par mois) : à vérifier chez lui.
- Un **nom de domaine** (ou sous-domaine, par ex. `demo.mondomaine.fr`) que vous pouvez faire pointer vers le serveur.
- Des **clés d'IA dédiées à la démo** (voir « Coûts et clés »).

## Étapes
1. **Louer le serveur** et noter son adresse IP. Dans le pare-feu du fournisseur (s'il en a un), ouvrir **22, 80 et 443**.
2. **DNS** : créer l'enregistrement `A` `demo.mondomaine.fr` → adresse IP du serveur, puis attendre sa propagation (quelques minutes à quelques heures). Sans DNS correct, le certificat HTTPS ne sera pas délivré.
3. **Amener le dépôt sur le serveur** (dépôt privé : évitez de laisser un jeton sur le serveur). Depuis **votre poste** :
   ```bash
   git archive --format=tar.gz -o gmeeting.tar.gz HEAD            # depuis une copie à jour du dépôt
   scp gmeeting.tar.gz root@IP-DU-SERVEUR:/root/
   ssh root@IP-DU-SERVEUR "mkdir -p gmeeting && tar xzf gmeeting.tar.gz -C gmeeting"
   ```
4. **Se connecter** (`ssh root@IP-DU-SERVEUR`) puis **simuler** :
   ```bash
   cd gmeeting
   ./deploy/bootstrap-vps.sh demo.mondomaine.fr --demo --dry-run     # n'écrit rien : montre ce qui sera fait
   ```
5. **Installer pour de bon** (clés fournies par l'environnement, jamais écrites dans l'historique de commandes si vous les saisissez après `read -s`) :
   ```bash
   read -r -s -p "Clé Anthropic : " ANTHROPIC_API_KEY; export ANTHROPIC_API_KEY; echo
   read -r -s -p "Clé OpenAI : " OPENAI_API_KEY; export OPENAI_API_KEY; echo
   sudo -E ./deploy/bootstrap-vps.sh demo.mondomaine.fr --demo
   ```
   Le script installe Docker (dépôt officiel), configure le pare-feu (SSH, 80, 443 seulement), active les mises à jour de sécurité automatiques, puis lance `deploy/install.sh --demo` : conservation **1 jour**, audio jamais gardé, mot de passe fort généré, fichier **`DEMO_ACCESS.txt`**.
6. **Vérifier depuis votre poste** (pas depuis le serveur) :
   ```bash
   ./deploy/check-server.sh https://demo.mondomaine.fr LE-MOT-DE-PASSE
   ```
   Il contrôle : certificat HTTPS valide, `/healthz`, en-têtes de sécurité (CSP, HSTS…), **mot de passe exigé** (une interface ouverte est un échec), mot de passe accepté / mauvais refusé, page Confidentialité, IA et transcription configurées, conservation. Tout doit être « ok » ; lisez les « attention ».
7. **Essayer avec un téléphone** : installer l'application, saisir `https://demo.mondomaine.fr` et le mot de passe, enregistrer, générer. C'est le test **A4** puis **B1** de `docs/TESTS_TELEPHONE.md`.
8. **Play Console** → Contenu de l'application → *Accès à l'application* : coller le contenu de `DEMO_ACCESS.txt` (adresse, mot de passe, instructions FR/EN pour le relecteur).

## Coûts et clés d'IA
- Les relecteurs et testeurs consomment **vos** crédits d'IA. Créez des **clés dédiées à la démo**, avec un **plafond de dépense** chez chaque fournisseur, distinctes de vos clés de production.
- Surveillez la consommation pendant la revue Google ; **révoquez** les clés dès que la démo n'est plus utile.

## Pendant la revue Google
- Gardez le serveur **allumé et joignable plusieurs jours** : la revue n'est pas instantanée et peut être refaite à chaque mise à jour.
- Un relecteur qui trouve une erreur de connexion ou un serveur lent peut refuser l'application. Refaites `check-server.sh` avant chaque envoi.
- Les données de démonstration sont **supprimées automatiquement après 24 heures** (aucune donnée de vrai client ne doit y passer).

## Entretien et sécurité
- **Changer le mot de passe** : modifier `GMEETING_PASSWORD` dans `.env`, puis `docker compose up -d`. Mettre à jour `DEMO_ACCESS.txt` et la console.
- `DEMO_ACCESS.txt` contient le mot de passe : lecture réservée (droits 600), **jamais versionné** (`.gitignore`), à supprimer du serveur une fois recopié.
- Mises à jour : `./deploy/update.sh` (sauvegarde d'abord). Mises à jour de sécurité du système : automatiques (`unattended-upgrades`).
- **Démonter** : `docker compose down -v` (efface les données), résilier le serveur, supprimer l'enregistrement DNS, révoquer les clés d'IA.

## Dépannage
| Symptôme | Cause probable | Solution |
|---|---|---|
| `check-server.sh` : « certificat HTTPS invalide » | certificat pas encore délivré | DNS non propagé, ports 80/443 fermés (pare-feu du fournisseur ou `ufw status`) ; voir `docker compose logs caddy` ; patienter puis relancer |
| « serveur injoignable » | service arrêté, DNS ou pare-feu | `docker compose ps`, `docker compose logs app`, ouvrir 80/443 chez le fournisseur |
| « le serveur est OUVERT » | mot de passe vide | définir `GMEETING_PASSWORD` dans `.env` puis `docker compose up -d` (ne jamais publier avant) |
| « HSTS absent » | proxy non utilisé (accès direct au port 8000) | passer par Caddy (`docker-compose.yml`), ne pas exposer le port 8000 |
| « ANTHROPIC_API_KEY absente » | clé non fournie | l'ajouter dans `.env`, `docker compose up -d` |
| Le script s'arrête sur « DNS non prêt » | le nom ne se résout pas | créer / attendre l'enregistrement `A`, puis relancer |

## Vérifié / non vérifié
| | État |
|---|---|
| `install.sh --demo` : conservation 1 jour, audio supprimé, fichier de relecteur en droits 600 | testé automatiquement |
| `bootstrap-vps.sh` en simulation : plan complet, SSH autorisé avant d'activer le pare-feu, refus d'un domaine invalide ou d'un système non pris en charge | testé automatiquement |
| `check-server.sh` : serveur protégé accepté ; mot de passe faux, serveur ouvert, HTTP, serveur injoignable refusés | testé contre de vrais serveurs locaux |
| Image Docker durcie et démarrage avec Caddy | vérifiés en CI (job `docker`) |
| **Exécution réelle de `bootstrap-vps.sh`** (installation de Docker, `ufw`, mises à jour automatiques) sur un serveur Ubuntu / Debian | **jamais essayée** : demande un serveur |
| **Obtention du certificat HTTPS** par Caddy sur un vrai domaine, contrôle HSTS en HTTPS | **jamais essayés** |

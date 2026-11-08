# Déployer GMeeting sur votre serveur (Docker)

Résultat : GMeeting accessible en **HTTPS** sur votre nom de domaine, protégé par mot de passe, avec sauvegardes et mises à jour en une commande.
Le micro du navigateur n'est autorisé qu'en HTTPS : c'est pourquoi le déploiement inclut Caddy, qui obtient et renouvelle le certificat tout seul.

## 1. Ce qu'il vous faut

| Élément | Détail |
|---|---|
| Serveur Linux | Ubuntu/Debian récent. **2 vCPU, 4 Go de RAM, 20 Go de disque** suffisent avec la transcription par API ; prévoir 8 Go et un disque plus large pour la transcription locale (modèles Whisper) |
| Docker | Docker Engine **et le plugin `docker compose` v2** ([installation officielle](https://docs.docker.com/engine/install/)) |
| Nom de domaine | Un enregistrement DNS **A** (et AAAA si IPv6) de `reunions.votre-domaine.fr` vers l'IP du serveur, **avant** l'installation |
| Ports | **80 et 443** ouverts depuis Internet (80 sert à l'obtention du certificat) ; 22 pour SSH |
| Clé API | `ANTHROPIC_API_KEY` (rédaction). Pour la transcription : `OPENAI_API_KEY`, **ou** transcription locale (voir `.env.example`) |

## 2. Préparer le serveur (une fois)

```bash
sudo apt update && sudo apt -y upgrade
sudo ufw allow OpenSSH && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw --force enable
sudo usermod -aG docker "$USER"     # puis se déconnecter / reconnecter pour appliquer
```

> Docker publie lui-même les ports 80 et 443 en contournant `ufw` : c'est voulu ici, **seuls** ces deux ports sont publiés (l'application
> n'est jamais exposée directement, voir `docker-compose.yml`).

## 3. Installer

```bash
sudo mkdir -p /opt/gmeeting && sudo chown "$USER" /opt/gmeeting
git clone <URL-de-votre-dépôt> /opt/gmeeting && cd /opt/gmeeting
./deploy/install.sh reunions.votre-domaine.fr
```

Le script : crée `.env` (droits 600), demande votre clé Anthropic, **génère un mot de passe fort** (affiché une seule fois : notez-le dans un
gestionnaire de mots de passe), construit l'image, démarre, et attend que l'application réponde. La première construction prend plusieurs
minutes. Relancer le script est sans danger (il ne change ni mot de passe ni domaine déjà définis).

Sans nom de domaine (essai) : `./deploy/install.sh` → `https://localhost`, avec un certificat local (avertissement du navigateur).

## 4. Vérifier

1. Ouvrir `https://reunions.votre-domaine.fr` : le navigateur demande le mot de passe (nom d'utilisateur libre).
2. L'en-tête de l'application ne doit afficher aucun avertissement « clé manquante ».
3. Sur un **téléphone**, ouvrir la page une fois en ligne, puis « Ajouter à l'écran d'accueil » (l'enregistrement en mode avion en dépend).
4. Faire un **essai complet** : enregistrer 1 minute, terminer, vérifier le PV ; puis joindre un mail ou un compte rendu précédent et régénérer.
5. État du service : `docker compose ps` (les deux services « running », `app` « healthy »).

## 5. Réglages utiles pour un serveur

Tout se règle dans `.env` (liste complète dans le README). Après modification : `docker compose up -d`.

* `RETENTION_DAYS=90` : supprime automatiquement les réunions de plus de 90 jours (0 = jamais). À décider selon votre politique de conservation.
* `KEEP_AUDIO=true` : conserve un audio compact réécoutable (≈ 12 Mo/h) ; sinon l'audio est supprimé après traitement.
* `TRANSCRIBE_PROVIDER=local` : l'audio ne quitte pas le serveur (seul le texte part vers l'API de rédaction). Exige plus de RAM/CPU.

## 6. Sauvegardes (indispensable)

```bash
./deploy/backup.sh                 # → backups/gmeeting-AAAAMMJJ-HHMMSS.tar.gz (14 dernières conservées)
./deploy/backup.sh --no-audio      # sans l'audio conservé (plus léger)
```

Contenu : base de données (instantané cohérent même en service), pièces jointes, gabarit, audio conservé. **Non inclus** : les enregistrements en
cours de traitement (transitoires) et le fichier `.env` (à conserver séparément, dans votre gestionnaire de mots de passe).

**Planification** (tous les jours à 3 h) :

```bash
( crontab -l 2>/dev/null; echo '0 3 * * * cd /opt/gmeeting && ./deploy/backup.sh --no-audio >> backups/backup.log 2>&1' ) | crontab -
```

**Une sauvegarde qui reste sur le même serveur ne protège pas d'une panne du serveur.** Copiez-la régulièrement ailleurs, **chiffrée** (elle contient
vos comptes rendus) :

```bash
f=$(ls -1t backups/gmeeting-*.tar.gz | head -1)
gpg --symmetric --cipher-algo AES256 -o "$f.gpg" "$f" && scp "$f.gpg" utilisateur@autre-serveur:/sauvegardes/   # exemple
```

**Testez la restauration** au moins une fois (sur un serveur de test) : une sauvegarde jamais restaurée n'est pas une garantie.

## 7. Restaurer, ou migrer vers un autre serveur

Sur le nouveau serveur : installer (§ 3), puis

```bash
./deploy/restore.sh backups/gmeeting-AAAAMMJJ-HHMMSS.tar.gz            # serveur neuf : aucune donnée à écraser
./deploy/restore.sh backups/gmeeting-AAAAMMJJ-HHMMSS.tar.gz --force    # remplace des données existantes (sauvegarde de sécurité d'abord)
```

Le script arrête l'application, restaure, redémarre et vérifie. L'archive est contrôlée avant extraction (une archive piégée est refusée).
Recopiez aussi votre `.env` (ou régénérez-le : seul le mot de passe change).

## 8. Mettre à jour

```bash
./deploy/update.sh
```

Sauvegarde préalable → `git pull` → reconstruction → redémarrage → vérification. Si l'application ne répond pas ensuite, la commande de **retour
arrière** exacte est affichée. Les données (volume `gmeeting-data`) ne sont jamais touchées par une mise à jour.

## 9. Exploitation courante

| Besoin | Commande |
|---|---|
| Journaux | `docker compose logs -f --tail 100 app` (et `caddy`) ; ils sont limités à 50 Mo par service |
| Redémarrer | `docker compose restart app` |
| Changer le mot de passe | modifier `GMEETING_PASSWORD` dans `.env`, puis `docker compose up -d` |
| Espace disque | `docker compose exec app du -sh /data/*` ; `docker system df` |
| Voir la santé | `docker compose ps` ; `docker compose exec app python -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8000/healthz').read())"` |

L'application tourne en **un seul processus** (ne pas lancer plusieurs instances sur le même volume). Une réunion en cours de traitement lors d'un
redémarrage passe en erreur explicite avec un bouton « Relancer » (l'audio est conservé).

## 10. Sécurité : liste de contrôle

- [ ] Mot de passe fort (celui généré convient) ; `.env` en droits 600, jamais dans git.
- [ ] Seuls les ports 22, 80, 443 ouverts ; SSH par clé uniquement ; mises à jour du système régulières.
- [ ] Sauvegardes quotidiennes **chiffrées et copiées hors du serveur** ; restauration testée.
- [ ] `RETENTION_DAYS` choisi en fonction de votre politique de conservation des données.
- [ ] Contenus très sensibles : l'authentification par mot de passe sur Internet est un minimum. Pour aller plus loin, **restreignez l'accès par
      adresse IP** (réseau de l'entreprise, VPN) dans le `Caddyfile` :

```caddyfile
{$DOMAIN:localhost} {
	@interdit not remote_ip 203.0.113.0/24 198.51.100.7
	respond @interdit "Accès refusé" 403
	encode zstd gzip
	request_body {
		max_size 1100MB
	}
	reverse_proxy app:8000
}
```

Puis `docker compose up -d` (remplacez les adresses par les vôtres). Protections déjà en place : conteneur non-root, système de fichiers en lecture seule,
aucune capacité Linux, CSP stricte, protection CSRF, en-têtes de sécurité, HSTS.

## 11. Dépannage

| Symptôme | Cause probable et solution |
|---|---|
| Pas de certificat / navigateur « non sécurisé » | Le DNS ne pointe pas encore vers le serveur, ou 80/443 fermés : `docker compose logs caddy`. Attendre la propagation DNS puis `docker compose restart caddy` |
| « Micro non supporté » / accès refusé | La page n'est pas en HTTPS (ou domaine non fiable). Utiliser le nom de domaine en `https://` |
| Mot de passe refusé | Voir `.env` (`GMEETING_PASSWORD`) ; le nom d'utilisateur est libre |
| `app` jamais « healthy » | `docker compose logs app` ; vérifier `.env` (valeurs numériques valides) et l'espace disque |
| Rédaction en erreur « clé manquante » | Renseigner `ANTHROPIC_API_KEY` dans `.env` puis `docker compose up -d` ; relancer la réunion |
| « Traitement interrompu par un redémarrage » | Normal après un redémarrage ; cliquer sur « Relancer » |
| Disque plein | `docker system df`, réduire `RETENTION_DAYS`, supprimer d'anciennes sauvegardes ; ne jamais supprimer le volume |

## 12. Désinstaller

```bash
docker compose down            # arrête et supprime les conteneurs ; les DONNÉES sont conservées (volume)
docker compose down -v         # ⚠ supprime AUSSI les données et les certificats : faites une sauvegarde avant
```

## 13. Ce qui a été vérifié (et ce qui ne l'a pas été)

Essais réalisés avec de **vrais conteneurs** (image construite, Compose et Caddy réels, vos scripts réels) :

| Vérifié | Résultat |
|---|---|
| Image construite et démarrée avec le durcissement de production (non-root uid 10001, système de fichiers en lecture seule, aucune capacité Linux, `/tmp` de 64 Mo) | Sain en 9 s ; écriture refusée hors `/data` et `/tmp` |
| `docker compose up -d` : `app` puis Caddy (condition `service_healthy`) | Démarrage dans l'ordre ; sonde de santé du Dockerfile opérationnelle |
| HTTPS par Caddy, redirection HTTP→HTTPS, HSTS, CSP, interface protégée par mot de passe, `/healthz` sans mot de passe | Conformes |
| Envoi d'un fichier de **100 Mo** avec un `/tmp` de 64 Mo | Réussi, 0 Mo utilisé en mémoire (fichiers temporaires dans le volume) |
| `backup.sh` → `restore.sh` sur le même serveur, **sur un serveur neuf**, avec `--force`, sans `--force` | Corrects ; une restauration refusée ou une archive invalide laissent le service **en ligne, données intactes** |
| `update.sh` : sauvegarde préalable, récupération d'une nouvelle version, refus si fichiers modifiés localement, **échec de construction** | Corrects ; l'ancienne version continue de tourner et le retour arrière est indiqué |
| **CI GitHub (serveur Ubuntu vierge)** : construction du **vrai Dockerfile** (apt, ffmpeg et encodeur libopus compris), démarrage durci, sonde, non-root, lecture seule, interface protégée, sauvegarde puis restauration vers un volume neuf | Réussi (job `docker`, 36 s de construction) à chaque modification |
| `install.sh` (préparation de `.env`) : mot de passe fort généré, idempotence, caractères spéciaux, droits 600 | Testés automatiquement (tests de la CI) |
| Extrait Caddy de restriction par IP (§ 10) et `Caddyfile` du dépôt | Validés par `caddy validate` |

Défauts trouvés **et corrigés** grâce à ces essais : restauration impossible depuis un fichier de l'hôte (droits), service laissé arrêté après une restauration
refusée, mot de passe non généré (script interrompu en silence), extrait Caddy invalide dans ce guide, et garde de restauration trop stricte sur un serveur neuf.

**Non vérifié** :

- L'**installation complète `install.sh` avec construction sur un vrai hôte** : chacune de ses étapes a été vérifiée (préparation de `.env` par les tests, construction du vrai Dockerfile et démarrage durci par la CI, attente de santé et scripts par les essais), mais le script n'a pas été exécuté d'un bloc sur une machine neuve. C'est le premier essai à faire chez vous. (Dans l'environnement de développement, l'accès aux miroirs Debian est interdit : les essais en conteneurs y ont utilisé une variante où seul ffmpeg était fourni autrement ; la CI a confirmé le vrai Dockerfile.)
- L'émission d'un **vrai certificat Let's Encrypt** (nécessite votre domaine, ports 80/443 joignables) ; seul le certificat local de Caddy a été essayé.
- Les **sauvegardes planifiées par cron** et la copie chiffrée hors serveur (à tester chez vous, § 6).
- La charge réelle (nombre d'utilisateurs, très longues réunions) et le dimensionnement du serveur : les chiffres du § 1 sont des ordres de grandeur.

## Serveur de démonstration (relecteurs Google Play, essais, démos)
Préparation d'un serveur neuf en une commande, vérification à distance et texte d'accès pour la Play Console : [`docs/SERVEUR_DEMO.md`](docs/SERVEUR_DEMO.md) (`deploy/bootstrap-vps.sh`, `deploy/check-server.sh`, `install.sh --demo`).

## Emplacement des données et sauvegardes dans un cloud
Disque désigné pour les données (`--data-dir`), sauvegardes chiffrées vers le cloud de votre choix (`backup-cloud.sh`, `restore-cloud.sh`), copie de l'audio sur le téléphone : [`docs/STOCKAGE.md`](docs/STOCKAGE.md).

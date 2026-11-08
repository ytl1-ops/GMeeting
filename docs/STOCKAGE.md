# Où sont conservées vos données : disque du PC, cloud, téléphone

GMeeting sépare **trois rôles**, que vous désignez chacun. J'ai interprété « disque désigné » ainsi, parce que c'est ce qui est techniquement sûr :

| Rôle | Où | Pourquoi ce choix |
|---|---|---|
| **Données de référence** (base, comptes rendus, pièces jointes) | **le disque du PC ou du serveur que vous désignez** | la base SQLite doit être sur un disque local : sur un cloud synchronisé ou un partage réseau, elle peut se corrompre |
| **Sauvegardes** | **le cloud que vous désignez** (chiffrées avant l'envoi) | une copie hors du serveur protège d'une panne ou d'un vol ; le cloud ne lit jamais vos comptes rendus |
| **Copie de l'audio** | **un dossier du téléphone que vous désignez** (mémoire, carte SD, dossier synchronisé avec un cloud) | garder l'enregistrement chez vous, même si le serveur est perdu |

Le téléphone ne peut pas être le serveur : la transcription et la rédaction demandent un serveur. Un cloud ne peut pas non plus servir de disque « en direct » (voir ci-dessus).

---

## 1. Le disque du PC ou du serveur

Par défaut, les données sont dans un **volume Docker**. Pour les placer sur un disque ou un dossier précis (disque externe, autre partition, volume de bloc d'un hébergeur) :

```bash
./deploy/install.sh reunions.exemple.fr --data-dir /mnt/disque/gmeeting
# ou, sur un serveur neuf :  sudo ./deploy/bootstrap-vps.sh reunions.exemple.fr --data-dir /mnt/volume/gmeeting
```
Le script crée le dossier, le donne à l'utilisateur du conteneur (10001, jamais root), refuse un chemin relatif, la racine ou un dossier qui contient d'autres fichiers, et écrit `GMEETING_DATA` dans `.env`.

**Précautions**
- **Disque local** (ext4, xfs…). Évitez un partage réseau (NFS, SMB/CIFS), un dossier synchronisé (Drive, OneDrive, Dropbox) ou un disque exFAT/NTFS monté sans droits Unix : la base peut s'y corrompre. Le script avertit pour les partages réseau.
- **Disque toujours monté au démarrage** (ligne `fstab` avec une option qui n'invente pas un dossier vide si le disque manque) : sinon l'application démarrerait sur un dossier vide. Vérifiez avec `df` avant de relancer.
- **Chiffrez le disque** (LUKS, BitLocker, FileVault…) : GMeeting ne chiffre pas ses fichiers lui-même.
- **Migrer des données existantes** : `./deploy/backup.sh`, puis relancer l'installation avec `--data-dir`, puis `./deploy/restore.sh backups/gmeeting-….tar.gz`. Il n'y a pas de déplacement automatique.
- Surveillez l'espace libre : l'audio en cours de traitement et les archives (`KEEP_AUDIO`) s'y accumulent.

## 2. Le cloud désigné (sauvegardes chiffrées)

Tout service géré par [rclone](https://rclone.org/) convient : Google Drive, OneDrive, Dropbox, S3 et compatibles, Nextcloud / WebDAV, SFTP…

```bash
sudo apt install rclone gnupg            # (gnupg est déjà installé par bootstrap-vps.sh)
rclone config                            # une fois : crée un accès, par ex. « macloud », en suivant l'assistant du service choisi
./deploy/backup-cloud.sh --init          # enregistre « macloud:gmeeting-sauvegardes » et crée la PHRASE SECRÈTE de chiffrement
./deploy/backup-cloud.sh                 # sauvegarde + chiffrement + envoi + vérification + nettoyage des anciennes copies
./deploy/restore-cloud.sh                # restaure la plus récente (même phrase secrète)
```
À planifier chaque nuit : `30 3 * * *  cd /opt/gmeeting && ./deploy/backup-cloud.sh >> backups/backup.log 2>&1`.

**Garanties et limites**
- L'archive est **chiffrée sur votre serveur** (GnuPG, AES-256) **avant** l'envoi : le cloud ne reçoit que des données illisibles. Toute altération d'une copie est détectée au déchiffrement, et aucune restauration n'est lancée à partir d'une copie douteuse.
- **La phrase secrète est dans `.backup-cloud.env`** (droits 600, jamais versionné, jamais transmis au conteneur). **Sans elle, les copies du cloud sont illisibles, même pour vous** : gardez-en une copie dans un gestionnaire de mots de passe, hors du serveur.
- Le fournisseur voit quand vous sauvegardez, la taille et le nom des fichiers, pas leur contenu.
- Ce sont des **sauvegardes périodiques**, pas une copie en direct : ce qui est créé après la dernière sauvegarde n'y est pas. Par défaut, les 14 plus récentes sont gardées (`BACKUP_KEEP_REMOTE`).
- Les quotas et tarifs du cloud sont ceux de votre fournisseur.

## 3. Le téléphone (copie de l'audio)

Dans l'application : **Confidentialité → Sur ce téléphone → Copie de l'audio → Choisir un dossier**. Le sélecteur du système vous laisse désigner la mémoire du téléphone, la carte SD ou un dossier synchronisé avec un cloud (Drive, OneDrive…). L'application n'a aucune autre autorisation de stockage.

- Chaque minute enregistrée y est copiée (`GMeeting-<réunion>/seg_0001.m4a`…), **en plus** de l'envoi au serveur. Seul l'audio est copié, pas les documents.
- Désactivé par défaut. « Ne plus copier » retire l'accès à ce dossier.
- **Ces copies ne sont pas chiffrées** : si le dossier est synchronisé avec un cloud, ce cloud les voit. Protégez ce dossier.
- Une copie qui échoue (dossier supprimé, carte retirée) **n'empêche jamais** l'enregistrement ni l'envoi : la page Confidentialité signale « La dernière copie a échoué ».
- Les segments d'une minute sont des fichiers distincts ; pour les réécouter d'une traite, il faut les assembler (ou garder `KEEP_AUDIO` côté serveur).

---

## Vérifié / non vérifié
| | État |
|---|---|
| `--data-dir` : dossier créé, propriétaire 10001, refus des chemins dangereux et des dossiers non vides, montage correct dans `docker compose config`, volume Docker par défaut inchangé | testé automatiquement |
| Cloud : chiffrement réel (GnuPG), l'archive en clair n'apparaît jamais côté cloud, aller-retour identique, mauvaise phrase et copie altérée refusées, purge des anciennes copies, phrase jamais écrasée | testé automatiquement avec un **faux rclone** (dossier local) |
| Envoi vers un **vrai** cloud avec un vrai `rclone`, quotas, authentification du service | **jamais essayé** |
| Dossier du téléphone : choix, état, bouton « Ne plus copier », signalement d'un échec, textes FR/EN | testé dans le navigateur avec un faux pont natif |
| Copie réelle des segments par le sélecteur de dossiers d'Android (carte SD, Drive…) | **compile en CI, jamais exécuté sur un téléphone** |
| Montage réel d'un disque externe ou d'un volume de bloc en production | **jamais essayé** |

# Fiche de mission : installer GMeeting sur un serveur Oracle Cloud gratuit

*À remettre à la personne qui fait l'installation (administrateur système, prestataire ou ami technicien). Durée estimée : 2 à 3 heures, dont l'attente du DNS (estimation non mesurée).*

## L'objectif
Un serveur **GMeeting en HTTPS**, joignable sur un nom de domaine, protégé par un mot de passe, qui servira à une application Android (essais et revue Google Play). Le projet fournit des **scripts qui font l'essentiel** ; la mission consiste à créer le serveur et à les lancer.

## Ce que le propriétaire fournit (par un canal sûr, jamais par e-mail ou message en clair)
- L'accès au dépôt GitHub du projet (lecture), ou l'archive du projet.
- Un **compte Oracle Cloud « Always Free » ouvert au nom du propriétaire** (la carte bancaire et le code SMS sont les siens : il crée lui-même le compte). Pour vous donner accès : une invitation d'utilisateur dans la console (menu *Identity*), avec les droits strictement nécessaires (instances, réseau), **sans partager son mot de passe**. À défaut, il crée l'instance lui-même en suivant `docs/ORACLE.md`, vous faites le reste en SSH.
- Un nom de domaine ou sous-domaine modifiable (DuckDNS gratuit convient).
- Deux **clés d'API dédiées à la démonstration**, avec un plafond de dépense : Anthropic (rédaction) et OpenAI (transcription).

## Ce que vous faites
Tout est décrit pas à pas dans **`docs/ORACLE.md`** (10 étapes) ; les valeurs à utiliser :
1. Instance **Canonical Ubuntu 24.04 ARM**, forme **VM.Standard.A1.Flex, 2 OCPU / 12 Go**, disque 50 Go, IP publique, badge « Always Free-eligible » vérifié. En cas d'erreur « Out of host capacity » : réessayer plus tard, changer de domaine de disponibilité ou passer à 1 OCPU / 6 Go.
2. **Liste de sécurité du réseau virtuel** : entrées TCP **80** et **443** depuis `0.0.0.0/0` (rien d'autre à ouvrir).
3. DNS : enregistrement `A` vers l'IP de l'instance.
4. Depuis un poste avec le dépôt : `./deploy/oracle-helper.sh keygen`, `pack`, `send IP DOMAINE --demo`.
5. Sur le serveur : `./deploy/bootstrap-vps.sh DOMAINE --demo --dry-run`, puis la même commande sans `--dry-run` avec `sudo -E` (les clés d'API saisies avec `read -s`).
6. Contrôle depuis un autre poste : `./deploy/check-server.sh https://DOMAINE MOT_DE_PASSE`.

## Critères d'acceptation (à fournir au propriétaire)
- [ ] `check-server.sh` se termine par **CONTRÔLE OK** (certificat HTTPS valide, mot de passe exigé, en-têtes de sécurité, IA et transcription configurées).
- [ ] Le contenu de `DEMO_ACCESS.txt` est remis au propriétaire (adresse, mot de passe, instructions pour les relecteurs), puis le fichier est supprimé du serveur (`shred -u`).
- [ ] Le propriétaire a **changé son mot de passe Oracle** si vous avez eu un accès partagé, ou votre accès d'utilisateur est supprimé.
- [ ] Une **alerte de budget** à un montant très bas est créée (menu *Billing → Budgets*).
- [ ] Les accès SSH : la clé privée reste chez vous ou chez le propriétaire (jamais envoyée) ; le propriétaire dispose d'une clé d'accès de son côté.
- [ ] Un court compte rendu : adresse IP, région, forme choisie, date, ce qui a été difficile.

## Points d'attention
- **Machine inactive** : Oracle peut arrêter une machine « Always Free » peu utilisée (sources tierces, non confirmé). Prévenir le propriétaire et lui indiquer comment redémarrer l'instance dans la console.
- **Le gratuit peut devenir payant** si une ressource n'est pas « Always Free-eligible » ou si le compte passe en « Pay As You Go » : ne le faire que sur accord écrit du propriétaire.
- Les données de démonstration sont supprimées automatiquement après 24 h : **aucune donnée de vrai client ne doit y passer**.
- Ne jamais désactiver le mot de passe, ni le HTTPS, ni les contrôles de `check-server.sh`.
- Ce que **personne n'a encore vérifié sur un vrai serveur Oracle** : la création de l'instance, les règles de pare-feu de l'image Ubuntu d'Oracle, l'obtention du certificat. Si un script échoue, **notez le message exact** : il sert à corriger le projet.

## En cas de blocage
Le tableau de dépannage de `docs/ORACLE.md` (étape 7) couvre les cas connus : ports fermés (deux barrières à contrôler), certificat non délivré, mot de passe vide. Au-delà, transmettre au propriétaire le message d'erreur complet (sans clé ni mot de passe) pour correction.

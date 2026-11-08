# Créer le serveur Oracle Cloud « Always Free » — pas à pas

Durée : environ 45 minutes, dont l'attente du DNS. Résultat : GMeeting en HTTPS sur un serveur gratuit, vérifié depuis votre poste, avec le texte d'accès pour les relecteurs Google Play.

> **Ce que je ne peux pas faire** : créer le compte, l'instance ou le DNS à votre place. Cela demande votre identité, votre carte bancaire (vérification), vos clés SSH, et un accès à Oracle que mon environnement n'a pas. **Vous cliquez ; les scripts du dépôt font tout le reste** (clé SSH, envoi du projet, pare-feu, Docker, installation, vérification).
> **Ce que je n'ai pas pu vérifier** : les écrans de la console Oracle. Les intitulés ci-dessous viennent de la documentation et de guides tiers (les pages officielles d'Oracle sont hors du réseau autorisé de ma session) : s'ils diffèrent, suivez ceux de la console, et gardez les valeurs (forme, taille, ports).
> **Ne me transmettez jamais** vos mots de passe, clés privées ou clés d'API : tout se fait sur votre poste.

## Étape 0 — Préparer (sur votre poste, 5 min)
1. **Une clé SSH dédiée** :
   ```bash
   ./deploy/oracle-helper.sh keygen
   ```
   Il crée `~/.ssh/gmeeting_oracle` et **affiche la partie publique** (une ligne `ssh-ed25519 …`) : gardez-la pour l'étape 2. La clé privée ne quitte jamais votre poste ; sauvegardez-la dans votre coffre de mots de passe.
2. **Des clés d'IA dédiées à la démo**, avec un plafond de dépense (Anthropic, OpenAI) : voir `docs/SERVEUR_DEMO.md`.
3. **Un nom de domaine** : un sous-domaine gratuit DuckDNS suffit (créé à l'étape 4).
4. Une **carte bancaire** (vérification d'identité à l'inscription) et votre téléphone.

## Étape 1 — Compte Oracle Cloud (10 min)
1. Inscription sur la page « Cloud Free Tier » d'Oracle.
2. **Région d'origine** : choisissez une région **d'Europe proche de vous**. Les ressources « Always Free » se créent dans cette région et, d'après la documentation d'Oracle, elle ne se change pas ensuite : prenez le temps. La capacité ARM varie selon les régions.
3. La carte sert à vérifier votre identité. Restez en **« Always Free »** pour l'instant ; la question du passage à « Pay As You Go » est traitée à l'étape 9.

## Étape 2 — Créer l'instance (10 min)
Console → menu ≡ → **Compute → Instances → Create instance** :
| Champ | Valeur |
|---|---|
| Nom | `gmeeting-demo` |
| **Image** | *Change image* → **Canonical Ubuntu 24.04** (ou 22.04), version ARM (aarch64) |
| **Forme** | *Change shape* → **Ampere → VM.Standard.A1.Flex** → **2 OCPU, 12 Go de mémoire** |
| Réseau | *Create new virtual cloud network* + sous-réseau **public**, coche **Assign a public IPv4 address** |
| Clés SSH | *Paste public keys* → collez la ligne `ssh-ed25519 …` de l'étape 0 |
| Disque de démarrage | 50 Go (valeur par défaut ≈ 47 Go, suffisante) |

- **Vérifiez le badge « Always Free-eligible »** à côté de l'image et de la forme : sans lui, la ressource peut être facturée.
- Pourquoi 2 OCPU / 12 Go : c'est assez pour GMeeting (transcription par l'API) et cela reste dans les **deux** valeurs de quota annoncées (4 OCPU / 24 Go, ou la baisse à 2 / 12 évoquée par des sources non confirmées).
- Cliquez **Create**, attendez l'état **Running**, notez l'**adresse IP publique**.
- **Erreur « Out of host capacity »** : d'après la documentation d'Oracle, c'est un manque temporaire de capacité. Réessayez plus tard, changez de *domaine de disponibilité*, ou essayez 1 OCPU / 6 Go. Ce n'est pas un problème de compte.

## Étape 3 — Ouvrir les ports côté Oracle (3 min)
Il y a **deux barrières** ; voici la première (réseau virtuel du compte). Instance → **Primary VNIC → Subnet → Security Lists → Default Security List → Add Ingress Rules** :
| Source CIDR | Protocole | Port de destination |
|---|---|---|
| `0.0.0.0/0` | TCP | `80` |
| `0.0.0.0/0` | TCP | `443` |

N'ouvrez **que** 80 et 443 (le 22 pour SSH existe déjà) : surtout pas « tous les protocoles ». La seconde barrière (pare-feu du serveur) est réglée automatiquement à l'étape 6.

## Étape 4 — DNS (5 min + attente)
1. Sur duckdns.org, connectez-vous, créez un sous-domaine (par ex. `ma-demo-gmeeting`) et collez l'**IP publique** de l'étape 2.
2. Votre domaine est `ma-demo-gmeeting.duckdns.org`. Vérifiez : `nslookup ma-demo-gmeeting.duckdns.org` doit renvoyer l'IP.
(Un domaine acheté convient aussi : enregistrement `A` vers l'IP.)

## Étape 5 — Envoyer le projet (sur votre poste, 2 min)
```bash
./deploy/oracle-helper.sh pack                       # archive de la version commitée, sans aucun secret
./deploy/oracle-helper.sh send IP-PUBLIQUE ma-demo-gmeeting.duckdns.org --demo
```
Le script envoie l'archive par `scp` (la première connexion mémorise l'empreinte du serveur) puis **affiche les commandes à copier-coller** pour l'étape 6. Ajoutez `--dry-run` pour voir ce qu'il ferait sans rien envoyer. `--data-dir /chemin` place les données sur un volume de bloc monté (voir `docs/STOCKAGE.md`).

## Étape 6 — Installer (sur le serveur, 10 min)
Copiez-collez ce que l'étape 5 a affiché :
```bash
ssh -i ~/.ssh/gmeeting_oracle ubuntu@IP-PUBLIQUE
cd gmeeting
./deploy/bootstrap-vps.sh ma-demo-gmeeting.duckdns.org --demo --dry-run     # simulation : rien n'est modifié
read -r -s -p "Clé Anthropic : " ANTHROPIC_API_KEY; export ANTHROPIC_API_KEY; echo
read -r -s -p "Clé OpenAI : " OPENAI_API_KEY; export OPENAI_API_KEY; echo
sudo -E ./deploy/bootstrap-vps.sh ma-demo-gmeeting.duckdns.org --demo
```
Sur Oracle, le script **détecte le serveur** et, au lieu d'`ufw`, insère les règles `iptables` pour 80 et 443 **avant la règle de rejet finale** (une règle placée après serait ignorée) puis les enregistre pour qu'elles survivent au redémarrage. Il installe Docker, les mises à jour de sécurité automatiques, GMeeting avec HTTPS, et écrit `DEMO_ACCESS.txt`. **Notez le mot de passe affiché.**

## Étape 7 — Vérifier (depuis votre poste)
```bash
./deploy/check-server.sh https://ma-demo-gmeeting.duckdns.org LE-MOT-DE-PASSE
```
Tout doit être « ok » (certificat valide, mot de passe exigé, en-têtes, IA configurée).
| Symptôme | Cause probable | Solution |
|---|---|---|
| « serveur injoignable » ou « no route to host » | une des deux barrières ferme les ports | étape 3 (liste de sécurité) ; sur le serveur : `sudo iptables -L INPUT --line-numbers -n` doit montrer 80 et 443 **au-dessus** de la ligne `REJECT` ; sinon `sudo ./deploy/oracle-firewall.sh` |
| « certificat HTTPS invalide » | certificat pas encore délivré | DNS non propagé ou ports 80/443 fermés ; `cd ~/gmeeting && sudo docker compose logs caddy` |
| « le serveur est OUVERT » | mot de passe vide | `GMEETING_PASSWORD` dans `.env`, puis `sudo docker compose up -d` |
| l'installation échoue sur ARM | paquet sans version ARM | le contrôle de CI `docker-arm64` est vert ; envoyez-moi le message d'erreur |

## Étape 8 — Play Console
Sur le serveur : `cat ~/gmeeting/DEMO_ACCESS.txt`, collez le contenu dans *Contenu de l'application → Accès à l'application*, puis `shred -u ~/gmeeting/DEMO_ACCESS.txt`.

## Étape 9 — Garder le serveur en vie, maîtriser les coûts
- **Reprise d'une machine inactive** : d'après des sources tierces, Oracle peut arrêter ou reprendre une machine « Always Free » peu utilisée (environ 20 % de processeur, réseau et, en ARM, mémoire pendant 7 jours). Un serveur de démonstration est dans ce cas. **Surveillez-le** (`check-server.sh` régulièrement) ; si l'instance est arrêtée, redémarrez-la dans la console.
- **« Pay As You Go »** : des sources tierces indiquent qu'il évite cette reprise tout en restant gratuit dans les limites « Always Free ». **À vérifier chez Oracle avant de le faire** : c'est une décision financière, qui vous expose à la facturation si vous dépassez les limites. Si vous le faites : créez un **budget avec alerte** (menu *Billing → Budgets*) à un montant très bas, et ne créez que des ressources « Always Free-eligible ».
- **Sauvegardes** : si l'instance est supprimée, les données le sont aussi. Pour une démonstration c'est acceptable (conservation de 1 jour) ; sinon, `docs/STOCKAGE.md` (sauvegardes chiffrées vers un cloud).

## Étape 10 — Démonter
Console → instance → **Terminate** en cochant **« Permanently delete the attached boot volume »**, puis supprimez le réseau virtuel créé pour elle, supprimez le sous-domaine DuckDNS, révoquez les clés d'IA, et supprimez `~/.ssh/gmeeting_oracle` si vous ne la réutilisez pas.

---

## Vérifié / non vérifié
| | État |
|---|---|
| `oracle-firewall.sh` : règles insérées **avant** le rejet final, SSH et règles existantes intactes, pas de doublon à la 2ᵉ exécution, simulation sans effet, avertissement si l'enregistrement est impossible | testé automatiquement avec un **iptables simulé** |
| `bootstrap-vps.sh` : détection d'Oracle, `iptables-persistent` au lieu d'`ufw`, ufw conservé ailleurs | testé en simulation |
| `oracle-helper.sh` : clé dédiée (droits, partie publique seule affichée, jamais écrasée), archive sans secret, `send` validé et simulé | testé automatiquement (la création de clé s'exécute en CI) |
| Image du serveur pour ARM64 (démarrage durci, exports des 4 formats) | vérifiée en CI par émulation |
| **Création du compte, de l'instance, des règles réseau ; écrans de la console** | **jamais essayés** : demandent votre compte |
| **Règles iptables sur une vraie image Ubuntu d'Oracle**, Docker en ARM natif, certificat Let's Encrypt via DuckDNS | **jamais essayés** |
| Chiffres du quota, reprise des machines inactives, effet de « Pay As You Go » | **non confirmés** (sources tierces) |

Sources : [Always Free Resources — Oracle](https://docs.oracle.com/en-us/iaas/Content/FreeTier/resourceref.htm) · [Enabling network traffic to Ubuntu images in OCI — Oracle](https://blogs.oracle.com/developers/post/enabling-network-traffic-to-ubuntu-images-in-oracle-cloud-infrastructure) · [Oracle Always Free : réduction 2026 (tiers)](https://braindetox.kr/en/posts/oracle_always_free_tier_reduced_2026.html) · [Ports 80/443 sur Oracle Cloud (tiers)](https://dev.to/armiedema/opening-up-port-80-and-443-for-oracle-cloud-servers-j35).

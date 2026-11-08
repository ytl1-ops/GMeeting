/* Interface bilingue FR / EN.
   Le code de l'interface est écrit en français : en français rien ne change. En anglais, ce fichier traduit le texte affiché (dictionnaire exact
   + motifs pour les textes à valeurs) au fur et à mesure que la page se construit. Le CONTENU des réunions (comptes rendus, transcription, titres,
   noms) n'est jamais traduit ici : voir `.doc`, `[data-notr]`, les champs de saisie. La langue des rapports se choisit séparément (champ « Langue du rapport »).
   Langue : choix mémorisé (bouton FR | EN), sinon langue du navigateur ou du téléphone (français → FR, sinon EN). */
(() => {
  const stored = (() => { try { return localStorage.getItem("gm_lang"); } catch { return null; } })();
  const LANG = stored === "fr" || stored === "en" ? stored : (/^fr\b/i.test(navigator.language || "fr") ? "fr" : "en");
  window.GM_LANG = LANG;
  window.GM_LOCALE = LANG === "fr" ? "fr-FR" : "en-GB";
  document.documentElement.lang = LANG;

  const setLang = (l) => { try { localStorage.setItem("gm_lang", l); } catch {} location.reload(); };
  window.GM_setLang = setLang;

  /* ------------------------------------------------------------------ dictionnaire exact (français → anglais) */
  const EN = {
    // navigation, accueil
    "Accueil GMeeting": "GMeeting home", "Retour": "Back", "🎨 Gabarit": "🎨 Template", "Gabarit": "Template",
    "Nouvelle réunion": "New meeting", "Mes réunions": "My meetings", "Aucune réunion pour l'instant.": "No meetings yet.",
    "Hors connexion — la liste des réunions s'affichera au retour du réseau. Vous pouvez néanmoins enregistrer.": "Offline — the meeting list will appear when the network returns. You can still record.",
    "Chargement…": "Loading…", "Sans titre": "Untitled", "Réunion sans titre": "Untitled meeting",
    "🎙 Enregistrer": "🎙 Record", "🔗 Lien vidéo": "🔗 Video link", "📁 Fichier": "📁 File", "📝 Texte": "📝 Text",
    // statuts
    "Enregistrement": "Recording", "En attente": "Pending", "En file": "Queued", "Traitement": "Processing", "Rédaction": "Drafting", "Prêt": "Ready", "Erreur": "Error",
    // onglets et documents
    "Procès-verbal": "Formal minutes", "Compte rendu": "Meeting report", "Note de synthèse": "Executive summary", "Présentation": "Presentation",
    "Présentation illustrée": "Illustrated presentation", "Pièces jointes": "Attachments", "Transcription": "Transcript", "Informations": "Details",
    "Exporter :": "Export:", "← Toutes les réunions": "← All meetings", "← Retour": "← Back", "Retour à l'enregistreur": "Back to the recorder",
    // formulaire
    "Informations et pièces jointes (facultatif, améliore la qualité du rendu)": "Details and attachments (optional, improves the result)",
    "https://… (YouTube, Vimeo, LinkedIn, Loom, lien direct .mp4/.mp3, etc.)": "https://… (YouTube, Vimeo, LinkedIn, Loom, direct .mp4/.mp3 link, etc.)",
    "Titre": "Title", "Date": "Date", "Lieu / outil": "Place / tool", "Participants": "Participants", "Contexte / consignes": "Context / instructions",
    "Ex. COPIL sûreté site Nord": "e.g. Steering committee – North site", "Teams, salle B12…": "Teams, room B12…",
    "Langue parlée": "Spoken language", "Détection auto": "Auto-detect", "Français": "French", "Anglais": "English", "Allemand": "German", "Espagnol": "Spanish",
    "Portugais": "Portuguese", "Arabe": "Arabic",
    "Participants (nom, fonction – un par ligne)": "Participants (name, role – one per line)",
    "Awa Koné – Directrice sûreté\nMarc Dubois – DSI": "Jane Smith – Security Director\nMark Dupont – CIO",
    "Contexte / consignes de rédaction": "Context / drafting instructions",
    "Acronymes, enjeux, ton souhaité, destinataires du document…": "Acronyms, stakes, desired tone, recipients of the document…",
    "Langue du rapport": "Report language",
    "Ajouter des pièces jointes": "Add attachments", "Pièce partagée": "Shared attachment", "Partagée depuis une autre application": "Shared from another app",
    "Mail Outlook (.msg ou .eml), Word, Excel, PDF, PowerPoint, texte, images. Elles sont lues par l'IA pour mieux rédiger (noms, chiffres, ordre du jour) et insérées en annexe des rapports.":
      "Outlook email (.msg or .eml), Word, Excel, PDF, PowerPoint, text, images. The AI reads them to write better (names, figures, agenda) and they are inserted as annexes in the reports.",
    // enregistreur
    "Démarrer l'enregistrement": "Start recording", "REC": "REC", "⏸ Pause": "⏸ Pause", "▶ Reprendre": "▶ Resume", "Repérer un moment important": "Mark an important moment",
    "⭐ Marquer": "⭐ Mark", "⏹ Terminer et générer": "⏹ Finish and generate", "Qualité audio": "Audio quality",
    "Compromis qualité / taille de l'enregistrement": "Trade-off between quality and recording size",
    "Micro seul (présentiel, téléphone)": "Microphone only (in person, phone)", "Micro + audio de l'onglet (visio web)": "Microphone + tab audio (web video call)",
    "Économique": "Economy", "Équilibré (recommandé)": "Balanced (recommended)", "Haute qualité": "High quality",
    "≈ 11 Mo/h max — réunions calmes, stockage limité (mode avion long)": "≈ 11 MB/h max — quiet meetings, limited storage (long airplane mode)",
    "≈ 14 Mo/h max — voix claire, taille réduite": "≈ 14 MB/h max — clear voice, small size",
    "≈ 29 Mo/h max — salle bruyante ou vaste, plusieurs voix éloignées": "≈ 29 MB/h max — noisy or large room, several distant voices",
    " · mono, voix optimisée": " · mono, voice-optimised",
    "⏸ En pause.": "⏸ Paused.", "⏸ Pause ": "⏸ Paused ", "⚠ Interrompu ": "⚠ Interrupted ", "⚠ Toucher pour reprendre ": "⚠ Tap to resume ", "● REC ": "● REC ",
    "⚠ Micro interrompu (appel en cours ?). L'enregistrement reprendra tout seul à la fin de l'appel — gardez cette page ouverte.":
      "⚠ Microphone interrupted (phone call?). Recording will resume by itself when the call ends — keep this page open.",
    "Le navigateur demande une confirmation pour rouvrir le micro.": "The browser asks for confirmation to reopen the microphone.",
    "Interruption du micro": "Microphone interruption", "appel ou micro occupé": "call or microphone in use", "micro coupé": "microphone cut",
    "Enregistreur relancé automatiquement": "Recorder restarted automatically",
    "Partage de l'onglet arrêté : enregistrement poursuivi avec le micro seul": "Tab sharing stopped: recording continues with the microphone only",
    "⚠ Espace de stockage faible sur l'appareil : libérez de la place ou rétablissez le réseau pour envoyer l'audio":
      "⚠ Low storage space on the device: free some space or restore the network to upload the audio",
    "Enregistrement non supporté par ce navigateur.": "Recording is not supported by this browser.",
    "Moment marqué ⭐": "Moment marked ⭐", "Enregistrement terminé.": "Recording finished.",
    "Enregistrement terminé. Envoi en attente de connexion : il reprendra automatiquement.": "Recording finished. Upload is waiting for a connection and will resume automatically.",
    "Enregistrement assuré par l'application : il continue écran verrouillé et pendant un appel, et l'audio non envoyé reste sur le téléphone.":
      "Recording is handled by the app: it continues with the screen locked and during a call, and audio not yet uploaded stays on the phone.",
    "L'audio est écrit sur l'appareil puis envoyé en continu : une coupure réseau, un appel téléphonique ou la fermeture de la page ne font pas perdre l'enregistrement. ":
      "Audio is written to the device and then uploaded continuously: a network drop, a phone call or closing the page will not lose the recording. ",
    "Gardez la page ouverte et l'écran allumé. L'accès au micro exige HTTPS ou localhost.": "Keep the page open and the screen on. Microphone access requires HTTPS or localhost.",
    "✈ Mode avion : ": "✈ Airplane mode: ", "vous pouvez enregistrer sans aucun réseau, donc sans appel qui coupe le micro. ": "you can record with no network at all, so no phone call can cut the microphone. ",
    "L'application est prête pour l'usage hors-ligne. Activez le mode avion (vous pouvez ensuite rallumer le Wi-Fi seul si besoin) puis lancez l'enregistrement ; l'envoi se fera au retour du réseau.":
      "The app is ready for offline use. Turn on airplane mode (you can then switch Wi-Fi back on alone if needed) and start recording; the upload will happen when the network returns.",
    "Pour cela, rechargez cette page une fois en ligne (installation hors-ligne en cours), puis installez l'application sur l'écran d'accueil si possible.":
      "To do this, reload this page once online (offline installation in progress), then install the app on the home screen if possible.",
    "Aucun son partagé. Dans la fenêtre de partage, choisissez un onglet (Chrome/Edge) et cochez « Partager l'audio de l'onglet ».":
      "No shared sound. In the sharing window, choose a tab (Chrome/Edge) and tick “Share tab audio”.",
    "Le partage d'un onglet n'existe pas dans l'application : utilisez le micro (placez le téléphone près de la source).":
      "Tab sharing does not exist in the app: use the microphone (place the phone near the source).",
    "Autorisez le micro pour enregistrer (Réglages Android → Applications → GMeeting → Autorisations).": "Allow the microphone to record (Android Settings → Apps → GMeeting → Permissions).",
    "Impossible de démarrer l'enregistrement.": "Unable to start recording.",
    "Micro indisponible : un appel ou une autre application l'utilise-t-il ?": "Microphone unavailable: is a call or another app using it?",
    "● Enregistrement en cours sur cet appareil": "● Recording in progress on this device", "🎙 Reprendre l'enregistrement": "🎙 Back to the recording",
    "⚠ Un enregistrement n'a pas été terminé": "⚠ A recording was not finished", "Tout l'audio a été envoyé. ": "All the audio has been uploaded. ",
    "Récupérer et générer les documents": "Recover and generate the documents", "Supprimer": "Delete",
    "Supprimer définitivement cet enregistrement ?": "Permanently delete this recording?",
    "Envoi impossible pour l'instant (": "Unable to upload right now (", "). Réessayez avec une connexion.": "). Try again with a connection.",
    "Enregistrement non finalisé": "Recording not finalised", "Finaliser et générer les documents": "Finalise and generate the documents",
    // lien, fichier, texte
    "Analyser le lien": "Analyse the link", "Collez un lien.": "Paste a link.", "Lien de la vidéo ou de l'audio": "Video or audio link",
    "Utiliser les sous-titres existants quand ils sont disponibles (plus rapide)": "Use existing subtitles when available (faster)",
    "Les liens privés (Teams, Zoom, Drive protégés) ne sont pas accessibles : téléchargez le fichier puis utilisez l'onglet « Fichier ».":
      "Private links (protected Teams, Zoom, Drive) are not accessible: download the file and use the “File” tab.",
    "Transcrire et générer": "Transcribe and generate", "Choisissez un fichier.": "Choose a file.",
    "Fichier audio ou vidéo (mp3, m4a, wav, mp4, webm…)": "Audio or video file (mp3, m4a, wav, mp4, webm…)",
    "Fonctionne avec les enregistrements Plaud, dictaphone, Teams, Zoom, etc.": "Works with Plaud, voice recorder, Teams, Zoom recordings, etc.",
    "Collez ici une transcription existante (Teams, Zoom, Otter, sous-titres…)": "Paste an existing transcript here (Teams, Zoom, Otter, subtitles…)",
    "Générer les documents": "Generate the documents", "Collez un texte.": "Paste some text.",
    "clé ANTHROPIC_API_KEY manquante": "ANTHROPIC_API_KEY missing", "aucun moteur de transcription configuré": "no transcription engine configured",
    // réunion
    "↻ Relancer la rédaction": "↻ Restart drafting", "↻ Relancer le traitement (audio conservé)": "↻ Restart processing (audio kept)",
    "ℹ Les pièces jointes ont changé depuis la rédaction. ": "ℹ The attachments have changed since the drafting. ",
    "Régénérez pour que les rapports en tiennent compte (citations des sources, recoupements, suivi des actions antérieures). ":
      "Regenerate so the reports take them into account (source citations, cross-checks, follow-up of earlier actions). ",
    "↻ Régénérer maintenant": "↻ Regenerate now", " Inclure": " Include",
    "Aperçu de l'en-tête et du pied de page": "Header and footer preview",
    "Réécoutez l'enregistrement pour vérifier un passage (audio compact conservé)": "Listen to the recording again to check a passage (compact audio kept)",
    "Corrigez les noms propres ou acronymes mal transcrits, puis régénérez : les trois documents sont réécrits à partir du texte corrigé.":
      "Correct any misheard proper names or acronyms, then regenerate: the three documents are rewritten from the corrected text.",
    "Enregistrer": "Save", "Enregistré. Utilisez « Régénérer » pour appliquer au contenu.": "Saved. Use “Regenerate” to apply it to the content.",
    "↻ Régénérer les documents": "↻ Regenerate the documents", "Enregistrer et régénérer les documents": "Save and regenerate the documents",
    "Supprimer définitivement cette réunion et ses documents ?": "Permanently delete this meeting and its documents?",
    "⬇ .txt": "⬇ .txt", "⬇ Original": "⬇ Original",
    "Pièce jointe": "Attachment", "Voir le contenu extrait": "View extracted content", "Décochez pour exclure des rapports et de la rédaction": "Untick to exclude from the reports and the drafting",
    "Les pièces jointes incluses sont lues par l'IA lors de la rédaction (régénérez pour en tenir compte) et peuvent être insérées en annexe de tous les rapports : PV, CR, note, Word, Excel, PDF, PowerPoint. Le fichier d'origine reste téléchargeable.":
      "Included attachments are read by the AI when drafting (regenerate to take them into account) and can be inserted as an annex in all reports: minutes, report, summary, Word, Excel, PDF, PowerPoint. The original file remains downloadable.",
    "↻ Régénérer en tenant compte des pièces jointes": "↻ Regenerate taking the attachments into account",
    "Aucune pièce jointe. Ajoutez un mail Outlook, un Word, un Excel…": "No attachments. Add an Outlook email, a Word, an Excel…",
    // gabarit
    "Gabarit des documents": "Document template", "Ces éléments sont appliqués à tous les exports (PV, CR, note de synthèse) en PDF, Word et Excel.":
      "These elements are applied to all exports (minutes, report, executive summary) in PDF, Word and Excel.",
    "Logo (PNG, JPEG, GIF ou WebP – fond transparent recommandé)": "Logo (PNG, JPEG, GIF or WebP – transparent background recommended)",
    "Fichier logo": "Logo file", "Logo": "Logo", "Logo actuel": "Current logo", "Aucun logo": "No logo", "Logo enregistré.": "Logo saved.", "Retirer le logo": "Remove the logo",
    "Nom de l'organisation": "Organisation name", "Ex. Direction de la Sûreté – ACME": "e.g. Security Department – ACME",
    "Texte d'en-tête (à droite)": "Header text (right)", "Ex. ACME – Document interne": "e.g. ACME – Internal document",
    "Pied de page (remplace le pied par défaut)": "Footer (replaces the default footer)", "Mention de confidentialité": "Confidentiality notice", "Ex. CONFIDENTIEL": "e.g. CONFIDENTIAL",
    "Couleur des titres et des tableaux": "Colour of headings and tables", "Code couleur": "Colour code", "Ex. Diffusion restreinte": "e.g. Restricted distribution",
    "Enregistrer le gabarit": "Save the template", "Gabarit enregistré : il s'applique aux nouveaux exports PDF, Word et Excel.": "Template saved: it applies to new PDF, Word and Excel exports.",
    "Ajoutez un logo ou un texte d'en-tête": "Add a logo or a header text", "Exemple de titre de section": "Example section title", "PROCÈS-VERBAL DE RÉUNION": "MEETING MINUTES", "DÉCISIONS": "DECISIONS",
    "Démo : les exports PDF, Word, Excel et PowerPoint sont disponibles avec votre serveur.": "Demo: PDF, Word, Excel and PowerPoint exports are available with your own server.",
    "Gardez la page ouverte et l'écran allumé.": "Keep the page open and the screen on.", "L'accès au micro exige HTTPS ou localhost.": "Microphone access requires HTTPS or localhost.",
    // progression du traitement (messages du serveur)
    "Assemblage de l'enregistrement…": "Assembling the recording…", "En file d'attente": "Queued", "Terminé": "Done", "Préparation de l'audio…": "Preparing the audio…",
    "Extraction spécialisée impossible, tentative de téléchargement direct…": "Specialised extraction impossible, trying a direct download…",
    "Lecture des informations du lien…": "Reading the link information…", "Téléchargement de la piste audio…": "Downloading the audio track…",
    "Transcription en cours…": "Transcription in progress…", "Rédaction du PV, du CR et de la note de synthèse…": "Drafting the minutes, the report and the executive summary…",
    // page Confidentialité
    "🔒 Confidentialité": "🔒 Privacy", "Confidentialité": "Privacy", "Confidentialité et protection des données": "Privacy and data protection",
    "Où sont vos données": "Where your data is",
    "Vos réunions, enregistrements, transcriptions et documents sont stockés sur le serveur GMeeting que vous utilisez : le vôtre ou celui de votre organisation.":
      "Your meetings, recordings, transcripts and documents are stored on the GMeeting server you use: your own or your organisation's.",
    "L'éditeur de l'application n'en reçoit aucune copie. Aucune publicité, aucun outil de mesure d'audience.": "The app publisher receives no copy of them. No ads, no analytics tools.",
    "Ce qui est envoyé à un service d'IA": "What is sent to an AI service",
    "Pour rédiger les comptes rendus, le texte de la réunion (transcription, contexte et pièces jointes incluses) est envoyé au service d'IA Anthropic configuré sur ce serveur.":
      "To write the reports, the meeting text (transcript, context and included attachments) is sent to the Anthropic AI service configured on this server.",
    "La rédaction par IA n'est pas configurée sur ce serveur : aucun texte n'est envoyé.": "AI drafting is not configured on this server: no text is sent.",
    "L'audio de vos réunions est envoyé au service de transcription OpenAI pour être transcrit.": "The audio of your meetings is sent to the OpenAI transcription service to be transcribed.",
    "La transcription est faite sur ce serveur : l'audio ne le quitte pas.": "Transcription is done on this server: the audio never leaves it.",
    "Ces services agissent comme sous-traitants : leurs conditions s'appliquent. Informez les participants avant d'enregistrer (le RGPD demande d'informer les personnes dont la voix est enregistrée).":
      "These services act as processors: their terms apply. Inform participants before recording (the GDPR requires informing people whose voice is recorded).",
    "Combien de temps": "How long",
    "Aucune suppression automatique des réunions : elles restent jusqu'à ce que vous les supprimiez.": "No automatic deletion of meetings: they stay until you delete them.",
    "L'audio compact de chaque réunion est conservé pour la réécoute.": "A compact copy of each meeting's audio is kept for replay.",
    "L'audio est supprimé après la rédaction : seuls le texte et les documents restent.": "The audio is deleted after drafting: only the text and documents remain.",
    "Une réunion supprimée l'est définitivement, avec son audio, sa transcription, ses documents et ses pièces jointes.": "A deleted meeting is gone for good, with its audio, transcript, documents and attachments.",
    "Qui peut y accéder": "Who can access it",
    "L'accès est protégé par un mot de passe.": "Access is protected by a password.",
    "Aucun mot de passe n'est configuré : toute personne qui atteint ce serveur peut lire les réunions. Configurez GMEETING_PASSWORD.":
      "No password is set: anyone who can reach this server can read the meetings. Set GMEETING_PASSWORD.",
    "La connexion est chiffrée (HTTPS).": "The connection is encrypted (HTTPS).",
    "La connexion n'est pas chiffrée (HTTP) : réservez cela à votre réseau local et utilisez HTTPS partout ailleurs.": "The connection is not encrypted (HTTP): keep this for your local network and use HTTPS everywhere else.",
    "Partages": "Sharing",
    "Quand vous partagez un fichier, un mail ou un lien vers GMeeting depuis une autre application, il est envoyé uniquement à votre serveur (en HTTPS dans la version publiée). La copie temporaire faite sur le téléphone est supprimée aussitôt.":
      "When you share a file, an email or a link to GMeeting from another app, it is sent only to your server (over HTTPS in the published version). The temporary copy made on the phone is deleted right away.",
    "Un document reçu par partage et jamais rattaché à une réunion est supprimé automatiquement au bout de 24 heures.": "A document received by sharing and never attached to a meeting is automatically deleted after 24 hours.",
    "Les documents exportés (PDF, Word, Excel, PowerPoint) sont des fichiers ordinaires enregistrés sur votre appareil : conservez-les et transmettez-les par un canal sûr.":
      "Exported documents (PDF, Word, Excel, PowerPoint) are ordinary files saved on your device: keep them safe and send them through a secure channel.",
    "Ajoutez une mention de confidentialité sur tous vos documents : ": "Add a confidentiality notice to all your documents: ",
    "Sur ce téléphone": "On this phone",
    " Protéger l'écran : masquer l'aperçu dans les applications récentes et bloquer les captures d'écran": " Protect the screen: hide the preview in recent apps and block screenshots",
    "Par défaut, elles sont sur le disque du serveur ; l'administrateur peut désigner un autre disque, et envoyer des sauvegardes chiffrées vers un cloud de son choix. Le téléphone peut en plus garder une copie de l'audio dans un dossier que vous désignez (voir plus bas).":
      "By default they are on the server's disk; the administrator can designate another disk and send encrypted backups to a cloud of their choice. The phone can also keep a copy of the audio in a folder you designate (see below).",
    "Copie de l'audio sur ce téléphone": "Audio copy on this phone",
    "Pour garder aussi l'audio sur le téléphone (mémoire, carte SD, dossier synchronisé avec un cloud), désignez un dossier : chaque minute enregistrée y est copiée en .m4a, en plus de l'envoi à votre serveur. Ces copies ne sont pas chiffrées : protégez ce dossier.":
      "To also keep the audio on the phone (storage, SD card, folder synced with a cloud), designate a folder: each recorded minute is copied there as .m4a, in addition to being sent to your server. These copies are not encrypted: protect this folder.",
    "Aucune copie sur le téléphone.": "No copy on the phone.",
    "La dernière copie a échoué : le dossier existe-t-il encore ? Désignez-le à nouveau.": "The last copy failed: does the folder still exist? Designate it again.",
    "Changer de dossier": "Change folder", "Choisir un dossier": "Choose a folder", "Ne plus copier": "Stop copying",
    "Vos droits": "Your rights",
    "Vous pouvez supprimer une réunion depuis sa fiche. Pour une demande d'accès, de rectification ou d'effacement concernant une personne, adressez-vous à l'administrateur du serveur.":
      "You can delete a meeting from its page. For an access, rectification or erasure request concerning a person, contact the server administrator.",
    // erreurs serveur (détails renvoyés par l'API)
    "Erreur inconnue": "Unknown error", "Réunion introuvable": "Meeting not found", "Pièce jointe introuvable": "Attachment not found", "Fichier introuvable": "File not found",
    "Texte vide": "Empty text", "Pas de transcription disponible": "No transcript available", "Analyse non disponible pour cette réunion": "Analysis not available for this meeting",
    "Aucun audio reçu pour cet enregistrement": "No audio received for this recording", "Aucun audio conservé pour cette réunion (activez KEEP_AUDIO)": "No audio kept for this meeting (enable KEEP_AUDIO)",
    "Enregistrement déjà en cours de traitement ou terminé": "Recording already being processed or finished", "Cet enregistrement n'accepte plus de segments": "This recording no longer accepts segments",
    "Segment vide ou trop volumineux": "Empty or oversized segment", "Identifiant invalide": "Invalid identifier", "Identifiant déjà utilisé": "Identifier already in use",
    "Le lien doit commencer par http:// ou https://": "The link must start with http:// or https://", "Type de document inconnu": "Unknown document type",
    "Rien à relancer : l'audio d'origine n'est plus disponible": "Nothing to restart: the original audio is no longer available", "Seul un traitement en erreur peut être relancé": "Only a failed processing can be restarted",
    "Fichier corrompu ou format non reconnu.": "Corrupted file or unrecognised format.", "Fichier Office trop volumineux une fois décompressé.": "Office file too large once decompressed.",
    "Fichier image invalide. Formats acceptés : PNG, JPEG, GIF, WebP.": "Invalid image file. Accepted formats: PNG, JPEG, GIF, WebP.", "Image illisible ou trop grande.": "Unreadable or too large image.",
    "Logo trop volumineux (max 5 Mo).": "Logo too large (max 5 MB).", "Couleur invalide (format attendu : #RRGGBB).": "Invalid colour (expected format: #RRGGBB).",
    "Les présentations s'exportent en .pptx ; les autres documents en PDF, Word ou Excel.": "Presentations export as .pptx; other documents as PDF, Word or Excel.",
    "La lecture des .msg nécessite le paquet « extract-msg » (pip install extract-msg) ; enregistrez le mail au format .eml en attendant.":
      "Reading .msg files requires the “extract-msg” package (pip install extract-msg); save the email as .eml in the meantime.",
  };

  /* ------------------------------------------------------------------ motifs (textes avec valeurs) */
  const P = [
    [/^« ([\s\S]*) », démarré le ([\s\S]*)\.$/, (m) => `“${m[1]}”, started on ${m[2]}.`],
    [/^(\d+) segment\(s\) audio sont conservés sur cet appareil et n'ont pas encore été envoyés\.$/, (m) => `${m[1]} audio segment(s) are kept on this device and have not been uploaded yet.`],
    [/^Envoi en cours… (\d+) segment\(s\) en attente\.$/, (m) => `Uploading… ${m[1]} segment(s) pending.`],
    [/^✈ Hors connexion \(mode avion \?\) — l'enregistrement se poursuit normalement\. L'audio est conservé sur cet appareil et sera envoyé automatiquement au retour du réseau \((\d+) segment\(s\) en attente\)\.$/,
      (m) => `✈ Offline (airplane mode?) — recording continues normally. Audio is kept on this device and will be uploaded automatically when the network returns (${m[1]} segment(s) pending).`],
    [/^⭐ Repère n°(\d+) à ([\s\S]*)$/, (m) => `⭐ Marker #${m[1]} at ${m[2]}`],
    [/^(\d+) segment\(s\) reçus$/, (m) => `${m[1]} segment(s) received`],
    [/^ · dernier il y a (\d+) s$/, (m) => ` · last ${m[1]} s ago`],
    [/^ Insérer les pièces jointes en annexe \((\d+)\)$/, (m) => ` Insert the attachments as an annex (${m[1]})`],
    [/^(\d+) diapositives\. Aperçu simplifié : le fichier PowerPoint contient les pictogrammes vectoriels modifiables, les images et les graphiques natifs( \(version sobre : texte et tableaux\))?\.$/,
      (m) => `${m[1]} slides. Simplified preview: the PowerPoint file contains editable vector icons, images and native charts${m[2] ? " (plain version: text and tables)" : ""}.`],
    [/^Supprimer « ([\s\S]*) » \?$/, (m) => `Delete “${m[1]}”?`],
    [/^Retirer ([\s\S]*)$/, (m) => `Remove ${m[1]}`],
    [/^Audio : ([\s\S]*)$/, (m) => `Audio: ${T(m[1])}`],
    [/^Transcription : ([\s\S]*) · Rédaction : ([\s\S]*)$/, (m) => `Transcription: ${m[1]} · Drafting: ${m[2]}`],
    [/^([\s\S]*) — (\d+) ligne\(s\)$/, (m) => `${m[1]} — ${m[2]} row(s)`],
    [/^Enregistrement repris \(interruption de (\d+) s\)$/, (m) => `Recording resumed (interruption of ${m[1]} s)`],
    [/^(\d+) haute · (\d+) moyenne · (\d+) basse$/, (m) => `${m[1]} high · ${m[2]} medium · ${m[3]} low`],
    [/^Liste indisponible : ([\s\S]*)$/, (m) => `List unavailable: ${T(m[1])}`],
    [/^(\d{1,2}:\d{2}:\d{2}) — ([\s\S]*)$/, (m) => `${m[1]} — ${T(m[2])}`],
    [/^([\s\S]*) · mono, voix optimisée$/, (m) => `${T(m[1])} · mono, voice-optimised`],
    [/^([\s\S]*) · (lien|fichier|enregistrement|texte)$/, (m) => `${m[1]} · ${{ lien: "link", fichier: "file", enregistrement: "recording", texte: "text" }[m[2]]}`],
    [/^Analyse du tronçon (\d+)\/(\d+)…$/, (m) => `Analysing part ${m[1]}/${m[2]}…`],
    [/^Chargement du modèle Whisper « ([\s\S]*) »…$/, (m) => `Loading the Whisper model “${m[1]}”…`],
    [/^Sous-titres '([\s\S]*)' trouvés, récupération du texte…$/, (m) => `Subtitles '${m[1]}' found, retrieving the text…`],
    [/^Transcription locale… (\d+) %$/, (m) => `Local transcription… ${m[1]}%`],
    [/^Transcription… segment (\d+)\/(\d+)$/, (m) => `Transcription… segment ${m[1]}/${m[2]}`],
    [/^Copie dans le dossier : ([\s\S]*)$/, (m) => `Copy in folder: ${m[1]}`],
    [/^Les réunions sont supprimées automatiquement après (\d+) jours\.$/, (m) => `Meetings are automatically deleted after ${m[1]} days.`],
    [/^Fichier trop volumineux \(max (\d+) Mo\)$/, (m) => `File too large (max ${m[1]} MB)`],
    [/^Trop de pièces jointes \(maximum (\d+) par réunion\)\.$/, (m) => `Too many attachments (maximum ${m[1]} per meeting).`],
    [/^« ([\s\S]*) » dépasse (\d+) Mo\.$/, (m) => `“${m[1]}” exceeds ${m[2]} MB.`],
    [/^« ([\s\S]*) » est vide\.$/, (m) => `“${m[1]}” is empty.`],
    [/^« ([\s\S]*) » : les fichiers exécutables ou scripts ne sont pas acceptés\.$/, (m) => `“${m[1]}”: executable files and scripts are not accepted.`],
    [/^Format inconnu : ([\s\S]*)$/, (m) => `Unknown format: ${m[1]}`],
    [/^Type de document inconnu : ([\s\S]*)$/, (m) => `Unknown document type: ${m[1]}`],
  ];

  /* unités : « 1,5 Mo » → « 1.5 MB » */
  const UNITS = [[/(\d+),(\d+) Mo\b/g, "$1.$2 MB"], [/(\d+) Mo\b/g, "$1 MB"], [/(\d+) Ko\b/g, "$1 KB"]];

  function T(s) {
    if (LANG === "fr" || !s) return s;
    const lead = s.match(/^\s*/)[0], trail = s.match(/\s*$/)[0], core = s.trim();
    if (!core) return s;
    // les textes du dictionnaire ont parfois une espace en début/fin : on essaie d'abord le texte brut
    let out = EN[s] ?? EN[core];
    if (out !== undefined) return EN[s] !== undefined ? out : lead + out + trail;
    for (const [re, f] of P) { const m = core.match(re); if (m) return lead + f(m) + trail; }
    // pictogramme + texte (« ✅ … », « ⚠ … ») : on traduit le texte et on garde le pictogramme
    const pm = core.match(/^(✅|⚠|ℹ|⭐|✈|⏸|▶|⬇|↻|●|■)\s+([\s\S]+)$/u);
    if (pm) { const t = T(pm[2]); if (t !== pm[2]) return lead + pm[1] + " " + t + trail; }
    // texte composé de plusieurs phrases connues (littéraux concaténés dans le code)
    const parts = core.split(/(?<=[.!?…])\s+/);
    if (parts.length > 1) {
      let hit = 0; const tr = parts.map((x) => { const y = EN[x] ?? EN[x + " "]; if (y !== undefined) { hit++; return y.trim(); } return x; });
      if (hit) return lead + tr.join(" ") + trail;
    }
    let r = s; for (const [re, rep] of UNITS) r = r.replace(re, rep);
    return r;
  }
  window.GM_T = T;

  /* ------------------------------------------------------------------ traducteur du DOM */
  const SKIP = "script,style,textarea,input,code,pre,.doc:not(.sample),[data-notr],.slides";
  const ATTRS = ["placeholder", "aria-label", "title", "alt"];
  const USER = ".doc:not(.sample),[data-notr],.slides";                       // contenu de réunion : jamais traduit
  const skipNode = (n) => { const e = n.nodeType === 1 ? n : n.parentElement; return !e || e.closest(SKIP); };
  const skipAttr = (e) => !!e.closest(USER);
  function walk(root) {
    if (LANG === "fr" || !root) return;
    if (root.nodeType === 3) { if (!skipNode(root)) { const t = T(root.nodeValue); if (t !== root.nodeValue) root.nodeValue = t; } return; }
    if (root.nodeType !== 1) return;
    if (!skipAttr(root)) for (const a of ATTRS) { const v = root.getAttribute(a); if (v) { const t = T(v); if (t !== v) root.setAttribute(a, t); } }
    if (skipNode(root)) return;
    for (const c of root.childNodes) walk(c);
  }
  if (LANG !== "fr") {
    const start = () => {
      document.title = T(document.title) || document.title;
      walk(document.body);
      new MutationObserver((muts) => {
        for (const m of muts) {
          if (m.type === "characterData") walk(m.target);
          else if (m.type === "attributes") { const v = skipAttr(m.target) ? null : m.target.getAttribute(m.attributeName); if (v) { const t = T(v); if (t !== v) m.target.setAttribute(m.attributeName, t); } }
          else m.addedNodes.forEach(walk);
        }
      }).observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS });
    };
    if (document.body) start(); else document.addEventListener("DOMContentLoaded", start);
    // boîtes de dialogue natives (non couvertes par le DOM)
    const c = window.confirm.bind(window), a = window.alert.bind(window);
    window.confirm = (m) => c(T(String(m))); window.alert = (m) => a(T(String(m)));
  }

  /* ------------------------------------------------------------------ bascule FR | EN dans l'en-tête */
  const mount = () => {
    const nav = document.querySelector(".nav"); if (!nav || document.getElementById("gm-lang")) return;
    const w = document.createElement("span"); w.id = "gm-lang"; w.setAttribute("data-notr", ""); w.style.cssText = "margin-left:10px;font-size:13px;white-space:nowrap";
    for (const l of ["fr", "en"]) {
      const b = document.createElement("button"); b.type = "button"; b.textContent = l.toUpperCase(); b.lang = l;
      b.setAttribute("aria-label", l === "fr" ? "Français" : "English"); b.setAttribute("aria-pressed", String(l === LANG));
      b.style.cssText = "border:0;background:none;padding:4px 6px;cursor:pointer;font:inherit;color:inherit;" + (l === LANG ? "font-weight:700;text-decoration:underline" : "opacity:.7");
      b.onclick = () => l !== LANG && setLang(l); w.append(b);
    }
    nav.append(w);
  };
  if (document.body) mount(); else document.addEventListener("DOMContentLoaded", mount);
})();

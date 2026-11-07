package app.gmeeting.core

import com.google.gson.JsonParser

/** Ce que l'application fait d'un contenu reçu par « Partager » depuis une autre application. */
sealed class ShareAction {
    /** Lien (YouTube, Teams, Zoom…) → nouvelle réunion. */
    data class MeetingFromLink(val url: String) : ShareAction()
    /** Fichier audio/vidéo → nouvelle réunion ; les autres fichiers reçus en même temps deviennent ses pièces jointes. */
    data class MeetingFromAudio(val audioIndex: Int, val attachmentIndexes: List<Int>) : ShareAction()
    /** Documents (mail Outlook, Word, Excel, PDF…) → pièces jointes d'une réunion à créer dans l'application. */
    data class Attachments(val indexes: List<Int>) : ShareAction()
    object Unsupported : ShareAction()
}

object ShareRouting {
    private val URL = Regex("""https://[^\s<>"']+""", RegexOption.IGNORE_CASE)
    private val AUDIO_EXT = setOf("m4a", "mp3", "wav", "ogg", "opus", "aac", "flac", "mp4", "webm", "mkv", "mov", "3gp", "amr")

    /** Premier lien HTTPS d'un texte partagé (« Titre\nhttps://youtu.be/x » → l'URL), sans la ponctuation finale. */
    fun extractUrl(text: String?): String? =
        text?.let { URL.find(it)?.value?.trimEnd('.', ',', ';', ')', ']', '!', '?') }

    fun isAudioOrVideo(mime: String?, fileName: String?): Boolean {
        val m = mime?.lowercase().orEmpty()
        if (m.startsWith("audio/") || m.startsWith("video/")) return true
        val ext = fileName?.substringAfterLast('.', "")?.lowercase().orEmpty()
        return (m.isEmpty() || m == "application/octet-stream") && ext in AUDIO_EXT
    }

    /**
     * @param mimes types des fichiers reçus (dans l'ordre), @param names leurs noms, @param text texte partagé éventuel.
     * Priorité : un fichier audio/vidéo crée la réunion ; sinon un lien ; sinon les documents deviennent des pièces jointes.
     */
    fun classify(mimes: List<String?>, names: List<String?>, text: String?): ShareAction {
        val audio = mimes.indices.firstOrNull { isAudioOrVideo(mimes[it], names.getOrNull(it)) }
        if (audio != null) return ShareAction.MeetingFromAudio(audio, mimes.indices.filter { it != audio })
        extractUrl(text)?.let { return ShareAction.MeetingFromLink(it) }
        if (mimes.isNotEmpty()) return ShareAction.Attachments(mimes.indices.toList())
        return ShareAction.Unsupported
    }
}

/** Messages du pont JavaScript ↔ application : lus de façon défensive (la page web est une entrée non fiable). */
object BridgeJson {
    data class Finish(val meta: Map<String, String>, val attachmentIds: List<String>)

    private val ID = Regex("[0-9a-f]{12}")

    fun parseMeta(json: String?): Map<String, String> = try {
        val o = JsonParser.parseString(json.orEmpty()).asJsonObject
        GMeetingApi.META_KEYS.mapNotNull { k ->
            val v = o.get(k)
            if (v != null && v.isJsonPrimitive) k to v.asString.trim().take(if (k == "context" || k == "participants") 8000 else 300) else null
        }.filter { it.second.isNotEmpty() }.toMap()
    } catch (e: Exception) { emptyMap() }

    fun parseFinish(json: String?): Finish = try {
        val o = JsonParser.parseString(json.orEmpty()).asJsonObject
        val ids = o.getAsJsonArray("attachment_ids")?.mapNotNull { it.asString }?.filter { ID.matches(it) }?.take(20).orEmpty()
        Finish(parseMeta(o.get("meta")?.toString()), ids)
    } catch (e: Exception) { Finish(emptyMap(), emptyList()) }

    /** Profil de qualité demandé par la page → débit AAC en kbps (seulement des valeurs prévues). */
    fun kbps(requested: Int): Int = when { requested <= 24 -> 24; requested >= 64 -> 64; else -> 32 }
}

package app.gmeeting.core

import com.google.gson.Gson
import com.google.gson.JsonParser
import com.google.gson.annotations.SerializedName
import okhttp3.Credentials
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import java.io.File
import java.io.IOException
import java.net.URI
import java.util.concurrent.TimeUnit

/** Connexion au serveur GMeeting de l'utilisateur (auto-hébergé : chaque utilisateur a sa propre adresse). */
data class ServerConfig(val baseUrl: String, val password: String, val user: String = "gmeeting") {
    val root: String get() = baseUrl.trim().trimEnd('/')
    fun authHeader(): String = Credentials.basic(user, password, Charsets.UTF_8)

    companion object {
        /**
         * Normalise l'adresse saisie : « reunions.exemple.fr » → « https://reunions.exemple.fr ».
         * HTTPS est exigé (le mot de passe circule dans chaque requête) ; `allowHttp` sert aux tests et aux versions de débogage.
         * Retourne null si l'adresse est inutilisable.
         */
        fun normalizeUrl(raw: String, allowHttp: Boolean = false): String? {
            var s = raw.trim()
            if (s.isEmpty() || s.any { it.isWhitespace() }) return null
            if (!s.contains("://")) s = "https://$s"            // le schéma se cherche AVANT de retirer les « / » finaux
            s = s.trimEnd('/')
            val uri = try { URI(s) } catch (e: Exception) { return null }
            val scheme = uri.scheme?.lowercase() ?: return null
            if (scheme != "https" && !(allowHttp && scheme == "http")) return null
            val host = uri.host ?: return null
            // nom complet (avec un point), localhost ou IPv6 : « http », « test »… sont des fautes de frappe, pas des serveurs
            if (!HOST.matches(host) || !(host.contains('.') || host == "localhost" || host.startsWith("[")) || uri.userInfo != null || uri.rawQuery != null || uri.rawFragment != null || s.endsWith(":")) return null
            return s
        }

        private val HOST = Regex("[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?|\\[[0-9A-Fa-f:.]+\\]")
    }
}

/** Réponse du serveur en erreur (4xx/5xx) avec le message du serveur quand il existe. */
class ApiException(val code: Int, message: String) : Exception(message)

/** Le serveur refuse le mot de passe : l'utilisateur doit agir, inutile de réessayer en boucle. */
class UnauthorizedException : Exception("Mot de passe refusé par le serveur")

enum class RegisterResult { OK, OFFLINE }
enum class ChunkResult { OK, GONE, REJECTED }
enum class FinishResult { OK, ALREADY }

data class Interruption(val at: Int, val duration: Int? = null, val reason: String = "")

data class FinishPayload(
    val meta: Map<String, String> = emptyMap(),
    val markers: List<Int> = emptyList(),
    val interruptions: List<Interruption> = emptyList(),
    @SerializedName("attachment_ids") val attachmentIds: List<String> = emptyList(),
)

data class ServerInfo(val hasAnthropic: Boolean, val transcribeProvider: String, val model: String)

/**
 * Client de l'API GMeeting. Reprend EXACTEMENT le protocole de l'interface web (voir app/main.py) :
 *  - POST /api/recordings           (id et heure de début fournis par l'appareil : démarrage possible sans réseau)
 *  - PUT  /api/recordings/{id}/parts/{n}/chunks/{seq}   (idempotent : un segment renvoyé est écrasé)
 *  - POST /api/recordings/{id}/finish
 * Chaque segment d'enregistrement natif est un fichier audio complet : c'est une « partie » (part) d'un seul segment (seq 0).
 */
class GMeetingApi(private val cfg: ServerConfig, client: OkHttpClient? = null) {
    private val gson = Gson()
    private val http: OkHttpClient = client ?: OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS).readTimeout(60, TimeUnit.SECONDS).writeTimeout(120, TimeUnit.SECONDS)
        .build()

    private fun req(path: String) = Request.Builder().url(cfg.root + path).header("Authorization", cfg.authHeader())

    private fun detail(resp: Response): String {
        val body = try { resp.body?.string().orEmpty() } catch (e: IOException) { "" }
        return try {
            val d = JsonParser.parseString(body).asJsonObject.get("detail")
            if (d != null && d.isJsonPrimitive) d.asString else "HTTP ${resp.code}"
        } catch (e: Exception) { "HTTP ${resp.code}" }
    }

    /** Vérifie l'adresse ET le mot de passe (écran de configuration). Lève IOException si le serveur est injoignable. */
    fun checkServer(): ServerInfo {
        http.newCall(Request.Builder().url(cfg.root + "/healthz").build()).execute().use { r ->
            if (!r.isSuccessful) throw ApiException(r.code, "Ce serveur ne répond pas comme GMeeting (HTTP ${r.code})")
            val ok = try { JsonParser.parseString(r.body?.string().orEmpty()).asJsonObject.get("status")?.asString == "ok" } catch (e: Exception) { false }
            if (!ok) throw ApiException(r.code, "Ce serveur ne répond pas comme GMeeting")
        }
        http.newCall(req("/api/config").get().build()).execute().use { r ->
            if (r.code == 401) throw UnauthorizedException()
            if (!r.isSuccessful) throw ApiException(r.code, detail(r))
            val o = JsonParser.parseString(r.body?.string().orEmpty()).asJsonObject
            return ServerInfo(
                hasAnthropic = o.get("has_anthropic")?.asBoolean ?: false,
                transcribeProvider = o.get("transcribe_provider")?.asString ?: "",
                model = o.get("model")?.asString ?: "",
            )
        }
    }

    private data class RegisterBody(
        val id: String,
        @SerializedName("started_at") val startedAt: String,
        val title: String, @SerializedName("meeting_date") val meetingDate: String, val location: String,
        val participants: String, val context: String, val language: String,
        @SerializedName("report_lang") val reportLang: String,
    )

    /** Déclare la session. OFFLINE = serveur injoignable ou en erreur : à réessayer (l'enregistrement, lui, continue). */
    fun register(id: String, startedAtIso: String, meta: Map<String, String>): RegisterResult {
        val body = RegisterBody(id, startedAtIso, meta["title"].orEmpty(), meta["meeting_date"].orEmpty(), meta["location"].orEmpty(),
            meta["participants"].orEmpty(), meta["context"].orEmpty(), meta["language"].orEmpty(), meta["report_lang"].orEmpty())
        val r = req("/api/recordings").post(gson.toJson(body).toRequestBody(JSON)).build()
        try {
            http.newCall(r).execute().use { resp ->
                return when {
                    resp.code == 401 -> throw UnauthorizedException()
                    resp.isSuccessful -> RegisterResult.OK
                    resp.code >= 500 -> RegisterResult.OFFLINE
                    else -> throw ApiException(resp.code, detail(resp))
                }
            }
        } catch (e: IOException) {
            return RegisterResult.OFFLINE
        }
    }

    /** Envoie un segment. GONE : réunion déjà finalisée ou supprimée (inutile de renvoyer). REJECTED : segment invalide (vide, trop gros). */
    fun putChunk(id: String, part: Int, seq: Int, file: File): ChunkResult {
        val r = req("/api/recordings/$id/parts/$part/chunks/$seq").put(file.asRequestBody(OCTET)).build()
        http.newCall(r).execute().use { resp ->
            return when {
                resp.code == 401 -> throw UnauthorizedException()
                resp.isSuccessful -> ChunkResult.OK
                resp.code == 404 || resp.code == 409 -> ChunkResult.GONE
                resp.code == 422 -> ChunkResult.REJECTED
                else -> throw ApiException(resp.code, detail(resp))
            }
        }
    }

    /** Termine l'enregistrement et lance la transcription et la rédaction. ALREADY : déjà pris en charge par le serveur. */
    fun finish(id: String, payload: FinishPayload): FinishResult {
        val r = req("/api/recordings/$id/finish").post(gson.toJson(payload).toRequestBody(JSON)).build()
        http.newCall(r).execute().use { resp ->
            return when {
                resp.code == 401 -> throw UnauthorizedException()
                resp.isSuccessful -> FinishResult.OK
                resp.code == 409 -> FinishResult.ALREADY
                else -> throw ApiException(resp.code, detail(resp))
            }
        }
    }

    /** Supprime une réunion (enregistrement vide abandonné). */
    fun discard(id: String) {
        http.newCall(req("/api/meetings/$id").delete().build()).execute().use { resp ->
            if (resp.code == 401) throw UnauthorizedException()
        }
    }

    /** Dépose des pièces jointes en zone d'attente (partage depuis une autre application) : retourne leurs identifiants. */
    fun uploadAttachments(files: List<Pair<String, File>>): List<String> {
        val mp = MultipartBody.Builder().setType(MultipartBody.FORM)
        files.forEach { (name, f) -> mp.addFormDataPart("files", name, f.asRequestBody(OCTET)) }
        http.newCall(req("/api/attachments").post(mp.build()).build()).execute().use { resp ->
            if (resp.code == 401) throw UnauthorizedException()
            if (!resp.isSuccessful) throw ApiException(resp.code, detail(resp))
            val arr = JsonParser.parseString(resp.body?.string().orEmpty()).asJsonObject.getAsJsonArray("attachments")
            return arr.map { it.asJsonObject.get("id").asString }
        }
    }

    /** Crée une réunion à partir d'un fichier audio/vidéo reçu par partage. Retourne l'identifiant de la réunion. */
    fun createFromAudio(file: File, displayName: String, meta: Map<String, String>, attachmentIds: List<String>): String {
        val mp = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("file", displayName, file.asRequestBody(OCTET))
            .addFormDataPart("source_type", "upload")
            .addFormDataPart("attachment_ids", attachmentIds.joinToString(","))
        for (k in META_KEYS) mp.addFormDataPart(k, meta[k].orEmpty())
        return postForId("/api/meetings/audio", mp.build())
    }

    /** Crée une réunion à partir d'un lien (vidéo/audio de n'importe quelle source). */
    fun createFromUrl(url: String, meta: Map<String, String>, attachmentIds: List<String>): String {
        val body = mutableMapOf<String, Any>("url" to url, "attachment_ids" to attachmentIds)
        for (k in META_KEYS) body[k] = meta[k].orEmpty()
        return postForId("/api/meetings/url", gson.toJson(body).toRequestBody(JSON))
    }

    private fun postForId(path: String, body: RequestBody): String {
        http.newCall(req(path).post(body).build()).execute().use { resp ->
            if (resp.code == 401) throw UnauthorizedException()
            if (!resp.isSuccessful) throw ApiException(resp.code, detail(resp))
            return JsonParser.parseString(resp.body?.string().orEmpty()).asJsonObject.get("id").asString
        }
    }

    companion object {
        private val JSON = "application/json; charset=utf-8".toMediaType()
        private val OCTET = "application/octet-stream".toMediaType()
        val META_KEYS = listOf("title", "meeting_date", "location", "participants", "context", "language", "report_lang")
    }
}

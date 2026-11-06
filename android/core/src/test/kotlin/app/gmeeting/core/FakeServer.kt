package app.gmeeting.core

import com.google.gson.JsonParser
import okhttp3.Credentials
import okhttp3.mockwebserver.Dispatcher
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.RecordedRequest
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.CopyOnWriteArrayList

/**
 * Faux serveur GMeeting qui reproduit le contrat de l'API réelle (app/main.py), tel que vérifié par ses propres tests :
 * authentification Basic, 404 réunion inconnue, 409 réunion plus en enregistrement, 422 segment vide, idempotence de l'enregistrement.
 * Le test d'intégration (IntegrationTest) confronte ensuite ce modèle au VRAI serveur.
 */
class FakeServer(var password: String = "secret") : Dispatcher() {
    val log = CopyOnWriteArrayList<String>()
    val chunks = ConcurrentHashMap<String, MutableList<String>>()      // id -> « part/seq:taille »
    val status = ConcurrentHashMap<String, String>()                   // id -> recording | queued
    val registered = CopyOnWriteArrayList<String>()                    // corps JSON des enregistrements
    val finished = CopyOnWriteArrayList<String>()                      // corps JSON des finalisations
    val failNextChunks = ArrayDeque<Int>()                             // codes HTTP à renvoyer avant de réussir
    @Volatile var forceRegister: Int? = null

    private fun json(code: Int, body: String) = MockResponse().setResponseCode(code).setHeader("Content-Type", "application/json").setBody(body)
    private fun err(code: Int, detail: String) = json(code, """{"detail":"$detail"}""")

    override fun dispatch(request: RecordedRequest): MockResponse {
        val path = request.path ?: ""
        log += "${request.method} $path"
        if (path != "/healthz" && request.getHeader("Authorization") != Credentials.basic("gmeeting", password, Charsets.UTF_8))
            return err(401, "Authentification requise")
        val chunk = Regex("/api/recordings/([0-9a-f]{12})/parts/(\\d+)/chunks/(\\d+)").matchEntire(path)
        val finish = Regex("/api/recordings/([0-9a-f]{12})/finish").matchEntire(path)
        return when {
            path == "/healthz" -> json(200, """{"status":"ok","ffmpeg":true}""")
            path == "/api/config" -> json(200, """{"transcribe_provider":"openai","has_anthropic":true,"model":"m"}""")
            request.method == "POST" && path == "/api/recordings" -> {
                val body = request.body.readUtf8(); registered += body
                forceRegister?.let { return err(it, "refus simulé") }
                val id = JsonParser.parseString(body).asJsonObject.get("id").asString
                if (status[id] != null && status[id] != "recording") err(409, "Identifiant déjà utilisé")
                else { status.putIfAbsent(id, "recording"); chunks.putIfAbsent(id, CopyOnWriteArrayList()); json(200, """{"id":"$id"}""") }
            }
            request.method == "PUT" && chunk != null -> {
                val (id, part, seq) = chunk.destructured
                val data = request.body.readByteArray()
                synchronized(failNextChunks) { if (failNextChunks.isNotEmpty()) return err(failNextChunks.removeFirst(), "panne simulée") }
                when {
                    status[id] == null -> err(404, "Réunion introuvable")
                    status[id] != "recording" -> err(409, "Cet enregistrement n'accepte plus de segments")
                    data.isEmpty() -> err(422, "Segment vide ou trop volumineux")
                    else -> { chunks[id]!!.add("$part/$seq:${data.size}"); json(200, """{"ok":true}""") }
                }
            }
            request.method == "POST" && finish != null -> {
                val id = finish.groupValues[1]; finished += request.body.readUtf8()
                when {
                    status[id] == null -> err(404, "Réunion introuvable")
                    status[id] != "recording" -> err(409, "Enregistrement déjà en cours de traitement ou terminé")
                    chunks[id].isNullOrEmpty() -> err(409, "Aucun audio reçu pour cet enregistrement")
                    else -> { status[id] = "queued"; json(200, """{"id":"$id"}""") }
                }
            }
            request.method == "DELETE" && path.startsWith("/api/meetings/") -> { status.remove(path.substringAfterLast('/')); json(200, """{"ok":true}""") }
            else -> err(404, "inconnu")
        }
    }
}

package app.gmeeting.core

import com.google.gson.JsonParser
import okhttp3.Credentials
import okhttp3.OkHttpClient
import okhttp3.Request
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable
import org.junit.jupiter.api.io.TempDir
import java.io.File
import java.time.Instant
import java.time.LocalDateTime
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

/**
 * Le VRAI client contre le VRAI serveur GMeeting (Python/FastAPI) : confronte le modèle utilisé par les autres tests à la réalité.
 * Activé par GMEETING_URL (et GMEETING_PASSWORD). Lancer d'abord :
 *   PORT=8795 GMEETING_PASSWORD=secret python tests/e2e/run_stub.py
 *   GMEETING_URL=http://127.0.0.1:8795 GMEETING_PASSWORD=secret gradle :core:test
 * (le serveur de test simule seulement la transcription et la rédaction ; assemblage audio, base et API sont réels)
 */
@EnabledIfEnvironmentVariable(named = "GMEETING_URL", matches = ".+")
class IntegrationTest {
    @TempDir lateinit var tmp: File
    private val url = System.getenv("GMEETING_URL")
    private val pw = System.getenv("GMEETING_PASSWORD") ?: "secret"
    private val cfg = ServerConfig(url, pw)
    private val api = GMeetingApi(cfg)
    private val http = OkHttpClient()

    private fun meeting(id: String): com.google.gson.JsonObject =
        http.newCall(Request.Builder().url("$url/api/meetings/$id").header("Authorization", Credentials.basic("x", pw)).build()).execute().use {
            JsonParser.parseString(it.body!!.string()).asJsonObject
        }

    private fun waitDone(id: String): com.google.gson.JsonObject {
        repeat(60) { val m = meeting(id); if (m["status"].asString in listOf("done", "error")) return m; Thread.sleep(500) }
        error("traitement non terminé")
    }

    private fun tone(): File = File(tmp, "tone.m4a").also { f -> javaClass.getResourceAsStream("/tone.m4a")!!.use { i -> f.outputStream().use { o -> i.copyTo(o) } } }

    private fun segmentsOf(store: SessionStore, id: String, n: Int) {
        repeat(n) { val (i, f) = store.allocateSegment(id); tone().copyTo(f, overwrite = true); store.commitSegment(id, i, f) }
    }

    @Test fun `le serveur reel repond comme attendu a la verification de l'ecran de configuration`() {
        assertTrue(api.checkServer().transcribeProvider.isNotEmpty())
        assertFailsWith<UnauthorizedException> { GMeetingApi(ServerConfig(url, "mauvais")).checkServer() }
    }

    @Test fun `enregistrement natif complet contre le vrai serveur - demarre il y a une heure, hors-ligne puis rattrape`() {
        val store = SessionStore(File(tmp, "data"))
        val startedAt = Instant.now().minusSeconds(3600)
        val s = store.create(mapOf("title" to "Réunion native", "language" to "fr", "report_lang" to "en"), now = startedAt)
        segmentsOf(store, s.id, 2)
        // 1) pas de réseau : rien n'est perdu
        assertTrue(Uploader(store, GMeetingApi(ServerConfig("http://127.0.0.1:1", pw))).drain(s.id) is DrainResult.Retry)
        // 2) pièce jointe déposée en zone d'attente, puis fin de l'enregistrement avec repères et interruption
        val att = api.uploadAttachments(listOf("ordre.m4a" to tone())).single()
        store.update(s.id) { it.copy(finishRequested = true, markers = listOf(1), attachmentIds = listOf(att),
            interruptions = listOf(Interruption(0, 7, "appel téléphonique"))) }
        // 3) le réseau revient
        val r = Uploader(store, api).drain(s.id)
        assertEquals(DrainResult.Done(listOf(s.id)), r)
        val m = waitDone(s.id)
        assertEquals("done", m["status"].asString, m["error"]?.toString())
        assertEquals("Réunion native", m["title"].asString)
        assertEquals("en", m["report_lang"].asString, "la langue du rapport choisie sur le téléphone arrive jusqu'au serveur")
        assertEquals("en", m["analysis"].asJsonObject["_lang"].asString)
        assertTrue(m["duration"].asDouble in 1.5..3.5, "durée ${m["duration"]} : deux segments de 1 s assemblés")
        val ctx = m["context"].asString
        assertTrue("Moments marqués" in ctx && "Interruptions techniques" in ctx && "appel téléphonique" in ctx, ctx)
        val created = LocalDateTime.parse(m["created_at"].asString)                      // heure locale du serveur (même machine)
        assertTrue(created.isBefore(LocalDateTime.now().minusMinutes(50)), "la réunion garde son heure de début réelle : $created")
        assertEquals(1, http.newCall(Request.Builder().url("$url/api/meetings/${s.id}/attachments").header("Authorization", Credentials.basic("x", pw)).build())
            .execute().use { JsonParser.parseString(it.body!!.string()).asJsonArray.size() })
    }

    @Test fun `segment envoye apres la finalisation et reunion supprimee - le vrai serveur repond comme le modele`() {
        val store = SessionStore(File(tmp, "data2"))
        val s = store.create(mapOf("title" to "x")); segmentsOf(store, s.id, 1)
        store.update(s.id) { it.copy(finishRequested = true) }
        assertTrue(Uploader(store, api).drain(s.id) is DrainResult.Done)
        assertEquals(ChunkResult.GONE, api.putChunk(s.id, 9, 0, tone()))                      // 409 : déjà finalisée
        assertEquals(ChunkResult.GONE, api.putChunk("0123456789ab", 0, 0, tone()))            // 404 : inconnue
        assertEquals(FinishResult.ALREADY, api.finish(s.id, FinishPayload()))                // 409
        val empty = File(tmp, "vide.m4a").apply { writeBytes(ByteArray(0)) }
        val fresh = store.create(emptyMap()); assertEquals(RegisterResult.OK, api.register(fresh.id, fresh.startedAt, emptyMap()))
        assertEquals(ChunkResult.REJECTED, api.putChunk(fresh.id, 0, 0, empty))               // 422 : segment vide
        assertEquals(RegisterResult.OK, api.register(fresh.id, fresh.startedAt, emptyMap())) // idempotent
        api.discard(fresh.id)
    }

    @Test fun `enregistrement vide termine - aucune reunion fantome sur le vrai serveur`() {
        val store = SessionStore(File(tmp, "data3"))
        val s = store.create(mapOf("title" to "fantôme")); store.update(s.id) { it.copy(finishRequested = true) }
        assertTrue(Uploader(store, api).drain(s.id) is DrainResult.Done)
        val code = http.newCall(Request.Builder().url("$url/api/meetings/${s.id}").header("Authorization", Credentials.basic("x", pw)).build()).execute().use { it.code }
        assertEquals(404, code)
    }

    @Test fun `partage d'un fichier audio et d'un lien cree bien une reunion sur le vrai serveur`() {
        val att = api.uploadAttachments(listOf("convocation.m4a" to tone())).single()
        val id = api.createFromAudio(tone(), "reunion.m4a", mapOf("title" to "Partagée"), listOf(att))
        val m = waitDone(id)
        assertEquals("Partagée", m["title"].asString)
        assertTrue(m["status"].asString in listOf("done", "error"))
    }
}

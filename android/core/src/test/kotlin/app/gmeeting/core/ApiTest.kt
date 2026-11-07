package app.gmeeting.core

import com.google.gson.JsonParser
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.jupiter.api.AfterEach
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import java.io.File
import java.io.IOException
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class ApiTest {
    private lateinit var server: MockWebServer
    private lateinit var api: GMeetingApi
    private val cfg get() = ServerConfig(server.url("/").toString(), "secret")

    @BeforeEach fun up() { server = MockWebServer(); server.start(); api = GMeetingApi(cfg) }
    @AfterEach fun down() { runCatching { server.shutdown() } }

    // ------------------------------------------------------------------ adresse du serveur
    @Test fun `l'adresse saisie est normalisee et HTTPS est exige`() {
        assertEquals("https://reunions.exemple.fr", ServerConfig.normalizeUrl("reunions.exemple.fr"))
        assertEquals("https://reunions.exemple.fr", ServerConfig.normalizeUrl("  https://reunions.exemple.fr/  "))
        assertEquals("https://x.fr:8443", ServerConfig.normalizeUrl("x.fr:8443"))
        assertNull(ServerConfig.normalizeUrl("http://reunions.exemple.fr"))               // le mot de passe circule à chaque requête
        assertEquals("http://localhost:8000", ServerConfig.normalizeUrl("http://localhost:8000", allowHttp = true))
        for (bad in listOf("", "   ", "ftp://x.fr", "https://", "https:", "https://https:", "http", "https://:8443", "https://-x.fr", "https://u:p@x.fr", "https://x.fr?a=1", "https://x fr", "javascript:alert(1)"))
            assertNull(ServerConfig.normalizeUrl(bad), bad)
    }

    // ------------------------------------------------------------------ déclaration de la session
    @Test fun `register envoie l'identifiant, l'heure de debut et les metadonnees avec l'authentification`() {
        server.enqueue(MockResponse().setBody("""{"id":"abcdef012345"}"""))
        assertEquals(RegisterResult.OK, api.register("abcdef012345", "2026-11-06T04:00:00Z", mapOf("title" to "COPIL", "language" to "fr", "report_lang" to "en")))
        val r = server.takeRequest()
        assertEquals("POST", r.method); assertEquals("/api/recordings", r.path)
        assertTrue(r.getHeader("Authorization")!!.startsWith("Basic "))
        val b = JsonParser.parseString(r.body.readUtf8()).asJsonObject
        assertEquals("abcdef012345", b["id"].asString); assertEquals("2026-11-06T04:00:00Z", b["started_at"].asString)
        assertEquals("COPIL", b["title"].asString); assertEquals("fr", b["language"].asString); assertEquals("", b["location"].asString)
        assertEquals("en", b["report_lang"].asString)      // langue des documents : transmise au serveur
    }

    @Test fun `register hors-ligne ou serveur en panne donne OFFLINE sans exception`() {
        server.enqueue(MockResponse().setResponseCode(503))
        assertEquals(RegisterResult.OFFLINE, api.register("abcdef012345", "2026-11-06T04:00:00Z", emptyMap()))
        val closed = GMeetingApi(ServerConfig("http://127.0.0.1:1", "x"))                  // port fermé : connexion refusée
        assertEquals(RegisterResult.OFFLINE, closed.register("abcdef012345", "2026-11-06T04:00:00Z", emptyMap()))
    }

    @Test fun `register refuse proprement un mot de passe errone ou un identifiant invalide`() {
        server.enqueue(MockResponse().setResponseCode(401))
        assertFailsWith<UnauthorizedException> { api.register("abcdef012345", "x", emptyMap()) }
        server.enqueue(MockResponse().setResponseCode(422).setBody("""{"detail":"Identifiant invalide"}"""))
        val e = assertFailsWith<ApiException> { api.register("zz", "x", emptyMap()) }
        assertEquals(422, e.code); assertEquals("Identifiant invalide", e.message)
    }

    // ------------------------------------------------------------------ segments
    @Test fun `putChunk envoie le fichier brut sur la bonne route et gere les statuts du serveur`() {
        val f = File.createTempFile("seg", ".m4a").apply { writeBytes(byteArrayOf(1, 2, 3, 4)); deleteOnExit() }
        server.enqueue(MockResponse().setBody("""{"ok":true}"""))
        assertEquals(ChunkResult.OK, api.putChunk("abcdef012345", 3, 0, f))
        val r = server.takeRequest()
        assertEquals("PUT", r.method); assertEquals("/api/recordings/abcdef012345/parts/3/chunks/0", r.path)
        assertEquals(listOf<Byte>(1, 2, 3, 4), r.body.readByteArray().toList())
        assertEquals("application/octet-stream", r.getHeader("Content-Type"))
        server.enqueue(MockResponse().setResponseCode(409)); assertEquals(ChunkResult.GONE, api.putChunk("abcdef012345", 0, 0, f))
        server.enqueue(MockResponse().setResponseCode(404)); assertEquals(ChunkResult.GONE, api.putChunk("abcdef012345", 0, 0, f))
        server.enqueue(MockResponse().setResponseCode(422)); assertEquals(ChunkResult.REJECTED, api.putChunk("abcdef012345", 0, 0, f))
        server.enqueue(MockResponse().setResponseCode(500)); assertEquals(500, assertFailsWith<ApiException> { api.putChunk("abcdef012345", 0, 0, f) }.code)
        server.enqueue(MockResponse().setResponseCode(401)); assertFailsWith<UnauthorizedException> { api.putChunk("abcdef012345", 0, 0, f) }
    }

    @Test fun `finish transmet reperes, interruptions et pieces jointes`() {
        server.enqueue(MockResponse().setBody("""{"id":"abcdef012345"}"""))
        val p = FinishPayload(mapOf("title" to "T"), listOf(75, 5), listOf(Interruption(3, 12, "appel")), listOf("aaaaaaaaaaaa"))
        assertEquals(FinishResult.OK, api.finish("abcdef012345", p))
        val r = server.takeRequest(); assertEquals("/api/recordings/abcdef012345/finish", r.path)
        val b = JsonParser.parseString(r.body.readUtf8()).asJsonObject
        assertEquals("T", b["meta"].asJsonObject["title"].asString); assertEquals(75, b["markers"].asJsonArray[0].asInt)
        assertEquals(3, b["interruptions"].asJsonArray[0].asJsonObject["at"].asInt)
        assertEquals("aaaaaaaaaaaa", b["attachment_ids"].asJsonArray[0].asString)               // clé exacte attendue par le serveur
        server.enqueue(MockResponse().setResponseCode(409)); assertEquals(FinishResult.ALREADY, api.finish("abcdef012345", p))
    }

    // ------------------------------------------------------------------ vérification du serveur (écran de configuration)
    @Test fun `checkServer valide l'adresse puis le mot de passe`() {
        server.enqueue(MockResponse().setBody("""{"status":"ok","ffmpeg":true}"""))
        server.enqueue(MockResponse().setBody("""{"transcribe_provider":"openai","has_anthropic":true,"model":"claude"}"""))
        val info = api.checkServer()
        assertTrue(info.hasAnthropic); assertEquals("claude", info.model)
        assertNull(server.takeRequest().getHeader("Authorization"))                        // /healthz n'exige pas de mot de passe
        assertNotNull(server.takeRequest().getHeader("Authorization"))
    }

    @Test fun `checkServer distingue mauvais mot de passe, serveur etranger et serveur injoignable`() {
        server.enqueue(MockResponse().setBody("""{"status":"ok"}""")); server.enqueue(MockResponse().setResponseCode(401))
        assertFailsWith<UnauthorizedException> { api.checkServer() }
        server.enqueue(MockResponse().setBody("<html>autre site</html>"))
        assertFailsWith<ApiException> { api.checkServer() }
        assertFailsWith<IOException> { GMeetingApi(ServerConfig("http://127.0.0.1:1", "x")).checkServer() }
    }

    // ------------------------------------------------------------------ partage depuis une autre application
    @Test fun `pieces jointes et creation de reunion par partage utilisent les routes et champs du serveur`() {
        val f = File.createTempFile("pjx", ".eml").apply { writeText("From: x"); deleteOnExit() }
        server.enqueue(MockResponse().setBody("""{"attachments":[{"id":"aaaaaaaaaaaa"},{"id":"bbbbbbbbbbbb"}],"errors":[]}"""))
        assertEquals(listOf("aaaaaaaaaaaa", "bbbbbbbbbbbb"), api.uploadAttachments(listOf("ordre.eml" to f, "b.eml" to f)))
        val up = server.takeRequest(); assertEquals("/api/attachments", up.path)
        val text = up.body.readUtf8(); assertTrue(text.contains("name=\"files\"") && text.contains("filename=\"ordre.eml\""))
        server.enqueue(MockResponse().setBody("""{"id":"cccccccccccc"}"""))
        assertEquals("cccccccccccc", api.createFromAudio(f, "reunion.m4a", mapOf("title" to "T"), listOf("aaaaaaaaaaaa", "bbbbbbbbbbbb")))
        val au = server.takeRequest().body.readUtf8()
        assertTrue(au.contains("name=\"attachment_ids\"") && au.contains("aaaaaaaaaaaa,bbbbbbbbbbbb") && au.contains("name=\"file\""))
        server.enqueue(MockResponse().setBody("""{"id":"dddddddddddd"}"""))
        assertEquals("dddddddddddd", api.createFromUrl("https://youtu.be/x", emptyMap(), listOf("aaaaaaaaaaaa")))
        val u = JsonParser.parseString(server.takeRequest().also { assertEquals("/api/meetings/url", it.path) }.body.readUtf8()).asJsonObject
        assertEquals("https://youtu.be/x", u["url"].asString); assertEquals("aaaaaaaaaaaa", u["attachment_ids"].asJsonArray[0].asString)
    }
}

package app.gmeeting.core

import com.google.gson.JsonParser
import okhttp3.mockwebserver.MockWebServer
import org.junit.jupiter.api.AfterEach
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.io.File
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class UploaderTest {
    @TempDir lateinit var tmp: File
    private lateinit var ws: MockWebServer
    private lateinit var fake: FakeServer
    private lateinit var store: SessionStore

    @BeforeEach fun up() {
        fake = FakeServer(); ws = MockWebServer().apply { dispatcher = fake; start() }
        store = SessionStore(tmp)
    }
    @AfterEach fun down() { runCatching { ws.shutdown() } }

    private fun uploader(url: String = ws.url("/").toString(), pw: String = "secret", s: SessionStore = store) =
        Uploader(s, GMeetingApi(ServerConfig(url, pw)))

    /** Crée une session avec `n` segments fermés (fichiers réels), comme le ferait le service d'enregistrement. */
    private fun session(n: Int, finish: Boolean = false, meta: Map<String, String> = mapOf("title" to "COPIL")): SessionState {
        var s = store.create(meta)
        repeat(n) { val (i, f) = store.allocateSegment(s.id); f.writeBytes(ByteArray(100 + i) { it.toByte() }); s = store.commitSegment(s.id, i, f) }
        if (finish) s = store.update(s.id) { it.copy(finishRequested = true) }
        return s
    }

    private fun seq() = fake.log.filter { !it.endsWith("/healthz") }

    @Test fun `parcours nominal declaration, segments dans l'ordre, finalisation, nettoyage`() {
        val s = session(3, finish = true)
        val r = uploader().drain(s.id)
        assertEquals(DrainResult.Done(listOf(s.id)), r)
        assertEquals(listOf("POST /api/recordings",
            "PUT /api/recordings/${s.id}/parts/0/chunks/0", "PUT /api/recordings/${s.id}/parts/1/chunks/0", "PUT /api/recordings/${s.id}/parts/2/chunks/0",
            "POST /api/recordings/${s.id}/finish"), seq())
        assertEquals("queued", fake.status[s.id])                     // le serveur a lancé le traitement
        assertNull(store.load(s.id)); assertFalse(store.dir(s.id).exists())   // plus rien sur le téléphone
    }

    @Test fun `la finalisation n'est jamais demandee avant la fin de l'enregistrement`() {
        val s = session(2, finish = false)
        assertEquals(DrainResult.Idle, uploader().drain(s.id))
        assertTrue(seq().none { it.endsWith("/finish") })
        assertEquals(listOf("0/0:100", "1/0:101"), fake.chunks[s.id]?.toList())   // mais les segments partent au fil de l'eau
        store.update(s.id) { it.copy(finishRequested = true) }
        assertTrue(uploader().drain(s.id) is DrainResult.Done)
    }

    @Test fun `demarrage hors-ligne puis rattrapage la session garde son heure de debut`() {
        val s = session(2, finish = true)
        val offline = uploader(url = "http://127.0.0.1:1")           // pas de réseau (mode avion)
        assertEquals("serveur injoignable", (offline.drain(s.id) as DrainResult.Retry).reason)
        assertFalse(store.load(s.id)!!.registered)
        assertEquals(2, store.load(s.id)!!.segments.count { !it.uploaded })      // rien n'est perdu
        // « le réseau revient » (et l'application a pu être relancée entre-temps : nouveau SessionStore sur le même dossier)
        val r = uploader(s = SessionStore(tmp)).drain(s.id)
        assertTrue(r is DrainResult.Done)
        assertEquals(s.startedAt, JsonParser.parseString(fake.registered.single()).asJsonObject["started_at"].asString)
    }

    @Test fun `une panne en cours d'envoi ne renvoie pas ce qui est deja acquitte`() {
        val s = session(3, finish = true)
        fake.failNextChunks.addLast(500)                                   // le 1er PUT échoue
        assertTrue(uploader().drain(s.id) is DrainResult.Retry)
        assertEquals(3, store.load(s.id)!!.segments.count { !it.uploaded })
        assertTrue(uploader().drain(s.id) is DrainResult.Done)
        assertEquals(listOf("0/0:100", "1/0:101", "2/0:102"), fake.chunks[s.id]?.toList())   // chaque segment arrivé exactement une fois
    }

    @Test fun `panne au milieu - les segments deja envoyes ne repartent pas`() {
        val s = session(3, finish = true)
        val up = uploader()
        // 1er segment OK, 2e en panne (une seule fois)
        ws.dispatcher = object : okhttp3.mockwebserver.Dispatcher() {
            var n = 0
            override fun dispatch(request: okhttp3.mockwebserver.RecordedRequest): okhttp3.mockwebserver.MockResponse {
                if (request.method == "PUT" && request.path!!.contains("/parts/1/") && n++ == 0) return okhttp3.mockwebserver.MockResponse().setResponseCode(502)
                return fake.dispatch(request)
            }
        }
        assertTrue(up.drain(s.id) is DrainResult.Retry)
        assertEquals(listOf(true, false, false), store.load(s.id)!!.segments.sortedBy { it.index }.map { it.uploaded })
        assertTrue(up.drain(s.id) is DrainResult.Done)
        assertEquals(1, fake.log.count { it.endsWith("/parts/0/chunks/0") })      // le segment 0 n'a été envoyé qu'une seule fois
        assertEquals(listOf("0/0:100", "1/0:101", "2/0:102"), fake.chunks[s.id]?.toList())
    }

    @Test fun `reunion deja finalisee ou supprimee cote serveur - on cesse d'envoyer sans bloquer`() {
        val s = session(2, finish = false)
        uploader().drain(s.id)
        fake.status[s.id] = "queued"                                        // finalisée depuis un autre appareil
        val (i, f) = store.allocateSegment(s.id); f.writeBytes(ByteArray(10)); store.commitSegment(s.id, i, f)
        assertEquals(DrainResult.Idle, uploader().drain(s.id))              // 409 → GONE : fichier supprimé, marqué envoyé
        assertTrue(store.load(s.id)!!.segments.all { it.uploaded } && !f.exists())
    }

    @Test fun `mauvais mot de passe - arret net, aucune donnee supprimee`() {
        val s = session(2, finish = true)
        val r = uploader(pw = "mauvais").drain(s.id)
        assertTrue(r is DrainResult.AuthFailed)
        assertEquals(2, store.load(s.id)!!.segments.count { !it.uploaded })
        assertTrue(store.dir(s.id).listFiles()!!.any { it.name.startsWith("seg_") })
        assertTrue(uploader().drain(s.id) is DrainResult.Done)               // une fois reconnecté, tout part
    }

    @Test fun `refus definitif du serveur - session marquee en echec et non retentee en boucle`() {
        val s = session(1, finish = true); fake.forceRegister = 409
        assertTrue(uploader().drain(s.id) is DrainResult.Failed)
        assertNotNull(store.load(s.id)!!.failedReason)
        fake.log.clear()
        assertEquals(DrainResult.Idle, uploader().drainAll())                // drainAll ignore les sessions en échec
        assertTrue(fake.log.isEmpty())
    }

    @Test fun `enregistrement vide - aucune reunion fantome sur le serveur`() {
        val s = session(0, finish = true)
        assertTrue(uploader().drain(s.id) is DrainResult.Done)
        assertEquals(listOf("POST /api/recordings", "DELETE /api/meetings/${s.id}"), seq())
        assertNull(store.load(s.id))
    }

    @Test fun `la finalisation porte metadonnees, reperes, interruptions et pieces jointes`() {
        var s = session(1, meta = mapOf("title" to "Brouillon"))
        s = store.update(s.id) { it.copy(finishRequested = true, meta = mapOf("title" to "Titre final", "language" to "fr"),
            markers = listOf(75, 5), interruptions = listOf(Interruption(3, 12, "appel")), attachmentIds = listOf("aaaaaaaaaaaa")) }
        uploader().drain(s.id)
        val b = JsonParser.parseString(fake.finished.single()).asJsonObject
        assertEquals("Titre final", b["meta"].asJsonObject["title"].asString)
        assertEquals(listOf(75, 5), b["markers"].asJsonArray.map { it.asInt })
        assertEquals("appel", b["interruptions"].asJsonArray[0].asJsonObject["reason"].asString)
        assertEquals("aaaaaaaaaaaa", b["attachment_ids"].asJsonArray[0].asString)
    }

    @Test fun `drainAll traite plusieurs sessions et remonte le reseau absent`() {
        val a = session(1, finish = true); val b = session(1, finish = true)
        val r = uploader().drainAll()
        assertEquals(DrainResult.Done(listOf(a.id, b.id)), r)
        val c = session(1, finish = true)
        assertTrue(uploader(url = "http://127.0.0.1:1").drainAll() is DrainResult.Retry)
        assertNotNull(store.load(c.id))
    }

    @Test fun `un fichier de session corrompu est ecarte sans bloquer les autres`() {
        val good = session(1, finish = true); val bad = session(1, finish = true)
        File(store.dir(bad.id), "session.json").writeText("{ pas du json")
        assertEquals(DrainResult.Done(listOf(good.id)), uploader().drainAll())
        assertTrue(File(store.dir(bad.id), "session.json.corrupt").exists())
    }

    @Test fun `la persistance survit a un redemarrage et reserve les segments sans collision`() {
        val s = store.create(mapOf("title" to "x"))
        val (i0, f0) = store.allocateSegment(s.id); val (i1, f1) = store.allocateSegment(s.id)
        assertEquals(listOf(0, 1), listOf(i0, i1)); assertTrue(f0.name != f1.name)
        val reopened = SessionStore(tmp)                                  // « l'application a été tuée puis relancée »
        assertEquals(2, reopened.load(s.id)!!.nextIndex)
        assertEquals(listOf(s.id), reopened.list().map { it.id })
        assertTrue(Regex("[0-9a-f]{12}").matches(s.id))
    }
}

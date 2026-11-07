package app.gmeeting.core

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

class ShareRoutingTest {
    @Test fun `extrait le lien d'un texte partage par YouTube, Teams ou un navigateur`() {
        assertEquals("https://youtu.be/abc123", ShareRouting.extractUrl("Réunion COPIL\nhttps://youtu.be/abc123"))
        assertEquals("https://teams.microsoft.com/l/meetup-join/x?y=1", ShareRouting.extractUrl("Rejoindre : https://teams.microsoft.com/l/meetup-join/x?y=1."))
        assertEquals("https://x.fr/a", ShareRouting.extractUrl("(voir https://x.fr/a)"))
        assertNull(ShareRouting.extractUrl("pas de lien ici")); assertNull(ShareRouting.extractUrl(null))
        assertNull(ShareRouting.extractUrl("http://non-securise.fr/x"))                      // seuls les liens HTTPS sont acceptés
    }

    @Test fun `reconnait l'audio et la video par le type ou, a defaut, par l'extension`() {
        assertTrue(ShareRouting.isAudioOrVideo("audio/mp4", null)); assertTrue(ShareRouting.isAudioOrVideo("video/mp4", "x.mp4"))
        assertTrue(ShareRouting.isAudioOrVideo(null, "enregistrement.M4A")); assertTrue(ShareRouting.isAudioOrVideo("application/octet-stream", "r.opus"))
        assertTrue(!ShareRouting.isAudioOrVideo("application/pdf", "audio.pdf")); assertTrue(!ShareRouting.isAudioOrVideo("message/rfc822", "a.eml"))
    }

    @Test fun `un audio cree la reunion et les autres fichiers deviennent ses pieces jointes`() {
        val r = ShareRouting.classify(listOf("application/pdf", "audio/mp4", "message/rfc822"), listOf("a.pdf", "r.m4a", "m.eml"), null)
        assertEquals(ShareAction.MeetingFromAudio(1, listOf(0, 2)), r)
    }

    @Test fun `un lien cree une reunion, des documents deviennent des pieces jointes, le reste est refuse`() {
        assertEquals(ShareAction.MeetingFromLink("https://youtu.be/x"), ShareRouting.classify(emptyList(), emptyList(), "Vidéo https://youtu.be/x"))
        assertEquals(ShareAction.Attachments(listOf(0, 1)), ShareRouting.classify(listOf("application/vnd.ms-outlook", "application/pdf"), listOf("o.msg", "p.pdf"), null))
        assertEquals(ShareAction.Unsupported, ShareRouting.classify(emptyList(), emptyList(), "juste du texte"))
    }

    @Test fun `le pont lit les metadonnees de facon defensive`() {
        val m = BridgeJson.parseMeta("""{"title":"  COPIL  ","language":"fr","report_lang":"en","inconnu":"x","location":"","context":123,"date":null}""")
        assertEquals(mapOf("title" to "COPIL", "language" to "fr", "report_lang" to "en", "context" to "123"), m)           // clés inconnues et valeurs vides écartées
        assertEquals(300, BridgeJson.parseMeta("""{"title":"${"x".repeat(1000)}"}""")["title"]!!.length)  // bornes de taille
        assertEquals(emptyMap(), BridgeJson.parseMeta("pas du json")); assertEquals(emptyMap(), BridgeJson.parseMeta(null)); assertEquals(emptyMap(), BridgeJson.parseMeta("[1,2]"))
    }

    @Test fun `le pont ne laisse passer que des identifiants de pieces jointes valides`() {
        val f = BridgeJson.parseFinish("""{"meta":{"title":"T"},"attachment_ids":["aaaaaaaaaaaa","../../etc","BBBBBBBBBBBB","bbbbbbbbbbbb"]}""")
        assertEquals(listOf("aaaaaaaaaaaa", "bbbbbbbbbbbb"), f.attachmentIds); assertEquals("T", f.meta["title"])
        assertEquals(BridgeJson.Finish(emptyMap(), emptyList()), BridgeJson.parseFinish("{{"))
        assertEquals(20, BridgeJson.parseFinish("""{"attachment_ids":[${(1..30).joinToString(",") { "\"%012x\"".format(it) }}]}""").attachmentIds.size)
    }

    @Test fun `le debit demande est ramene a un profil prevu`() {
        assertEquals(listOf(24, 24, 32, 32, 64, 64), listOf(8, 24, 32, 48, 64, 500).map { BridgeJson.kbps(it) })
    }
}

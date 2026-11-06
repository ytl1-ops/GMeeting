package app.gmeeting.core

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

class ClockTest {
    private var t = 0L
    private val clock = SessionClock { t }

    @Test fun `le temps ecoule exclut les pauses`() {
        clock.start(); t += 10_000; assertEquals(10, clock.elapsedSec())
        clock.pause(); t += 60_000; assertEquals(10, clock.elapsedSec())        // en pause : le temps ne court pas
        clock.resume(); t += 5_000; assertEquals(15, clock.elapsedSec())
        clock.stop(); t += 99_000; assertEquals(15, clock.elapsedSec())
    }

    @Test fun `une interruption est datee et mesuree, une seule a la fois`() {
        val log = InterruptionLog(clock) { t }
        clock.start(); t += 30_000
        assertTrue(log.begin("appel téléphonique")); assertFalse(log.begin("autre"))      // la 2e est ignorée
        t += 12_400
        val i = log.end()!!
        assertEquals(Interruption(30, 12, "appel téléphonique"), i)
        assertNull(log.end()); assertFalse(log.isOpen)
        assertEquals(listOf(i), log.items)
    }

    @Test fun `les delais de reprise croissent puis sont plafonnes`() {
        assertEquals(listOf(2000L, 4000L, 8000L, 16000L, 32000L, 60000L, 60000L), (0..6).map { Backoff.delayMs(it) })
        assertEquals(2000L, Backoff.delayMs(-3)); assertEquals(60000L, Backoff.delayMs(1000))
    }
}

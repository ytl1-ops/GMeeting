package app.gmeeting.core

/** Temps écoulé d'un enregistrement, pauses exclues : sert aux repères ⭐ et aux horodatages d'interruptions. */
class SessionClock(private val now: () -> Long = System::currentTimeMillis) {
    private var acc = 0L
    private var t0 = 0L
    var running = false
        private set

    fun start() { acc = 0; t0 = now(); running = true }
    fun pause() { if (running) { acc += now() - t0; running = false } }
    fun resume() { if (!running) { t0 = now(); running = true } }
    fun stop() { pause() }
    fun elapsedSec(): Int = ((acc + if (running) now() - t0 else 0L) / 1000).toInt()
}

/**
 * Journal des interruptions du micro (appel téléphonique, autre application qui prend le micro) : début, fin, durée.
 * Sur Android, le service continue et reprend seul à la fin de l'appel ; ce journal permet d'en informer la rédaction du compte rendu.
 */
class InterruptionLog(private val clock: SessionClock, private val now: () -> Long = System::currentTimeMillis) {
    private val done = mutableListOf<Interruption>()
    private var openAt = -1
    private var openT = 0L
    private var openReason = ""

    val isOpen: Boolean get() = openAt >= 0
    val items: List<Interruption> get() = done.toList()

    fun begin(reason: String): Boolean {
        if (isOpen) return false
        openAt = clock.elapsedSec(); openT = now(); openReason = reason.take(60)
        return true
    }

    fun end(): Interruption? {
        if (!isOpen) return null
        val i = Interruption(openAt, ((now() - openT) / 1000).toInt(), openReason)
        done += i; openAt = -1
        return i
    }
}

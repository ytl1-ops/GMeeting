package app.gmeeting.core

import com.google.gson.Gson
import com.google.gson.JsonSyntaxException
import java.io.File
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.security.SecureRandom
import java.time.Instant

/** Un segment d'enregistrement : un fichier audio complet, envoyé comme « partie » `index` (un seul morceau). */
data class Segment(val index: Int, val file: String, val uploaded: Boolean = false)

/**
 * État d'un enregistrement, écrit sur disque à chaque changement : si l'application est tuée (batterie, système, plantage),
 * l'enregistrement et sa file d'envoi se retrouvent tels quels au redémarrage. Rien n'est perdu tant que le fichier n'est pas acquitté.
 */
data class SessionState(
    val id: String,
    val startedAt: String,
    val meta: Map<String, String> = emptyMap(),
    val registered: Boolean = false,
    val finishRequested: Boolean = false,
    val finished: Boolean = false,
    val failedReason: String? = null,
    val markers: List<Int> = emptyList(),
    val interruptions: List<Interruption> = emptyList(),
    val attachmentIds: List<String> = emptyList(),
    val segments: List<Segment> = emptyList(),
    val nextIndex: Int = 0,
)

class SessionStore(private val root: File) {
    private val gson = Gson()
    private val lock = Any()

    init { File(root, "sessions").mkdirs() }

    private fun base() = File(root, "sessions")
    fun dir(id: String) = File(base(), id)
    private fun stateFile(id: String) = File(dir(id), "session.json")

    /** Crée une session (identifiant de 12 caractères hexadécimaux, comme l'attend le serveur). */
    fun create(meta: Map<String, String>, now: Instant = Instant.now(), id: String = newId()): SessionState {
        require(ID.matches(id)) { "identifiant invalide" }
        val s = SessionState(id = id, startedAt = now.toString(), meta = meta)
        synchronized(lock) { dir(id).mkdirs(); write(s) }
        return s
    }

    fun load(id: String): SessionState? = synchronized(lock) { read(id) }

    fun list(): List<SessionState> = synchronized(lock) {
        (base().listFiles { f -> f.isDirectory } ?: emptyArray()).mapNotNull { read(it.name) }.sortedBy { it.startedAt }
    }

    /** Modifie l'état de façon atomique (verrou + écriture temporaire puis renommage). */
    fun update(id: String, change: (SessionState) -> SessionState): SessionState = synchronized(lock) {
        val cur = read(id) ?: throw IllegalStateException("session inconnue : $id")
        change(cur).also { write(it) }
    }

    /** Réserve le fichier du prochain segment (le service y écrit), sans l'inscrire tant qu'il n'est pas fermé. */
    fun allocateSegment(id: String, extension: String = "m4a"): Pair<Int, File> = synchronized(lock) {
        val cur = read(id) ?: throw IllegalStateException("session inconnue : $id")
        write(cur.copy(nextIndex = cur.nextIndex + 1))
        cur.nextIndex to File(dir(id), "seg_%04d.%s".format(cur.nextIndex, extension))
    }

    /** Inscrit un segment fermé dans la file d'envoi. */
    fun commitSegment(id: String, index: Int, file: File): SessionState =
        update(id) { it.copy(segments = it.segments + Segment(index, file.name)) }

    fun delete(id: String) { synchronized(lock) { dir(id).deleteRecursively() } }

    private fun read(id: String): SessionState? {
        val f = stateFile(id)
        if (!f.exists()) return null
        return try { gson.fromJson(f.readText(), SessionState::class.java) }
        catch (e: JsonSyntaxException) {                       // fichier corrompu : on le met de côté au lieu de planter en boucle
            f.renameTo(File(f.parentFile, "session.json.corrupt")); null
        }
    }

    private fun write(s: SessionState) {
        val f = stateFile(s.id)
        val tmp = File(f.parentFile, "session.json.tmp")
        tmp.writeText(gson.toJson(s))
        Files.move(tmp.toPath(), f.toPath(), StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING)
    }

    companion object {
        private val ID = Regex("[0-9a-f]{12}")
        fun newId(): String { val b = ByteArray(6); SecureRandom().nextBytes(b); return b.joinToString("") { "%02x".format(it) } }
    }
}

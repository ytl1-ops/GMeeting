package app.gmeeting.core

import java.io.File
import java.io.IOException

sealed class DrainResult {
    /** Rien à faire. */
    object Idle : DrainResult()
    /** Tout est envoyé ; les sessions terminées ont été finalisées côté serveur (transcription lancée). */
    data class Done(val finished: List<String>) : DrainResult()
    /** Réseau ou serveur indisponible : réessayer plus tard (rien n'est perdu). */
    data class Retry(val reason: String) : DrainResult()
    /** Mot de passe refusé : l'utilisateur doit se reconnecter ; inutile de boucler. */
    data class AuthFailed(val reason: String) : DrainResult()
    /** Refus définitif du serveur pour une session (ex. identifiant déjà pris) : visible dans l'application. */
    data class Failed(val reason: String) : DrainResult()
}

/**
 * Envoie les enregistrements en attente. Mêmes garanties que l'interface web :
 *  - la session est déclarée au serveur au premier envoi possible (démarrage hors-ligne autorisé) ;
 *  - un segment n'est effacé du téléphone qu'une fois acquitté ; renvoyer un segment est sans danger (idempotent) ;
 *  - la finalisation n'est demandée qu'APRÈS l'envoi de tous les segments, dans l'ordre.
 */
class Uploader(private val store: SessionStore, private val api: GMeetingApi) {

    fun drainAll(): DrainResult {
        val finished = mutableListOf<String>()
        var retry: DrainResult.Retry? = null
        var anything = false
        for (s in store.list()) {
            if (s.failedReason != null) continue
            when (val r = drain(s.id)) {
                is DrainResult.AuthFailed -> return r                    // inutile d'insister sur les suivantes
                is DrainResult.Retry -> retry = retry ?: r
                is DrainResult.Done -> { finished += r.finished; anything = true }
                is DrainResult.Failed, DrainResult.Idle -> {}
            }
        }
        return retry ?: if (anything) DrainResult.Done(finished) else DrainResult.Idle
    }

    /** Un seul envoi à la fois dans toute l'application (service d'enregistrement ET travail en arrière-plan peuvent se déclencher ensemble). */
    fun drain(id: String): DrainResult = synchronized(LOCK) {
        try { drainLocked(id) } catch (e: IllegalStateException) { DrainResult.Idle }     // la session a été supprimée entre-temps (annulation)
    }

    private fun drainLocked(id: String): DrainResult {
        var s = store.load(id) ?: return DrainResult.Idle
        try {
            if (!s.registered) {
                when (api.register(s.id, s.startedAt, s.meta)) {
                    RegisterResult.OFFLINE -> return DrainResult.Retry("serveur injoignable")
                    RegisterResult.OK -> s = store.update(id) { it.copy(registered = true) }
                }
            }
            for (seg in s.segments.filter { !it.uploaded }.sortedBy { it.index }) {
                val f = File(store.dir(id), seg.file)
                if (f.exists() && f.length() > 0) {
                    api.putChunk(id, seg.index, 0, f)       // OK, GONE ou REJECTED : dans tous les cas il n'y a plus rien à renvoyer
                }
                f.delete()
                store.update(id) { st -> st.copy(segments = st.segments.map { if (it.index == seg.index) it.copy(uploaded = true) else it }) }
            }
            s = store.load(id) ?: return DrainResult.Idle
            if (s.finishRequested && s.segments.all { it.uploaded }) {
                if (s.segments.isEmpty()) api.discard(id)         // rien n'a été enregistré : on ne laisse pas une réunion vide sur le serveur
                else api.finish(id, FinishPayload(s.meta, s.markers, s.interruptions, s.attachmentIds))
                store.delete(id)
                return DrainResult.Done(listOf(id))
            }
            return DrainResult.Idle
        } catch (e: UnauthorizedException) {
            return DrainResult.AuthFailed(e.message ?: "authentification")
        } catch (e: IOException) {
            return DrainResult.Retry(e.message ?: "réseau")
        } catch (e: ApiException) {
            if (e.code >= 500) return DrainResult.Retry("erreur serveur ${e.code}")
            store.update(id) { it.copy(failedReason = "${e.code} : ${e.message}") }
            return DrainResult.Failed("${e.code} : ${e.message}")
        }
    }
}

private val LOCK = Any()

/** Délai avant la prochaine tentative : 2 s, 4 s, 8 s… plafonné à 60 s (identique à l'interface web). */
object Backoff {
    fun delayMs(attempt: Int): Long = minOf(2000L shl minOf(attempt.coerceAtLeast(0), 10), 60_000L)
}

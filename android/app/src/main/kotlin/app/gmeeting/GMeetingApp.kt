package app.gmeeting

import android.app.Application
import android.content.Context
import app.gmeeting.core.SessionStore

class GMeetingApp : Application() {
    lateinit var store: SessionStore
        private set
    lateinit var secure: SecureStore
        private set

    override fun onCreate() {
        super.onCreate()
        store = SessionStore(filesDir)
        secure = SecureStore(this)
        Notifications.createChannels(this)
        // Le processus vient de démarrer : aucun enregistrement n'est en cours. Une session jamais terminée est donc un enregistrement
        // interrompu brutalement (batterie, système) : on la termine pour que ce qui a été capté soit transcrit au lieu d'être perdu.
        Thread {
            LocalCopy.wipeStaging(this)
            runCatching { java.io.File(cacheDir, "share").deleteRecursively() }     // copies de partage restées après un arrêt brutal : jamais conservées
            runCatching {
                store.list().filter { !it.finishRequested && it.failedReason == null }.forEach { s ->
                    store.update(s.id) { it.copy(finishRequested = true) }
                }
            }
            UploadWorker.enqueue(this)
            UploadWorker.schedulePeriodic(this)
        }.start()
    }

    companion object {
        fun from(context: Context): GMeetingApp = context.applicationContext as GMeetingApp
    }
}

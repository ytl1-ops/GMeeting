package app.gmeeting

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import app.gmeeting.core.DrainResult
import app.gmeeting.core.GMeetingApi
import app.gmeeting.core.Uploader
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.util.concurrent.TimeUnit

/**
 * Envoie les enregistrements en attente dès que le réseau est disponible (mode avion levé, Wi-Fi retrouvé…), même application fermée.
 * Le système relance le travail après un redémarrage du téléphone : un enregistrement fait hors-ligne finit toujours par partir.
 */
class UploadWorker(ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {
    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val app = GMeetingApp.from(applicationContext)
        val cfg = app.secure.load() ?: return@withContext Result.success()      // pas encore configuré : rien à envoyer
        when (Uploader(app.store, GMeetingApi(cfg)).drainAll()) {
            is DrainResult.Retry -> Result.retry()                              // réseau/serveur : le système réessaiera avec un délai croissant
            is DrainResult.AuthFailed -> { Notifications.authNeeded(applicationContext); Result.success() }
            else -> Result.success()
        }
    }

    companion object {
        private val NETWORK = Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()

        fun enqueue(ctx: Context) {
            val req = OneTimeWorkRequestBuilder<UploadWorker>().setConstraints(NETWORK)
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS).build()
            WorkManager.getInstance(ctx).enqueueUniqueWork("gmeeting-upload", ExistingWorkPolicy.KEEP, req)
        }

        /** Filet de sécurité : même sans nouvel enregistrement, on revérifie régulièrement qu'aucun fichier n'est resté en attente. */
        fun schedulePeriodic(ctx: Context) {
            val req = PeriodicWorkRequestBuilder<UploadWorker>(15, TimeUnit.MINUTES).setConstraints(NETWORK).build()
            WorkManager.getInstance(ctx).enqueueUniquePeriodicWork("gmeeting-upload-periodic", ExistingPeriodicWorkPolicy.KEEP, req)
        }
    }
}

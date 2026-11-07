package app.gmeeting

import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.AudioManager
import android.media.AudioRecordingConfiguration
import android.media.MediaRecorder
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import app.gmeeting.core.BridgeJson
import app.gmeeting.core.GMeetingApi
import app.gmeeting.core.InterruptionLog
import app.gmeeting.core.SessionClock
import app.gmeeting.core.SessionStore
import app.gmeeting.core.DrainResult
import app.gmeeting.core.Uploader
import java.io.File
import java.util.concurrent.Executors

/**
 * Enregistrement de la réunion au premier plan : continue écran verrouillé, application en arrière-plan, et pendant un appel.
 *
 *  - Segments d'UNE minute (fichiers AAC complets) enchaînés SANS coupure grâce à MediaRecorder.setNextOutputFile ; si l'appareil
 *    ne le supporte pas, repli par redémarrage. Un arrêt brutal ne coûte donc qu'une minute au plus.
 *  - Chaque segment fermé est inscrit dans la file persistante (SessionStore) puis envoyé : réseau absent (mode avion) = il attend.
 *  - Un appel qui prend le micro est détecté (AudioRecordingCallback, sans permission téléphone) et journalisé ; la capture reprend seule.
 */
class RecordingService : Service() {

    private val handler = Handler(Looper.getMainLooper())
    private val io = Executors.newSingleThreadExecutor()
    private lateinit var store: SessionStore
    private val clock = SessionClock()
    private var log = InterruptionLog(clock)

    private var sessionId: String? = null
    private var kbps = 32
    private var sampleRate = 16000
    private var recorder: MediaRecorder? = null
    private var curIdx = -1; private var curFile: File? = null
    private var nextIdx = -1; private var nextFile: File? = null
    private var state = "idle"
    private var startedWall = 0L
    private var wake: PowerManager.WakeLock? = null
    private var level = 0f

    private val tick = object : Runnable {
        override fun run() {
            val r = recorder ?: return
            level = if (state == "recording") (runCatching { r.maxAmplitude }.getOrDefault(0) / 32767f).coerceIn(0f, 1f) else 0f
            publish()
            handler.postDelayed(this, 250)
        }
    }

    private val recCallback = object : AudioManager.AudioRecordingCallback() {
        override fun onRecordingConfigChanged(configs: MutableList<AudioRecordingConfiguration>?) {
            if (Build.VERSION.SDK_INT < 29 || state == "paused") return
            val mine = recorder?.activeRecordingConfiguration ?: return
            if (mine.isClientSilenced) {
                if (log.begin("appel ou autre application utilisant le micro")) setState("interrupted")
            } else if (log.end() != null) {
                persistInterruptions(); setState("recording")
            }
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        store = GMeetingApp.from(this).store
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> start(intent)
            ACTION_PAUSE -> pause()
            ACTION_RESUME -> resume()
            ACTION_STOP -> finish(intent.getStringExtra(EXTRA_FINISH))
            ACTION_CANCEL -> cancel()
            ACTION_MARK -> mark()
            else -> if (recorder == null) stopSelf()
        }
        if (recorder == null && state == "idle") stopSelf()      // service relancé sans enregistrement (ex. bouton de notification après un arrêt du processus)
        return START_NOT_STICKY
    }

    // ------------------------------------------------------------------ cycle de vie de l'enregistrement
    private fun start(intent: Intent) {
        if (recorder != null) return
        val id = intent.getStringExtra(EXTRA_SESSION) ?: return stopSelf()
        kbps = BridgeJson.kbps(intent.getIntExtra(EXTRA_KBPS, 32))
        sessionId = id
        try {
            startedWall = System.currentTimeMillis()
            promote(Notifications.recording(this, "recording", startedWall))   // doit suivre immédiatement startForegroundService
        } catch (e: Exception) {
            return fail("Autorisation du micro ou du service refusée")
        }
        wake = (getSystemService(Context.POWER_SERVICE) as PowerManager).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "gmeeting:recording")
            .apply { acquire(10 * 3600 * 1000L) }
        clock.start(); log = InterruptionLog(clock)
        if (!openSegment()) return fail("Micro indisponible (déjà utilisé par une autre application ?)")
        (getSystemService(Context.AUDIO_SERVICE) as AudioManager).registerAudioRecordingCallback(recCallback, handler)
        setState("recording")
        handler.post(tick)
    }

    private fun pause() {
        val r = recorder ?: return
        if (state == "paused") return
        runCatching { r.pause() }; clock.pause(); setState("paused")
    }

    private fun resume() {
        val r = recorder ?: return
        if (state != "paused") return
        runCatching { r.resume() }; clock.resume(); setState(if (log.isOpen) "interrupted" else "recording")
    }

    private fun finish(finishJson: String?) {
        val id = sessionId ?: return stopSelf()
        val f = BridgeJson.parseFinish(finishJson)
        stopRecording()
        log.end()
        runCatching {
            store.update(id) { it.copy(finishRequested = true, meta = it.meta + f.meta, attachmentIds = f.attachmentIds, interruptions = log.items) }
        }
        cleanupOrphans(id)
        kickUpload()
        UploadWorker.enqueue(this)
        endService()
    }

    private fun cancel() {
        val id = sessionId ?: return stopSelf()
        stopRecording()
        val registered = store.load(id)?.registered == true
        store.delete(id)
        if (registered) io.execute { runCatching { GMeetingApp.from(this).secure.load()?.let { GMeetingApi(it).discard(id) } } }
        endService()
    }

    private fun mark() {
        val id = sessionId ?: return
        if (recorder == null) return
        val t = clock.elapsedSec()
        runCatching { store.update(id) { it.copy(markers = it.markers + t) } }
    }

    private fun fail(reason: String) {
        lastError = reason
        sessionId?.let { runCatching { store.delete(it) } }
        stopRecording(); endService(keepError = true)
    }

    // ------------------------------------------------------------------ segments (MediaRecorder)
    private fun newRecorder(file: File, rate: Int): MediaRecorder {
        val r = if (Build.VERSION.SDK_INT >= 31) MediaRecorder(this) else @Suppress("DEPRECATION") MediaRecorder()
        r.setAudioSource(MediaRecorder.AudioSource.MIC)
        r.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
        r.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
        r.setAudioChannels(1)                                   // la parole n'a pas besoin de stéréo : moitié moins de données
        r.setAudioSamplingRate(rate)
        r.setAudioEncodingBitRate(kbps * 1000)
        r.setMaxDuration(SEGMENT_MS)
        r.setOutputFile(file.absolutePath)
        r.setOnInfoListener { _, what, _ -> onInfo(what) }
        r.setOnErrorListener { _, _, _ -> handler.post { rotateByRestart() } }
        r.prepare()
        return r
    }

    /** Ouvre un nouveau segment ; teste plusieurs fréquences d'échantillonnage car certains encodeurs refusent 16 kHz. */
    private fun openSegment(): Boolean {
        val id = sessionId ?: return false
        for (rate in listOf(sampleRate, 22050, 44100).distinct()) {
            val (idx, file) = store.allocateSegment(id)
            try {
                val r = newRecorder(file, rate)
                r.start()
                recorder = r; curIdx = idx; curFile = file; sampleRate = rate
                armNext()
                return true
            } catch (e: Exception) {
                file.delete()
            }
        }
        return false
    }

    /** Prépare le segment suivant : le système bascule dessus à l'échéance, sans perdre une seule milliseconde de son. */
    private fun armNext() {
        val r = recorder ?: return
        val id = sessionId ?: return
        nextFile?.delete(); nextFile = null
        runCatching {
            val (ni, nf) = store.allocateSegment(id)
            r.setNextOutputFile(nf)
            nextIdx = ni; nextFile = nf
        }
    }

    private fun onInfo(what: Int) {
        when (what) {
            MediaRecorder.MEDIA_RECORDER_INFO_NEXT_OUTPUT_FILE_STARTED -> {   // l'ancien segment est complet : on l'inscrit puis on arme le suivant
                commit(curIdx, curFile)
                curIdx = nextIdx; curFile = nextFile; nextFile = null
                armNext()
            }
            MediaRecorder.MEDIA_RECORDER_INFO_MAX_DURATION_REACHED, MediaRecorder.MEDIA_RECORDER_INFO_MAX_FILESIZE_REACHED ->
                handler.post { rotateByRestart() }                              // pas de basculement sans coupure possible : repli
        }
    }

    /** Repli : fermer le segment et en ouvrir un autre (quelques centaines de millisecondes perdues). */
    private fun rotateByRestart() {
        val r = recorder ?: return
        if (state == "paused") return
        runCatching { r.stop() }; runCatching { r.release() }
        recorder = null
        commit(curIdx, curFile); curFile = null
        nextFile?.delete(); nextFile = null
        if (!openSegment()) { lastError = "Le micro est devenu indisponible"; finish(null) }
    }

    private fun stopRecording() {
        handler.removeCallbacks(tick)
        runCatching { (getSystemService(Context.AUDIO_SERVICE) as AudioManager).unregisterAudioRecordingCallback(recCallback) }
        val r = recorder; recorder = null
        if (r != null) {
            runCatching { r.stop() }            // lève une exception si rien n'a été enregistré : sans importance
            runCatching { r.release() }
            commit(curIdx, curFile); curFile = null
        }
        nextFile?.delete(); nextFile = null
        clock.stop()
    }

    private fun commit(index: Int, file: File?) {
        val id = sessionId ?: return
        if (file == null || !file.exists()) return
        if (file.length() == 0L) { file.delete(); return }
        runCatching { store.commitSegment(id, index, file) }
        kickUpload()
    }

    /** Supprime les fichiers de segments restés sur disque sans être inscrits (segment en cours lors d'un arrêt brutal, segments inutilisés). */
    private fun cleanupOrphans(id: String) {
        val known = store.load(id)?.segments?.map { it.file }?.toSet() ?: return
        store.dir(id).listFiles { f -> f.name.startsWith("seg_") && f.name !in known }?.forEach { it.delete() }
    }

    // ------------------------------------------------------------------ envoi, état, notification
    private fun kickUpload() {
        val ctx = applicationContext
        io.execute {
            runCatching {
                val app = GMeetingApp.from(ctx)
                val cfg = app.secure.load() ?: return@execute
                when (Uploader(app.store, GMeetingApi(cfg)).drainAll()) {
                    is DrainResult.Retry -> UploadWorker.enqueue(ctx)
                    is DrainResult.AuthFailed -> Notifications.authNeeded(ctx)
                    else -> {}
                }
            }
        }
    }

    private fun persistInterruptions() {
        val id = sessionId ?: return
        runCatching { store.update(id) { it.copy(interruptions = log.items) } }
    }

    private fun setState(s: String) {
        state = s
        publish()
        runCatching { NotificationManagerCompat.from(this).notify(Notifications.ID_RECORDING, Notifications.recording(this, s, startedWall)) }
    }

    private fun publish() { snapshot = Snapshot(sessionId, state, clock.elapsedSec(), level, null) }

    private fun promote(n: android.app.Notification) {
        if (Build.VERSION.SDK_INT >= 29) startForeground(Notifications.ID_RECORDING, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
        else startForeground(Notifications.ID_RECORDING, n)
    }

    private fun endService(keepError: Boolean = false) {
        wake?.let { if (it.isHeld) it.release() }; wake = null
        state = "idle"; sessionId = null
        snapshot = Snapshot(error = if (keepError) lastError else null)
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        if (recorder != null) { stopRecording(); sessionId?.let { runCatching { store.update(it) { s -> s.copy(finishRequested = true) } } } }
        wake?.let { if (it.isHeld) it.release() }
        io.shutdown()
        super.onDestroy()
    }

    data class Snapshot(val sessionId: String? = null, val state: String = "idle", val elapsedSec: Int = 0, val level: Float = 0f, val error: String? = null)

    companion object {
        const val ACTION_START = "app.gmeeting.action.START"
        const val ACTION_PAUSE = "app.gmeeting.action.PAUSE"
        const val ACTION_RESUME = "app.gmeeting.action.RESUME"
        const val ACTION_STOP = "app.gmeeting.action.STOP"
        const val ACTION_CANCEL = "app.gmeeting.action.CANCEL"
        const val ACTION_MARK = "app.gmeeting.action.MARK"
        private const val EXTRA_SESSION = "session"
        private const val EXTRA_KBPS = "kbps"
        private const val EXTRA_FINISH = "finish"
        private const val SEGMENT_MS = 60_000

        @Volatile var snapshot = Snapshot()
        @Volatile var lastError: String? = null

        fun begin(ctx: Context, sessionId: String, kbps: Int) {
            lastError = null
            ContextCompat.startForegroundService(ctx, Intent(ctx, RecordingService::class.java).setAction(ACTION_START)
                .putExtra(EXTRA_SESSION, sessionId).putExtra(EXTRA_KBPS, kbps))
        }

        fun send(ctx: Context, action: String, finishJson: String? = null) {
            ctx.startService(Intent(ctx, RecordingService::class.java).setAction(action).apply { finishJson?.let { putExtra(EXTRA_FINISH, it) } })
        }
    }
}

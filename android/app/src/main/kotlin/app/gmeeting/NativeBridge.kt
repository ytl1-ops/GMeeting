package app.gmeeting

import android.content.Context
import android.webkit.JavascriptInterface
import app.gmeeting.core.BridgeJson
import com.google.gson.Gson

/**
 * Pont JavaScript : la page web pilote l'enregistreur natif (qui survit à l'écran verrouillé et aux appels).
 * La page est une entrée NON fiable : chaque appel vérifie que la page affichée vient bien du serveur configuré, et les paramètres sont relus de façon défensive.
 */
class NativeBridge(
    private val ctx: Context,
    private val isTrusted: () -> Boolean,
    private val askPermissions: () -> Unit,
    private val readSecure: () -> Boolean = { true },
    private val writeSecure: (Boolean) -> Unit = {},
    private val pickCopyFolder: () -> Unit = {},
) {
    private val gson = Gson()

    @JavascriptInterface fun isAvailable(): Boolean = isTrusted()

    @JavascriptInterface fun version(): String = runCatching { ctx.packageManager.getPackageInfo(ctx.packageName, 0).versionName }.getOrNull() ?: ""

    @JavascriptInterface fun hasMicPermission(): Boolean = isTrusted() &&
        ctx.checkSelfPermission(android.Manifest.permission.RECORD_AUDIO) == android.content.pm.PackageManager.PERMISSION_GRANTED

    @JavascriptInterface fun requestPermissions() { if (isTrusted()) askPermissions() }

    /** Démarre l'enregistrement ; retourne l'identifiant de session (12 caractères hexadécimaux) ou une chaîne vide en cas de refus. */
    @JavascriptInterface fun start(metaJson: String?, kbps: Int): String {
        if (!isTrusted() || !hasMicPermission()) return ""
        if (RecordingService.snapshot.state != "idle") return RecordingService.snapshot.sessionId.orEmpty()
        val store = GMeetingApp.from(ctx).store
        val s = store.create(BridgeJson.parseMeta(metaJson))
        RecordingService.begin(ctx, s.id, kbps)
        return s.id
    }

    /** Écran protégé : aperçu masqué dans les applications récentes et captures d'écran bloquées (réglage mémorisé, activé par défaut). */
    @JavascriptInterface fun isSecureScreen(): Boolean = isTrusted() && readSecure()
    @JavascriptInterface fun setSecureScreen(on: Boolean) { if (isTrusted()) writeSecure(on) }

    /** Copie facultative de l'audio dans un dossier désigné du téléphone : {"name":"…","failed":false} (name vide = désactivée). */
    @JavascriptInterface fun copyFolderStatus(): String =
        if (!isTrusted()) "{}" else gson.toJson(mapOf("name" to LocalCopy.label(ctx), "failed" to LocalCopy.failed(ctx)))
    @JavascriptInterface fun chooseCopyFolder() { if (isTrusted()) pickCopyFolder() }
    @JavascriptInterface fun clearCopyFolder() { if (isTrusted()) LocalCopy.clear(ctx) }

    @JavascriptInterface fun pause() { if (isTrusted()) RecordingService.send(ctx, RecordingService.ACTION_PAUSE) }
    @JavascriptInterface fun resume() { if (isTrusted()) RecordingService.send(ctx, RecordingService.ACTION_RESUME) }
    @JavascriptInterface fun mark() { if (isTrusted()) RecordingService.send(ctx, RecordingService.ACTION_MARK) }
    @JavascriptInterface fun cancel() { if (isTrusted()) RecordingService.send(ctx, RecordingService.ACTION_CANCEL) }

    /** Termine : `finishJson` = {"meta":{…},"attachment_ids":[…]} ; la transcription démarre dès que les segments sont envoyés (réseau requis). */
    @JavascriptInterface fun finish(finishJson: String?) { if (isTrusted()) RecordingService.send(ctx, RecordingService.ACTION_STOP, finishJson ?: "{}") }

    /** {"state":"idle|recording|paused|interrupted","elapsed":s,"level":0..1,"id":"…","error":"…"} */
    @JavascriptInterface fun state(): String {
        if (!isTrusted()) return "{}"
        val s = RecordingService.snapshot
        return gson.toJson(mapOf("state" to s.state, "elapsed" to s.elapsedSec, "level" to s.level, "id" to s.sessionId, "error" to (s.error ?: RecordingService.lastError)))
    }
}

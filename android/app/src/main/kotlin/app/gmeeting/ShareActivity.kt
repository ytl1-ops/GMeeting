package app.gmeeting

import android.app.Activity
import android.content.ClipData
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.OpenableColumns
import android.widget.Toast
import app.gmeeting.core.GMeetingApi
import app.gmeeting.core.ShareAction
import app.gmeeting.core.ShareRouting
import app.gmeeting.core.UnauthorizedException
import java.io.File

/** « Partager vers GMeeting » : lien de visio, audio, mail Outlook, Word, Excel, PDF… → réunion ou pièces jointes, puis ouverture de l'application. */
class ShareActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val cfg = GMeetingApp.from(this).secure.load()
        if (cfg == null) { startActivity(Intent(this, SetupActivity::class.java)); finish(); return }
        val uris = uris(intent)
        val text = intent.getStringExtra(Intent.EXTRA_TEXT)
        val names = uris.map { name(it) }
        val mimes = uris.map { contentResolver.getType(it) }
        val action = ShareRouting.classify(mimes, names, text)
        if (action is ShareAction.Unsupported) { toast(getString(R.string.share_unsupported)); finish(); return }
        toast(getString(R.string.share_sending))
        val meta = mapOf("report_lang" to if (java.util.Locale.getDefault().language == "fr") "fr" else "en")     // même règle que l'interface web
        val dir = File(cacheDir, "share").apply { deleteRecursively(); mkdirs() }
        Thread {
            var path: String? = null
            var err: String? = null
            try {
                val api = GMeetingApi(cfg)
                fun copy(i: Int): Pair<String, File> {
                    val n = (names[i] ?: "piece-$i").replace(Regex("[/\\\\]"), "_")
                    val f = File(dir, "$i-$n")
                    contentResolver.openInputStream(uris[i]).use { input -> f.outputStream().use { input!!.copyTo(it) } }
                    return n to f
                }
                path = when (action) {
                    is ShareAction.MeetingFromLink -> "/m/" + api.createFromUrl(action.url, meta, emptyList())
                    is ShareAction.MeetingFromAudio -> {
                        val ids = if (action.attachmentIndexes.isEmpty()) emptyList() else api.uploadAttachments(action.attachmentIndexes.map { copy(it) })
                        val (n, f) = copy(action.audioIndex)
                        "/m/" + api.createFromAudio(f, n, meta, ids)
                    }
                    is ShareAction.Attachments -> "/?pj=" + api.uploadAttachments(action.indexes.map { copy(it) }).joinToString(",")
                    ShareAction.Unsupported -> null
                }
            } catch (e: UnauthorizedException) {
                err = getString(R.string.share_auth)
                startActivity(Intent(this, SetupActivity::class.java))
            } catch (e: Exception) { err = e.message?.take(120) ?: getString(R.string.share_failed) }
            finally { dir.deleteRecursively() }
            runOnUiThread {
                if (err != null) toast(err)
                else if (path != null) startActivity(Intent(this, MainActivity::class.java).putExtra(MainActivity.EXTRA_PATH, path)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP))
                finish()
            }
        }.start()
    }

    @Suppress("DEPRECATION")
    private fun uris(i: Intent): List<Uri> {
        val out = linkedSetOf<Uri>()
        if (i.action == Intent.ACTION_SEND) i.getParcelableExtra<Uri>(Intent.EXTRA_STREAM)?.let { out += it }
        else i.getParcelableArrayListExtra<Uri>(Intent.EXTRA_STREAM)?.let { out += it }
        val clip: ClipData? = i.clipData
        if (out.isEmpty() && clip != null) for (k in 0 until clip.itemCount) clip.getItemAt(k).uri?.let { out += it }
        return out.filter { it.scheme == "content" }.take(10)       // jamais file:// (lecture de fichiers privés de l'application)
    }

    private fun name(u: Uri): String? = runCatching {
        contentResolver.query(u, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c -> if (c.moveToFirst()) c.getString(0) else null }
    }.getOrNull() ?: u.lastPathSegment

    private fun toast(m: String) = runOnUiThread { Toast.makeText(this, m, Toast.LENGTH_LONG).show() }
}

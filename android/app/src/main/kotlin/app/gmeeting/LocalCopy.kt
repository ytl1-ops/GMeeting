package app.gmeeting

import android.content.Context
import android.content.Intent
import android.database.Cursor
import android.net.Uri
import android.provider.DocumentsContract
import java.io.File

/**
 * Copie de l'audio sur le téléphone, dans un dossier DÉSIGNÉ par l'utilisateur (mémoire du téléphone, carte SD, dossier synchronisé avec un cloud…).
 * Facultatif, désactivé par défaut. Le dossier est choisi avec le sélecteur du système (aucune autorisation de stockage à demander) ; GMeeting n'a accès
 * qu'à CE dossier. Chaque minute d'audio y est copiée (`GMeeting-<id de réunion>/seg_0001.m4a`…) en plus de l'envoi au serveur.
 * Une copie qui échoue n'empêche JAMAIS l'enregistrement ni l'envoi. Ces fichiers ne sont pas chiffrés : le dossier doit être protégé par l'utilisateur.
 */
object LocalCopy {
    private const val PREF = "ui"
    private const val KEY_TREE = "copy_tree"
    private const val KEY_FAILED = "copy_failed"
    private fun prefs(ctx: Context) = ctx.getSharedPreferences(PREF, Context.MODE_PRIVATE)

    fun tree(ctx: Context): Uri? = prefs(ctx).getString(KEY_TREE, null)?.let { Uri.parse(it) }
    fun failed(ctx: Context): Boolean = prefs(ctx).getBoolean(KEY_FAILED, false)

    fun set(ctx: Context, uri: Uri) { prefs(ctx).edit().putString(KEY_TREE, uri.toString()).putBoolean(KEY_FAILED, false).apply() }

    fun clear(ctx: Context) {
        tree(ctx)?.let { runCatching { ctx.contentResolver.releasePersistableUriPermission(it, Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION) } }
        prefs(ctx).edit().remove(KEY_TREE).putBoolean(KEY_FAILED, false).apply()
    }

    /** Nom lisible du dossier choisi (vide si aucun). */
    fun label(ctx: Context): String {
        val t = tree(ctx) ?: return ""
        return runCatching {
            val doc = DocumentsContract.buildDocumentUriUsingTree(t, DocumentsContract.getTreeDocumentId(t))
            ctx.contentResolver.query(doc, arrayOf(DocumentsContract.Document.COLUMN_DISPLAY_NAME), null, null, null)?.use { c -> if (c.moveToFirst()) c.getString(0) else null }
        }.getOrNull() ?: Uri.decode(t.lastPathSegment.orEmpty())
    }

    /**
     * Étape 1, appelée dès qu'un segment est fermé (rapide, locale) : met le segment à l'abri dans le cache de l'application.
     * Le fichier d'origine peut ainsi être envoyé puis supprimé sans que la copie ne soit perdue.
     */
    fun stage(ctx: Context, sessionId: String, index: Int, file: File): File? {
        if (tree(ctx) == null) return null
        return runCatching {
            val dir = File(ctx.cacheDir, "localcopy").apply { mkdirs() }
            File(dir, "${sessionId}_$index.m4a").also { file.copyTo(it, overwrite = true) }
        }.getOrNull()
    }

    /** Étape 2, hors du fil principal : écrit le segment dans le dossier désigné, puis supprime la copie temporaire. */
    fun write(ctx: Context, sessionId: String, index: Int, staged: File) {
        val ok = runCatching {
            val t = tree(ctx) ?: return@runCatching
            val resolver = ctx.contentResolver
            val root = DocumentsContract.buildDocumentUriUsingTree(t, DocumentsContract.getTreeDocumentId(t))
            val dir = child(ctx, t, root, "GMeeting-$sessionId", DocumentsContract.Document.MIME_TYPE_DIR, create = true) ?: error("dossier")
            val name = "seg_%04d.m4a".format(index)
            if (child(ctx, t, dir, name, "audio/mp4", create = false) != null) return@runCatching        // déjà copié
            val out = child(ctx, t, dir, name, "audio/mp4", create = true) ?: error("fichier")
            resolver.openOutputStream(out, "w")!!.use { o -> staged.inputStream().use { it.copyTo(o) } }
        }.isSuccess
        prefs(ctx).edit().putBoolean(KEY_FAILED, !ok).apply()
        staged.delete()
    }

    private fun child(ctx: Context, tree: Uri, parent: Uri, name: String, mime: String, create: Boolean): Uri? {
        val kids = DocumentsContract.buildChildDocumentsUriUsingTree(tree, DocumentsContract.getDocumentId(parent))
        val cols = arrayOf(DocumentsContract.Document.COLUMN_DOCUMENT_ID, DocumentsContract.Document.COLUMN_DISPLAY_NAME)
        ctx.contentResolver.query(kids, cols, null, null, null)?.use { c: Cursor ->
            while (c.moveToNext()) if (c.getString(1) == name) return DocumentsContract.buildDocumentUriUsingTree(tree, c.getString(0))
        }
        return if (create) DocumentsContract.createDocument(ctx.contentResolver, parent, mime, name) else null
    }

    /** Copies temporaires restées après un arrêt brutal : jamais conservées. */
    fun wipeStaging(ctx: Context) { runCatching { File(ctx.cacheDir, "localcopy").deleteRecursively() } }
}

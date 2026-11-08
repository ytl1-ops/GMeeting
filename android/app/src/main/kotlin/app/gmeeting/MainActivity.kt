package app.gmeeting

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.app.DownloadManager
import android.content.Intent
import android.net.Uri
import android.net.http.SslError
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.webkit.CookieManager
import android.webkit.DownloadListener
import android.webkit.HttpAuthHandler
import android.webkit.SslErrorHandler
import android.webkit.URLUtil
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import app.gmeeting.core.ServerConfig

/** Coque de l'application : l'interface web du serveur de l'utilisateur + enregistreur natif (voir NativeBridge). */
class MainActivity : Activity() {
    private lateinit var web: WebView
    private var cfg: ServerConfig? = null
    @Volatile private var trustedPage = false
    private var chooser: ValueCallback<Array<Uri>>? = null

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        cfg = GMeetingApp.from(this).secure.load()
        if (cfg == null) { startActivity(Intent(this, SetupActivity::class.java)); finish(); return }
        applySecure(secureOn())
        web = WebView(this)
        val root = android.widget.FrameLayout(this).apply { setBackgroundColor(android.graphics.Color.WHITE); addView(web, android.widget.FrameLayout.LayoutParams.MATCH_PARENT, android.widget.FrameLayout.LayoutParams.MATCH_PARENT) }
        setContentView(root)
        Insets.fit(root)
        // Android 13+ : geste « retour » prédictif ; obligatoire en ciblant Android 16 (onBackPressed n'est plus appelé par défaut)
        if (Build.VERSION.SDK_INT >= 33) onBackInvokedDispatcher.registerOnBackInvokedCallback(android.window.OnBackInvokedDispatcher.PRIORITY_DEFAULT) { goBackOrFinish() }
        web.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            allowFileAccess = false; allowContentAccess = false
            mediaPlaybackRequiresUserGesture = true
            mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            setSupportMultipleWindows(false)
        }
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, false)
        web.addJavascriptInterface(NativeBridge(this, { trustedPage }, { askPermissions() }, { secureOn() }, { on -> getSharedPreferences("ui", MODE_PRIVATE).edit().putBoolean("secure", on).apply(); runOnUiThread { applySecure(on) } }), "GMeetingNative")
        web.webViewClient = client()
        web.webChromeClient = chrome()
        web.setDownloadListener(download())
        if (savedInstanceState != null) web.restoreState(savedInstanceState) else load(intent)
    }

    override fun onNewIntent(intent: Intent) { super.onNewIntent(intent); setIntent(intent); if (cfg != null) load(intent) }

    override fun onSaveInstanceState(out: Bundle) { super.onSaveInstanceState(out); if (cfg != null) web.saveState(out) }

    /** Écran protégé : activé par défaut dans la version publiée (réunions confidentielles) ; désactivé en version de test pour pouvoir capturer l'écran. */
    private fun secureOn() = getSharedPreferences("ui", MODE_PRIVATE).getBoolean("secure", !BuildConfig.DEBUG)
    private fun applySecure(on: Boolean) {
        if (on) window.addFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE) else window.clearFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE)
    }

    private fun load(i: Intent?) {
        val c = cfg ?: return
        val path = i?.getStringExtra(EXTRA_PATH)?.takeIf { PATH.matches(it) }
        web.loadUrl(c.root + "/" + (path?.let { "#$it" } ?: ""))
    }

    private fun sameHost(u: Uri?): Boolean {
        val b = Uri.parse(cfg?.root ?: return false)
        return u != null && u.scheme == b.scheme && u.host == b.host && u.port == b.port
    }

    private fun client() = object : WebViewClient() {
        override fun shouldOverrideUrlLoading(v: WebView, r: WebResourceRequest): Boolean {
            if (sameHost(r.url)) return false
            runCatching { startActivity(Intent(Intent.ACTION_VIEW, r.url)) }      // liens externes : dans le navigateur, jamais dans notre WebView
            return true
        }
        override fun onPageStarted(v: WebView, url: String?, f: android.graphics.Bitmap?) { trustedPage = sameHost(Uri.parse(url ?: "")) }
        override fun onPageFinished(v: WebView, url: String?) { trustedPage = sameHost(Uri.parse(url ?: "")) }
        override fun onReceivedHttpAuthRequest(v: WebView, h: HttpAuthHandler, host: String?, realm: String?) {
            val c = cfg
            if (c != null && host == Uri.parse(c.root).host && !authTried) { authTried = true; h.proceed(c.user, c.password) }
            else { h.cancel(); startActivity(Intent(this@MainActivity, SetupActivity::class.java)) }
        }
        override fun onReceivedSslError(v: WebView, h: SslErrorHandler, e: SslError?) { h.cancel() }     // jamais de contournement du certificat
        override fun onReceivedError(v: WebView, r: WebResourceRequest, e: WebResourceError) {
            if (r.isForMainFrame) { trustedPage = false; showOffline() }
        }
    }

    private var authTried = false

    /** Serveur injoignable (mode avion…) : l'enregistrement reste possible, il sera envoyé au retour du réseau. */
    private fun showOffline() {
        val c = cfg ?: return
        fun h(id: Int) = android.text.TextUtils.htmlEncode(getString(id))          // texte affiché
        fun j(id: Int) = org.json.JSONObject.quote(getString(id))                  // chaîne JavaScript
        val html = """<meta name=viewport content="width=device-width,initial-scale=1"><body style="font-family:sans-serif;padding:24px;text-align:center">
            <h2>${h(R.string.offline_title)}</h2><p>${h(R.string.offline_body)}</p>
            <p><button id=s style="font-size:18px;padding:14px 22px">${h(R.string.offline_record)}</button></p><p><button id=e style="font-size:18px;padding:14px 22px">${h(R.string.offline_finish)}</button></p>
            <p id=t></p><p><button onclick="location.reload()">${h(R.string.offline_retry)}</button></p>
            <script>const N=window.GMeetingNative;const t=document.getElementById('t');
            document.getElementById('s').onclick=()=>{ if(!N||!N.hasMicPermission()){ if(N)N.requestPermissions(); t.textContent=${j(R.string.offline_need_perm)}; return;} N.start('{}',32); t.textContent=${j(R.string.offline_recording)}};
            document.getElementById('e').onclick=()=>{ if(N){N.finish('{}'); t.textContent=${j(R.string.offline_finished)}}};</script></body>"""
        trustedPage = true
        web.loadDataWithBaseURL(c.root + "/offline", html, "text/html", "utf-8", null)
    }

    private fun chrome() = object : WebChromeClient() {
        override fun onShowFileChooser(w: WebView, cb: ValueCallback<Array<Uri>>, p: FileChooserParams): Boolean {
            chooser?.onReceiveValue(null); chooser = cb
            return try { startActivityForResult(p.createIntent(), REQ_FILE); true } catch (e: Exception) { chooser = null; false }
        }
        override fun onPermissionRequest(request: android.webkit.PermissionRequest) { request.deny() }     // le micro passe par le service natif, pas par la page
    }

    /** Téléchargement d'un rendu (PDF, Word, Excel, PowerPoint) vers « Téléchargements » : avec le mot de passe, jamais vers un autre serveur. */
    private fun download() = DownloadListener { url, ua, cd, mime, _ ->
        val c = cfg ?: return@DownloadListener
        val name = URLUtil.guessFileName(url, cd, mime)
        when {
            url.startsWith("data:text/plain") -> saveText(url, name)
            sameHost(Uri.parse(url)) -> startDownload(Uri.parse(url), c, name, mime, ua)
            else -> Toast.makeText(this, getString(R.string.main_dl_foreign), Toast.LENGTH_LONG).show()
        }
    }

    private class Pending(val uri: Uri, val name: String, val mime: String?, val ua: String?)
    private var pendingDownload: Pending? = null

    private fun startDownload(uri: Uri, c: ServerConfig, name: String, mime: String?, ua: String?) {
        // Android 8 et 9 : écrire dans « Téléchargements » exige l'autorisation de stockage (inutile à partir d'Android 10)
        if (Build.VERSION.SDK_INT < 29 && checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            pendingDownload = Pending(uri, name, mime, ua)
            requestPermissions(arrayOf(Manifest.permission.WRITE_EXTERNAL_STORAGE), REQ_STORAGE)
            return
        }
        try {
            val r = DownloadManager.Request(uri).setMimeType(mime).addRequestHeader("Authorization", c.authHeader())
                .setTitle(name).setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                .setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, name)
            ua?.let { r.addRequestHeader("User-Agent", it) }
            getSystemService(DownloadManager::class.java).enqueue(r)
            Toast.makeText(this, getString(R.string.main_dl_started, name), Toast.LENGTH_LONG).show()
        } catch (e: Exception) {
            Toast.makeText(this, getString(R.string.main_dl_failed, e.message?.take(80) ?: ""), Toast.LENGTH_LONG).show()
        }
    }

    /** Lien « .txt » de la transcription (adresse data:) : enregistré dans Téléchargements. */
    private fun saveText(dataUrl: String, name: String) {
        try {
            val text = Uri.decode(dataUrl.substringAfter(','))
            val fileName = if (name.endsWith(".txt")) name else "transcription.txt"
            if (Build.VERSION.SDK_INT >= 29) {
                val v = android.content.ContentValues().apply {
                    put(android.provider.MediaStore.Downloads.DISPLAY_NAME, fileName); put(android.provider.MediaStore.Downloads.MIME_TYPE, "text/plain")
                }
                val u = contentResolver.insert(android.provider.MediaStore.Downloads.EXTERNAL_CONTENT_URI, v) ?: error("stockage indisponible")
                contentResolver.openOutputStream(u)!!.use { it.write(text.toByteArray()) }
            } else {
                val dir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS).apply { mkdirs() }
                java.io.File(dir, fileName).writeText(text)
            }
            Toast.makeText(this, getString(R.string.main_saved_txt, fileName), Toast.LENGTH_LONG).show()
        } catch (e: Exception) {
            Toast.makeText(this, getString(R.string.main_save_failed, e.message?.take(80) ?: ""), Toast.LENGTH_LONG).show()
        }
    }

    private fun askPermissions() {
        val p = mutableListOf(Manifest.permission.RECORD_AUDIO)
        if (Build.VERSION.SDK_INT >= 33) p += Manifest.permission.POST_NOTIFICATIONS
        runOnUiThread { requestPermissions(p.toTypedArray(), REQ_PERM) }
    }

    override fun onRequestPermissionsResult(code: Int, perms: Array<out String>, res: IntArray) {
        super.onRequestPermissionsResult(code, perms, res)
        if (code == REQ_STORAGE) {
            val p = pendingDownload; pendingDownload = null; val c = cfg
            if (p != null && c != null && res.firstOrNull() == android.content.pm.PackageManager.PERMISSION_GRANTED) startDownload(p.uri, c, p.name, p.mime, p.ua)
            else Toast.makeText(this, getString(R.string.main_storage_needed), Toast.LENGTH_LONG).show()
        }
        if (code == REQ_PERM && cfg != null) web.evaluateJavascript("window.dispatchEvent(new Event('gmeeting-permissions'))", null)
    }

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(req: Int, res: Int, data: Intent?) {
        super.onActivityResult(req, res, data)
        if (req == REQ_FILE) {
            val r = if (res == RESULT_OK && data != null) android.webkit.WebChromeClient.FileChooserParams.parseResult(res, data) else null
            chooser?.onReceiveValue(r); chooser = null
        }
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() { if (Build.VERSION.SDK_INT >= 33) goBackOrFinish() else if (cfg != null && web.canGoBack()) web.goBack() else super.onBackPressed() }

    private fun goBackOrFinish() { if (cfg != null && web.canGoBack()) web.goBack() else finish() }

    override fun onDestroy() { if (cfg != null) { web.removeJavascriptInterface("GMeetingNative"); web.destroy() }; super.onDestroy() }

    companion object {
        const val EXTRA_PATH = "path"
        private val PATH = Regex("/(m/[0-9a-zA-Z]{1,32}|\\?pj=[0-9a-f,]{1,300})")
        private const val REQ_FILE = 11
        private const val REQ_PERM = 12
        private const val REQ_STORAGE = 13
    }
}

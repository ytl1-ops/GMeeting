package app.gmeeting

import android.app.Activity
import android.content.Intent
import android.graphics.Typeface
import android.os.Bundle
import android.text.InputType
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import app.gmeeting.core.ApiException
import app.gmeeting.core.GMeetingApi
import app.gmeeting.core.ServerConfig
import app.gmeeting.core.UnauthorizedException
import java.io.IOException
import javax.net.ssl.SSLException

/** Première configuration : adresse du serveur GMeeting de l'utilisateur et mot de passe. Vérifiés avant d'être enregistrés (chiffrés). */
class SetupActivity : Activity() {
    private lateinit var url: EditText
    private lateinit var pw: EditText
    private lateinit var status: TextView
    private lateinit var go: Button

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(24), dp(48), dp(24), dp(24)) }
        col.addView(TextView(this).apply { text = "GMeeting"; textSize = 28f; setTypeface(null, Typeface.BOLD); setTextColor(getColor(R.color.brand)) })
        col.addView(TextView(this).apply {
            text = "Connectez l'application à votre serveur GMeeting. Vos réunions restent chez vous : l'application n'envoie rien ailleurs."
            textSize = 15f; setPadding(0, dp(8), 0, dp(24))
        })
        url = EditText(this).apply { hint = "Adresse (ex. reunions.exemple.fr)"; inputType = InputType.TYPE_TEXT_VARIATION_URI or InputType.TYPE_CLASS_TEXT; setSingleLine() }
        pw = EditText(this).apply { hint = "Mot de passe"; inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD; setSingleLine() }
        GMeetingApp.from(this).secure.load()?.let { url.setText(it.root) }
        go = Button(this).apply { text = "Se connecter"; setOnClickListener { connect() } }
        status = TextView(this).apply { textSize = 14f; setPadding(0, dp(16), 0, 0) }
        col.addView(url); col.addView(pw); col.addView(go); col.addView(status)
        setContentView(ScrollView(this).apply { addView(col, ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT) })
    }

    private fun say(msg: String, error: Boolean = true) {
        status.text = msg
        status.setTextColor(if (error) getColor(R.color.rec) else getColor(R.color.brand))
    }

    private fun connect() {
        var raw = url.text.toString().trim()
        // version de test : une adresse du réseau local (192.168.x.x:8000) se saisit sans « http:// »
        if (BuildConfig.DEBUG && !raw.contains("://") && Regex("^((\\d{1,3}\\.){3}\\d{1,3}|localhost)(:\\d+)?(/.*)?$").matches(raw)) raw = "http://$raw"
        val base = ServerConfig.normalizeUrl(raw, allowHttp = BuildConfig.DEBUG)
        if (base == null) { say("Adresse invalide. Exemple : reunions.exemple.fr (HTTPS obligatoire)."); return }
        val password = pw.text.toString()
        if (password.isEmpty()) { say("Saisissez le mot de passe du serveur."); return }
        go.isEnabled = false; say("Vérification…", false)
        val cfg = ServerConfig(base, password)
        Thread {
            val msg: String? = try { GMeetingApi(cfg).checkServer(); null }
            catch (e: UnauthorizedException) { "Mot de passe refusé par le serveur." }
            catch (e: ApiException) { e.message ?: "Réponse inattendue du serveur." }
            catch (e: SSLException) { "Certificat HTTPS non reconnu : vérifiez l'adresse et le certificat du serveur." }
            catch (e: IOException) { "Serveur injoignable : vérifiez l'adresse et votre connexion." }
            catch (e: Exception) { "Réponse inattendue du serveur." }
            runOnUiThread {
                go.isEnabled = true
                if (msg != null) { say(msg); return@runOnUiThread }
                GMeetingApp.from(this).secure.save(cfg)
                UploadWorker.enqueue(this)               // des enregistrements en attente d'un mot de passe valide repartent aussitôt
                startActivity(Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP))
                finish()
            }
        }.start()
    }
}

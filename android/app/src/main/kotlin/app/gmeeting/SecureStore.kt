package app.gmeeting

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import app.gmeeting.core.ServerConfig

/** Adresse du serveur et mot de passe, chiffrés avec une clé du coffre Android (Keystore) : jamais en clair sur le disque. */
class SecureStore(private val context: Context) {
    private val prefs: SharedPreferences by lazy { open() }

    private fun open(): SharedPreferences {
        fun create(): SharedPreferences {
            val key = MasterKey.Builder(context).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build()
            return EncryptedSharedPreferences.create(
                context, FILE, key,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
            )
        }
        return try { create() } catch (e: Exception) {
            // Clé du coffre invalidée (restauration, changement de verrouillage…) : on repart d'un coffre vide ; l'utilisateur se reconnecte.
            context.deleteSharedPreferences(FILE)
            create()
        }
    }

    fun load(): ServerConfig? {
        val url = prefs.getString(K_URL, null) ?: return null
        val pw = prefs.getString(K_PW, null) ?: return null
        return ServerConfig(url, pw)
    }

    fun save(cfg: ServerConfig) { prefs.edit().putString(K_URL, cfg.root).putString(K_PW, cfg.password).apply() }
    fun clear() { prefs.edit().clear().apply() }

    private companion object { const val FILE = "gmeeting_secure"; const val K_URL = "server_url"; const val K_PW = "password" }
}

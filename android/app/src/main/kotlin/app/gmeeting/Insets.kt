package app.gmeeting

import android.os.Build
import android.view.View
import android.view.WindowInsets

/**
 * Android 15+ (et obligatoirement en ciblant Android 15/16) : l'application est dessinée sous la barre d'état et la barre de navigation.
 * On décale le contenu de la hauteur de ces barres (et du clavier) pour que l'en-tête et les boutons restent atteignables.
 * Avant Android 15, le système réserve déjà cette place : rien à faire.
 */
object Insets {
    fun fit(root: View) {
        if (Build.VERSION.SDK_INT < 35) return
        root.setOnApplyWindowInsetsListener { v, insets ->
            val b = insets.getInsets(WindowInsets.Type.systemBars() or WindowInsets.Type.displayCutout() or WindowInsets.Type.ime())
            v.setPadding(b.left, b.top, b.right, b.bottom)
            WindowInsets.CONSUMED
        }
        root.requestApplyInsets()
    }
}

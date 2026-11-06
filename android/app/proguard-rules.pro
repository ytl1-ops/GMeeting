# La minification est désactivée (voir build.gradle.kts). Si elle est activée un jour, ces règles sont indispensables :
# Gson sérialise ces classes par réflexion (état des sessions sur disque ET corps des requêtes envoyées au serveur).
-keepattributes Signature, *Annotation*
-keep class app.gmeeting.core.** { *; }

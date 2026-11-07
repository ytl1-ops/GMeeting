pluginManagement {
    repositories { gradlePluginPortal(); google(); mavenCentral() }
    plugins {
        id("org.jetbrains.kotlin.jvm") version "2.0.21"
        id("org.jetbrains.kotlin.android") version "2.0.21"
        id("com.android.application") version "8.7.3"
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.PREFER_SETTINGS)
    repositories { mavenCentral(); google() }
}
rootProject.name = "gmeeting-android"

// Le cœur (Kotlin pur) se construit et se teste partout, y compris sans SDK Android.
// L'application n'est incluse que si un SDK Android est présent (CI, poste de développement Android Studio) ou avec -PwithApp.
include(":core")
if (System.getenv("ANDROID_HOME") != null || System.getenv("ANDROID_SDK_ROOT") != null || providers.gradleProperty("withApp").isPresent) {
    include(":app")
}

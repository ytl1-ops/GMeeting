import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// Paramétrable sans toucher au code : ./gradlew :app:bundleRelease -PappId=fr.mondomaine.gmeeting -PversionCode=7 -PversionName=1.0.2
// ATTENTION : l'identifiant d'application est DÉFINITIF dès le premier envoi sur le Play Store.
val appId = (project.findProperty("appId") as String?) ?: "app.gmeeting.android"
val keystoreFile = rootProject.file("keystore.properties")        // jamais versionné ; absent = version non signée (CI sans secrets)

android {
    namespace = "app.gmeeting"
    compileSdk = 36

    defaultConfig {
        applicationId = appId
        minSdk = 26          // Android 8.0 : MediaRecorder.setNextOutputFile (segments sans coupure), icônes adaptatives
        targetSdk = 36       // Android 16 : exigé par le Play Store pour toute NOUVELLE application depuis le 31/08/2026. Google relève l'exigence chaque année : à relever (et retester) à temps
        versionCode = (project.findProperty("versionCode") as String?)?.toInt() ?: 1
        versionName = (project.findProperty("versionName") as String?) ?: "0.1.0"
    }

    signingConfigs {
        if (keystoreFile.exists()) {
            create("release") {
                val p = Properties().apply { keystoreFile.inputStream().use { load(it) } }
                storeFile = rootProject.file(p.getProperty("storeFile"))
                storePassword = p.getProperty("storePassword")
                keyAlias = p.getProperty("keyAlias")
                keyPassword = p.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false      // l'application est petite ; Gson (réflexion) et R8 demandent des règles à valider sur appareil
            if (keystoreFile.exists()) signingConfig = signingConfigs.getByName("release")
        }
        debug { applicationIdSuffix = ".debug"; versionNameSuffix = "-debug" }
    }

    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { buildConfig = true }
    lint { abortOnError = false; checkReleaseBuilds = false; warningsAsErrors = false }
    packaging { resources { excludes += setOf("/META-INF/{AL2.0,LGPL2.1}", "META-INF/DEPENDENCIES") } }
}

dependencies {
    implementation(project(":core"))
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.activity:activity-ktx:1.9.3")
    implementation("androidx.work:work-runtime-ktx:2.9.1")
    implementation("androidx.security:security-crypto:1.1.0-alpha06")
}

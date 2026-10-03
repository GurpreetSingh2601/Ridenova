import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
}

val localProperties = Properties().apply {
    val file = rootProject.file("local.properties")
    if (file.exists()) file.inputStream().use(::load)
}

val mapsApiKey = providers.gradleProperty("MAPS_API_KEY").orNull
    ?.trim()
    ?.takeIf { it.isNotEmpty() }
    ?: localProperties.getProperty("MAPS_API_KEY")
        ?.trim()
        ?.takeIf { it.isNotEmpty() }
    ?: ""

fun buildLiteral(value: String): String = "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"") + "\""
val devUrl = localProperties.getProperty("RIDENOVA_DEV_URL", "http://127.0.0.1:8080").trim()
val devToken = localProperties.getProperty("RIDENOVA_DEV_TOKEN", "").trim()

android {
    namespace = "com.ridenova.driver"
    compileSdk {
        version = release(37) {
            minorApiLevel = 0
        }
    }

    defaultConfig {
        applicationId = "com.ridenova.driver"
        minSdk = 26
        targetSdk = 37
        versionCode = 41
        versionName = "0.19.1-build42.1"

        // Supports MAPS_API_KEY in either gradle.properties or local.properties.
        manifestPlaceholders["MAPS_API_KEY"] = mapsApiKey
        buildConfigField("boolean", "MAPS_API_KEY_CONFIGURED", mapsApiKey.isNotEmpty().toString())
        buildConfigField("String", "MAPS_API_KEY", buildLiteral(mapsApiKey))
        buildConfigField("boolean", "RIDENOVA_LEGACY_DRIVER", "false")
        buildConfigField("String", "RIDENOVA_ENVIRONMENT", "\"development\"")
        buildConfigField("String", "RIDENOVA_DEV_URL", "\"\"")
        buildConfigField("String", "RIDENOVA_DEV_TOKEN", "\"\"")
    }

    buildTypes {
        create("staging") {
            initWith(getByName("debug"))
            isDebuggable = false
            signingConfig = signingConfigs.getByName("debug")
            applicationIdSuffix = ".staging"
            versionNameSuffix = "-staging"
            matchingFallbacks += listOf("debug")
            val origin = providers.gradleProperty("RIDENOVA_STAGING_API_BASE_URL").orElse("").get().trim()
            buildConfigField("String", "RIDENOVA_ENVIRONMENT", "\"staging\"")
            buildConfigField("String", "RIDENOVA_DEV_URL", buildLiteral(origin))
            buildConfigField("String", "RIDENOVA_DEV_TOKEN", "\"\"")
            buildConfigField("boolean", "RIDENOVA_LEGACY_DRIVER", "false")
            require(origin.isEmpty() || origin.matches(Regex("https://[A-Za-z0-9.-]+/?"))) { "Staging requires a plain HTTPS origin" }
            tasks.matching { it.name == "preStagingBuild" }.configureEach {
                doFirst { require(origin.isNotBlank()) { "Set RIDENOVA_STAGING_API_BASE_URL to your deployed HTTPS API" } }
            }
        }
        getByName("debug") {
            buildConfigField("boolean", "RIDENOVA_LEGACY_DRIVER", (localProperties.getProperty("RIDENOVA_LEGACY_DRIVER", "false") == "true").toString())
            buildConfigField("String", "RIDENOVA_DEV_URL", buildLiteral(devUrl))
            buildConfigField("String", "RIDENOVA_DEV_TOKEN", buildLiteral(devToken))
        }
    }
    tasks.matching { it.name == "preReleaseBuild" }.configureEach {
        doFirst { error("Public production release is gated until launch readiness is verified") }
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    packaging {
        resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
    }
}

if (mapsApiKey.isEmpty()) {
    logger.warn("RideNova Driver: MAPS_API_KEY is missing. Add MAPS_API_KEY=... to gradle.properties or local.properties.")
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2026.08.00")
    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation("androidx.core:core-ktx:1.17.0")
    implementation("androidx.activity:activity-compose:1.13.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.10.0")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.10.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.10.0")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.navigation:navigation-compose:2.10.0")

    implementation("com.google.maps.android:maps-compose:8.4.0")
    implementation("com.google.android.gms:play-services-maps:19.2.0")
    implementation("com.google.android.gms:play-services-location:21.3.0")

    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}

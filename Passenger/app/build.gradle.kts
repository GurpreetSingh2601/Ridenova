plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.google.android.libraries.mapsplatform.secrets-gradle-plugin")
}

android {
    namespace = "com.ridenova.passenger"
    compileSdk {
        version = release(37) {
            minorApiLevel = 0
        }
    }

    defaultConfig {
        applicationId = "com.ridenova.passenger"
        minSdk = 26
        targetSdk = 36
        versionCode = 45
        versionName = "0.34.1-build42.1"

        // v0.14 backend-ready environment hooks. These are intentionally non-secret.
        buildConfigField("String", "RIDENOVA_ENVIRONMENT", "\"development\"")
        val apiUrl = providers.gradleProperty("RIDENOVA_API_BASE_URL").orElse("").get().trim()
        require(apiUrl.isNotBlank()) {
            "RideNova Passenger requires RIDENOVA_API_BASE_URL in Passenger gradle.properties. " +
            "Example: RIDENOVA_API_BASE_URL=http://127.0.0.1:8080 (requires adb reverse tcp:8080 tcp:8080). " +
            "Do not install an offline demo build."
        }
        require(apiUrl.isBlank() || apiUrl.matches(Regex("https?://[A-Za-z0-9.:-]+/?"))) { "Use a plain backend origin URL without credentials, query or path" }
        buildConfigField("String", "RIDENOVA_API_BASE_URL", "\"$apiUrl\"")
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
            buildConfigField("String", "RIDENOVA_API_BASE_URL", "\"$origin\"")
            require(origin.isEmpty() || origin.matches(Regex("https://[A-Za-z0-9.-]+/?"))) { "Staging requires a plain HTTPS origin" }
            tasks.matching { it.name == "preStagingBuild" }.configureEach {
                doFirst { require(origin.isNotBlank()) { "Set RIDENOVA_STAGING_API_BASE_URL to your deployed HTTPS API" } }
            }
        }
        getByName("release") {
            buildConfigField("String", "RIDENOVA_ENVIRONMENT", "\"production\"")
        }
    }
    tasks.matching { it.name == "preReleaseBuild" }.configureEach {
        doFirst { error("Public production release is gated until launch readiness is verified") }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }


    buildFeatures {
        compose = true
        buildConfig = true
    }

    packaging {
        resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2026.08.00")
    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation("androidx.core:core-ktx:1.19.0")
    implementation("androidx.activity:activity-compose:1.13.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.10.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.10.0")
    implementation("androidx.navigation:navigation-compose:2.10.1")

    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")

    // Live map, device location, and Google Places autocomplete.
    implementation("com.google.maps.android:maps-compose:8.4.0")
    implementation("com.google.android.gms:play-services-location:21.4.0")
    implementation("com.google.android.libraries.places:places:5.3.0")

    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}

secrets {
    propertiesFileName = "local.properties"
    defaultPropertiesFileName = "local.defaults.properties"
}

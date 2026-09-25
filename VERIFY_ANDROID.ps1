# Run after configuring Android SDK/JDK and Maps settings in Android Studio.
param([string]$StagingOrigin = "")
$ErrorActionPreference = "Stop"
$projects = @("Driver", "Passenger")
foreach ($project in $projects) {
    Push-Location (Join-Path $PSScriptRoot $project)
    try {
        & .\gradlew.bat :app:assembleDebug :app:lintDebug
        if ($LASTEXITCODE -ne 0) { throw "Android verification failed for $project" }
        if ($StagingOrigin) {
            & .\gradlew.bat :app:assembleStaging :app:lintStaging "-PRIDENOVA_STAGING_API_BASE_URL=$StagingOrigin"
            if ($LASTEXITCODE -ne 0) { throw "Staging verification failed for $project" }
        }
    } finally {
        Pop-Location
    }
}
Write-Host "Both Android builds and lint checks passed. Device testing is still required."

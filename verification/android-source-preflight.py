"""Build 42 Android source/configuration preflight; this is not an Android compilation."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


def balanced_kotlin(path):
    source = path.read_text(encoding='utf-8')
    # Remove comments and string/character literals before checking structural delimiters.
    scrubbed = re.sub(r'/\*[\s\S]*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', '', source)
    pairs = {')': '(', ']': '[', '}': '{'}
    stack = []
    for char in scrubbed:
        if char in '([{':
            stack.append(char)
        elif char in pairs:
            assert stack and stack.pop() == pairs[char], f'Unbalanced {char} in {path}'
    assert not stack, f'Unclosed delimiters {stack[-5:]} in {path}'


def main():
    passenger_gradle = (ROOT / 'Passenger/app/build.gradle.kts').read_text(encoding='utf-8')
    driver_gradle = (ROOT / 'Driver/app/build.gradle.kts').read_text(encoding='utf-8')
    assert 'versionName = "0.34.0-build42"' in passenger_gradle
    assert 'versionName = "0.19.0-build42"' in driver_gradle
    for project in ('Passenger', 'Driver'):
        staging_manifest = ROOT / project / 'app/src/staging/AndroidManifest.xml'
        ET.parse(staging_manifest)
        staging = staging_manifest.read_text(encoding='utf-8')
        assert 'android:usesCleartextTraffic="false"' in staging
        gradle = (ROOT / project / 'app/build.gradle.kts').read_text(encoding='utf-8')
        assert 'applicationIdSuffix = ".staging"' in gradle
        assert 'RIDENOVA_STAGING_API_BASE_URL' in gradle
        manifest = ROOT / project / 'app/src/main/AndroidManifest.xml'
        ET.parse(manifest)
        for path in (ROOT / project).rglob('*.kt'):
            balanced_kotlin(path)
        for path in (ROOT / project).rglob('*.kts'):
            balanced_kotlin(path)
    driver_manifest = (ROOT / 'Driver/app/src/main/AndroidManifest.xml').read_text(encoding='utf-8')
    for required in ('android.permission.FOREGROUND_SERVICE_LOCATION',
                     'android:foregroundServiceType="location"',
                     'android.permission.ACCESS_FINE_LOCATION'):
        assert required in driver_manifest, f'Missing Driver location requirement: {required}'
    http = (ROOT / 'Passenger/app/src/main/java/com/ridenova/passenger/data/RideNovaHttpClient.kt').read_text(encoding='utf-8')
    assert 'val connection = URL(endpoint).openConnection() as HttpURLConnection' in http
    repository = (ROOT / 'Passenger/app/src/main/java/com/ridenova/passenger/data/BackendRideNovaRepository.kt').read_text(encoding='utf-8')
    assert 'request.quoteToken != null' in repository and 'client.post("v1/passenger/rides", json)' in repository
    create_body = repository.split('override suspend fun createRide', 1)[1].split('override suspend fun cancelRide', 1)[0]
    assert '.put("draft"' not in create_body and 'draftJson(' not in create_body
    assert '.put("quoteToken", quoteToken)' in create_body
    assert '(json.opt("routeChangeReason") as? String)' in repository
    for relative in ('ui/DriverViewModel.kt', 'location/DriverLocationService.kt'):
        source = (ROOT/'Driver/app/src/main/java/com/ridenova/driver'/relative).read_text()
        assert 'BuildConfig.DEBUG && BuildConfig.RIDENOVA_DEV_URL' not in source
    print('PASS: Android manifests parse; Kotlin/Gradle delimiters and Build 42 source invariants are valid.')
    print('NOTE: This preflight does not replace Gradle compilation or real-device testing.')


if __name__ == '__main__':
    main()

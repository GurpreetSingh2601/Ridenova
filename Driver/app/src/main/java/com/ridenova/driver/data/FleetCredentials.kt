package com.ridenova.driver.data

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.io.File
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Per-install development credential; encrypted by Android Keystore and excluded from backups. */
class FleetCredentials(private val context: Context) {
    private val file = File(context.noBackupFilesDir, "fleet-credential")
    fun clear() {
        if (file.exists()) check(file.delete()) { "Could not clear saved driver access" }
        clearAccountCache()
    }
    fun clearAccountCache() {
        for (name in listOf("driver_demo_session", "driver_demo_trips", "driver_demo_profile")) {
            check(context.getSharedPreferences(name, Context.MODE_PRIVATE).edit().clear().commit()) { "Could not clear account cache" }
        }
    }
    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey("ridenova-fleet", null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder("ridenova-fleet", KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        }.generateKey()
    }
    fun load(): String = runCatching {
        val bytes = file.readBytes()
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, bytes.copyOfRange(0, 12)))
        String(cipher.doFinal(bytes.copyOfRange(12, bytes.size)), Charsets.UTF_8)
    }.getOrDefault("")
    fun save(token: String) {
        require(token.matches(Regex("[A-Za-z0-9_-]{30,128}"))) { "Invalid development token" }
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val temporary = File(file.parentFile, "fleet-credential.tmp")
        temporary.writeBytes(cipher.iv + cipher.doFinal(token.toByteArray(Charsets.UTF_8)))
        check(temporary.renameTo(file)) { "Could not save driver access" }
    }
}

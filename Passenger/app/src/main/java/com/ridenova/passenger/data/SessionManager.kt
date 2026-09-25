package com.ridenova.passenger.data

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import org.json.JSONObject
import java.security.KeyStore
import java.util.UUID
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Stores authentication tokens encrypted by an app-private Android Keystore key. */
class SessionManager(context: Context) {
    private val prefs = context.getSharedPreferences("ridenova_session", Context.MODE_PRIVATE)

    fun sessionId(): String = synchronized(this) {
        prefs.getString(KEY_SESSION_ID, null)?.takeIf { it.isNotBlank() } ?: UUID.randomUUID().toString().also {
            prefs.edit().putString(KEY_SESSION_ID, it).apply()
        }
    }

    @Synchronized fun accessToken(): String? = tokenJson()?.optString("accessToken")?.takeIf { it.isNotBlank() }
    @Synchronized fun refreshToken(): String? = tokenJson()?.optString("refreshToken")?.takeIf { it.isNotBlank() }
    @Synchronized fun isSignedIn(): Boolean = refreshToken() != null

    @Synchronized
    fun saveTokens(accessToken: String, refreshToken: String, accessExpiresAtEpochMs: Long, refreshExpiresAtEpochMs: Long) {
        val raw = JSONObject().put("accessToken", accessToken).put("refreshToken", refreshToken)
            .put("accessExpiresAtEpochMs", accessExpiresAtEpochMs).put("refreshExpiresAtEpochMs", refreshExpiresAtEpochMs).toString()
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, key())
        prefs.edit()
            .putString(KEY_TOKENS, Base64.encodeToString(cipher.doFinal(raw.toByteArray(Charsets.UTF_8)), Base64.NO_WRAP))
            .putString(KEY_IV, Base64.encodeToString(cipher.iv, Base64.NO_WRAP)).apply()
    }

    @Synchronized fun clearAuthentication() {
        prefs.edit().remove(KEY_TOKENS).remove(KEY_IV).apply()
    }

    private fun tokenJson(): JSONObject? = runCatching {
        val encrypted = Base64.decode(prefs.getString(KEY_TOKENS, null) ?: return null, Base64.NO_WRAP)
        val iv = Base64.decode(prefs.getString(KEY_IV, null) ?: return null, Base64.NO_WRAP)
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, iv))
        JSONObject(String(cipher.doFinal(encrypted), Charsets.UTF_8))
    }.getOrElse { clearAuthentication(); null }

    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").run {
            init(KeyGenParameterSpec.Builder(KEY_ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
            generateKey()
        }
    }

    private companion object {
        const val KEY_SESSION_ID = "session_id"
        const val KEY_TOKENS = "auth_tokens"
        const val KEY_IV = "auth_tokens_iv"
        const val KEY_ALIAS = "ridenova_auth_v019"
        const val TRANSFORMATION = "AES/GCM/NoPadding"
    }
}

package com.messageflow.app.data

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.Signature

/**
 * Device identity backed by the Android Keystore.
 *
 * The RSA keypair is generated inside the Keystore with
 * setUserAuthenticationRequired(false) so no biometric prompt is needed
 * for background signing. The private key can never be extracted; only
 * the public key (PEM) is ever sent to the backend.
 */
object KeystoreIdentity {
    private const val KEY_ALIAS = "messageflow_device_key"
    private const val ANDROID_KEYSTORE = "AndroidKeyStore"

    /** Returns the PEM-encoded public key, generating the keypair on first use. */
    fun getPublicKeyPem(): String {
        val keyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }
        val publicKey = if (keyStore.containsAlias(KEY_ALIAS)) {
            // Private keys are non-extractable; the public key is read
            // from the self-signed certificate the Keystore stores.
            keyStore.getCertificate(KEY_ALIAS).publicKey
        } else {
            generateKeyPair().public
        }
        return encodePem(publicKey)
    }

    private fun generateKeyPair(): java.security.KeyPair {
        val generator = KeyPairGenerator.getInstance(
            KeyProperties.KEY_ALGORITHM_RSA, ANDROID_KEYSTORE
        )
        generator.initialize(
            KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_SIGN or KeyProperties.PURPOSE_VERIFY
            )
                .setDigests(KeyProperties.DIGEST_SHA256)
                .setSignaturePaddings(KeyProperties.SIGNATURE_PADDING_RSA_PKCS1)
                .setKeySize(2048)
                .setUserAuthenticationRequired(false)
                .build()
        )
        return generator.generateKeyPair()
    }

    /** Sign [data] (the WS challenge nonce) with the Keystore private key. */
    fun sign(data: String): String {
        val keyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }
        if (!keyStore.containsAlias(KEY_ALIAS)) {
            throw IllegalStateException("Device key missing - pair the device first")
        }
        val privateKey = keyStore.getKey(KEY_ALIAS, null) as java.security.PrivateKey
        val signature = Signature.getInstance("SHA256withRSA")
        signature.initSign(privateKey)
        signature.update(data.toByteArray(Charsets.UTF_8))
        return Base64.encodeToString(signature.sign(), Base64.NO_WRAP)
    }

    private fun encodePem(publicKey: java.security.PublicKey): String {
        val encoded = Base64.encodeToString(publicKey.encoded, Base64.NO_WRAP)
        val wrapped = encoded.chunked(64).joinToString("\n")
        return "-----BEGIN PUBLIC KEY-----\n$wrapped\n-----END PUBLIC KEY-----\n"
    }
}

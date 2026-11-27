package com.trustcapture.vendor

import com.google.gson.JsonParser
import com.trustcapture.vendor.ui.inspection.InspectionRepeatForm
import java.security.KeyFactory
import java.security.MessageDigest
import java.security.Signature
import java.security.spec.X509EncodedKeySpec
import java.util.Base64
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class InspectionFormTest {
    @Test
    fun preservesRepeatOrderAndExactAnswerTypes() {
        val definition = JsonParser.parseString(
            """{"repeat_items":["second","first"],"repeat_fields":{"note":{"type":"text"},"reading":{"type":"number","scale":2,"unit":"mm"},"ok":{"type":"boolean"}}}"""
        ).asJsonObject
        val form = requireNotNull(InspectionRepeatForm.parse(definition))
        assertEquals(listOf("second", "first"), form.itemIds)
        val (note, reading, ok) = form.fields
        assertEquals("\"note\"", note.encode("note").toString())
        assertEquals("""{"value":"2.00","scale":2,"unit":"mm"}""", reading.encode("2.00").toString())
        assertNull(reading.encode("2.0"))
        assertNull(reading.encode("02.00"))
        assertEquals("false", ok.encode("false").toString())
    }

    @Test
    fun verifiesBackendSignatureOverUtf8LowercaseDigest() {
        val (original, expectedDigest, signature, publicKey) =
            requireNotNull(javaClass.getResourceAsStream("/gate1-signing-vector.txt"))
                .bufferedReader().use { it.readLines() }
        val decoder = Base64.getDecoder()
        val digest = MessageDigest.getInstance("SHA-256").digest(decoder.decode(original))
        assertEquals(expectedDigest, digest.joinToString("") { "%02x".format(it) })
        val key = KeyFactory.getInstance("EC").generatePublic(X509EncodedKeySpec(decoder.decode(publicKey)))
        val verifier = Signature.getInstance("SHA256withECDSA")
        verifier.initVerify(key)
        verifier.update(expectedDigest.toByteArray(Charsets.UTF_8))
        assertTrue(verifier.verify(decoder.decode(signature)))
        verifier.update(digest)
        assertFalse(verifier.verify(decoder.decode(signature)))
    }
}

package com.trustcapture.vendor

import com.trustcapture.vendor.data.remote.dto.InspectionPackageDto
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

class InspectionPackageDecodingTest {
    @Test
    fun decodesSanitizedStagingPackage() {
        val json = requireNotNull(javaClass.getResourceAsStream("/gate1-staging-package-sanitized.json"))
            .bufferedReader().use { it.readText() }
        val retrofit = Retrofit.Builder()
            .baseUrl("https://example.invalid/")
            .addConverterFactory(GsonConverterFactory.create())
            .build()
        val converter = retrofit.responseBodyConverter<InspectionPackageDto>(
            InspectionPackageDto::class.java, emptyArray()
        )
        val body = requireNotNull(converter.convert(json.toResponseBody("application/json".toMediaType())))

        assertEquals("PACKAGE_READY", body.code)
        val condition = body.documentRequirements.single().activationCondition
        assertTrue(condition == null || condition.isJsonNull)
        val document = body.documents.single()
        val repeatItems = document.definition.getAsJsonArray("repeat_items")
        assertEquals(2, repeatItems.size())
        val target = document.captureTargets.single()
        assertEquals(repeatItems[1].asString, target.repeatItemId)
        assertTrue(target.required)
    }
}

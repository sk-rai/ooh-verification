package com.trustcapture.vendor.data.remote.interceptor

import com.trustcapture.vendor.data.local.datastore.UserPreferences
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import okhttp3.Interceptor
import okhttp3.Response
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class TenantInterceptor @Inject constructor(
    private val userPreferences: UserPreferences
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val tenantId = runBlocking { userPreferences.tenantId.first() }
        val request = if (!tenantId.isNullOrBlank()) {
            chain.request().newBuilder()
                .addHeader("X-Tenant-ID", tenantId)
                .build()
        } else {
            chain.request()
        }
        return chain.proceed(request)
    }
}

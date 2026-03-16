package com.trustcapture.vendor.domain.validator

import com.trustcapture.vendor.data.local.db.CampaignDao
import com.trustcapture.vendor.data.local.entity.CampaignEntity
import com.trustcapture.vendor.data.remote.api.CampaignApi
import com.trustcapture.vendor.util.Resource
import kotlinx.coroutines.withTimeoutOrNull
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Validates campaign codes with local caching and server refresh.
 *
 * - Checks local cache first (valid for 30 minutes)
 * - Refreshes assigned campaigns from server with 3-second timeout
 * - Returns cached result if server is unreachable
 * - Validates campaign code format before any lookup
 */
@Singleton
class CampaignValidator @Inject constructor(
    private val campaignApi: CampaignApi,
    private val campaignDao: CampaignDao
) {
    companion object {
        private const val CACHE_TTL_MS = 30 * 60 * 1000L // 30 minutes
        private const val NETWORK_TIMEOUT_MS = 3000L
        private val CODE_PATTERN = Regex("^[A-Za-z0-9\\-]{3,30}$")
    }

    /**
     * Validates a campaign code. Returns the campaign if valid, or an error.
     */
    suspend fun validate(code: String): Resource<CampaignEntity> {
        val trimmed = code.trim().uppercase()

        if (!CODE_PATTERN.matches(trimmed)) {
            return Resource.Error("Invalid campaign code format")
        }

        // Check local cache
        val cached = campaignDao.getByCode(trimmed)
        if (cached != null) {
            val age = System.currentTimeMillis() - cached.lastValidatedAt
            if (age < CACHE_TTL_MS) {
                return if (cached.status.equals("active", ignoreCase = true)) {
                    Resource.Success(cached)
                } else {
                    Resource.Error("Campaign is ${cached.status}")
                }
            }
        }

        // Refresh from server with timeout
        val refreshed = withTimeoutOrNull(NETWORK_TIMEOUT_MS) {
            try {
                val response = campaignApi.getAssignedCampaigns()
                if (response.isSuccessful) {
                    response.body()?.campaigns?.map { dto ->
                        CampaignEntity(
                            campaignId = dto.campaignId,
                            campaignCode = dto.campaignCode,
                            name = dto.name,
                            campaignType = dto.campaignType,
                            startDate = dto.startDate,
                            endDate = dto.endDate,
                            status = dto.status,
                            lastValidatedAt = System.currentTimeMillis()
                        )
                    }
                } else null
            } catch (_: Exception) { null }
        }

        if (refreshed != null) {
            campaignDao.deleteAll()
            campaignDao.insertAll(refreshed)
            val match = refreshed.find { it.campaignCode.equals(trimmed, ignoreCase = true) }
            return if (match != null) {
                if (match.status.equals("active", ignoreCase = true)) {
                    Resource.Success(match)
                } else {
                    Resource.Error("Campaign is ${match.status}")
                }
            } else {
                Resource.Error("Campaign not found or not assigned to you: $trimmed")
            }
        }

        // Timeout — fall back to stale cache
        if (cached != null && cached.status.equals("active", ignoreCase = true)) {
            return Resource.Success(cached)
        }

        return Resource.Error("Server unreachable and no cached data for $trimmed")
    }
}

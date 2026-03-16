package com.trustcapture.vendor.domain.model

/**
 * Supported campaign types mapped from backend campaign_type field.
 */
enum class CampaignType(val key: String) {
    OOH("ooh"),
    CONSTRUCTION("construction"),
    INSURANCE("insurance"),
    DELIVERY("delivery"),
    HEALTHCARE("healthcare"),
    PROPERTY_MANAGEMENT("property_management"),
    GENERAL("general");

    companion object {
        fun fromString(value: String): CampaignType =
            entries.find { it.key.equals(value, ignoreCase = true) } ?: GENERAL
    }
}

/**
 * Configuration flags derived from campaign type.
 * Core sensor capture + crypto signing remain the same for all types (Req 18.7).
 */
data class CampaignTypeConfig(
    val type: CampaignType,
    /** Construction: require safety compliance tags (Req 18.1) */
    val requiresSafetyTags: Boolean = false,
    /** Insurance: allow multiple photos per claim with sequential numbering (Req 18.2) */
    val allowMultiPhoto: Boolean = false,
    /** Delivery: capture recipient signature (Req 18.3) */
    val requiresSignature: Boolean = false,
    /** Healthcare: enforce HIPAA-compliant encryption and audit logging (Req 18.4) */
    val enforceHipaa: Boolean = false,
    /** Property management: room-by-room photo organization (Req 18.5) */
    val roomOrganization: Boolean = false,
    /** Human-readable label for UI display */
    val displayLabel: String = "General"
) {
    companion object {
        fun forType(type: CampaignType): CampaignTypeConfig = when (type) {
            CampaignType.OOH -> CampaignTypeConfig(
                type = type,
                displayLabel = "Out-of-Home"
            )
            CampaignType.CONSTRUCTION -> CampaignTypeConfig(
                type = type,
                requiresSafetyTags = true,
                displayLabel = "Construction"
            )
            CampaignType.INSURANCE -> CampaignTypeConfig(
                type = type,
                allowMultiPhoto = true,
                displayLabel = "Insurance"
            )
            CampaignType.DELIVERY -> CampaignTypeConfig(
                type = type,
                requiresSignature = true,
                displayLabel = "Delivery"
            )
            CampaignType.HEALTHCARE -> CampaignTypeConfig(
                type = type,
                enforceHipaa = true,
                displayLabel = "Healthcare"
            )
            CampaignType.PROPERTY_MANAGEMENT -> CampaignTypeConfig(
                type = type,
                roomOrganization = true,
                displayLabel = "Property Management"
            )
            CampaignType.GENERAL -> CampaignTypeConfig(
                type = type,
                displayLabel = "General"
            )
        }

        fun fromString(campaignTypeStr: String): CampaignTypeConfig =
            forType(CampaignType.fromString(campaignTypeStr))
    }
}

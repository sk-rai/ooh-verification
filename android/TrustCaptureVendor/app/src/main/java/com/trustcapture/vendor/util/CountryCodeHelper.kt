package com.trustcapture.vendor.util

import android.content.Context
import android.telephony.TelephonyManager
import java.util.Locale

/**
 * Resolves the phone country dial code from the device's SIM or locale.
 * Priority: SIM country → network country → device locale.
 */
object CountryCodeHelper {

    /** Returns dial code with '+' prefix, e.g. "+91", "+1", "+44". */
    fun getDialCode(context: Context): String {
        val tm = context.getSystemService(Context.TELEPHONY_SERVICE) as? TelephonyManager
        val countryIso = tm?.simCountryIso?.uppercase()
            ?: tm?.networkCountryIso?.uppercase()
            ?: Locale.getDefault().country.uppercase()
        return COUNTRY_DIAL_CODES[countryIso] ?: "+1" // default to US if unknown
    }

    /** Returns 2-letter ISO country code, e.g. "IN", "US", "GB". */
    fun getCountryIso(context: Context): String {
        val tm = context.getSystemService(Context.TELEPHONY_SERVICE) as? TelephonyManager
        return (tm?.simCountryIso?.uppercase()
            ?: tm?.networkCountryIso?.uppercase()
            ?: Locale.getDefault().country.uppercase())
    }

    // Common country dial codes — covers major markets
    private val COUNTRY_DIAL_CODES = mapOf(
        "AF" to "+93", "AL" to "+355", "DZ" to "+213", "AR" to "+54",
        "AU" to "+61", "AT" to "+43", "BD" to "+880", "BE" to "+32",
        "BR" to "+55", "CA" to "+1", "CL" to "+56", "CN" to "+86",
        "CO" to "+57", "CZ" to "+420", "DK" to "+45", "EG" to "+20",
        "FI" to "+358", "FR" to "+33", "DE" to "+49", "GH" to "+233",
        "GR" to "+30", "HK" to "+852", "HU" to "+36", "IN" to "+91",
        "ID" to "+62", "IR" to "+98", "IQ" to "+964", "IE" to "+353",
        "IL" to "+972", "IT" to "+39", "JP" to "+81", "KE" to "+254",
        "KR" to "+82", "KW" to "+965", "MY" to "+60", "MX" to "+52",
        "MA" to "+212", "NL" to "+31", "NZ" to "+64", "NG" to "+234",
        "NO" to "+47", "PK" to "+92", "PE" to "+51", "PH" to "+63",
        "PL" to "+48", "PT" to "+351", "QA" to "+974", "RO" to "+40",
        "RU" to "+7", "SA" to "+966", "SG" to "+65", "ZA" to "+27",
        "ES" to "+34", "LK" to "+94", "SE" to "+46", "CH" to "+41",
        "TW" to "+886", "TH" to "+66", "TR" to "+90", "AE" to "+971",
        "GB" to "+44", "US" to "+1", "VN" to "+84", "ZW" to "+263",
        "NP" to "+977", "MM" to "+95", "KH" to "+855", "ET" to "+251",
        "TZ" to "+255", "UG" to "+256", "UA" to "+380", "UZ" to "+998"
    )
}

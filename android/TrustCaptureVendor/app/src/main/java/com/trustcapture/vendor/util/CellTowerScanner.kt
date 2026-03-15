package com.trustcapture.vendor.util

import android.annotation.SuppressLint
import android.content.Context
import android.os.Build
import android.telephony.CellIdentityGsm
import android.telephony.CellIdentityLte
import android.telephony.CellIdentityNr
import android.telephony.CellIdentityWcdma
import android.telephony.CellInfo
import android.telephony.CellInfoGsm
import android.telephony.CellInfoLte
import android.telephony.CellInfoNr
import android.telephony.CellInfoWcdma
import android.telephony.CellSignalStrengthNr
import android.telephony.TelephonyManager
import javax.inject.Inject
import javax.inject.Singleton

/**
 * A single cell tower observation.
 */
data class CellTowerInfo(
    val cellId: Int,
    val lac: Int,
    val mcc: Int,
    val mnc: Int,
    val signalDbm: Int,
    val networkType: String
)

/**
 * Result of a cell tower scan.
 */
data class CellTowerScanResult(
    val towers: List<CellTowerInfo>,
    val scanTimestamp: Long = System.currentTimeMillis()
)

/**
 * Scans for nearby cell towers using TelephonyManager.
 * Captures Cell ID, LAC, MCC, MNC, signal strength, and network type.
 *
 * On emulator, cell tower data is typically unavailable or returns
 * placeholder values — this is expected and handled gracefully.
 */
@Singleton
class CellTowerScanner @Inject constructor() {

    /**
     * Gets current cell tower information.
     * Returns all visible towers sorted by signal strength.
     */
    @SuppressLint("MissingPermission")
    fun scan(context: Context): CellTowerScanResult {
        val telephony = context.getSystemService(Context.TELEPHONY_SERVICE)
            as? TelephonyManager ?: return CellTowerScanResult(emptyList())

        return try {
            val cellInfoList = telephony.allCellInfo ?: emptyList()
            val towers = cellInfoList.mapNotNull { parseCellInfo(it) }
                .sortedByDescending { it.signalDbm }
            CellTowerScanResult(towers = towers)
        } catch (_: Exception) {
            CellTowerScanResult(emptyList())
        }
    }

    private fun parseCellInfo(info: CellInfo): CellTowerInfo? {
        return when (info) {
            is CellInfoLte -> parseLte(info)
            is CellInfoWcdma -> parseWcdma(info)
            is CellInfoGsm -> parseGsm(info)
            else -> {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q && info is CellInfoNr) {
                    parseNr(info)
                } else null
            }
        }
    }

    private fun parseLte(info: CellInfoLte): CellTowerInfo? {
        val id = info.cellIdentity as CellIdentityLte
        val cid = id.ci
        if (cid == Int.MAX_VALUE) return null // Unknown
        return CellTowerInfo(
            cellId = cid,
            lac = id.tac,
            mcc = id.mccString?.toIntOrNull() ?: 0,
            mnc = id.mncString?.toIntOrNull() ?: 0,
            signalDbm = info.cellSignalStrength.dbm,
            networkType = "LTE"
        )
    }

    private fun parseWcdma(info: CellInfoWcdma): CellTowerInfo? {
        val id = info.cellIdentity as CellIdentityWcdma
        val cid = id.cid
        if (cid == Int.MAX_VALUE) return null
        return CellTowerInfo(
            cellId = cid,
            lac = id.lac,
            mcc = id.mccString?.toIntOrNull() ?: 0,
            mnc = id.mncString?.toIntOrNull() ?: 0,
            signalDbm = info.cellSignalStrength.dbm,
            networkType = "WCDMA"
        )
    }

    private fun parseGsm(info: CellInfoGsm): CellTowerInfo? {
        val id = info.cellIdentity as CellIdentityGsm
        val cid = id.cid
        if (cid == Int.MAX_VALUE) return null
        return CellTowerInfo(
            cellId = cid,
            lac = id.lac,
            mcc = id.mccString?.toIntOrNull() ?: 0,
            mnc = id.mncString?.toIntOrNull() ?: 0,
            signalDbm = info.cellSignalStrength.dbm,
            networkType = "GSM"
        )
    }

    private fun parseNr(info: CellInfoNr): CellTowerInfo? {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return null
        val id = info.cellIdentity as CellIdentityNr
        val nci = id.nci.toInt()
        if (nci == Int.MAX_VALUE) return null
        return CellTowerInfo(
            cellId = nci,
            lac = id.tac,
            mcc = id.mccString?.toIntOrNull() ?: 0,
            mnc = id.mncString?.toIntOrNull() ?: 0,
            signalDbm = (info.cellSignalStrength as CellSignalStrengthNr).dbm,
            networkType = "5G NR"
        )
    }
}

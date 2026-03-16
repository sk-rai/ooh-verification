package com.trustcapture.vendor.util

import android.content.Context
import android.os.Build
import android.provider.Settings
import android.util.Log
import dagger.hilt.android.qualifiers.ApplicationContext
import java.io.File
import javax.inject.Inject
import javax.inject.Singleton

private const val TAG = "SecurityManager"

/**
 * Device security assessment: root detection, emulator detection, and integrity flags.
 * Results are cached after first check and included in audit records + upload metadata.
 */
@Singleton
class SecurityManager @Inject constructor(
    @ApplicationContext private val context: Context
) {
    data class SecurityAssessment(
        val isRooted: Boolean = false,
        val rootIndicators: List<String> = emptyList(),
        val isEmulator: Boolean = false,
        val emulatorIndicators: List<String> = emptyList(),
        val integrityFlags: List<String> = emptyList()
    ) {
        /** Flags to attach to audit records and upload payloads */
        fun toAuditFlags(): List<String> {
            val flags = mutableListOf<String>()
            if (isRooted) flags.add("ROOTED_DEVICE")
            if (isEmulator) flags.add("EMULATOR_MODE")
            flags.addAll(integrityFlags)
            return flags
        }

        fun toJson(): String {
            val sb = StringBuilder("{")
            sb.append("\"is_rooted\":$isRooted,")
            sb.append("\"root_indicators\":[${rootIndicators.joinToString(",") { "\"$it\"" }}],")
            sb.append("\"is_emulator\":$isEmulator,")
            sb.append("\"emulator_indicators\":[${emulatorIndicators.joinToString(",") { "\"$it\"" }}],")
            sb.append("\"integrity_flags\":[${toAuditFlags().joinToString(",") { "\"$it\"" }}]")
            sb.append("}")
            return sb.toString()
        }
    }

    @Volatile
    private var cachedAssessment: SecurityAssessment? = null

    /** Run full security check (cached after first call). */
    fun assess(): SecurityAssessment {
        cachedAssessment?.let { return it }
        val assessment = SecurityAssessment(
            isRooted = checkRoot().first,
            rootIndicators = checkRoot().second,
            isEmulator = checkEmulator().first,
            emulatorIndicators = checkEmulator().second
        )
        cachedAssessment = assessment
        Log.i(TAG, "Security assessment: rooted=${assessment.isRooted}, emulator=${assessment.isEmulator}, flags=${assessment.toAuditFlags()}")
        return assessment
    }

    // ── Root Detection ──────────────────────────────────────────────────

    private fun checkRoot(): Pair<Boolean, List<String>> {
        val indicators = mutableListOf<String>()

        // 1. Check for su binary in common paths
        val suPaths = listOf(
            "/system/bin/su", "/system/xbin/su", "/sbin/su",
            "/data/local/xbin/su", "/data/local/bin/su",
            "/system/sd/xbin/su", "/system/bin/failsafe/su",
            "/data/local/su", "/su/bin/su"
        )
        for (path in suPaths) {
            if (File(path).exists()) {
                indicators.add("su_binary:$path")
            }
        }

        // 2. Check for root management apps
        val rootApps = listOf(
            "com.topjohnwu.magisk",          // Magisk
            "eu.chainfire.supersu",           // SuperSU
            "com.koushikdutta.superuser",     // Superuser
            "com.noshufou.android.su",        // Superuser (older)
            "com.thirdparty.superuser",       // Another superuser
            "com.yellowes.su",                // Root checker
            "com.kingroot.kinguser",          // KingRoot
            "com.kingo.root",                 // KingoRoot
            "com.smedialink.oneclickroot",    // One Click Root
            "com.zhiqupk.root.global"         // iRoot
        )
        val pm = context.packageManager
        for (pkg in rootApps) {
            try {
                pm.getPackageInfo(pkg, 0)
                indicators.add("root_app:$pkg")
            } catch (_: Exception) {
                // Not installed
            }
        }

        // 3. Check build tags
        val buildTags = Build.TAGS ?: ""
        if (buildTags.contains("test-keys")) {
            indicators.add("test_keys")
        }

        // 4. Check for Magisk hide paths
        val magiskPaths = listOf(
            "/sbin/.magisk", "/data/adb/magisk",
            "/cache/.disable_magisk"
        )
        for (path in magiskPaths) {
            if (File(path).exists()) {
                indicators.add("magisk_path:$path")
            }
        }

        // 5. Check if /system is writable
        try {
            val mount = Runtime.getRuntime().exec("mount")
            val output = mount.inputStream.bufferedReader().readText()
            if (output.contains("/system") && output.contains("rw")) {
                indicators.add("system_rw")
            }
        } catch (_: Exception) { }

        return Pair(indicators.isNotEmpty(), indicators)
    }

    // ── Emulator Detection ──────────────────────────────────────────────

    private fun checkEmulator(): Pair<Boolean, List<String>> {
        val indicators = mutableListOf<String>()

        // 1. Build properties
        if (Build.FINGERPRINT.contains("generic") || Build.FINGERPRINT.contains("unknown")) {
            indicators.add("fingerprint_generic")
        }
        if (Build.MODEL.contains("google_sdk") || Build.MODEL.contains("Emulator") ||
            Build.MODEL.contains("Android SDK built for x86") || Build.MODEL.contains("sdk_gphone")) {
            indicators.add("model_emulator")
        }
        if (Build.MANUFACTURER.contains("Genymotion")) {
            indicators.add("genymotion")
        }
        if (Build.BRAND.startsWith("generic") && Build.DEVICE.startsWith("generic")) {
            indicators.add("generic_brand_device")
        }
        if (Build.PRODUCT.contains("sdk") || Build.PRODUCT.contains("emulator") ||
            Build.PRODUCT.contains("simulator")) {
            indicators.add("product_sdk")
        }
        if (Build.HARDWARE.contains("goldfish") || Build.HARDWARE.contains("ranchu")) {
            indicators.add("hardware_emulator")
        }
        if (Build.BOARD.contains("unknown") || Build.BOARD == "") {
            indicators.add("board_unknown")
        }

        // 2. Check for emulator-specific files
        val emuFiles = listOf(
            "/dev/socket/qemud", "/dev/qemu_pipe",
            "/system/lib/libc_malloc_debug_qemu.so",
            "/sys/qemu_trace", "/system/bin/qemu-props"
        )
        for (path in emuFiles) {
            if (File(path).exists()) {
                indicators.add("emu_file:$path")
            }
        }

        // 3. Check for QEMU driver
        try {
            val drivers = File("/proc/tty/drivers").readText()
            if (drivers.contains("goldfish")) {
                indicators.add("goldfish_driver")
            }
        } catch (_: Exception) { }

        return Pair(indicators.isNotEmpty(), indicators)
    }
}

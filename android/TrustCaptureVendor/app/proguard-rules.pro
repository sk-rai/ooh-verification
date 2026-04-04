# ── TrustCapture ProGuard Rules ──

# Keep line numbers for crash reports
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile

# ── Retrofit + OkHttp ──
-keepattributes Signature
-keepattributes *Annotation*
-keep class retrofit2.** { *; }
-keepclasseswithmembers class * {
    @retrofit2.http.* <methods>;
}
-dontwarn retrofit2.**
-dontwarn okhttp3.**
-dontwarn okio.**
-keep class okhttp3.** { *; }
-keep class okio.** { *; }

# ── Gson ──
-keepattributes Signature
-keep class com.google.gson.** { *; }
-keep class * implements com.google.gson.TypeAdapterFactory
-keep class * implements com.google.gson.JsonSerializer
-keep class * implements com.google.gson.JsonDeserializer
# Keep all DTO classes (Gson uses reflection)
-keep class com.trustcapture.vendor.data.remote.dto.** { *; }
-keep class com.trustcapture.vendor.data.local.entity.** { *; }
-keep class com.trustcapture.vendor.domain.model.** { *; }

# ── Room ──
-keep class * extends androidx.room.RoomDatabase
-keep @androidx.room.Entity class *
-keep @androidx.room.Dao class *
-dontwarn androidx.room.paging.**

# ── Hilt / Dagger ──
-keep class dagger.hilt.** { *; }
-keep class javax.inject.** { *; }
-keep class * extends dagger.hilt.android.internal.managers.ViewComponentManager$FragmentContextWrapper { *; }
-dontwarn dagger.hilt.**

# ── SQLCipher ──
-keep class net.sqlcipher.** { *; }
-dontwarn net.sqlcipher.**

# ── CameraX ──
-keep class androidx.camera.** { *; }
-dontwarn androidx.camera.**

# ── WorkManager + HiltWorker ──
-keep class * extends androidx.work.Worker
-keep class * extends androidx.work.CoroutineWorker
-keep class * extends androidx.work.ListenableWorker
-keep @androidx.hilt.work.HiltWorker class * { *; }

# ── Compose ──
-dontwarn androidx.compose.**

# ── Play Services Location ──
-keep class com.google.android.gms.** { *; }
-dontwarn com.google.android.gms.**

# ── DataStore ──
-keep class androidx.datastore.** { *; }

# ── Kotlin Coroutines ──
-dontwarn kotlinx.coroutines.**
-keep class kotlinx.coroutines.** { *; }

# ── Coil ──
-dontwarn coil.**

# ── App-specific: keep Resource sealed class ──
-keep class com.trustcapture.vendor.util.Resource { *; }
-keep class com.trustcapture.vendor.util.Resource$* { *; }

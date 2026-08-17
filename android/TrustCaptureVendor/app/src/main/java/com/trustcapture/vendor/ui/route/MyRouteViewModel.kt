package com.trustcapture.vendor.ui.route

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.trustcapture.vendor.data.local.dao.TrackingDao
import com.trustcapture.vendor.data.local.entity.TrackingPointEntity
import com.trustcapture.vendor.domain.repository.TrackingRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.util.Calendar
import javax.inject.Inject
import kotlin.math.*

data class MyRouteUiState(
    val points: List<TrackingPointEntity> = emptyList(),
    val totalPoints: Int = 0,
    val durationText: String = "--",
    val distanceText: String = "--",
    val unsyncedCount: Int = 0,
    val isSyncing: Boolean = false,
    val lastSyncResult: String? = null,
    val isLoading: Boolean = true
)

@HiltViewModel
class MyRouteViewModel @Inject constructor(
    private val trackingDao: TrackingDao,
    private val trackingRepository: TrackingRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(MyRouteUiState())
    val uiState: StateFlow<MyRouteUiState> = _uiState.asStateFlow()

    init {
        loadTodayPoints()
    }

    fun loadTodayPoints() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)

            val startOfDay = getStartOfToday()
            val points = trackingDao.getTodayPoints(startOfDay)
            val unsyncedCount = trackingDao.getUnsyncedCount()

            val duration = calculateDuration(points)
            val distance = calculateDistance(points)

            _uiState.value = MyRouteUiState(
                points = points,
                totalPoints = points.size,
                durationText = duration,
                distanceText = distance,
                unsyncedCount = unsyncedCount,
                isSyncing = false,
                lastSyncResult = _uiState.value.lastSyncResult,
                isLoading = false
            )
        }
    }

    fun syncNow() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isSyncing = true, lastSyncResult = null)
            val success = trackingRepository.syncToBackend()
            val unsyncedCount = trackingDao.getUnsyncedCount()
            _uiState.value = _uiState.value.copy(
                isSyncing = false,
                unsyncedCount = unsyncedCount,
                lastSyncResult = if (success) "All points synced ✓" else "Sync failed — will retry"
            )
        }
    }

    private fun getStartOfToday(): Long {
        val cal = Calendar.getInstance().apply {
            set(Calendar.HOUR_OF_DAY, 0)
            set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }
        return cal.timeInMillis
    }

    private fun calculateDuration(points: List<TrackingPointEntity>): String {
        if (points.size < 2) return "--"
        val first = points.first().timestampMs
        val last = points.last().timestampMs
        val diffMs = last - first
        val hours = diffMs / (1000 * 60 * 60)
        val minutes = (diffMs % (1000 * 60 * 60)) / (1000 * 60)
        return if (hours > 0) "${hours}h ${minutes}m" else "${minutes}m"
    }

    private fun calculateDistance(points: List<TrackingPointEntity>): String {
        if (points.size < 2) return "--"
        var totalMeters = 0.0
        for (i in 0 until points.size - 1) {
            totalMeters += haversine(
                points[i].latitude, points[i].longitude,
                points[i + 1].latitude, points[i + 1].longitude
            )
        }
        return if (totalMeters < 1000) {
            "${totalMeters.roundToInt()} m"
        } else {
            "${"%.1f".format(totalMeters / 1000)} km"
        }
    }

    /**
     * Haversine formula: calculates distance between two GPS points in meters.
     */
    private fun haversine(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
        val R = 6371000.0 // Earth radius in meters
        val dLat = Math.toRadians(lat2 - lat1)
        val dLon = Math.toRadians(lon2 - lon1)
        val a = sin(dLat / 2).pow(2) +
                cos(Math.toRadians(lat1)) * cos(Math.toRadians(lat2)) *
                sin(dLon / 2).pow(2)
        val c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return R * c
    }
}

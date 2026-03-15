package com.trustcapture.vendor.data.local.db

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.trustcapture.vendor.data.local.entity.CampaignEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface CampaignDao {

    @Query("SELECT * FROM campaigns ORDER BY name ASC")
    fun getAllCampaigns(): Flow<List<CampaignEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(campaigns: List<CampaignEntity>)

    @Query("DELETE FROM campaigns")
    suspend fun deleteAll()
}

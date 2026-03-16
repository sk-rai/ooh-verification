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

    @Query("SELECT * FROM campaigns WHERE campaignCode = :code LIMIT 1")
    suspend fun getByCode(code: String): CampaignEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(campaigns: List<CampaignEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(campaign: CampaignEntity)

    @Query("DELETE FROM campaigns")
    suspend fun deleteAll()
}

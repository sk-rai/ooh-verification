package com.trustcapture.vendor.di

import com.trustcapture.vendor.BuildConfig
import com.trustcapture.vendor.data.remote.api.AuthApi
import com.trustcapture.vendor.data.remote.api.CampaignApi
import com.trustcapture.vendor.data.remote.api.PhotoApi
import com.trustcapture.vendor.data.remote.interceptor.AuthInterceptor
import com.trustcapture.vendor.data.remote.interceptor.TenantInterceptor
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {

    @Provides
    @Singleton
    fun provideLoggingInterceptor(): HttpLoggingInterceptor =
        HttpLoggingInterceptor().apply {
            level = if (BuildConfig.DEBUG)
                HttpLoggingInterceptor.Level.BODY
            else
                HttpLoggingInterceptor.Level.NONE
        }

    @Provides
    @Singleton
    fun provideOkHttpClient(
        loggingInterceptor: HttpLoggingInterceptor,
        authInterceptor: AuthInterceptor,
        tenantInterceptor: TenantInterceptor
    ): OkHttpClient =
        OkHttpClient.Builder()
            .addInterceptor(tenantInterceptor)
            .addInterceptor(authInterceptor)
            .addInterceptor(loggingInterceptor)
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(60, TimeUnit.SECONDS)
            .build()

    @Provides
    @Singleton
    fun provideRetrofit(okHttpClient: OkHttpClient): Retrofit =
        Retrofit.Builder()
            .baseUrl(BuildConfig.BASE_URL)
            .client(okHttpClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()

    @Provides
    @Singleton
    fun provideAuthApi(retrofit: Retrofit): AuthApi =
        retrofit.create(AuthApi::class.java)

    @Provides
    @Singleton
    fun provideCampaignApi(retrofit: Retrofit): CampaignApi =
        retrofit.create(CampaignApi::class.java)

    @Provides
    @Singleton
    fun providePhotoApi(retrofit: Retrofit): PhotoApi =
        retrofit.create(PhotoApi::class.java)
}

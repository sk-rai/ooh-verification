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
import okhttp3.CertificatePinner
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

/**
 * Certificate pins for api.trustcapture.com
 * 
 * IMPORTANT: Replace these placeholder pins with actual SHA-256 fingerprints before release.
 * 
 * To generate pins from your server certificate:
 * openssl s_client -connect api.trustcapture.com:443 | openssl x509 -pubkey -noout | \
 *     openssl pkey -pubin -outform der | openssl dgst -sha256 -binary | openssl enc -base64
 * 
 * Best practice: Pin to intermediate CA certificate for easier rotation.
 * Include a backup pin for key rotation scenarios.
 */
private object CertPins {
    const val PRODUCTION_HOST = "api.trustcapture.com"
    // TODO: Replace with actual certificate SHA-256 pins before production release
    const val PRIMARY_PIN = "sha256/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    const val BACKUP_PIN = "sha256/BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB="
}

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {

    @Provides
    @Singleton
    fun provideLoggingInterceptor(): HttpLoggingInterceptor =
        HttpLoggingInterceptor().apply {
            level = if (BuildConfig.DEBUG)
                HttpLoggingInterceptor.Level.HEADERS
            else
                HttpLoggingInterceptor.Level.NONE
        }

    @Provides
    @Singleton
    fun provideCertificatePinner(): CertificatePinner =
        if (BuildConfig.DEBUG) {
            // No pinning in debug — allows emulator HTTP to 10.0.2.2
            CertificatePinner.DEFAULT
        } else {
            CertificatePinner.Builder()
                .add(CertPins.PRODUCTION_HOST, CertPins.PRIMARY_PIN)
                .add(CertPins.PRODUCTION_HOST, CertPins.BACKUP_PIN)
                .build()
        }

    @Provides
    @Singleton
    fun provideOkHttpClient(
        loggingInterceptor: HttpLoggingInterceptor,
        authInterceptor: AuthInterceptor,
        tenantInterceptor: TenantInterceptor,
        certificatePinner: CertificatePinner
    ): OkHttpClient =
        OkHttpClient.Builder()
            .addInterceptor(tenantInterceptor)
            .addInterceptor(authInterceptor)
            .addInterceptor(loggingInterceptor)
            .certificatePinner(certificatePinner)
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

package com.trustcapture.vendor.util

import com.google.gson.Gson
import retrofit2.Response

data class ApiError(val detail: String = "Unknown error")

suspend fun <T> safeApiCall(call: suspend () -> Response<T>): Resource<T> {
    return try {
        val response = call()
        if (response.isSuccessful) {
            response.body()?.let {
                Resource.Success(it)
            } ?: Resource.Error("Empty response body")
        } else {
            val errorBody = response.errorBody()?.string()
            val message = try {
                Gson().fromJson(errorBody, ApiError::class.java).detail
            } catch (e: Exception) {
                errorBody ?: "Unknown error"
            }
            Resource.Error(message, response.code())
        }
    } catch (e: Exception) {
        Resource.Error(e.localizedMessage ?: "Network error")
    }
}

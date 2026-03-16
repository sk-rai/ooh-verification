package com.trustcapture.vendor.util

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Matrix
import android.graphics.Paint
import android.graphics.Rect
import android.graphics.Typeface
import android.net.Uri
import android.content.Context
import androidx.exifinterface.media.ExifInterface
import java.io.File
import java.io.FileOutputStream
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

data class WatermarkData(
    val latitude: Double?,
    val longitude: Double?,
    val accuracy: Float?,
    val campaignCode: String,
    val vendorId: String,
    val timestamp: Date = Date()
)

object WatermarkGenerator {

    /**
     * Burns watermark into photo pixels. Returns URI of the watermarked file.
     * The watermark is rendered in the bottom 15% of the image with a
     * semi-transparent black background, using monospace font.
     *
     * Uses BitmapFactory.Options.inSampleSize to downsample large photos
     * before processing, reducing memory usage significantly.
     */
    fun applyWatermark(
        context: Context,
        sourceUri: Uri,
        data: WatermarkData
    ): Uri? {
        return try {
            // First pass: decode bounds only to determine dimensions
            val options = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            context.contentResolver.openInputStream(sourceUri)?.use { stream ->
                BitmapFactory.decodeStream(stream, null, options)
            }

            // Calculate inSampleSize: downsample if either dimension > 3000px
            val maxDim = 3000
            var sampleSize = 1
            val w = options.outWidth
            val h = options.outHeight
            if (w > maxDim || h > maxDim) {
                val halfW = w / 2
                val halfH = h / 2
                while ((halfW / sampleSize) >= maxDim || (halfH / sampleSize) >= maxDim) {
                    sampleSize *= 2
                }
            }

            // Second pass: decode with sample size
            val decodeOptions = BitmapFactory.Options().apply {
                inSampleSize = sampleSize
                inPreferredConfig = Bitmap.Config.ARGB_8888
            }
            val inputStream = context.contentResolver.openInputStream(sourceUri)
                ?: return null
            val original = BitmapFactory.decodeStream(inputStream, null, decodeOptions)
            inputStream.close()

            if (original == null) return null

            // Apply EXIF rotation so the image matches what the camera preview showed
            val rotated = applyExifRotation(context, sourceUri, original)

            // Create mutable copy to draw on
            val bitmap = rotated.copy(Bitmap.Config.ARGB_8888, true)
            if (rotated !== original) rotated.recycle()
            original.recycle()

            val canvas = Canvas(bitmap)
            val width = bitmap.width
            val height = bitmap.height

            // Watermark occupies bottom 15% of image
            val watermarkHeight = (height * 0.15f).toInt()
            val watermarkTop = height - watermarkHeight

            // Semi-transparent black background
            val bgPaint = Paint().apply {
                color = Color.argb(160, 0, 0, 0)
                style = Paint.Style.FILL
            }
            canvas.drawRect(
                0f, watermarkTop.toFloat(),
                width.toFloat(), height.toFloat(),
                bgPaint
            )

            // Text paint — monospace, white
            val fontSize = calculateFontSize(width, height)
            val textPaint = Paint().apply {
                color = Color.WHITE
                textSize = fontSize
                typeface = Typeface.MONOSPACE
                isAntiAlias = true
                setShadowLayer(2f, 1f, 1f, Color.BLACK)
            }

            // Build watermark lines
            val lines = buildWatermarkLines(data)

            // Calculate line height and starting Y position
            val lineHeight = fontSize * 1.4f
            val totalTextHeight = lines.size * lineHeight
            val startY = watermarkTop + (watermarkHeight - totalTextHeight) / 2 + fontSize
            val leftPadding = width * 0.03f

            // Draw each line
            lines.forEachIndexed { index, line ->
                canvas.drawText(
                    line,
                    leftPadding,
                    startY + (index * lineHeight),
                    textPaint
                )
            }

            // Draw TrustCapture branding (right-aligned, smaller)
            val brandPaint = Paint().apply {
                color = Color.argb(200, 255, 255, 255)
                textSize = fontSize * 0.7f
                typeface = Typeface.create(Typeface.MONOSPACE, Typeface.BOLD)
                isAntiAlias = true
                textAlign = Paint.Align.RIGHT
            }
            canvas.drawText(
                "TrustCapture™",
                width - leftPadding,
                watermarkTop + fontSize,
                brandPaint
            )

            // Save watermarked bitmap with adaptive compression
            // Target: ~1-2MB output. Start at 90% quality, reduce if too large.
            val outputFile = File(
                context.cacheDir,
                "WM_${SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(data.timestamp)}.jpg"
            )
            var quality = 90
            FileOutputStream(outputFile).use { out ->
                bitmap.compress(Bitmap.CompressFormat.JPEG, quality, out)
            }
            // If file > 2MB, recompress at lower quality
            if (outputFile.length() > 2 * 1024 * 1024) {
                quality = 80
                FileOutputStream(outputFile).use { out ->
                    bitmap.compress(Bitmap.CompressFormat.JPEG, quality, out)
                }
            }
            bitmap.recycle()

            Uri.fromFile(outputFile)
        } catch (e: Exception) {
            e.printStackTrace()
            null
        }
    }

    private fun buildWatermarkLines(data: WatermarkData): List<String> {
        val dateFormat = SimpleDateFormat("yyyy-MM-dd HH:mm:ss z", Locale.US)
        val lines = mutableListOf<String>()

        // GPS line
        if (data.latitude != null && data.longitude != null) {
            val accStr = data.accuracy?.let { " ±${it.toInt()}m" } ?: ""
            lines.add("GPS: %.7f, %.7f%s".format(data.latitude, data.longitude, accStr))
        } else {
            lines.add("GPS: Not available")
        }

        // Timestamp
        lines.add("Time: ${dateFormat.format(data.timestamp)}")

        // Campaign + Vendor
        lines.add("Campaign: ${data.campaignCode}  Vendor: ${data.vendorId}")

        return lines
    }

    /**
     * Calculates font size based on image dimensions.
     * Targets roughly 40 chars fitting across the image width.
     */
    private fun calculateFontSize(width: Int, height: Int): Float {
        val shortSide = minOf(width, height)
        return (shortSide / 28f).coerceIn(20f, 60f)
    }

    /**
     * Reads EXIF orientation from the photo and rotates the bitmap accordingly.
     * CameraX saves photos with EXIF rotation tags rather than rotating pixels,
     * so we need to apply the rotation before watermarking.
     */
    private fun applyExifRotation(context: Context, uri: Uri, bitmap: Bitmap): Bitmap {
        return try {
            val inputStream = context.contentResolver.openInputStream(uri) ?: return bitmap
            val exif = ExifInterface(inputStream)
            inputStream.close()

            val orientation = exif.getAttributeInt(
                ExifInterface.TAG_ORIENTATION,
                ExifInterface.ORIENTATION_NORMAL
            )

            val matrix = Matrix()
            when (orientation) {
                ExifInterface.ORIENTATION_ROTATE_90 -> matrix.postRotate(90f)
                ExifInterface.ORIENTATION_ROTATE_180 -> matrix.postRotate(180f)
                ExifInterface.ORIENTATION_ROTATE_270 -> matrix.postRotate(270f)
                ExifInterface.ORIENTATION_FLIP_HORIZONTAL -> matrix.preScale(-1f, 1f)
                ExifInterface.ORIENTATION_FLIP_VERTICAL -> matrix.preScale(1f, -1f)
                ExifInterface.ORIENTATION_TRANSPOSE -> {
                    matrix.postRotate(90f)
                    matrix.preScale(-1f, 1f)
                }
                ExifInterface.ORIENTATION_TRANSVERSE -> {
                    matrix.postRotate(270f)
                    matrix.preScale(-1f, 1f)
                }
                else -> return bitmap // No rotation needed
            }

            Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
        } catch (e: Exception) {
            bitmap // Return original on any error
        }
    }
}

package com.trustcapture.vendor.ui.inspection

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner
import java.io.File

@Composable
internal fun InspectionOriginalCamera(
    output: File,
    onSaved: () -> Unit,
    onCancel: () -> Unit
) {
    val context = LocalContext.current
    val owner = LocalLifecycleOwner.current
    val executor = remember(context) { ContextCompat.getMainExecutor(context) }
    var permitted by remember {
        mutableStateOf(ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED)
    }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { permitted = it }
    val previewView = remember(context) { PreviewView(context) }
    val preview = remember { Preview.Builder().build() }
    val capture = remember { ImageCapture.Builder().build() }
    var ready by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var failure by remember { mutableStateOf(false) }
    DisposableEffect(permitted, owner) {
        var boundProvider: ProcessCameraProvider? = null
        var disposed = false
        ready = false
        if (permitted) {
            val provider = ProcessCameraProvider.getInstance(context)
            provider.addListener({
                if (!disposed) {
                    try {
                        val cameraProvider = provider.get()
                        preview.setSurfaceProvider(previewView.surfaceProvider)
                        cameraProvider.bindToLifecycle(owner, CameraSelector.DEFAULT_BACK_CAMERA, preview, capture)
                        boundProvider = cameraProvider
                        ready = true
                    } catch (_: Exception) {
                        failure = true
                    }
                }
            }, executor)
        }
        onDispose {
            disposed = true
            boundProvider?.unbind(preview, capture)
        }
    }
    Column {
        if (permitted) {
            AndroidView({ previewView }, Modifier.fillMaxWidth().height(320.dp))
            Button(enabled = ready && !busy, onClick = {
                busy = true
                failure = false
                capture.takePicture(
                    ImageCapture.OutputFileOptions.Builder(output).build(),
                    executor,
                    object : ImageCapture.OnImageSavedCallback {
                        override fun onImageSaved(outputFileResults: ImageCapture.OutputFileResults) = onSaved()
                        override fun onError(exception: ImageCaptureException) {
                            failure = true
                            busy = false
                        }
                    }
                )
            }) { Text("Take inspection photo") }
        } else {
            Button(onClick = { permission.launch(Manifest.permission.CAMERA) }) { Text("Allow camera access") }
        }
        if (failure) Text("The camera could not complete the capture.")
        TextButton(enabled = !busy, onClick = onCancel) { Text("Back to inspection") }
    }
}

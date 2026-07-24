package com.trustcapture.vendor.ui.capture

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

data class CaptureCategory(
    val id: String,
    val label: String,
    val icon: ImageVector
)

private val defaultCategories = listOf(
    CaptureCategory("accident", "Accident", Icons.Default.CarCrash),
    CaptureCategory("damage", "Damage", Icons.Default.BrokenImage),
    CaptureCategory("inspection", "Inspection", Icons.Default.Search),
    CaptureCategory("delivery_proof", "Delivery", Icons.Default.LocalShipping),
    CaptureCategory("hazard", "Hazard", Icons.Default.Warning),
    CaptureCategory("other", "Other", Icons.Default.MoreHoriz)
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun QuickCaptureScreen(
    onCategorySelected: (String) -> Unit,
    onBack: () -> Unit,
    categories: List<String> = defaultCategories.map { it.id }
) {
    val displayCategories = categories.map { catId ->
        defaultCategories.find { it.id == catId }
            ?: CaptureCategory(catId, catId.replaceFirstChar { it.uppercase() }, Icons.Default.Label)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Quick Capture") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                "What are you capturing?",
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.SemiBold,
                textAlign = TextAlign.Center
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                "Select a category for your evidence",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center
            )
            Spacer(modifier = Modifier.height(24.dp))

            LazyVerticalGrid(
                columns = GridCells.Fixed(2),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                items(displayCategories) { category ->
                    ElevatedCard(
                        onClick = { onCategorySelected(category.id) },
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Column(
                            modifier = Modifier
                                .padding(16.dp)
                                .fillMaxWidth(),
                            horizontalAlignment = Alignment.CenterHorizontally
                        ) {
                            Icon(
                                category.icon,
                                contentDescription = category.label,
                                modifier = Modifier.size(36.dp),
                                tint = MaterialTheme.colorScheme.primary
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                            Text(
                                category.label,
                                style = MaterialTheme.typography.bodyMedium,
                                fontWeight = FontWeight.Medium,
                                textAlign = TextAlign.Center
                            )
                        }
                    }
                }
            }
        }
    }
}

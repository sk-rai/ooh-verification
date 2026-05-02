package com.trustcapture.vendor.ui.campaigns

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.CloudUpload
import androidx.compose.material.icons.filled.Logout
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.trustcapture.vendor.data.local.entity.CampaignEntity
import com.trustcapture.vendor.domain.model.CampaignTypeConfig

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CampaignsScreen(
    onCampaignSelected: (campaignId: String, campaignCode: String, campaignType: String) -> Unit,
    onLoggedOut: () -> Unit,
    onSettings: () -> Unit = {},
    viewModel: CampaignsViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val campaigns by viewModel.campaigns.collectAsState()
    val pendingUploads by viewModel.pendingUploadCount.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("My Campaigns") },
                actions = {
                    IconButton(onClick = viewModel::refresh) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh")
                    }
                    IconButton(onClick = onSettings) {
                        Icon(Icons.Default.Settings, contentDescription = "Settings")
                    }
                    IconButton(onClick = { viewModel.logout(onLoggedOut) }) {
                        Icon(Icons.Default.Logout, contentDescription = "Logout")
                    }
                }
            )
        }
    ) { padding ->
        PullToRefreshBox(
            isRefreshing = uiState.isRefreshing,
            onRefresh = viewModel::refresh,
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            if (campaigns.isEmpty() && !uiState.isRefreshing) {
                // Empty state
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(
                            Icons.Default.CameraAlt,
                            contentDescription = null,
                            modifier = Modifier.size(64.dp),
                            tint = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                        Text(
                            text = "No campaigns assigned yet",
                            style = MaterialTheme.typography.bodyLarge,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        if (uiState.error != null) {
                            Spacer(modifier = Modifier.height(8.dp))
                            Text(
                                text = uiState.error!!,
                                color = MaterialTheme.colorScheme.error,
                                style = MaterialTheme.typography.bodySmall
                            )
                        }
                    }
                }
            } else {
                LazyColumn(
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    if (pendingUploads > 0) {
                        item {
                            Card(
                                colors = CardDefaults.cardColors(
                                    containerColor = MaterialTheme.colorScheme.secondaryContainer
                                )
                            ) {
                                Row(
                                    modifier = Modifier.padding(16.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Icon(
                                        Icons.Default.CloudUpload,
                                        contentDescription = null,
                                        tint = MaterialTheme.colorScheme.onSecondaryContainer
                                    )
                                    Spacer(modifier = Modifier.width(12.dp))
                                    Text(
                                        text = "$pendingUploads photo(s) pending upload",
                                        color = MaterialTheme.colorScheme.onSecondaryContainer,
                                        style = MaterialTheme.typography.bodyMedium
                                    )
                                }
                            }
                        }
                    }
                    // Campaign code entry
                    item {
                        CampaignCodeEntry(
                            code = uiState.campaignCodeInput,
                            onCodeChanged = viewModel::onCampaignCodeChanged,
                            onSubmit = { viewModel.validateAndOpenCampaign(onCampaignSelected) },
                            isValidating = uiState.isValidating,
                            error = uiState.validationError
                        )
                    }
                    if (uiState.error != null) {
                        item {
                            Card(
                                colors = CardDefaults.cardColors(
                                    containerColor = MaterialTheme.colorScheme.errorContainer
                                )
                            ) {
                                Text(
                                    text = uiState.error!!,
                                    modifier = Modifier.padding(16.dp),
                                    color = MaterialTheme.colorScheme.onErrorContainer,
                                    style = MaterialTheme.typography.bodySmall
                                )
                            }
                        }
                    }
                    items(campaigns, key = { it.campaignId }) { campaign ->
                        CampaignCard(
                            campaign = campaign,
                            onClick = { onCampaignSelected(campaign.campaignId, campaign.campaignCode, campaign.campaignType) }
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun CampaignCard(
    campaign: CampaignEntity,
    onClick: () -> Unit
) {
    val statusColor = when (campaign.status.lowercase()) {
        "active" -> MaterialTheme.colorScheme.primary
        "completed" -> MaterialTheme.colorScheme.tertiary
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }

    // Format ISO dates to readable format
    fun formatDate(isoDate: String): String {
        return try {
            val parts = isoDate.split("T")[0].split("-")
            if (parts.size == 3) "${parts[2]}/${parts[1]}/${parts[0]}" else isoDate
        } catch (e: Exception) { isoDate }
    }

    ElevatedCard(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = campaign.name,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f)
                )
                AssistChip(
                    onClick = {},
                    label = { Text(campaign.status) },
                    colors = AssistChipDefaults.assistChipColors(
                        labelColor = statusColor
                    )
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column {
                    Text(
                        text = "Code: ${campaign.campaignCode}",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Text(
                        text = "Type: ${CampaignTypeConfig.fromString(campaign.campaignType).displayLabel}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    if (campaign.locationCount > 0) {
                        Text(
                            text = "${campaign.locationCount} location(s)",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.primary
                        )
                    }
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(
                        text = formatDate(campaign.startDate),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Text(
                        text = "to ${formatDate(campaign.endDate)}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            FilledTonalButton(
                onClick = onClick,
                modifier = Modifier.fillMaxWidth()
            ) {
                Icon(
                    Icons.Default.CameraAlt,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text("Open Camera")
            }
        }
    }
}


@Composable
private fun CampaignCodeEntry(
    code: String,
    onCodeChanged: (String) -> Unit,
    onSubmit: () -> Unit,
    isValidating: Boolean,
    error: String?
) {
    OutlinedCard {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = "Enter Campaign Code",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold
            )
            Spacer(modifier = Modifier.height(8.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(
                    value = code,
                    onValueChange = onCodeChanged,
                    modifier = Modifier.weight(1f),
                    placeholder = { Text("e.g. CAM-2026-ABC") },
                    singleLine = true,
                    isError = error != null,
                    enabled = !isValidating,
                    keyboardOptions = KeyboardOptions(
                        capitalization = KeyboardCapitalization.Characters,
                        imeAction = ImeAction.Go
                    ),
                    keyboardActions = KeyboardActions(onGo = { onSubmit() })
                )
                Spacer(modifier = Modifier.width(8.dp))
                if (isValidating) {
                    CircularProgressIndicator(modifier = Modifier.size(40.dp))
                } else {
                    IconButton(onClick = onSubmit, enabled = code.isNotBlank()) {
                        Icon(Icons.Default.Search, contentDescription = "Validate")
                    }
                }
            }
            if (error != null) {
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = error,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall
                )
            }
        }
    }
}

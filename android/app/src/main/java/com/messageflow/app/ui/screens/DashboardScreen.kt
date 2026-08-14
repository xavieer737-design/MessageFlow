package com.messageflow.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.messageflow.app.viewmodel.AppViewModel

/**
 * Device dashboard: connection status, telemetry, SIM state and the
 * permission gate for SMS sending.
 */
@Composable
fun DashboardScreen(
    viewModel: AppViewModel,
    onGrantSmsPermission: () -> Unit,
    onOpenSettings: () -> Unit,
    onDisconnected: () -> Unit,
) {
    val state = viewModel.appState.value

    Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(24.dp),
        ) {
            Text(
                "Device Dashboard",
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Bold,
            )
            Spacer(Modifier.height(4.dp))
            Text(
                "This phone sends SMS for campaigns you start on the MessageFlow dashboard.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.6f),
            )
            Spacer(Modifier.height(20.dp))

            StatusCard(state.connectionLabel)
            Spacer(Modifier.height(12.dp))
            TelemetryCard(state)
            Spacer(Modifier.height(12.dp))

            if (!state.hasSmsPermission) {
                SmsPermissionCard(onGrant = onGrantSmsPermission)
                Spacer(Modifier.height(12.dp))
            }

            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("About this phone", fontWeight = FontWeight.SemiBold)
                    Spacer(Modifier.height(8.dp))
                    DetailRow("Phone model", state.phoneModel)
                    DetailRow("Android version", state.androidVersion)
                    DetailRow("Device ID", state.deviceIdentifier)
                    DetailRow("Server", state.serverUrl)
                    DetailRow("Last sync", state.lastSync ?: "never")
                }
            }

            Spacer(Modifier.height(20.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedButton(onClick = onOpenSettings, modifier = Modifier.weight(1f)) {
                    Text("Settings")
                }
                OutlinedButton(
                    onClick = {
                        viewModel.disconnectDevice()
                        onDisconnected()
                    },
                    modifier = Modifier.weight(1f),
                ) {
                    Text("Disconnect")
                }
            }
        }
    }
}

@Composable
private fun StatusCard(label: String) {
    val color = when (label) {
        "CONNECTED" -> MaterialTheme.colorScheme.primary
        else -> MaterialTheme.colorScheme.error
    }
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.padding(16.dp).fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("Connection status", color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f))
            Text(label, fontWeight = FontWeight.Bold, color = color)
        }
    }
}

@Composable
private fun TelemetryCard(state: com.messageflow.app.viewmodel.AppUiState) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text("Phone status", fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(8.dp))
            DetailRow("Battery", state.batteryLevel?.let { "$it%" } ?: "—")
            DetailRow("SIM", state.simState ?: "—")
            DetailRow("Network", state.networkState ?: "—")
            DetailRow(
                "SMS permission",
                if (state.hasSmsPermission) "Granted" else "Not granted",
            )
        }
    }
}

@Composable
private fun SmsPermissionCard(onGrant: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text("SMS permission required", fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(6.dp))
            Text(
                "MessageFlow sends SMS through Android's official SmsManager API. " +
                    "The SEND_SMS permission lets this app send the messages you explicitly " +
                    "start from the dashboard - nothing is sent without your campaign.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f),
            )
            Spacer(Modifier.height(10.dp))
            Button(onClick = onGrant) {
                Text("Grant SMS Permission")
            }
        }
    }
}

@Composable
private fun DetailRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 3.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(label, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f))
        Text(value, fontWeight = FontWeight.Medium)
    }
}

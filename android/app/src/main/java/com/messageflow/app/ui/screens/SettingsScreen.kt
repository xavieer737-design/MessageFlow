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
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.platform.LocalContext
import com.messageflow.app.viewmodel.AppViewModel

@Composable
fun SettingsScreen(
    viewModel: AppViewModel,
    onRequestReceiveSms: () -> Unit,
    onBack: () -> Unit,
) {
    val state = viewModel.appState.value
    val context = LocalContext.current
    var optIn by remember { mutableStateOf(state.receiveSmsOptIn) }

    Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(24.dp),
        ) {
            Text(
                "Settings",
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Bold,
            )
            Spacer(Modifier.height(20.dp))

            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("Device identity", fontWeight = FontWeight.SemiBold)
                    Spacer(Modifier.height(8.dp))
                    Text(
                        "Device identifier: ${state.deviceIdentifier}",
                        style = MaterialTheme.typography.bodySmall,
                    )
                    Text(
                        "Connection: ${state.connectionLabel}",
                        style = MaterialTheme.typography.bodySmall,
                    )
                    Text(
                        "Server: ${state.serverUrl}",
                        style = MaterialTheme.typography.bodySmall,
                    )
                    Spacer(Modifier.height(12.dp))
                    Row {
                        OutlinedButton(onClick = { viewModel.startDeviceService(context) }) {
                            Text("Reconnect")
                        }
                        Spacer(Modifier.weight(1f))
                    }
                }
            }

            Spacer(Modifier.height(12.dp))

            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("STOP keyword handling", fontWeight = FontWeight.SemiBold)
                    Spacer(Modifier.height(6.dp))
                    Text(
                        "When enabled, incoming SMS matching STOP / UNSUBSCRIBE / CANCEL / END / QUIT " +
                            "is forwarded to your dashboard, which adds the sender to your opt-out list " +
                            "so they receive no further messages. Requires the RECEIVE_SMS permission.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f),
                    )
                    Spacer(Modifier.height(8.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text("Enable STOP handling")
                        Switch(
                            checked = optIn,
                            onCheckedChange = { enabled ->
                                optIn = enabled
                                viewModel.toggleReceiveSmsOptIn(enabled)
                                if (enabled && !state.hasReceiveSmsPermission) {
                                    onRequestReceiveSms()
                                }
                            },
                        )
                    }
                    Text(
                        if (state.hasReceiveSmsPermission) "RECEIVE_SMS permission granted"
                        else "RECEIVE_SMS permission not granted",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f),
                    )
                }
            }

            Spacer(Modifier.height(12.dp))

            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("Danger zone", fontWeight = FontWeight.SemiBold)
                    Spacer(Modifier.height(6.dp))
                    Text(
                        "Disconnect removes this phone from your MessageFlow account. " +
                            "Pairing is required to connect again.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f),
                    )
                    Spacer(Modifier.height(10.dp))
                    Button(onClick = { viewModel.disconnectDevice(); onBack() }) {
                        Text("Disconnect device")
                    }
                }
            }

            Spacer(Modifier.height(12.dp))
            OutlinedButton(onClick = onBack) { Text("Back") }
        }
    }
}

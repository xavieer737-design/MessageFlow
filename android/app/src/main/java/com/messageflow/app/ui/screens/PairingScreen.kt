package com.messageflow.app.ui.screens

import android.content.Intent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.journeyapps.barcodescanner.ScanOptions
import com.messageflow.app.viewmodel.AppViewModel
import com.messageflow.app.viewmodel.PairingPhase

/**
 * QR pairing screen.
 *
 * The zxing scanner returns the scanned raw text; the view model parses
 * the payload ({server, token}), completes pairing with the Keystore
 * public key, and stores the device token. Camera permission is only
 * requested here, for scanning.
 */
@Composable
fun PairingScreen(
    viewModel: AppViewModel,
    onPaired: () -> Unit,
    onBack: () -> Unit,
) {
    val state = viewModel.appState.value
    val context = LocalContext.current

    val scanLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == androidx.activity.result.ActivityResult.RESULT_OK) {
            val raw = result.data?.getStringExtra("SCAN_RESULT")
            if (!raw.isNullOrBlank()) viewModel.onQrScanned(raw)
        }
    }

    Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                "Scan QR code from MessageFlow dashboard",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.SemiBold,
                textAlign = TextAlign.Center,
            )
            Spacer(Modifier.height(8.dp))
            Text(
                "In MessageFlow, open Devices → Connect Android Device and scan the QR code shown there.",
                style = MaterialTheme.typography.bodyMedium,
                textAlign = TextAlign.Center,
                color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.6f),
            )
            Spacer(Modifier.height(24.dp))

            when (state.pairing) {
                PairingPhase.Idle -> {
                    Button(onClick = { launchScanner(context, scanLauncher) }) {
                        Text("Open QR Scanner")
                    }
                }
                PairingPhase.Completing -> {
                    CircularProgressIndicator()
                    Spacer(Modifier.height(12.dp))
                    Text("Pairing with your dashboard…")
                }
                PairingPhase.Success -> {
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(
                            modifier = Modifier.padding(20.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                        ) {
                            Text("✓ Device paired", fontWeight = FontWeight.Bold)
                            Spacer(Modifier.height(12.dp))
                            PairRow("Device name", state.deviceName)
                            PairRow("Phone model", state.phoneModel)
                            PairRow("Android version", state.androidVersion)
                            Spacer(Modifier.height(16.dp))
                            Button(onClick = onPaired) {
                                Text("Continue")
                            }
                        }
                    }
                }
                PairingPhase.Error -> {
                    Text(
                        "Pairing failed",
                        color = MaterialTheme.colorScheme.error,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Spacer(Modifier.height(8.dp))
                    Text(
                        state.pairingError ?: "Unknown error",
                        textAlign = TextAlign.Center,
                        color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.7f),
                    )
                    Spacer(Modifier.height(16.dp))
                    Row {
                        OutlinedButton(onClick = { launchScanner(context, scanLauncher) }) {
                            Text("Try again")
                        }
                        Spacer(Modifier.size(8.dp))
                        Button(onClick = onBack) { Text("Back") }
                    }
                }
            }
        }
    }
}

@Composable
private fun PairRow(label: String, value: String) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f))
        Text(value, fontWeight = FontWeight.Medium)
    }
}

private fun launchScanner(
    context: android.content.Context,
    launcher: ActivityResultLauncher<Intent>,
) {
    val intent = ScanOptions()
        .setDesiredBarcodeFormats(ScanOptions.QR_CODE)
        .setPrompt("Scan the MessageFlow pairing QR code")
        .setBeepEnabled(false)
        .setOrientationLocked(false)
        .createScanIntent(context)
    launcher.launch(intent)
}

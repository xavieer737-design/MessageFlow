package com.messageflow.app

import android.Manifest
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.messageflow.app.ui.screens.DashboardScreen
import com.messageflow.app.ui.screens.PairingScreen
import com.messageflow.app.ui.screens.PermissionScreen
import com.messageflow.app.ui.screens.SettingsScreen
import com.messageflow.app.ui.screens.WelcomeScreen
import com.messageflow.app.ui.theme.MessageFlowTheme
import com.messageflow.app.viewmodel.AppViewModel

class MainActivity : ComponentActivity() {

    private val viewModel: AppViewModel by viewModels()

    private val permissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { grants ->
            viewModel.onPermissionsResult(grants)
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MessageFlowTheme {
                val appState by viewModel.appState.collectAsState()
                val navController = rememberNavController()

                NavHost(
                    navController = navController,
                    startDestination = if (appState.paired) "dashboard" else "welcome",
                ) {
                    composable("welcome") {
                        WelcomeScreen(
                            onConnect = { navController.navigate("pairing") },
                        )
                    }
                    composable("pairing") {
                        PairingScreen(
                            viewModel = viewModel,
                            onPaired = {
                                viewModel.startDeviceService(applicationContext)
                                navController.navigate("dashboard") {
                                    popUpTo("welcome") { inclusive = true }
                                }
                            },
                            onBack = { navController.popBackStack() },
                        )
                    }
                    composable("dashboard") {
                        DashboardScreen(
                            viewModel = viewModel,
                            onGrantSmsPermission = {
                                permissionLauncher.launch(
                                    arrayOf(Manifest.permission.SEND_SMS)
                                )
                            },
                            onOpenSettings = { navController.navigate("settings") },
                            onDisconnected = {
                                navController.navigate("welcome") {
                                    popUpTo(0) { inclusive = true }
                                }
                            },
                        )
                    }
                    composable("settings") {
                        SettingsScreen(
                            viewModel = viewModel,
                            onRequestReceiveSms = {
                                permissionLauncher.launch(
                                    arrayOf(Manifest.permission.RECEIVE_SMS)
                                )
                            },
                            onBack = { navController.popBackStack() },
                        )
                    }
                }
            }
        }
    }
}

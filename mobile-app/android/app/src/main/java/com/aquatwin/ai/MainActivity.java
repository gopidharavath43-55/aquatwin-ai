package com.aquatwin.ai;

import android.os.Bundle;
import android.view.WindowManager;
import android.webkit.WebSettings;
import android.webkit.WebView;
import com.getcapacitor.BridgeActivity;

// AQUATWIN_NATIVE_SECURITY_V1
public class MainActivity extends BridgeActivity {
    // Set to false temporarily only if you need to take demo screenshots
    private static final boolean ENABLE_SCREEN_CAPTURE_LOCK = true;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // 1. Block unauthorized screenshots, screen recording & Recent Apps preview leaks
        if (ENABLE_SCREEN_CAPTURE_LOCK) {
            getWindow().setFlags(
                WindowManager.LayoutParams.FLAG_SECURE,
                WindowManager.LayoutParams.FLAG_SECURE
            );
        }

        // 2. Disable remote Chrome DevTools WebView debugging in production
        WebView.setWebContentsDebuggingEnabled(false);

        // 3. Harden Capacitor WebView settings against file-URL & mixed-content exploits
        try {
            if (getBridge() != null && getBridge().getWebView() != null) {
                WebSettings ws = getBridge().getWebView().getSettings();
                ws.setAllowFileAccess(false);
                ws.setAllowFileAccessFromFileURLs(false);
                ws.setAllowUniversalAccessFromFileURLs(false);
                ws.setGeolocationEnabled(false);
                ws.setSaveFormData(false);
                ws.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
            }
        } catch (Exception ignored) {
        }
    }
}

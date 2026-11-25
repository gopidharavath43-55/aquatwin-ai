package com.aquatwin.ai;

import android.os.Build;
import android.os.Bundle;
import android.view.Display;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.WebSettings;
import android.webkit.WebView;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {

    private void unlockHighRefreshRate() {
        try {
            Window window = getWindow();
            if (window == null) return;
            Display display = null;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                display = getDisplay();
            }
            if (display == null) {
                WindowManager wm = getWindowManager();
                if (wm != null) display = wm.getDefaultDisplay();
            }
            if (display != null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                Display.Mode current = display.getMode();
                Display.Mode best = current;
                for (Display.Mode m : display.getSupportedModes()) {
                    if (m.getPhysicalWidth() == current.getPhysicalWidth()
                        && m.getPhysicalHeight() == current.getPhysicalHeight()
                        && m.getRefreshRate() > best.getRefreshRate()) {
                        best = m;
                    }
                }
                WindowManager.LayoutParams lp = window.getAttributes();
                lp.preferredDisplayModeId = best.getModeId();
                lp.preferredRefreshRate = best.getRefreshRate();
                window.setAttributes(lp);
            }
        } catch (Exception ignored) {}
    }

    private void tuneWebViewFor120Fps() {
        try {
            if (getBridge() == null) return;
            WebView webView = getBridge().getWebView();
            if (webView == null) return;
            webView.setLayerType(View.LAYER_TYPE_HARDWARE, null);
            webView.setOverScrollMode(View.OVER_SCROLL_ALWAYS);
            webView.setVerticalScrollBarEnabled(false);
            webView.setHorizontalScrollBarEnabled(false);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                webView.setRendererPriorityPolicy(WebView.RENDERER_PRIORITY_IMPORTANT, false);
            }
            WebSettings ws = webView.getSettings();
            if (ws != null) {
                ws.setCacheMode(WebSettings.LOAD_DEFAULT);
                ws.setDomStorageEnabled(true);
                ws.setDatabaseEnabled(true);
                ws.setMediaPlaybackRequiresUserGesture(false);
            }
        } catch (Exception ignored) {}
    }

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        unlockHighRefreshRate();
        tuneWebViewFor120Fps();
    }

    @Override
    public void onResume() {
        super.onResume();
        unlockHighRefreshRate();
        tuneWebViewFor120Fps();
    }
}

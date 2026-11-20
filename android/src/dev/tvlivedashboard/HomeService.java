package dev.tvlivedashboard;

import android.accessibilityservice.AccessibilityService;
import android.content.Intent;
import android.os.SystemClock;
import android.view.accessibility.AccessibilityEvent;

public class HomeService extends AccessibilityService {
    private long lastLaunch;

    @Override protected void onServiceConnected() { showHome(); }

    private void showHome() {
        long now = SystemClock.elapsedRealtime();
        if (now - lastLaunch < 750) return;
        lastLaunch = now;
        Intent home = new Intent(this, MainActivity.class);
        home.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED);
        startActivity(home);
    }

    @Override public void onAccessibilityEvent(AccessibilityEvent event) {
        if (event.getEventType() != AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED || event.getPackageName() == null) return;
        String pkg = event.getPackageName().toString();
        if (!pkg.equals("com.google.android.apps.tv.launcherx") && !pkg.equals("com.google.android.tvlauncher")) return;
        showHome();
    }

    @Override public void onInterrupt() { }
}

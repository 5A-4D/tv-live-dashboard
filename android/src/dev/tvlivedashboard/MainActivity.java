package dev.tvlivedashboard;

import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.drawable.Drawable;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.util.Base64;
import android.util.Log;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

public class MainActivity extends Activity {
    private static final String ORIGIN = "https://jarvis.local/";
    private static final String TAG = "JarvisHome";
    private final Handler ui = new Handler(Looper.getMainLooper());
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final Set<String> launchable = Collections.synchronizedSet(new HashSet<String>());
    private final AtomicBoolean refreshing = new AtomicBoolean(false);
    private WebView web;
    private JSONObject config;
    private volatile boolean active;
    private volatile boolean ready;
    private final Runnable poll = new Runnable() {
        @Override public void run() {
            if (active && ready) refreshSnapshot();
            if (active) ui.postDelayed(this, 15000);
        }
    };

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN, WindowManager.LayoutParams.FLAG_FULLSCREEN);
        immersive();
        try { config = new JSONObject(readText(getAssets().open("private-config.json"), 8192)); }
        catch (Exception error) { config = new JSONObject(); }
        WebView.setWebContentsDebuggingEnabled(config.optBoolean("debug", false));
        web = new WebView(this);
        web.setBackgroundColor(Color.rgb(10, 13, 18));
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setJavaScriptCanOpenWindowsAutomatically(false);
        settings.setSupportMultipleWindows(false);
        settings.setMediaPlaybackRequiresUserGesture(true);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setTextZoom(100);
        web.addJavascriptInterface(new Bridge(), "JarvisNative");
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return !request.getUrl().toString().startsWith(ORIGIN);
            }
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                String url = request.getUrl().toString();
                if (!url.startsWith(ORIGIN)) return emptyResponse();
                String path = request.getUrl().getPath();
                if (path == null || path.contains("..") || path.contains("\\")) return emptyResponse();
                if (path.equals("/")) path = "/index.html";
                String type = path.endsWith(".html") ? "text/html" : path.endsWith(".css") ? "text/css" : path.endsWith(".js") ? "application/javascript" : path.endsWith(".svg") ? "image/svg+xml" : path.endsWith(".png") ? "image/png" : path.endsWith(".jpg") || path.endsWith(".jpeg") ? "image/jpeg" : path.endsWith(".webp") ? "image/webp" : "application/octet-stream";
                try {
                    WebResourceResponse response = new WebResourceResponse(type, type.startsWith("image/") ? null : "UTF-8", getAssets().open("web" + path));
                    Map<String, String> headers = new HashMap<>();
                    headers.put("Cache-Control", "no-store");
                    headers.put("X-Content-Type-Options", "nosniff");
                    response.setResponseHeaders(headers);
                    return response;
                } catch (Exception error) { return emptyResponse(); }
            }
        });
        setContentView(web);
        web.loadUrl(ORIGIN + "index.html");
    }

    private static WebResourceResponse emptyResponse() {
        return new WebResourceResponse("text/plain", "UTF-8", 403, "Blocked", new HashMap<String, String>(), new ByteArrayInputStream(new byte[0]));
    }

    private void immersive() {
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY | View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
    }

    @Override public void onWindowFocusChanged(boolean focus) { super.onWindowFocusChanged(focus); if (focus) immersive(); }
    @Override protected void onResume() { super.onResume(); active = true; web.onResume(); web.resumeTimers(); js("if(window.jarvisVisibility)window.jarvisVisibility(true)"); ui.removeCallbacks(poll); ui.post(poll); }
    @Override protected void onPause() { active = false; js("if(window.jarvisVisibility)window.jarvisVisibility(false)"); ui.removeCallbacks(poll); web.onPause(); web.pauseTimers(); super.onPause(); }
    @Override protected void onDestroy() { active = false; ui.removeCallbacks(poll); worker.shutdownNow(); web.removeJavascriptInterface("JarvisNative"); web.destroy(); super.onDestroy(); }

    @Override public boolean dispatchKeyEvent(KeyEvent event) {
        String key = null;
        switch (event.getKeyCode()) {
            case KeyEvent.KEYCODE_DPAD_LEFT: key = "left"; break;
            case KeyEvent.KEYCODE_DPAD_RIGHT: key = "right"; break;
            case KeyEvent.KEYCODE_DPAD_UP: key = "up"; break;
            case KeyEvent.KEYCODE_DPAD_DOWN: key = "down"; break;
            case KeyEvent.KEYCODE_DPAD_CENTER: case KeyEvent.KEYCODE_ENTER: key = "ok"; break;
            case KeyEvent.KEYCODE_BACK: key = "back"; break;
            case KeyEvent.KEYCODE_MENU: key = "menu"; break;
        }
        if (key != null && ready) {
            if (event.getAction() == KeyEvent.ACTION_DOWN && (event.getRepeatCount() == 0 || !key.equals("ok"))) {
                js("window.jarvisKey(" + JSONObject.quote(key) + ")");
            }
            return true;
        }
        return super.dispatchKeyEvent(event);
    }

    @Override public void onBackPressed() { js("window.jarvisKey('back')"); }
    private void js(String script) { ui.post(() -> { if (!isFinishing() && !isDestroyed()) web.evaluateJavascript(script, null); }); }

    private static String readText(InputStream stream, int maximum) throws Exception {
        try (InputStream input = stream; ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int count, total = 0;
            while ((count = input.read(buffer)) != -1) {
                total += count;
                if (total > maximum) throw new IllegalStateException("Response too large");
                output.write(buffer, 0, count);
            }
            return output.toString("UTF-8");
        }
    }

    private void loadApps() {
        worker.execute(() -> {
            try {
                PackageManager pm = getPackageManager();
                Map<String, ResolveInfo> unique = new HashMap<>();
                for (String category : new String[]{Intent.CATEGORY_LEANBACK_LAUNCHER, Intent.CATEGORY_LAUNCHER}) {
                    Intent intent = new Intent(Intent.ACTION_MAIN).addCategory(category);
                    for (ResolveInfo info : pm.queryIntentActivities(intent, 0)) {
                        String pkg = info.activityInfo.packageName;
                        if (!pkg.equals(getPackageName()) && !pkg.equals("com.google.android.apps.tv.launcherx") && !pkg.equals("com.google.android.tungsten.setupwraith")) unique.put(pkg, info);
                    }
                }
                List<String> names = new ArrayList<>(unique.keySet());
                Collections.sort(names, (a, b) -> unique.get(a).loadLabel(pm).toString().compareToIgnoreCase(unique.get(b).loadLabel(pm).toString()));
                JSONArray apps = new JSONArray();
                launchable.clear();
                for (String pkg : names) {
                    ResolveInfo info = unique.get(pkg);
                    JSONObject app = new JSONObject();
                    app.put("package", pkg);
                    app.put("label", info.loadLabel(pm).toString());
                    try {
                        Drawable icon = info.loadIcon(pm);
                        Bitmap bitmap = Bitmap.createBitmap(96, 96, Bitmap.Config.ARGB_8888);
                        icon.setBounds(0, 0, 96, 96);
                        icon.draw(new Canvas(bitmap));
                        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                        bitmap.compress(Bitmap.CompressFormat.PNG, 100, bytes);
                        bitmap.recycle();
                        app.put("icon", "data:image/png;base64," + Base64.encodeToString(bytes.toByteArray(), Base64.NO_WRAP));
                    } catch (Exception ignored) { }
                    apps.put(app);
                    launchable.add(pkg);
                }
                js("window.receiveApps(" + JSONObject.quote(apps.toString()) + ")");
                Log.i(TAG, "App inventory ready; count=" + apps.length());
            } catch (Exception error) { Log.w(TAG, "App inventory unavailable"); }
        });
    }

    private void refreshSnapshot() {
        if (!refreshing.compareAndSet(false, true)) return;
        worker.execute(() -> {
            HttpURLConnection connection = null;
            try {
                String endpoint = config.optString("endpoint");
                if (!endpoint.equals("http://192.0.2.10:8768/api/dashboard")) throw new IllegalStateException("Unexpected endpoint");
                connection = (HttpURLConnection) new URL(endpoint).openConnection();
                connection.setInstanceFollowRedirects(false);
                connection.setConnectTimeout(4000);
                connection.setReadTimeout(4000);
                connection.setRequestProperty("Authorization", "Bearer " + config.getString("token"));
                if (connection.getResponseCode() != 200) {
                    Log.w(TAG, "Dashboard HTTP status=" + connection.getResponseCode());
                    throw new IllegalStateException("API unavailable");
                }
                String value = readText(connection.getInputStream(), 1000000);
                JSONObject snapshot = new JSONObject(value);
                if (snapshot.optInt("schema") != 1) throw new IllegalStateException("Unsupported snapshot");
                File temporary = new File(getFilesDir(), "snapshot.tmp");
                try (FileOutputStream output = new FileOutputStream(temporary)) { output.write(value.getBytes(StandardCharsets.UTF_8)); }
                temporary.renameTo(new File(getFilesDir(), "snapshot.json"));
                js("window.receiveSnapshot(" + JSONObject.quote(value) + ",true)");
                Log.i(TAG, "Dashboard snapshot received");
            } catch (Exception error) {
                js("window.receiveNetworkError()");
                Log.w(TAG, "Dashboard API unavailable; local interface remains active");
            } finally {
                if (connection != null) connection.disconnect();
                refreshing.set(false);
            }
        });
    }

    public class Bridge {
        @JavascriptInterface public void ready() {
            ready = true;
            loadApps();
            worker.execute(() -> {
                try {
                    String cache = readText(new FileInputStream(new File(getFilesDir(), "snapshot.json")), 1000000);
                    js("window.receiveSnapshot(" + JSONObject.quote(cache) + ",false)");
                } catch (Exception ignored) { }
            });
            refreshSnapshot();
        }
        @JavascriptInterface public void refresh() { refreshSnapshot(); }
        @JavascriptInterface public void launch(String pkg) {
            if (!launchable.contains(pkg)) return;
            ui.post(() -> {
                try {
                    Intent intent = getPackageManager().getLeanbackLaunchIntentForPackage(pkg);
                    if (intent == null) intent = getPackageManager().getLaunchIntentForPackage(pkg);
                    if (intent == null) throw new IllegalStateException("No launcher");
                    startActivity(intent);
                    Log.i(TAG, "App shortcut opened: " + pkg);
                } catch (Exception error) { Toast.makeText(MainActivity.this, "This app could not be opened", Toast.LENGTH_SHORT).show(); }
            });
        }
        @JavascriptInterface public void settings() { ui.post(() -> startActivity(new Intent(Settings.ACTION_SETTINGS))); }
        @JavascriptInterface public void accessibility() { ui.post(() -> startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))); }
    }
}

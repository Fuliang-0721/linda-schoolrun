package com.acooldog.toolbox.utils;

import android.Manifest;
import android.app.Activity;
import android.app.Application;
import android.content.Context;
import android.content.pm.PackageManager;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import androidx.core.content.ContextCompat;
import com.acooldog.toolbox.BuildConfig;
import com.acooldog.toolbox.GuideActivity;
import com.acooldog.toolbox.WelcomeActivity;
import com.acooldog.toolbox.config.AppUpdateStore;
import com.acooldog.toolbox.config.LegalConsentStore;
import com.acooldog.toolbox.config.TelemetryStore;
import com.acooldog.toolbox.share.presentation.ShareModule;
import org.json.JSONObject;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Foreground-entry snapshot only. No timer, background location or disk location queue. */
public final class ClientTelemetry implements Application.ActivityLifecycleCallbacks {
    private static ClientTelemetry instance;
    private final Context context;
    private final TelemetryStore store;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private static final ExecutorService io = Executors.newSingleThreadExecutor();
    public static void enqueueReport(Runnable operation) { io.execute(operation); }
    private int visible;
    private boolean reported;
    private LocationManager manager;
    private LocationListener listener;
    private long simulationStarted;
    private final Runnable reset = () -> reported = false;
    private final Runnable timeout = () -> finishFix(null, "unavailable");

    private ClientTelemetry(Application app) {
        context = app;
        store = new TelemetryStore(app);
        app.registerActivityLifecycleCallbacks(this);
    }
    public static void install(Application app) { instance = new ClientTelemetry(app); }
    public static void consentChanged() {
        if (instance == null) return;
        instance.cancelFix();
        instance.simulationStarted = 0;
        instance.send(null, instance.store.locationEnabled() ? "unavailable" : "disabled");
    }
    public static void simulationStarted() {
        if (instance == null) return;
        instance.finishFix(null, "mock_active");
        if (instance.simulationStarted == 0 && instance.store.enabled()) {
            instance.simulationStarted = SystemClock.elapsedRealtime();
            instance.store.increment("simulations", 1);
        }
    }
    public static void simulationStopped() {
        if (instance == null) return;
        instance.checkpointSimulation();
        instance.simulationStarted = 0;
    }
    private void checkpointSimulation() {
        if (simulationStarted != 0) {
            long now = SystemClock.elapsedRealtime();
            if (store.enabled()) store.increment("seconds", (now - simulationStarted) / 1000);
            simulationStarted = now;
        }
    }
    private boolean permission(String name) {
        return ContextCompat.checkSelfPermission(context, name) == PackageManager.PERMISSION_GRANTED;
    }
    private void begin() {
        checkpointSimulation();
        // 使用统计自动上报（enabled() 恒为 true），这里只判断位置是否被允许
        if (store.enabled()) store.increment("launches", 1);
        if (!store.locationEnabled()) { send(null, "disabled"); return; }
        if (com.acooldog.toolbox.service.ServiceGo.isActive()) { send(null, "mock_active"); return; }
        if (!permission(Manifest.permission.ACCESS_COARSE_LOCATION)
                && !permission(Manifest.permission.ACCESS_FINE_LOCATION)) {
            send(null, "permission_denied"); return;
        }
        manager = (LocationManager) context.getSystemService(Context.LOCATION_SERVICE);
        if (manager == null) { send(null, "unavailable"); return; }
        listener = new LocationListener() {
            @Override public void onLocationChanged(Location location) {
                if (com.acooldog.toolbox.service.ServiceGo.isActive()) { finishFix(null, "mock_active"); return; }
                if (!store.locationEnabled() || visible == 0) { finishFix(null, "disabled"); return; }
                boolean mock = Build.VERSION.SDK_INT >= 31 ? location.isMock() : location.isFromMockProvider();
                long age = SystemClock.elapsedRealtimeNanos() - location.getElapsedRealtimeNanos();
                if (location.hasAccuracy() && LocationSnapshotPolicy.accepts(mock,
                        com.acooldog.toolbox.service.ServiceGo.isActive(), age,
                        location.getLatitude(), location.getLongitude(), location.getAccuracy())) {
                    finishFix(location, "available");
                }
            }
            @Override public void onStatusChanged(String provider, int status, Bundle extras) { }
            @Override public void onProviderEnabled(String provider) { }
            @Override public void onProviderDisabled(String provider) { }
        };
        int registered = 0;
        for (String provider : new String[]{LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER}) {
            try {
                if (manager.isProviderEnabled(provider)) {
                    manager.requestLocationUpdates(provider, 0L, 0f, listener, Looper.getMainLooper());
                    registered++;
                }
            } catch (SecurityException | IllegalArgumentException ignored) { }
        }
        if (registered == 0) finishFix(null, "unavailable");
        else handler.postDelayed(timeout, 15000);
    }
    private void cancelFix() {
        handler.removeCallbacks(timeout);
        if (manager != null && listener != null) {
            try { manager.removeUpdates(listener); } catch (RuntimeException ignored) { }
        }
        listener = null;
    }
    private void finishFix(Location location, String status) {
        if (listener == null) return;
        cancelFix();
        send(location, status);
    }
    private void send(Location location, String status) {
        // Single queue serializes uploads and erasure; consent is checked again just before I/O.
        final Location snapshot = location == null ? null : new Location(location);
        io.execute(() -> {
            try {
                if (!LegalConsentStore.isConsentAccepted(context)) return;
                JSONObject identity = new JSONObject().put("installId", new AppUpdateStore(context).getInstallId())
                        .put("token", store.token());
                long consentVersion = store.consentVersion();
                if (store.logsErasePending()) {
                    ShareModule.from(context).shareApiClient().eraseDeviceLogs(identity);
                    store.logsErased(consentVersion);
                }
                if (store.erasePending()) {
                    ShareModule.from(context).shareApiClient().sendTelemetry(identity, true);
                    store.erased(consentVersion);
                }
                if (!store.reportingEnabled()) return;
                JSONObject payload = identity.put("sequence", store.increment("sequence", 1))
                        .put("versionName", BuildConfig.VERSION_NAME).put("versionCode", BuildConfig.VERSION_CODE)
                        .put("deviceModel", (Build.MANUFACTURER + " " + Build.MODEL).substring(0,
                                Math.min(96, (Build.MANUFACTURER + " " + Build.MODEL).length())))
                        .put("androidSdk", Build.VERSION.SDK_INT).put("launches", (store.enabled() ? store.value("launches") : 0))
                        .put("simulationCount", (store.enabled() ? store.value("simulations") : 0)).put("simulationSeconds", (store.enabled() ? store.value("seconds") : 0));
                String effective = store.locationEnabled() ? status : "disabled";
                if ("available".equals(effective) && snapshot != null
                        && LocationSnapshotPolicy.accepts(
                                Build.VERSION.SDK_INT >= 31 ? snapshot.isMock() : snapshot.isFromMockProvider(),
                                com.acooldog.toolbox.service.ServiceGo.isActive(),
                                SystemClock.elapsedRealtimeNanos() - snapshot.getElapsedRealtimeNanos(),
                                snapshot.getLatitude(), snapshot.getLongitude(), snapshot.getAccuracy())) {
                    payload.put("location", new JSONObject().put("latitude", snapshot.getLatitude())
                            .put("longitude", snapshot.getLongitude()).put("accuracy", snapshot.getAccuracy())
                            .put("capturedAt", snapshot.getTime()));
                } else if ("available".equals(effective)) effective = "unavailable";
                payload.put("locationStatus", effective);
                if (consentVersion != store.consentVersion() || !store.beginSending()) return;
                ShareModule.from(context).shareApiClient().sendTelemetry(payload, false);
            } catch (Exception ignored) {
                // Coordinates and tokens must never reach logs or persistent retry storage.
            }
        });
    }
    @Override public void onActivityStarted(Activity activity) { visible++; handler.removeCallbacks(reset); }
    @Override public void onActivityResumed(Activity activity) {
        if (!(activity instanceof WelcomeActivity) && !(activity instanceof GuideActivity)
                && !reported && store.reviewed() && LegalConsentStore.isConsentAccepted(context)) {
            reported = true;
            begin();
        }
    }
    @Override public void onActivityStopped(Activity activity) {
        visible = Math.max(0, visible - 1);
        if (visible == 0) {
            finishFix(null, "unavailable");
            if (!activity.isChangingConfigurations()) handler.postDelayed(reset, 1000);
        }
    }
    @Override public void onActivityCreated(Activity a, Bundle b) { }
    @Override public void onActivityPaused(Activity a) { }
    @Override public void onActivitySaveInstanceState(Activity a, Bundle b) { }
    @Override public void onActivityDestroyed(Activity a) { }
}

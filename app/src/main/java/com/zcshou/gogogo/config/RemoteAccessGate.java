package com.acooldog.toolbox.config;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import androidx.annotation.Nullable;
import androidx.appcompat.app.AlertDialog;
import com.acooldog.toolbox.R;
import com.acooldog.toolbox.service.ServiceGo;
import com.acooldog.toolbox.share.presentation.ShareModule;
import com.acooldog.toolbox.share.domain.model.AppClientConfig;
import java.util.ArrayList;
import java.util.List;

/** A monotonic, in-memory two-minute service lease. */
public final class RemoteAccessGate {
    public static final long LEASE_MILLIS = 120_000L;
    public static final long RENEW_MILLIS = LEASE_MILLIS - 8_000L;
    private static final Handler MAIN = new Handler(Looper.getMainLooper());
    private static volatile long confirmedAt;
    private static long generation;
    private static boolean pending;
    private static final List<Callback> callbacks = new ArrayList<>();
    public interface Callback { void onResult(boolean allowed, @Nullable String message); }
    public static String channel(Context context) {
        return new InternalAuthStore(context).isLoggedIn() ? "internal" : "stable";
    }
    public static boolean isAllowed(Context context) {
        return confirmedAt > 0 && SystemClock.elapsedRealtime() - confirmedAt < LEASE_MILLIS
                && !new AppUpdateStore(context).isForceBlocked();
    }
    public static boolean shouldRecheck() {
        return confirmedAt == 0 || SystemClock.elapsedRealtime() - confirmedAt >= RENEW_MILLIS;
    }
    public static void invalidate(Context context) {
        MAIN.post(() -> { confirmedAt = 0; generation++; pending = false;
            List<Callback> old = new ArrayList<>(callbacks); callbacks.clear();
            stop(context); for (Callback cb : old) cb.onResult(false, null);
        });
    }
    public static void stop(Context context) {
        ServiceGo.halt(context);
    }
    public static void confirm(Context context, Callback callback) {
        Context app = context.getApplicationContext();
        MAIN.post(() -> {
            callbacks.add(callback);
            if (pending) return;
            pending = true;
            long ticket = ++generation;
            MAIN.postDelayed(() -> deliver(app, ticket, false, false, null), 8000L);
            new Thread(() -> {
                boolean allowed = false, explicit = false;
                String message = null;
                try {
                    AppClientConfig config = ShareModule.from(app).shareApiClient().getAppClientConfig(channel(app));
                    explicit = true; allowed = !config.isKillSwitch(); message = config.getKillSwitchMessage();
                    RemoteControlStore.update(app, config.isKillSwitch(), message);
                } catch (Exception ignored) { }
                final boolean result = allowed, confirmed = explicit;
                final String text = message;
                MAIN.post(() -> deliver(app, ticket, result, confirmed, text));
            }, "service-confirm").start();
        });
    }
    private static void deliver(Context app, long ticket, boolean allowed, boolean explicit, String message) {
        if (!pending || ticket != generation) return;
        pending = false;
        if (explicit) confirmedAt = allowed ? SystemClock.elapsedRealtime() : 0;
        if (explicit && !allowed) stop(app);
        List<Callback> copy = new ArrayList<>(callbacks); callbacks.clear();
        for (Callback callback : copy) callback.onResult(allowed, message);
    }
    public static void showBlockedDialog(Activity activity, String message, Runnable retry) {
        stop(activity);
        if (activity.isFinishing() || activity.isDestroyed()) return;
        new AlertDialog.Builder(activity).setTitle(R.string.remote_disabled_title)
                .setMessage(message == null || message.isEmpty() ? activity.getString(R.string.remote_check_failed_message) : message)
                .setCancelable(false).setNegativeButton(R.string.remote_disabled_exit, (d,w) -> activity.finishAffinity())
                .setPositiveButton(R.string.remote_check_retry, (d,w) -> retry.run()).show();
    }
}

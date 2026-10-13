package com.acooldog.toolbox.config;

import android.content.Context;
import android.content.SharedPreferences;

/**
 * 远程开关：后端 /api/client-config 下发 killSwitch 时，命中即关闭全部客户端。
 * 结果本地缓存，离线也生效，但缓存最多保留 {@link #MAX_CACHE_AGE_MILLIS}，
 * 避免后端长期不可达时把用户永久锁死。
 */
public final class RemoteControlStore {
    private static final String PREFS_NAME = "remote_control";
    private static final String KEY_DISABLED = "disabled";
    private static final String KEY_MESSAGE = "message";
    private static final String KEY_FETCHED_AT = "fetched_at";
    private static final long MAX_CACHE_AGE_MILLIS = 3L * 24 * 60 * 60 * 1000L;

    private RemoteControlStore() {
    }

    public static void update(Context context, boolean disabled, String message) {
        prefs(context).edit()
                .putBoolean(KEY_DISABLED, disabled)
                .putString(KEY_MESSAGE, message == null ? "" : message.trim())
                .putLong(KEY_FETCHED_AT, System.currentTimeMillis())
                .apply();
    }

    public static boolean isDisabled(Context context) {
        SharedPreferences preferences = prefs(context);
        if (!preferences.getBoolean(KEY_DISABLED, false)) {
            return false;
        }
        long fetchedAt = preferences.getLong(KEY_FETCHED_AT, 0L);
        return System.currentTimeMillis() - fetchedAt <= MAX_CACHE_AGE_MILLIS;
    }

    public static String message(Context context) {
        return prefs(context).getString(KEY_MESSAGE, "");
    }

    private static SharedPreferences prefs(Context context) {
        return context.getApplicationContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
    }
}

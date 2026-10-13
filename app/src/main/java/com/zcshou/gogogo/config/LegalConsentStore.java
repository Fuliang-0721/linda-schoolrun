package com.acooldog.toolbox.config;

import android.content.Context;
import android.content.SharedPreferences;

/**
 * 用户协议 / 免责声明的同意状态，以及“使用前设置向导”的完成标记。
 * 与 WelcomeActivity 共用同一份 SharedPreferences，避免两处状态不一致。
 */
public final class LegalConsentStore {
    private static final String PREFS_NAME = "KEY_ACCEPT_AGREEMENT";
    private static final String KEY_ACCEPT_AGREEMENT = "KEY_ACCEPT_AGREEMENT";
    private static final String KEY_ACCEPT_PRIVACY = "KEY_ACCEPT_PRIVACY";
    private static final String KEY_ACCEPT_DISCLAIMER = "KEY_ACCEPT_DISCLAIMER";
    private static final String KEY_GUIDE_COMPLETED = "KEY_GUIDE_COMPLETED";

    private LegalConsentStore() {
    }

    private static SharedPreferences prefs(Context context) {
        return context.getApplicationContext()
                .getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
    }

    public static boolean isConsentAccepted(Context context) {
        SharedPreferences preferences = prefs(context);
        boolean agreement = preferences.getBoolean(KEY_ACCEPT_AGREEMENT, false);
        boolean disclaimer = preferences.getBoolean(
                KEY_ACCEPT_DISCLAIMER,
                preferences.getBoolean(KEY_ACCEPT_PRIVACY, false)
        );
        return agreement && disclaimer;
    }

    public static void saveConsentAccepted(Context context) {
        prefs(context).edit()
                .putBoolean(KEY_ACCEPT_AGREEMENT, true)
                .putBoolean(KEY_ACCEPT_DISCLAIMER, true)
                .apply();
    }

    public static boolean isGuideCompleted(Context context) {
        return prefs(context).getBoolean(KEY_GUIDE_COMPLETED, false);
    }

    public static void markGuideCompleted(Context context) {
        prefs(context).edit().putBoolean(KEY_GUIDE_COMPLETED, true).apply();
    }
}

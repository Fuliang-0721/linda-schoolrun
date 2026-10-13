package com.acooldog.toolbox.config;

import android.content.Context;
import android.content.SharedPreferences;

import java.util.UUID;

/**
 * 自动更新的本地状态。
 * 只保存随机 installId（不含任何硬件标识）、上次检查时间、用户跳过的版本、下载/待安装路径。
 */
public final class AppUpdateStore {
    private static final String PREFS_NAME = "app_update_store";
    private static final String KEY_INSTALL_ID = "install_id";
    private static final String KEY_LAST_CHECK_AT = "last_check_at";
    private static final String KEY_SKIPPED_VERSION_CODE = "skipped_version_code";
    private static final String KEY_PENDING_INSTALL_PATH = "pending_install_path";
    private static final String KEY_DOWNLOADED_VERSION_CODE = "downloaded_version_code";
    private static final String KEY_DOWNLOADED_PATH = "downloaded_path";

    private final SharedPreferences preferences;

    public AppUpdateStore(Context context) {
        preferences = context.getApplicationContext()
                .getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
    }

    /** 随机安装标识，用于灰度分桶；与设备硬件信息无关，重装会变。 */
    public String getInstallId() {
        synchronized (AppUpdateStore.class) {
        String existing = preferences.getString(KEY_INSTALL_ID, "");
        if (existing != null && !existing.trim().isEmpty()) {
            return existing.trim();
        }
        String generated = UUID.randomUUID().toString().replace("-", "");
        preferences.edit().putString(KEY_INSTALL_ID, generated).apply();
        return generated;
        }
    }

    public boolean isForceBlocked() {
        return preferences.getInt("force_version", 0) > com.acooldog.toolbox.BuildConfig.VERSION_CODE;
    }
    public void requireVersion(int versionCode) {
        preferences.edit().putInt("force_version", versionCode).apply();
    }
    public long getLastCheckAt() {
        return preferences.getLong(KEY_LAST_CHECK_AT, 0L);
    }

    public void markCheckedNow() {
        preferences.edit().putLong(KEY_LAST_CHECK_AT, System.currentTimeMillis()).apply();
    }

    public int getSkippedVersionCode() {
        return preferences.getInt(KEY_SKIPPED_VERSION_CODE, 0);
    }

    public void skipVersion(int versionCode) {
        preferences.edit().putInt(KEY_SKIPPED_VERSION_CODE, versionCode).apply();
    }

    /** 下载完成但还没安装的包（用户去授权"安装未知应用"时暂存）。 */
    public String getPendingInstallPath() {
        return preferences.getString(KEY_PENDING_INSTALL_PATH, "");
    }

    public void setPendingInstallPath(String path) {
        preferences.edit().putString(KEY_PENDING_INSTALL_PATH, path == null ? "" : path).apply();
    }

    public void clearPendingInstallPath() {
        preferences.edit().remove(KEY_PENDING_INSTALL_PATH).apply();
    }

    /** 已下载好的安装包（同版本可复用，避免重复下载）。 */
    public String getDownloadedPath(int versionCode) {
        if (preferences.getInt(KEY_DOWNLOADED_VERSION_CODE, 0) != versionCode) {
            return "";
        }
        return preferences.getString(KEY_DOWNLOADED_PATH, "");
    }

    public void setDownloaded(int versionCode, String path) {
        preferences.edit()
                .putInt(KEY_DOWNLOADED_VERSION_CODE, versionCode)
                .putString(KEY_DOWNLOADED_PATH, path == null ? "" : path)
                .apply();
    }

    public void clearDownloaded() {
        preferences.edit()
                .remove(KEY_DOWNLOADED_VERSION_CODE)
                .remove(KEY_DOWNLOADED_PATH)
                .apply();
    }
}

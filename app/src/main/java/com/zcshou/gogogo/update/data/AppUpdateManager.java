package com.acooldog.toolbox.update.data;

import android.app.Activity;
import android.content.Context;

import androidx.annotation.Nullable;

import com.acooldog.toolbox.BuildConfig;
import com.acooldog.toolbox.config.AppUpdateStore;
import com.acooldog.toolbox.config.InternalAuthStore;
import com.acooldog.toolbox.share.presentation.ShareModule;
import com.acooldog.toolbox.update.domain.model.AppVersionInfo;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 版本检查：调服务端 /api/app/version，自动检查带 24 小时冷却（手动检查不受限）。
 * 灰度与是否强制由服务端决定，客户端只按返回结果处理。
 */
public final class AppUpdateManager {
    private static final String CHANNEL_STABLE = "stable";
    /** 内部渠道：服务端可只把新版本发给内部人员，普通用户不受影响。 */
    private static final String CHANNEL_INTERNAL = "internal";
    private static final String TARGET_ABI = "arm64-v8a";
    private static final long AUTO_CHECK_INTERVAL_MILLIS = 24L * 60L * 60L * 1000L;

    public interface Callback {
        void onResult(@Nullable AppVersionInfo info, @Nullable String error, boolean skippedByCooldown);
    }

    private final Context appContext;
    private final AppUpdateStore store;
    private static final ExecutorService executor = Executors.newSingleThreadExecutor();

    public AppUpdateManager(Context context) {
        this.appContext = context.getApplicationContext();
        this.store = new AppUpdateStore(context);
    }

    public void check(Activity activity, boolean manual, Callback callback) {
        if (!manual && !store.isForceBlocked()) {
            long lastCheckAt = store.getLastCheckAt();
            if (lastCheckAt > 0L && System.currentTimeMillis() >= lastCheckAt && System.currentTimeMillis() - lastCheckAt < AUTO_CHECK_INTERVAL_MILLIS) {
                callback.onResult(null, null, true);
                return;
            }
        }

        executor.execute(() -> {
            AppVersionInfo info = null;
            String error = null;
            try {
                info = ShareModule.from(appContext)
                        .shareApiClient()
                        .getAppVersionInfo(
                                appContext.getPackageName(),
                                resolveChannel(),
                                BuildConfig.VERSION_CODE,
                                TARGET_ABI,
                                store.getInstallId()
                        );
                if (info.isUpdate() && info.isForce()) {
                    store.requireVersion(info.getVersionCode());
                    com.acooldog.toolbox.config.RemoteAccessGate.stop(appContext);
                }
                store.markCheckedNow();
            } catch (Exception exception) {
                String message = exception.getMessage();
                error = exception.getClass().getSimpleName()
                        + (message == null || message.isEmpty() ? "" : ": " + message);
            }

            AppVersionInfo finalInfo = info;
            String finalError = error;
            if (activity.isFinishing() || activity.isDestroyed()) {
                return;
            }
            activity.runOnUiThread(() -> {
                if (!activity.isFinishing() && !activity.isDestroyed()) {
                    callback.onResult(finalInfo, finalError, false);
                }
            });
        });
    }

    /**
     * 内部账号已登录时走 internal 渠道。
     * 服务端行为：internal 渠道的版本只发给内部人员；也可用 installId 白名单定向发布。
     */
    private String resolveChannel() {
        try {
            return new InternalAuthStore(appContext).isLoggedIn() ? CHANNEL_INTERNAL : CHANNEL_STABLE;
        } catch (Exception exception) {
            return CHANNEL_STABLE;
        }
    }

    public boolean isSkipped(int versionCode) {
        return store.getSkippedVersionCode() == versionCode;
    }

    public void skip(int versionCode) {
        store.skipVersion(versionCode);
    }
}

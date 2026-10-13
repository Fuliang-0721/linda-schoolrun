package com.acooldog.toolbox.update.presentation;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import androidx.appcompat.app.AlertDialog;
import androidx.core.content.FileProvider;

import com.acooldog.toolbox.BuildConfig;
import com.acooldog.toolbox.R;
import com.acooldog.toolbox.config.AppUpdateStore;
import com.acooldog.toolbox.update.service.AppUpdateDownloadService;
import com.acooldog.toolbox.update.data.ApkDownloader;
import com.acooldog.toolbox.update.data.ApkVerifier;
import com.acooldog.toolbox.update.data.AppUpdateManager;
import com.acooldog.toolbox.update.domain.model.AppVersionInfo;
import com.acooldog.toolbox.utils.GoUtils;

import java.io.File;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** 自动更新的界面流程：检查 -> 提示 -> 下载（含镜像重试）-> 校验 -> 安装。 */
public final class AppUpdateController {
    private static final int REQUEST_CODE_NOTIFICATIONS = 0x1001;

    private AppUpdateController() {
    }

    /** @param manual true=用户主动点「检查更新」（不受 24 小时冷却限制，失败/最新都会提示） */
    public static void checkAndPrompt(@NonNull Activity activity, boolean manual) {
        AppUpdateManager manager = new AppUpdateManager(activity);
        manager.check(activity, manual, (info, error, skippedByCooldown) -> {
            if (activity.isFinishing() || activity.isDestroyed() || skippedByCooldown) {
                return;
            }
            if (error != null) {
                if (manual) {
                    GoUtils.DisplayToast(activity, activity.getString(R.string.update_check_failed, error));
                }
                return;
            }
            if (info == null) {
                if (manual) {
                    GoUtils.DisplayToast(activity, activity.getString(R.string.update_check_failed, "无响应"));
                }
                return;
            }
            if (!info.isUpdate()) {
                if (manual) {
                    GoUtils.DisplayToast(activity, activity.getString(
                            R.string.update_latest_toast, BuildConfig.VERSION_NAME));
                }
                return;
            }
            if (!manual && !info.isForce() && manager.isSkipped(info.getVersionCode())) {
                return;
            }
            showUpdateDialog(activity, info, manager);
        });
    }

    private static void showUpdateDialog(
            @NonNull Activity activity,
            @NonNull AppVersionInfo info,
            @NonNull AppUpdateManager manager
    ) {
        String message;
        if (info.getChangelog().isEmpty()) {
            message = activity.getString(R.string.update_dialog_message_simple,
                    BuildConfig.VERSION_NAME, info.getVersionName(), info.readableSize());
        } else {
            message = activity.getString(R.string.update_dialog_message,
                    BuildConfig.VERSION_NAME, info.getVersionName(), info.readableSize(), info.getChangelog());
        }
        if (info.isForce()) {
            new AppUpdateStore(activity).requireVersion(info.getVersionCode());
            com.acooldog.toolbox.config.RemoteAccessGate.stop(activity);
            message = message + activity.getString(R.string.update_force_hint);
        }

        AlertDialog.Builder builder = new AlertDialog.Builder(activity)
                .setTitle(activity.getString(R.string.update_dialog_title, info.getVersionName()))
                .setMessage(message)
                .setCancelable(!info.isForce())
                .setPositiveButton(R.string.update_action_now,
                        (dialog, which) -> startBackgroundDownload(activity, info));

        if (info.isForce()) {
            builder.setNegativeButton(R.string.update_action_exit, (dialog, which) -> activity.finishAffinity());
        } else {
            builder.setNegativeButton(R.string.update_action_later,
                    (dialog, which) -> manager.skip(info.getVersionCode()));
        }
        AlertDialog updateDialog = builder.create();
        if (info.isForce()) updateDialog.setOnShowListener(d -> updateDialog.getButton(AlertDialog.BUTTON_POSITIVE)
                .setOnClickListener(v -> startBackgroundDownload(activity, info)));
        updateDialog.show();
    }

    /** 交给前台服务后台下载，通知栏显示进度；App 退到后台也不会中断。 */
    private static void startBackgroundDownload(@NonNull Activity activity, @NonNull AppVersionInfo info) {
        List<String> urls = info.allDownloadUrls();
        if (urls.isEmpty()) {
            GoUtils.DisplayToast(activity, activity.getString(
                    R.string.update_download_failed, "没有可用的下载地址"));
            return;
        }

        requestNotificationPermissionIfNeeded(activity);

        Intent intent = new Intent(activity, AppUpdateDownloadService.class)
                .setAction(AppUpdateDownloadService.ACTION_START)
                .putExtra(AppUpdateDownloadService.EXTRA_VERSION_CODE, info.getVersionCode())
                .putExtra(AppUpdateDownloadService.EXTRA_VERSION_NAME, info.getVersionName())
                .putExtra(AppUpdateDownloadService.EXTRA_SIZE_BYTES, info.getSizeBytes())
                .putExtra(AppUpdateDownloadService.EXTRA_SHA256, info.getSha256())
                .putExtra(AppUpdateDownloadService.EXTRA_PACKAGE_NAME, info.getPackageName())
                .putExtra(AppUpdateDownloadService.EXTRA_ABI, info.getAbi())
                .putStringArrayListExtra(AppUpdateDownloadService.EXTRA_URLS, new ArrayList<>(urls));

        try {
            ContextCompat.startForegroundService(activity, intent);
            GoUtils.DisplayToast(activity, activity.getString(R.string.update_background_started));
        } catch (Exception exception) {
            GoUtils.DisplayToast(activity, activity.getString(
                    R.string.update_download_failed, describe(exception)));
        }
    }

    /** Android 13+ 需要通知权限才能看到下载进度（未授权也不影响下载本身）。 */
    private static void requestNotificationPermissionIfNeeded(@NonNull Activity activity) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) {
            return;
        }
        if (ActivityCompat.checkSelfPermission(activity, Manifest.permission.POST_NOTIFICATIONS)
                == PackageManager.PERMISSION_GRANTED) {
            return;
        }
        try {
            ActivityCompat.requestPermissions(
                    activity,
                    new String[]{Manifest.permission.POST_NOTIFICATIONS},
                    REQUEST_CODE_NOTIFICATIONS
            );
        } catch (Exception ignored) {
            // 用户拒绝时静默继续，下载照常进行
        }
    }

    private static void installApk(@NonNull Activity activity, @NonNull File apk) {
        AppUpdateStore store = new AppUpdateStore(activity);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                && !activity.getPackageManager().canRequestPackageInstalls()) {
            store.setPendingInstallPath(apk.getAbsolutePath());
            GoUtils.DisplayToast(activity, activity.getString(R.string.update_install_permission_needed));
            try {
                activity.startActivity(new Intent(
                        Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                        Uri.parse("package:" + activity.getPackageName())));
            } catch (Exception ignored) {
                // 个别机型没有该设置页
            }
            return;
        }

        try {
            Uri uri = FileProvider.getUriForFile(
                    activity, activity.getPackageName() + ".fileProvider", apk);
            Intent intent = new Intent(Intent.ACTION_VIEW)
                    .setDataAndType(uri, "application/vnd.android.package-archive")
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
            activity.startActivity(intent);
            store.clearPendingInstallPath();
        } catch (Exception exception) {
            GoUtils.DisplayToast(activity, activity.getString(
                    R.string.update_download_failed, describe(exception)));
        }
    }

    /**
     * 点击「更新已下载完成」通知 / 回到前台时调用：能装就拉起系统安装。
     *
     * 注意：缺「安装未知应用」权限时**不能静默返回**（旧实现就是这样，导致点通知毫无反应），
     * 要交给 installApk 去提示并跳转授权页，返回后再由 onResume 续装。
     */
    public static void installPendingIfPossible(@NonNull Activity activity) {
        AppUpdateStore store = new AppUpdateStore(activity);
        String path = store.getPendingInstallPath();
        if (path == null || path.isEmpty()) {
            return;
        }
        File apk = new File(path);
        if (!apk.exists()) {
            store.clearPendingInstallPath();
            return;
        }
        installApk(activity, apk);
    }

    private static String describe(Exception exception) {
        String message = exception.getMessage();
        return exception.getClass().getSimpleName()
                + (message == null || message.isEmpty() ? "" : ": " + message);
    }
}

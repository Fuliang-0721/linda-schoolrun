package com.acooldog.toolbox.update.service;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.IBinder;

import androidx.annotation.Nullable;
import androidx.core.app.NotificationCompat;
import androidx.core.content.FileProvider;

import com.acooldog.toolbox.HomeActivity;
import com.elvishew.xlog.XLog;
import com.acooldog.toolbox.R;
import com.acooldog.toolbox.config.AppUpdateStore;
import com.acooldog.toolbox.update.data.ApkDownloader;
import com.acooldog.toolbox.update.data.ApkVerifier;
import com.acooldog.toolbox.update.domain.model.AppVersionInfo;

import java.io.File;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 后台下载更新：前台服务 + 通知栏进度。
 *
 * - App 退到后台、切走、锁屏都不中断（前台服务 + WAKE_LOCK 由系统保障）
 * - 通知栏实时显示百分比；下载完成后通知可点击直接进入安装
 * - 下载/校验逻辑复用 ApkDownloader（多连接分片 + 断点续传）与 ApkVerifier（四重校验）
 */
public class AppUpdateDownloadService extends Service {
    public static final String ACTION_START = "com.acooldog.toolbox.update.action.START";
    public static final String ACTION_FINISHED = "com.acooldog.toolbox.update.action.FINISHED";

    public static final String EXTRA_VERSION_CODE = "extra_version_code";
    public static final String EXTRA_VERSION_NAME = "extra_version_name";
    public static final String EXTRA_SIZE_BYTES = "extra_size_bytes";
    public static final String EXTRA_SHA256 = "extra_sha256";
    public static final String EXTRA_PACKAGE_NAME = "extra_package_name";
    public static final String EXTRA_ABI = "extra_abi";
    public static final String EXTRA_URLS = "extra_urls";
    public static final String EXTRA_SUCCESS = "extra_success";
    public static final String EXTRA_MESSAGE = "extra_message";

    private static final String CHANNEL_PROGRESS = "app_update_progress";
    private static final String CHANNEL_RESULT = "app_update_result";
    private static final int NOTIFICATION_ID_PROGRESS = 0x5EED;
    private static final int NOTIFICATION_ID_RESULT = 0x5EEE;
    private static final int MAX_ATTEMPTS_PER_URL = 2;
    private static final long NOTIFY_INTERVAL_MILLIS = 500L;
    private static final String UPDATE_DIR = "Updates";

    private ExecutorService executor;
    private NotificationManager notificationManager;

    @Override
    public void onCreate() {
        super.onCreate();
        executor = Executors.newSingleThreadExecutor();
        notificationManager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        createChannels();
    }

    @Override
    public int onStartCommand(@Nullable Intent intent, int flags, int startId) {
        if (intent == null || !ACTION_START.equals(intent.getAction())) {
            stopSelf();
            return START_NOT_STICKY;
        }

        AppVersionInfo info = readInfo(intent);
        ArrayList<String> urls = intent.getStringArrayListExtra(EXTRA_URLS);
        if (urls == null) {
            urls = new ArrayList<>();
        }

        // 必须尽快进入前台，否则 Android 会抛 ForegroundServiceDidNotStartInTimeException
        startForegroundSafely(info);
        final AppVersionInfo finalInfo = info;
        final List<String> finalUrls = urls;
        executor.execute(() -> runDownload(finalInfo, finalUrls));
        return START_NOT_STICKY;
    }

    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        if (executor != null) {
            executor.shutdownNow();
            executor = null;
        }
        super.onDestroy();
    }

    // ------------------------------------------------------------------ 主流程
    private void runDownload(AppVersionInfo info, List<String> urls) {
        String failure = null;

        File targetDir = getExternalFilesDir(UPDATE_DIR);
        if (targetDir == null) {
            failure = "无法访问存储目录";
        } else if (urls.isEmpty()) {
            failure = "没有可用的下载地址";
        } else {
            File target = new File(targetDir, "freeschoolrun-" + info.getVersionCode() + ".apk");
            long usable = targetDir.getUsableSpace();
            if (info.getSizeBytes() > 0L && usable > 0L && usable < (long) (info.getSizeBytes() * 1.3d)) {
                failure = getString(R.string.update_no_space);
            } else {
                failure = downloadWithRetry(info, urls, target);
            }
        }

        boolean success = failure == null;
        showResultNotification(success, info.getVersionName(), failure == null ? "" : failure);
        sendFinishedBroadcast(success, failure);
        stopForeground(STOP_FOREGROUND_REMOVE);
        stopSelf();
    }

    @Nullable
    private String downloadWithRetry(AppVersionInfo info, List<String> urls, File target) {
        String downloadError = downloadOnce(info, urls, target);
        if (downloadError != null) {
            cleanupTarget(target);
            return downloadError;
        }

        String verifyError = ApkVerifier.verify(this, target, info);
        if (verifyError == null) {
            return markDownloaded(info, target);
        }

        // 校验不通过：内容很可能在传输中被截断或改写（代理/弱网）。
        // 先清空文件与所有残留分片，再原地下一次且不复用任何分片；仍失败才报错。
        String expectedSha = ApkVerifier.shortSha(info.getSha256());
        XLog.e("UPDATE: verify failed - " + verifyError
                + " | size=" + target.length() + "/" + info.getSizeBytes()
                + " | sha=" + ApkVerifier.shortSha(ApkVerifier.sha256Of(target)) + "/" + expectedSha);
        cleanupTarget(target);

        String retryError = downloadOnce(info, urls, target);
        if (retryError != null) {
            cleanupTarget(target);
            new AppUpdateStore(this).clearDownloaded();
            return retryError;
        }

        verifyError = ApkVerifier.verify(this, target, info);
        if (verifyError == null) {
            XLog.i("UPDATE: verify passed after clean re-download");
            return markDownloaded(info, target);
        }

        XLog.e("UPDATE: verify failed again after clean re-download - " + verifyError
                + " | size=" + target.length() + "/" + info.getSizeBytes()
                + " | sha=" + ApkVerifier.shortSha(ApkVerifier.sha256Of(target)) + "/" + expectedSha);
        cleanupTarget(target);
        new AppUpdateStore(this).clearDownloaded();
        return getString(R.string.update_verify_failed, verifyError)
                + getString(R.string.update_verify_expected_sha, expectedSha);
    }

    /** 依次尝试各下载地址与重试次数；成功返回 null，失败返回可展示的错误文案。 */
    @Nullable
    private String downloadOnce(AppVersionInfo info, List<String> urls, File target) {
        long[] lastNotifyAt = {0L};
        Exception downloadError = null;

        for (String url : urls) {
            for (int attempt = 1; attempt <= MAX_ATTEMPTS_PER_URL; attempt++) {
                try {
                    new ApkDownloader().download(url, target, (read, total) -> {
                        long now = System.currentTimeMillis();
                        boolean finished = total > 0L && read >= total;
                        if (!finished && now - lastNotifyAt[0] < NOTIFY_INTERVAL_MILLIS) {
                            return;
                        }
                        lastNotifyAt[0] = now;
                        int percent = total > 0L ? (int) Math.min(100L, read * 100L / total) : 0;
                        updateProgressNotification(info, percent, read, total);
                    });
                    downloadError = null;
                    break;
                } catch (Exception exception) {
                    downloadError = exception;
                }
            }
            if (downloadError == null) {
                break;
            }
        }

        if (downloadError != null) {
            return getString(R.string.update_download_failed, describe(downloadError));
        }
        return null;
    }

    @Nullable
    private String markDownloaded(AppVersionInfo info, File target) {
        AppUpdateStore store = new AppUpdateStore(this);
        store.setDownloaded(info.getVersionCode(), target.getAbsolutePath());
        // 交给界面层在合适的时机拉起安装（下载完成时 App 可能不在前台）
        store.setPendingInstallPath(target.getAbsolutePath());
        return null;
    }

    /** 删除目标文件与该版本可能残留的所有分片（.part、.part0…）。 */
    private void cleanupTarget(File target) {
        try {
            //noinspection ResultOfMethodCallIgnored
            target.delete();
            File dir = target.getParentFile();
            if (dir == null) {
                return;
            }
            String prefix = target.getName() + ".part";
            File[] leftovers = dir.listFiles((file, name) -> name.startsWith(prefix));
            if (leftovers != null) {
                for (File leftover : leftovers) {
                    //noinspection ResultOfMethodCallIgnored
                    leftover.delete();
                }
            }
        } catch (Exception ignored) {
            // 清理失败不影响后续流程
        }
    }

    // ------------------------------------------------------------------ 通知
    private void createChannels() {
        if (notificationManager == null || Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            return;
        }
        NotificationChannel progress = new NotificationChannel(
                CHANNEL_PROGRESS,
                getString(R.string.update_notify_channel_progress),
                NotificationManager.IMPORTANCE_LOW
        );
        progress.setShowBadge(false);
        notificationManager.createNotificationChannel(progress);

        NotificationChannel result = new NotificationChannel(
                CHANNEL_RESULT,
                getString(R.string.update_notify_channel_result),
                NotificationManager.IMPORTANCE_DEFAULT
        );
        notificationManager.createNotificationChannel(result);
    }

    private void startForegroundSafely(AppVersionInfo info) {
        // 清单已声明 android:foregroundServiceType="dataSync"，平台会据此判定类型
        // （不用 ServiceCompat.startForeground 4 参重载，避免依赖较高版本的 androidx.core）
        startForeground(NOTIFICATION_ID_PROGRESS, buildProgressNotification(info, 0, 0L, 0L));
    }

    private Notification buildProgressNotification(AppVersionInfo info, int percent, long done, long total) {
        String text = total > 0L
                ? getString(R.string.update_notify_progress_text, percent, formatBytes(done), formatBytes(total))
                : getString(R.string.update_download_prepare);
        return new NotificationCompat.Builder(this, CHANNEL_PROGRESS)
                .setSmallIcon(R.drawable.ic_menu_upgrade)
                .setContentTitle(getString(R.string.update_notify_progress_title, info.getVersionName()))
                .setContentText(text)
                .setOnlyAlertOnce(true)
                .setOngoing(true)
                .setPriority(NotificationCompat.PRIORITY_LOW)
                .setProgress(100, Math.max(0, Math.min(100, percent)), total <= 0L)
                .build();
    }

    private void updateProgressNotification(AppVersionInfo info, int percent, long done, long total) {
        if (notificationManager == null) {
            return;
        }
        notificationManager.notify(NOTIFICATION_ID_PROGRESS, buildProgressNotification(info, percent, done, total));
    }

    private void showResultNotification(boolean success, String versionName, String message) {
        if (notificationManager == null) {
            return;
        }

        // 已获「安装未知应用」权限时，点通知直接拉起系统安装界面；否则回 App 走授权引导
        Intent intent = null;
        File apk = installableApk();
        if (success && apk != null && canInstallPackages()) {
            try {
                Uri uri = FileProvider.getUriForFile(this, getPackageName() + ".fileProvider", apk);
                intent = new Intent(Intent.ACTION_VIEW)
                        .setDataAndType(uri, "application/vnd.android.package-archive")
                        .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
            } catch (Exception ignored) {
                intent = null;
            }
        }
        if (intent == null) {
            intent = new Intent(this, HomeActivity.class)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP)
                    .putExtra(HomeActivity.EXTRA_INSTALL_PENDING_UPDATE, success);
        }

        PendingIntent pendingIntent = PendingIntent.getActivity(
                this,
                0,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        String title = success
                ? getString(R.string.update_notify_done_title)
                : getString(R.string.update_notify_failed_title);
        String text = success
                ? getString(R.string.update_notify_done_text, versionName)
                : message;

        Notification notification = new NotificationCompat.Builder(this, CHANNEL_RESULT)
                .setSmallIcon(R.drawable.ic_menu_upgrade)
                .setContentTitle(title)
                .setContentText(text)
                .setStyle(new NotificationCompat.BigTextStyle().bigText(text))
                .setAutoCancel(true)
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setContentIntent(pendingIntent)
                .build();
        notificationManager.notify(NOTIFICATION_ID_RESULT, notification);
    }

    /** 已下载完成、待在本地可直接安装的安装包（没有则返回 null）。 */
    @Nullable
    private File installableApk() {
        String path = new AppUpdateStore(this).getPendingInstallPath();
        if (path == null || path.isEmpty()) {
            return null;
        }
        File apk = new File(path);
        return apk.exists() ? apk : null;
    }

    /** Android 8+ 需要「安装未知应用」权限才能拉起安装界面。 */
    private boolean canInstallPackages() {
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.O
                || getPackageManager().canRequestPackageInstalls();
    }

    private void sendFinishedBroadcast(boolean success, @Nullable String message) {
        Intent intent = new Intent(ACTION_FINISHED)
                .setPackage(getPackageName())
                .putExtra(EXTRA_SUCCESS, success)
                .putExtra(EXTRA_MESSAGE, message == null ? "" : message);
        sendBroadcast(intent);
    }

    // ------------------------------------------------------------------ 工具
    private AppVersionInfo readInfo(Intent intent) {
        return new AppVersionInfo(
                false,
                false,
                intent.getIntExtra(EXTRA_VERSION_CODE, 0),
                intent.getStringExtra(EXTRA_VERSION_NAME),
                0,
                intent.getLongExtra(EXTRA_SIZE_BYTES, 0L),
                intent.getStringExtra(EXTRA_SHA256),
                "",
                new ArrayList<>(),
                "",
                intent.getStringExtra(EXTRA_PACKAGE_NAME),
                intent.getStringExtra(EXTRA_ABI),
                100,
                0L
        );
    }

    private String formatBytes(long bytes) {
        if (bytes <= 0L) {
            return "0 KB";
        }
        double mb = bytes / 1024d / 1024d;
        if (mb >= 1d) {
            return String.format(Locale.US, "%.1f MB", mb);
        }
        return String.format(Locale.US, "%.0f KB", bytes / 1024d);
    }

    private String describe(Exception exception) {
        String message = exception.getMessage();
        return exception.getClass().getSimpleName()
                + (message == null || message.isEmpty() ? "" : ": " + message);
    }
}

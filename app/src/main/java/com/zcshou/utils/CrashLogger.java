package com.acooldog.toolbox.utils;

import android.content.Context;
import android.os.Build;

import com.acooldog.toolbox.BuildConfig;

import java.io.File;
import java.io.FileOutputStream;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * 崩溃现场记录：把未捕获异常的堆栈写到 files/crash/pending_crash.txt，
 * 下次启动由 {@link AppLogReporter} 自动上报，然后再交给系统默认处理器（保证仍会弹出/退出）。
 */
public final class CrashLogger {
    private static final String CRASH_DIR = "crash";
    private static final String PENDING_FILE = "pending_crash.txt";
    private static final AtomicBoolean INSTALLED = new AtomicBoolean(false);

    private CrashLogger() {
    }

    public static void install(Context context) {
        if (!INSTALLED.compareAndSet(false, true)) {
            return;
        }
        final Context appContext = context.getApplicationContext();
        final Thread.UncaughtExceptionHandler previous = Thread.getDefaultUncaughtExceptionHandler();
        Thread.setDefaultUncaughtExceptionHandler((thread, throwable) -> {
            try {
                if (com.acooldog.toolbox.config.LegalConsentStore.isConsentAccepted(appContext)
                        && new com.acooldog.toolbox.config.TelemetryStore(appContext).crashEnabled()) writeCrashReport(appContext, thread, throwable);
            } catch (Exception ignored) {
                // 记录崩溃失败不能再抛异常
            }
            if (previous != null) {
                previous.uncaughtException(thread, throwable);
            }
        });
    }

    public static File pendingFile(Context context) {
        File dir = new File(context.getFilesDir(), CRASH_DIR);
        if (!dir.exists()) {
            //noinspection ResultOfMethodCallIgnored
            dir.mkdirs();
        }
        return new File(dir, PENDING_FILE);
    }

    public static void clearPending(Context context) {
        File file = pendingFile(context);
        if (file.exists()) {
            //noinspection ResultOfMethodCallIgnored
            file.delete();
        }
    }

    private static void writeCrashReport(Context context, Thread thread, Throwable throwable) {
        StringBuilder builder = new StringBuilder(2048);
        builder.append("=== 崩溃时间 ===\n")
                .append(new SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(new Date()))
                .append('\n');
        builder.append("=== 应用版本 ===\n")
                .append(BuildConfig.VERSION_NAME).append(" (").append(BuildConfig.VERSION_CODE).append(")\n");
        builder.append("=== 机型 / 系统 ===\n")
                .append(Build.MANUFACTURER).append(' ').append(Build.MODEL)
                .append(" / Android API ").append(Build.VERSION.SDK_INT)
                .append(" (").append(Build.VERSION.RELEASE).append(")\n");
        builder.append("=== 线程 ===\n")
                .append(thread == null ? "-" : thread.getName())
                .append('\n');
        builder.append("=== 堆栈 ===\n");
        StringWriter writer = new StringWriter();
        throwable.printStackTrace(new PrintWriter(writer));
        builder.append(writer);

        try (FileOutputStream outputStream = new FileOutputStream(pendingFile(context), false)) {
            outputStream.write(builder.toString().getBytes(StandardCharsets.UTF_8));
            outputStream.flush();
        } catch (Exception ignored) {
            // 忽略：磁盘写失败时只能放弃这次记录
        }
    }
}

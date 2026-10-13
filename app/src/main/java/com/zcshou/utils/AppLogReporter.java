package com.acooldog.toolbox.utils;

import android.content.Context;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;

import com.acooldog.toolbox.BuildConfig;
import com.acooldog.toolbox.config.AppUpdateStore;
import com.acooldog.toolbox.share.presentation.ShareModule;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 运行日志上报：把「崩溃现场 + XLog 运行日志尾部 + 设备信息」打包上报到 /api/app-logs/device，
 * 供后台「运行日志」看板排查。
 *
 * - 崩溃：若存在 pending_crash.txt 且用户已同意统计，启动时自动上报（reason=crash），成功后删除该文件
 * - 手动：设置页「上传运行日志」按钮（reason=manual）
 * - 隐私：两处内容都会**先脱敏再上传**——崩溃报告只保留异常类型/消息/堆栈，运行日志逐行丢弃含坐标的行，
 *   其余行抹掉坐标与 URL 片段；未同意协议时完全不上传。
 */
public final class AppLogReporter {
    public static final String REASON_CRASH = "crash";
    public static final String REASON_MANUAL = "manual";

    private static final int MAX_CRASH_BYTES = 120 * 1024;
    private static final int MAX_LOG_BYTES = 220 * 1024;
    /** XLog 的日志目录与文件名（与 GoApplication.initXlog 保持一致）。 */
    private static final String LOG_DIR = "Logs";
    private static final String LOG_FILE = "LindaXiaopao.log";
    /** 高精度小数：一行里出现两个及以上，按坐标对处理。 */
    private static final Pattern COORDINATE_PATTERN = Pattern.compile("-?\\d{1,3}\\.\\d{5,}");

    public interface Callback {
        void onResult(boolean success, String message);
    }

    private AppLogReporter() {
    }

    public static void uploadAsync(Context context, String reason, Callback callback) {
        final Context appContext = context.getApplicationContext();
        if (!com.acooldog.toolbox.config.LegalConsentStore.isConsentAccepted(appContext)) {
            return;
        }
        final Handler mainHandler = new Handler(Looper.getMainLooper());
        ClientTelemetry.enqueueReport(() -> {
            boolean success;
            String message;
            try {
                com.acooldog.toolbox.config.TelemetryStore store = new com.acooldog.toolbox.config.TelemetryStore(appContext);
                if (REASON_CRASH.equals(reason) && !store.crashEnabled()) return;
                String logText = buildReport(appContext, reason);
                String logId = ShareModule.from(appContext)
                        .shareApiClient()
                        .uploadDeviceLog(
                                new AppUpdateStore(appContext).getInstallId(),
                                BuildConfig.VERSION_NAME,
                                BuildConfig.VERSION_CODE,
                                Build.MANUFACTURER + " " + Build.MODEL,
                                Build.VERSION.SDK_INT,
                                reason,
                                logText
                        );
                success = true;
                message = logId;
            } catch (Exception exception) {
                success = false;
                String detail = exception.getMessage();
                message = exception.getClass().getSimpleName()
                        + (detail == null || detail.isEmpty() ? "" : ": " + detail);
            }

            final boolean finalSuccess = success;
            final String finalMessage = message;
            if (callback != null) {
                mainHandler.post(() -> callback.onResult(finalSuccess, finalMessage));
            }
        });
    }

    /** 启动时调用：有上次崩溃现场就静默上报（统计自动上报，不再需要额外开关）。 */
    public static void uploadPendingCrashIfAny(Context context) {
        if (!new com.acooldog.toolbox.config.TelemetryStore(context).crashEnabled()) { CrashLogger.clearPending(context); return; }
        File pending = CrashLogger.pendingFile(context);
        if (!pending.exists() || pending.length() <= 0L) {
            return;
        }
        uploadAsync(context, REASON_CRASH, (success, message) -> {
            if (success) {
                CrashLogger.clearPending(context);
            }
        });
    }

    /**
     * 崩溃报告脱敏：保留 CrashLogger 写入的分节头（时间/版本/机型/线程）、异常类型与消息、
     * Caused by / Suppressed 链、全部堆栈帧；只逐行抹掉疑似坐标或 URL 的片段。
     */
    private static String safeStack(String raw) {
        StringBuilder clean = new StringBuilder();
        for (String line : raw.split("\\r?\\n")) {
            String trimmed = line.trim();
            if (trimmed.isEmpty()) {
                continue;
            }
            boolean keep = trimmed.startsWith("===")
                    || trimmed.matches("at [^\\r\\n]+")
                    || trimmed.startsWith("Caused by:")
                    || trimmed.startsWith("Suppressed:")
                    || trimmed.startsWith("... ")
                    || trimmed.matches("[A-Za-z_$][\\w$.]*(Exception|Error|Throwable)[^\\r\\n]*");
            if (keep) {
                clean.append(scrubSensitive(trimmed)).append('\n');
            }
        }
        return clean.toString();
    }

    /**
     * 运行日志尾部脱敏：逐行丢弃含坐标的行，其余行抹掉坐标/URL 片段后保留，
     * 末尾注明省略了多少行——既能排查问题，又不夹带位置信息。
     */
    private static String safeLogTail(String raw) {
        StringBuilder clean = new StringBuilder();
        int dropped = 0;
        for (String line : raw.split("\\r?\\n")) {
            String trimmed = line.trim();
            if (trimmed.isEmpty()) {
                continue;
            }
            if (looksLikeCoordinateLine(trimmed)) {
                dropped++;
                continue;
            }
            clean.append(scrubSensitive(trimmed)).append('\n');
        }
        if (dropped > 0) {
            clean.append("（已省略 ").append(dropped).append(" 行含坐标内容）\n");
        }
        return clean.toString();
    }

    /** 显式带 lat/lon/经纬度字样，或一行内出现两个及以上高精度小数，视为坐标行。 */
    private static boolean looksLikeCoordinateLine(String line) {
        String lower = line.toLowerCase(Locale.US);
        if (lower.contains("latitude") || lower.contains("longitude")
                || lower.contains("经度") || lower.contains("纬度")
                || lower.contains("bdlongitude") || lower.contains("wgslongitude")
                || lower.contains("coordinate")) {
            return true;
        }
        Matcher matcher = COORDINATE_PATTERN.matcher(line);
        int hits = 0;
        while (matcher.find()) {
            hits++;
            if (hits >= 2) {
                return true;
            }
        }
        return false;
    }

    /** 抹掉坐标/精度/URL 等可能定位到人或泄露地址的片段。 */
    private static String scrubSensitive(String line) {
        String scrubbed = line.replaceAll(
                "(?i)\\b(lat|lon|lng|latitude|longitude|accuracy|altitude)=[^,;\\s)\\]]+",
                "$1=<已隐去>");
        scrubbed = scrubbed.replaceAll("https?://\\S+", "<链接已隐去>");
        scrubbed = scrubbed.replaceAll("-?\\d{1,3}\\.\\d{5,}", "<数值已隐去>");
        return scrubbed;
    }

    private static String buildReport(Context context, String reason) throws IOException {
        StringBuilder builder = new StringBuilder(4096);
        builder.append("=== 上报原因 ===\n").append(reason).append("\n\n");

        File pending = CrashLogger.pendingFile(context);
        if (pending.exists() && pending.length() > 0L) {
            builder.append("=== 上次崩溃现场 ===\n")
                    .append(safeStack(readTail(pending, MAX_CRASH_BYTES)))
                    .append("\n\n");
        }

        File logDirectory = context.getExternalFilesDir(LOG_DIR);
        File logFile = logDirectory == null ? null : new File(logDirectory, LOG_FILE);
        if (logFile != null && logFile.exists() && logFile.length() > 0L) {
            builder.append("=== 运行日志（末尾 ").append(MAX_LOG_BYTES / 1024)
                    .append(" KB，已脱敏坐标）===\n")
                    .append(safeLogTail(readTail(logFile, MAX_LOG_BYTES)))
                    .append('\n');
        } else {
            builder.append("=== 运行日志 ===\n（未找到日志文件）\n");
        }
        return builder.toString();
    }

    /** 读取文件末尾 maxBytes 字节（日志/堆栈都在尾部）。 */
    private static String readTail(File file, int maxBytes) throws IOException {
        long length = file.length();
        long start = Math.max(0L, length - maxBytes);
        try (RandomAccessFile randomAccessFile = new RandomAccessFile(file, "r")) {
            randomAccessFile.seek(start);
            ByteArrayOutputStream buffer = new ByteArrayOutputStream();
            byte[] chunk = new byte[16 * 1024];
            int read;
            while ((read = randomAccessFile.read(chunk)) != -1) {
                buffer.write(chunk, 0, read);
            }
            String text = buffer.toString(StandardCharsets.UTF_8.name());
            if (start > 0L && text.length() > 0) {
                // 从中间截断可能切坏一行，去掉第一行残片
                int firstBreak = text.indexOf('\n');
                if (firstBreak > 0 && firstBreak < text.length() - 1) {
                    text = text.substring(firstBreak + 1);
                }
            }
            return text;
        }
    }

    /** 供设置页显示用：估算本次将上报多少内容。 */
    public static String describeReportSize(Context context) {
        try {
            return (buildReport(context, REASON_MANUAL).getBytes(StandardCharsets.UTF_8).length / 1024) + " KB";
        } catch (Exception exception) {
            return "0 KB";
        }
    }
}

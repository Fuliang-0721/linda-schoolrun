package com.acooldog.toolbox.update.data;

import androidx.annotation.Nullable;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.ResponseBody;

/**
 * APK 下载器。
 *
 * - 大于 {@link #MIN_PARALLEL_BYTES} 且服务端支持 Range 时：**多连接分片下载**（跨境弱网下单连接很难跑满带宽）
 * - 每个分片独立落盘（.partN），已下载部分会复用 → 断点续传
 * - 不支持 Range / 分片失败时自动回退单连接
 * - 最终文件长度必须与 Content-Length 一致；内容正确性由上层 sha256 校验兜底
 */
public final class ApkDownloader {
    public interface ProgressListener {
        void onProgress(long bytesRead, long totalBytes);
    }

    private interface ChunkListener {
        void onBytes(long bytes);
    }

    private static final int PARALLEL_CONNECTIONS = 4;
    private static final long MIN_PARALLEL_BYTES = 4L * 1024L * 1024L;

    private final OkHttpClient client;

    public ApkDownloader() {
        client = new OkHttpClient.Builder()
                .connectTimeout(15L, TimeUnit.SECONDS)
                .readTimeout(30L, TimeUnit.SECONDS)
                .writeTimeout(30L, TimeUnit.SECONDS)
                .retryOnConnectionFailure(true)
                .followSslRedirects(false)
                .followRedirects(true)
                .build();
    }

    public File download(String url, File target, @Nullable ProgressListener listener) throws IOException {
        if (!com.acooldog.toolbox.BuildConfig.DEBUG && !url.startsWith("https://")) throw new IOException("更新下载必须使用 HTTPS");
        File parent = target.getParentFile();
        if (parent != null && !parent.exists() && !parent.mkdirs()) {
            throw new IOException("无法创建下载目录");
        }

        long totalBytes = probeTotalBytes(url);
        if (totalBytes > 400L * 1024L * 1024L) throw new IOException("安装包超过大小限制");
        if (totalBytes >= MIN_PARALLEL_BYTES) {
            try {
                return downloadParallel(url, target, totalBytes, listener);
            } catch (IOException parallelFailure) {
                // 分片失败（例如中途被代理改写 Range）→ 清理后回退单连接
                cleanupParts(target);
            }
        }
        return downloadSingle(url, target, listener);
    }

    // ------------------------------------------------------------------ 单连接
    private File downloadSingle(String url, File target, @Nullable ProgressListener listener) throws IOException {
        File temp = new File(target.getAbsolutePath() + ".part");
        Request request = new Request.Builder().url(url).get().build();
        try (Response response = client.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                throw new IOException("HTTP " + response.code());
            }
            ResponseBody body = response.body();
            if (body == null) {
                throw new IOException("响应内容为空");
            }
            long total = body.contentLength();
            long read = 0L;
            try (InputStream input = body.byteStream();
                 FileOutputStream output = new FileOutputStream(temp)) {
                byte[] buffer = new byte[128 * 1024];
                int count;
                while ((count = input.read(buffer)) != -1) {
                    output.write(buffer, 0, count);
                    read += count;
                    if (read > 400L * 1024L * 1024L) throw new IOException("安装包超过大小限制");
                    if (listener != null) {
                        listener.onProgress(read, total);
                    }
                }
                output.flush();
                if (total >= 0 && read != total) throw new IOException("下载长度与服务器不一致");
            }
        } catch (IOException exception) {
            //noinspection ResultOfMethodCallIgnored
            temp.delete();
            throw exception;
        }
        return promote(temp, target);
    }

    // ------------------------------------------------------------------ 多连接分片
    private File downloadParallel(String url, File target, long totalBytes, @Nullable ProgressListener listener)
            throws IOException {
        int connections = PARALLEL_CONNECTIONS;
        long chunk = totalBytes / connections;
        File[] parts = new File[connections];
        AtomicLong received = new AtomicLong();
        AtomicReference<IOException> failure = new AtomicReference<>();
        ExecutorService pool = Executors.newFixedThreadPool(connections);
        List<Future<?>> futures = new ArrayList<>();

        try {
            for (int index = 0; index < connections; index++) {
                long start = index * chunk;
                long end = (index == connections - 1) ? totalBytes - 1L : start + chunk - 1L;
                File part = new File(target.getAbsolutePath() + ".part" + index);
                parts[index] = part;

                long alreadyDone = part.exists() ? part.length() : 0L;
                if (alreadyDone > 0L) {
                    received.addAndGet(alreadyDone);
                }

                final long rangeStart = start;
                final long rangeEnd = end;
                final long resumeFrom = alreadyDone;
                futures.add(pool.submit(() -> {
                    try {
                        downloadRange(url, part, rangeStart, rangeEnd, resumeFrom, bytes -> {
                            long done = received.addAndGet(bytes);
                            if (listener != null) {
                                listener.onProgress(done, totalBytes);
                            }
                        });
                    } catch (IOException exception) {
                        failure.compareAndSet(null, exception);
                    }
                }));
            }

            for (Future<?> future : futures) {
                future.get();
            }
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            cleanup(parts);
            throw new IOException("下载被中断", exception);
        } catch (Exception exception) {
            cleanup(parts);
            throw new IOException("分片下载失败：" + exception.getClass().getSimpleName(), exception);
        } finally {
            pool.shutdownNow();
        }

        if (failure.get() != null) {
            cleanup(parts);
            throw failure.get();
        }

        File merged = new File(target.getAbsolutePath() + ".part");
        try (FileOutputStream output = new FileOutputStream(merged)) {
            byte[] buffer = new byte[256 * 1024];
            for (File part : parts) {
                if (part == null || !part.exists()) {
                    throw new IOException("分片文件缺失");
                }
                try (FileInputStream input = new FileInputStream(part)) {
                    int count;
                    while ((count = input.read(buffer)) != -1) {
                        output.write(buffer, 0, count);
                    }
                }
            }
            output.flush();
        } catch (IOException exception) {
            //noinspection ResultOfMethodCallIgnored
            merged.delete();
            cleanup(parts);
            throw exception;
        }

        if (merged.length() != totalBytes) {
            //noinspection ResultOfMethodCallIgnored
            merged.delete();
            cleanup(parts);
            throw new IOException("分片合并后长度与服务器不一致");
        }
        cleanup(parts);
        return promote(merged, target);
    }

    private void downloadRange(String url, File part, long start, long end, long resumeFrom, ChunkListener listener)
            throws IOException {
        long expectedSize = end - start + 1;
        if (resumeFrom < 0 || resumeFrom > expectedSize) throw new IOException("已有分片长度异常");
        long from = start + resumeFrom;
        if (resumeFrom == expectedSize) return;
        Request request = new Request.Builder()
                .url(url)
                .header("Range", "bytes=" + from + "-" + end)
                .header("Accept-Encoding", "identity")
                .get()
                .build();
        try (Response response = client.newCall(request).execute()) {
            if (response.code() != 206) throw new IOException("服务端未按 Range 返回分片");
            String contentRange = response.header("Content-Range", "");
            if (!contentRange.startsWith("bytes " + from + "-" + end + "/"))
                throw new IOException("服务端返回的分片范围不一致");
            ResponseBody body = response.body();
            if (body == null) {
                throw new IOException("响应内容为空");
            }
            try (InputStream input = body.byteStream();
                 FileOutputStream output = new FileOutputStream(part, true)) {
                byte[] buffer = new byte[128 * 1024];
                int count;
                long remaining = end - from + 1;
                while ((count = input.read(buffer)) != -1) {
                    remaining -= count;
                    if (remaining < 0) throw new IOException("服务端分片内容超出范围");
                    output.write(buffer, 0, count);
                    listener.onBytes(count);
                }
                output.flush();
                if (remaining != 0) throw new IOException("服务端分片内容不完整");
            }
        }
    }

    // ------------------------------------------------------------------ 工具
    /** @return 文件总长度；不支持 Range 或探测失败时返回 0（走单连接）。 */
    private long probeTotalBytes(String url) {
        Request request = new Request.Builder()
                .url(url)
                .header("Range", "bytes=0-0")
                .get()
                .build();
        try (Response response = client.newCall(request).execute()) {
            if (response.code() != 206) {
                return 0L;
            }
            String contentRange = response.header("Content-Range");
            if (contentRange == null) {
                return 0L;
            }
            int slash = contentRange.lastIndexOf('/');
            if (slash < 0 || slash == contentRange.length() - 1) {
                return 0L;
            }
            return Long.parseLong(contentRange.substring(slash + 1).trim());
        } catch (Exception exception) {
            return 0L;
        }
    }

    private void cleanupParts(File target) {
        File[] parts = partsOf(target);
        cleanup(parts);
        File merged = new File(target.getAbsolutePath() + ".part");
        if (merged.exists()) {
            //noinspection ResultOfMethodCallIgnored
            merged.delete();
        }
    }

    private File[] partsOf(File target) {
        File[] parts = new File[PARALLEL_CONNECTIONS];
        for (int index = 0; index < parts.length; index++) {
            parts[index] = new File(target.getAbsolutePath() + ".part" + index);
        }
        return parts;
    }

    private void cleanup(File[] parts) {
        for (File part : parts) {
            if (part != null && part.exists()) {
                //noinspection ResultOfMethodCallIgnored
                part.delete();
            }
        }
    }

    private File promote(File temp, File target) throws IOException {
        if (!temp.exists()) {
            throw new IOException("临时文件不存在");
        }
        if (target.exists() && !target.delete()) {
            //noinspection ResultOfMethodCallIgnored
            temp.delete();
            throw new IOException("无法覆盖已有安装包");
        }
        if (!temp.renameTo(target)) {
            //noinspection ResultOfMethodCallIgnored
            temp.delete();
            throw new IOException("无法保存安装包");
        }
        return target;
    }
}

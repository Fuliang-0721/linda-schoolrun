package com.acooldog.toolbox.update.domain.model;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * 服务端 /api/app/version 返回的版本信息。
 * 版本检查响应。
 */
public final class AppVersionInfo {
    private final boolean update;
    private final boolean force;
    private final int versionCode;
    private final String versionName;
    private final int minSupportedVersionCode;
    private final long sizeBytes;
    private final String sha256;
    private final String downloadUrl;
    private final List<String> mirrorUrls;
    private final String changelog;
    private final String packageName;
    private final String abi;
    private final int rolloutPercent;
    private final long publishedAt;

    public AppVersionInfo(
            boolean update,
            boolean force,
            int versionCode,
            String versionName,
            int minSupportedVersionCode,
            long sizeBytes,
            String sha256,
            String downloadUrl,
            List<String> mirrorUrls,
            String changelog,
            String packageName,
            String abi,
            int rolloutPercent,
            long publishedAt
    ) {
        this.update = update;
        this.force = force;
        this.versionCode = versionCode;
        this.versionName = versionName == null ? "" : versionName.trim();
        this.minSupportedVersionCode = minSupportedVersionCode;
        this.sizeBytes = sizeBytes;
        this.sha256 = sha256 == null ? "" : sha256.trim().toLowerCase();
        this.downloadUrl = downloadUrl == null ? "" : downloadUrl.trim();
        this.mirrorUrls = mirrorUrls == null ? Collections.emptyList() : new ArrayList<>(mirrorUrls);
        this.changelog = changelog == null ? "" : changelog.trim();
        this.packageName = packageName == null ? "" : packageName.trim();
        this.abi = abi == null ? "" : abi.trim();
        this.rolloutPercent = rolloutPercent;
        this.publishedAt = publishedAt;
    }

    public boolean isUpdate() {
        return update;
    }

    public boolean isForce() {
        return force;
    }

    public int getVersionCode() {
        return versionCode;
    }

    public String getVersionName() {
        return versionName;
    }

    public int getMinSupportedVersionCode() {
        return minSupportedVersionCode;
    }

    public long getSizeBytes() {
        return sizeBytes;
    }

    public String getSha256() {
        return sha256;
    }

    public String getDownloadUrl() {
        return downloadUrl;
    }

    public List<String> getMirrorUrls() {
        return Collections.unmodifiableList(mirrorUrls);
    }

    public String getChangelog() {
        return changelog;
    }

    public String getPackageName() {
        return packageName;
    }

    public String getAbi() {
        return abi;
    }

    public int getRolloutPercent() {
        return rolloutPercent;
    }

    public long getPublishedAt() {
        return publishedAt;
    }

    /** 主下载地址 + 备用镜像，按顺序尝试。 */
    public List<String> allDownloadUrls() {
        List<String> urls = new ArrayList<>();
        if (!downloadUrl.isEmpty()) {
            urls.add(downloadUrl);
        }
        for (String mirror : mirrorUrls) {
            if (!mirror.isEmpty() && !urls.contains(mirror)) {
                urls.add(mirror);
            }
        }
        return urls;
    }

    /** 供界面显示的大小，例如 "25.1 MB"。 */
    public String readableSize() {
        if (sizeBytes <= 0) {
            return "未知";
        }
        double mb = sizeBytes / 1024d / 1024d;
        if (mb >= 1d) {
            return String.format(java.util.Locale.US, "%.1f MB", mb);
        }
        return String.format(java.util.Locale.US, "%.0f KB", sizeBytes / 1024d);
    }
}

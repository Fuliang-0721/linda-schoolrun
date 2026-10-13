package com.acooldog.toolbox.update.domain.model;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/** 更新记录条目（服务端 /api/app/releases 返回）。 */
public final class AppReleaseHistoryEntry {
    private final int versionCode;
    private final String versionName;
    private final String channel;
    private final long publishedAt;
    private final String changelog;

    public AppReleaseHistoryEntry(
            int versionCode,
            String versionName,
            String channel,
            long publishedAt,
            String changelog
    ) {
        this.versionCode = versionCode;
        this.versionName = versionName == null ? "" : versionName.trim();
        this.channel = channel == null ? "" : channel.trim();
        this.publishedAt = publishedAt;
        this.changelog = changelog == null ? "" : changelog.trim();
    }

    public int getVersionCode() {
        return versionCode;
    }

    public String getVersionName() {
        return versionName.isEmpty() ? ("(" + versionCode + ")") : versionName;
    }

    public String getChannel() {
        return channel;
    }

    public long getPublishedAt() {
        return publishedAt;
    }

    public String getChangelog() {
        return changelog;
    }

    /** 发布日期的可读形式（yyyy-MM-dd），无时间戳时返回空串。 */
    public String readableDate() {
        if (publishedAt <= 0L) {
            return "";
        }
        return new SimpleDateFormat("yyyy-MM-dd", Locale.US).format(new Date(publishedAt));
    }
}

package com.acooldog.toolbox.route.domain.model;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/** 云端路线条目（服务端 /api/shared/routes）。 */
public final class CloudRouteInfo {
    private final String id;
    private final String name;
    private final int pointCount;
    private final long createdAt;

    public CloudRouteInfo(String id, String name, int pointCount, long createdAt) {
        this.id = id == null ? "" : id.trim();
        this.name = name == null ? "" : name.trim();
        this.pointCount = pointCount;
        this.createdAt = createdAt;
    }

    public String getId() {
        return id;
    }

    public String getName() {
        return name.isEmpty() ? id : name;
    }

    public int getPointCount() {
        return pointCount;
    }

    public long getCreatedAt() {
        return createdAt;
    }

    public String readableCreatedAt() {
        if (createdAt <= 0L) {
            return "";
        }
        return new SimpleDateFormat("yyyy-MM-dd", Locale.US).format(new Date(createdAt));
    }
}

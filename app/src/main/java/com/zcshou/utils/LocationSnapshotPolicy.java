package com.acooldog.toolbox.utils;

/** Pure policy shared by capture and just-before-send validation. */
public final class LocationSnapshotPolicy {
    private LocationSnapshotPolicy() { }
    public static boolean accepts(boolean mock, boolean simulating, long ageNanos,
                                  double latitude, double longitude, float accuracy) {
        return !mock && !simulating && ageNanos >= 0 && ageNanos <= 60_000_000_000L
                && Double.isFinite(latitude) && latitude >= -90 && latitude <= 90
                && Double.isFinite(longitude) && longitude >= -180 && longitude <= 180
                && Float.isFinite(accuracy) && accuracy > 0 && accuracy <= 10000;
    }
}

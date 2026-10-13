package com.acooldog.toolbox.route.domain.model;

public final class RoutePoint {
    private final double bdLongitude;
    private final double bdLatitude;
    private final double wgsLongitude;
    private final double wgsLatitude;
    private final double altitude;

    public RoutePoint(double bdLongitude, double bdLatitude, double wgsLongitude, double wgsLatitude, double altitude) {
        if (!Double.isFinite(bdLongitude) || !Double.isFinite(bdLatitude) || !Double.isFinite(wgsLongitude)
                || !Double.isFinite(wgsLatitude) || !Double.isFinite(altitude)
                || Math.abs(bdLongitude) > 180 || Math.abs(wgsLongitude) > 180
                || Math.abs(bdLatitude) > 90 || Math.abs(wgsLatitude) > 90) throw new IllegalArgumentException("Invalid route coordinate");
        this.bdLongitude = bdLongitude;
        this.bdLatitude = bdLatitude;
        this.wgsLongitude = wgsLongitude;
        this.wgsLatitude = wgsLatitude;
        this.altitude = altitude;
    }

    public double getBdLongitude() {
        return bdLongitude;
    }

    public double getBdLatitude() {
        return bdLatitude;
    }

    public double getWgsLongitude() {
        return wgsLongitude;
    }

    public double getWgsLatitude() {
        return wgsLatitude;
    }

    public double getAltitude() {
        return altitude;
    }
}

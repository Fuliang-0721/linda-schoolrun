package com.acooldog.toolbox.utils;

import org.junit.Test;
import static org.junit.Assert.*;

public class LocationSnapshotPolicyTest {
    @Test public void neverAcceptsMockOrActiveSimulation() {
        assertFalse(LocationSnapshotPolicy.accepts(true, false, 0, 31, 121, 10));
        assertFalse(LocationSnapshotPolicy.accepts(false, true, 0, 31, 121, 10));
    }
    @Test public void rejectsStaleAndFutureFixes() {
        assertFalse(LocationSnapshotPolicy.accepts(false, false, -1, 31, 121, 10));
        assertFalse(LocationSnapshotPolicy.accepts(false, false, 60_000_000_001L, 31, 121, 10));
    }
    @Test public void rejectsInvalidCoordinatesAndAccuracy() {
        assertFalse(LocationSnapshotPolicy.accepts(false, false, 0, Double.NaN, 121, 10));
        assertFalse(LocationSnapshotPolicy.accepts(false, false, 0, 91, 121, 10));
        assertFalse(LocationSnapshotPolicy.accepts(false, false, 0, 31, 181, 10));
        assertFalse(LocationSnapshotPolicy.accepts(false, false, 0, 31, 121, Float.NaN));
        assertFalse(LocationSnapshotPolicy.accepts(false, false, 0, 31, 121, 0));
    }
    @Test public void permitsRecentApproximateLocationAndZeroCoordinates() {
        assertTrue(LocationSnapshotPolicy.accepts(false, false, 60_000_000_000L, 31, 121, 3000));
        assertTrue(LocationSnapshotPolicy.accepts(false, false, 0, 0, 0, 10));
    }
}

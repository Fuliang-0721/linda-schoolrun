package com.acooldog.toolbox.route.domain.service;

import com.acooldog.toolbox.route.domain.model.*;
import java.util.Arrays;
import org.junit.Test;
import static org.junit.Assert.*;

public class RouteSafetyTest {
    @Test public void multiLoopRouteIncludesReturnSegment() {
        RouteDefinition route = new RouteDefinition("x", "x", 0, 0, Arrays.asList(
                new RoutePoint(118,35,118,35,55), new RoutePoint(118.001,35,118.001,35,55)), null);
        RouteSimulationEngine engine = new RouteSimulationEngine(route, new RouteSimulationConfig(10,2,false,1000));
        double previous = 118;
        for (int i=0; i<50 && !engine.isFinished(); i++) {
            double longitude = engine.next().getPoint().getWgsLongitude();
            assertTrue("No teleport at a lap boundary", Math.abs(longitude-previous) < 0.00012);
            previous = longitude;
        }
        assertTrue(engine.isFinished());
        assertTrue(engine.getTraveledDistanceMeters() > 360);
    }
    @Test(expected=IllegalArgumentException.class) public void rejectsNanSpeed() {
        new RouteSimulationConfig(Double.NaN,1,false,1000);
    }
    @Test(expected=IllegalArgumentException.class) public void rejectsInvalidCoordinate() {
        new RoutePoint(118,35,Double.POSITIVE_INFINITY,35,55);
    }
    @Test(expected=IllegalArgumentException.class) public void rejectsZeroLengthRoute() {
        RoutePoint p = new RoutePoint(118,35,118,35,55);
        new RouteSimulationEngine(new RouteDefinition("x","x",0,0,Arrays.asList(p,p),null),new RouteSimulationConfig(1,100,false,1000));
    }
}

#set( $dollar = '$' )
#set( $hash = '#' )
package com.rain.${artifactId.replace('-', '_')};

import com.rain.${artifactId.replace('-', '_')}.trigger.HealthController;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;

class ApplicationTest {
    @Test
    void pingReturnsSuccessfulApiEnvelope() {
        var response = new HealthController().ping();
        assertEquals("0", response.code());
        assertEquals("success", response.message());
    }
}
